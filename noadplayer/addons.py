"""선택 기능(추가 기능 묶음) — 설치 파일에 넣지 않고, 처음 쓸 때 내려받아 %LOCALAPPDATA%\\NoAdPlayer\\addons\\<이름> 에 푼다.

  ffmpeg  영상 처리 도구 — 구간 저장, 자막용 오디오 추출, 내장 자막 읽기
  llama   번역 엔진(llama.cpp) — 내 PC 번역
  stt     받아쓰기 파이썬 라이브러리(ctranslate2·onnxruntime·faster-whisper·numpy 등)
  codecs  확장 코덱이 든 libmpv — 기본 libmpv 가 못 읽는 영상이 나올 때 (noadplayer/codecs.py)

묶음 목록(addons.json)과 파일은 공개 배포 저장소(Bh-Nakh/mong-downloads)의 릴리스(태그 addons)에서 받는다 — 토큰이 필요 없다.
(tools/build_addons.py 가 묶음을 만들고, 올리는 명령은 그 파일 설명에 있다)
개발·시험용: 환경변수 NOAD_ADDON_SOURCE 에 addons.json 과 zip 이 든 폴더를 지정하면 거기서 받는다.
"""
import importlib.util
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from . import VERSION
from .paths import ADDONS, FFMPEG, LLAMA_SERVER
from .stt.download import Cancelled, DownloadError, fetch

TAG_DEFAULT = "addons"
RELEASE_BASE = "https://github.com/Bh-Nakh/mong-downloads/releases/download"   # 공개 배포 저장소(토큰 불필요)
MANIFEST_URL = f"{RELEASE_BASE}/{TAG_DEFAULT}/addons.json"

# label: 화면에 보일 이름, mb: 내려받기 크기 안내용 대략값(정확한 값은 목록에서), dll_dirs: 풀린 폴더 안에서 DLL 을 찾을 곳
INFO = {
    "ffmpeg": {"label": "영상 처리 도구(ffmpeg)", "mb": 45},
    "llama": {"label": "번역 엔진", "mb": 40},
    "stt": {"label": "자막 받아쓰기 엔진", "mb": 60,
            "dll_dirs": ["ctranslate2", "onnxruntime/capi", "numpy.libs"]},
    "codecs": {"label": "확장 코덱", "mb": 35},
}
_active = set()
_manifest = None


class AddonError(DownloadError):
    pass


def path(name):
    return os.path.join(ADDONS, name)


def label(name):
    return INFO[name]["label"]


def approx_mb(name):
    return INFO[name]["mb"]


def installed(name):
    return os.path.isfile(os.path.join(path(name), "addon.json"))


def present(name):
    """쓸 수 있는 상태인가 — 받아 둔 것, 또는 개발 PC 에 이미 있는 것."""
    if installed(name):
        return True
    if name == "ffmpeg":
        return os.path.isfile(FFMPEG)
    if name == "llama":
        return os.path.isfile(LLAMA_SERVER)
    if name == "stt":
        return not getattr(sys, "frozen", False) and importlib.util.find_spec("faster_whisper") is not None
    return False


def activate(name):
    """풀어 둔 묶음을 쓸 수 있게 한다 (import 경로·DLL 검색 경로). 몇 번 불러도 한 번만 한다."""
    if name in _active or not installed(name):
        return
    _active.add(name)
    d = path(name)
    if name == "stt":
        sys.path.insert(0, d)
    for sub in INFO[name].get("dll_dirs", []):
        full = os.path.join(d, *sub.split("/"))
        if os.path.isdir(full):
            os.add_dll_directory(full)
            os.environ["PATH"] = full + os.pathsep + os.environ.get("PATH", "")


# ───────────────────────── 목록·내려받기 ─────────────────────────
def _source_dir():
    return os.environ.get("NOAD_ADDON_SOURCE") or None


def manifest(refresh=False):
    """→ {"tag", "abi", "addons": {이름: {version, asset, size, sha256}}}"""
    global _manifest
    if _manifest is not None and not refresh:
        return _manifest
    try:
        src = _source_dir()
        if src:
            with open(os.path.join(src, "addons.json"), encoding="utf-8-sig") as f:
                data = json.load(f)
        else:
            req = urllib.request.Request(MANIFEST_URL, headers={"User-Agent": f"NoAdPlayer/{VERSION}"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8-sig"))
    except urllib.error.HTTPError as e:
        raise AddonError(f"추가 기능 목록을 받지 못했습니다 ({e.code}).") from None
    except urllib.error.URLError as e:
        raise AddonError(f"추가 기능 목록을 받지 못했습니다. 인터넷 연결을 확인하세요 ({e.reason}).") from None
    except (OSError, ValueError) as e:
        raise AddonError(f"추가 기능 목록을 읽지 못했습니다: {e}") from None
    _manifest = data
    return data


def entry(name):
    m = manifest()
    abi = f"cp{sys.version_info.major}{sys.version_info.minor}"
    if name == "stt" and m.get("abi") not in (None, abi):          # 파이썬 확장 모듈은 설치본 파이썬 버전과 같아야 한다
        raise AddonError(f"'{label(name)}' 묶음({m.get('abi')})이 이 설치본(파이썬 {abi})과 맞지 않습니다.")
    try:
        return m["addons"][name]
    except KeyError:
        raise AddonError(f"이 버전용 '{label(name)}' 묶음이 아직 올라와 있지 않습니다.") from None


def size(name):
    """내려받을 크기(바이트) — 목록을 받을 수 없으면 안내용 대략값."""
    try:
        return int(entry(name)["size"])
    except (AddonError, KeyError, ValueError):
        return approx_mb(name) * 1_000_000


def _asset_url(tag, asset):
    """공개 릴리스 파일의 주소 (로그인·토큰 없이 받는다. 실제 파일은 GitHub 가 임시 주소로 넘겨 준다)."""
    return f"{RELEASE_BASE}/{urllib.parse.quote(tag)}/{urllib.parse.quote(asset)}"


def _copy_local(src, dest, total, progress, cancelled):
    done = 0
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(src, "rb") as fi, open(dest, "wb") as fo:
        while buf := fi.read(1 << 22):
            if cancelled():
                raise Cancelled()
            fo.write(buf)
            done += len(buf)
            progress(done, total)


def _download(name, e, dest, progress, cancelled):
    total = int(e["size"])
    src = _source_dir()
    if src:
        _copy_local(os.path.join(src, e["asset"]), dest, total, progress, cancelled)
        return
    tag = manifest().get("tag", TAG_DEFAULT)
    last = None
    for _ in range(8):                         # 끊기면 잠시 뒤 이어 받는다
        url = _asset_url(tag, e["asset"])
        try:
            fetch(url, dest, total, e.get("sha256"), lambda d: progress(d, total), cancelled, tries=1)
            return
        except DownloadError as ex:
            last = ex
            time.sleep(2)
    raise last


def _extract(zpath, dest, version):
    tmp = dest + ".new"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    try:
        with zipfile.ZipFile(zpath) as z:
            root = os.path.realpath(tmp)
            for n in z.namelist():
                if not os.path.realpath(os.path.join(tmp, n)).startswith(root + os.sep):
                    raise AddonError("추가 기능 파일에 안전하지 않은 경로가 있습니다.")
            z.extractall(tmp)
        with open(os.path.join(tmp, "addon.json"), "w", encoding="utf-8") as f:
            json.dump({"version": version}, f)
        shutil.rmtree(dest, ignore_errors=True)
        os.replace(tmp, dest)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def install(name, progress=lambda done, total: None, cancelled=lambda: False):
    """묶음을 내려받아 푼다. progress(받은 바이트, 전체 바이트). 취소하면 Cancelled."""
    e = entry(name)
    zpath = os.path.join(ADDONS, f"{name}.zip")
    _download(name, e, zpath, progress, cancelled)
    try:
        _extract(zpath, path(name), str(e.get("version", "")))
    finally:
        if os.path.isfile(zpath):
            os.remove(zpath)
    activate(name)


def ensure(name, progress=lambda done, total: None, cancelled=lambda: False):
    """쓰기 전에 부른다 — 없으면 받고, 있으면 쓸 수 있게 켠다. (작업 스레드에서)"""
    if not present(name):
        install(name, progress, cancelled)
    activate(name)
