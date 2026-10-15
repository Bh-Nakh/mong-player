"""추가 기능 묶음 만들기 → dist_addons\\<이름>-<해시>.zip, release\\addons.json

    .venv\\Scripts\\python.exe tools\\build_addons.py [ffmpeg] [llama] [stt] [codecs]     (생략하면 전부)

기본 설치 파일에서 뺀 큰 덩어리를 처음 쓸 때 받게 하는 묶음이다 (noadplayer/addons.py).
  ffmpeg : bin\\ffmpeg.exe
  llama  : bin\\llama\\ (번역에 안 쓰는 도구 DLL 은 뺀다)
  stt    : 받아쓰기 파이썬 라이브러리 — 앱 코드를 실제로 import 해 보고 쓰이는 패키지만 .venv 에서 골라 담는다
  codecs : 확장 코덱이 든 풀옵션 libmpv — bin\\libmpv-full\\libmpv-2.dll (tools/fetch_deps.py 가 받는다)

만든 뒤: release\\addons.json 은 커밋하고, zip 과 addons.json 은 공개 배포 저장소의 릴리스(태그 addons, 사전 릴리스)에 올린다(앱이 토큰 없이 받는다).
    gh release create addons dist_addons\\*.zip release\\addons.json --repo Bh-Nakh/mong-downloads --prerelease --notes "추가 기능 묶음"
    (이미 있으면: gh release upload addons dist_addons\\*.zip release\\addons.json --repo Bh-Nakh/mong-downloads --clobber)
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")
OUT = os.path.join(ROOT, "dist_addons")
SITE = os.path.join(ROOT, ".venv", "Lib", "site-packages")
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
TAG = "addons"

# llama.cpp 묶음에서 번역(llama-server)에 필요 없는 것
LLAMA_SKIP = ("llama-batched-bench-impl", "llama-bench-impl", "llama-cli-impl", "llama-completion-impl",
              "llama-fit-params-impl", "llama-perplexity-impl", "llama-quantize-impl", "ggml-rpc")

TRACE = r'''
import json, os, sys
sys.path.insert(0, os.getcwd())
sys.stdout.reconfigure(encoding="utf-8")
from noadplayer.stt import engine, core, lines, cleanup, timing, extract   # noqa: F401
engine._import_whisper()
import ctranslate2, onnxruntime, tokenizers, huggingface_hub, tqdm, yaml, numpy   # noqa: F401
import faster_whisper.vad, faster_whisper.tokenizer, faster_whisper.feature_extractor, faster_whisper.utils   # noqa: F401
try:
    import hf_xet   # noqa: F401
except ImportError:
    pass
import importlib.metadata as md
site = sys.argv[1]
tops = set()
for m in list(sys.modules.values()):
    f = getattr(m, "__file__", None)
    if f and os.path.normcase(f).startswith(os.path.normcase(site) + os.sep):
        tops.add(os.path.relpath(f, site).split(os.sep)[0])
pk = md.packages_distributions()
dists = {d for t in tops for d in pk.get(os.path.splitext(t)[0], [])}
for d in md.distributions():
    if d.metadata["Name"] in dists:
        for f in d.files or []:
            first = str(f).replace("\\", "/").split("/")[0]
            if first and first != ".." and first != "__pycache__":
                tops.add(first)
std = sorted(n for n in sys.modules if n.split(".")[0] in sys.stdlib_module_names
             and n not in sys.builtin_module_names and n != "__main__")
print(json.dumps({"tops": sorted(tops), "stdlib": std}))
'''


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for buf in iter(lambda: f.read(1 << 22), b""):
            h.update(buf)
    return h.hexdigest()


def zip_tree(src, dest, skip=lambda rel: False):
    n = 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_LZMA) as z:
        for base, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for fn in sorted(files):
                full = os.path.join(base, fn)
                rel = os.path.relpath(full, src).replace(os.sep, "/")
                if fn.endswith(".pyc") or skip(rel):
                    continue
                z.write(full, rel)
                n += 1
    return n


def stage_ffmpeg(tmp):
    shutil.copy2(os.path.join(BIN, "ffmpeg.exe"), tmp)


def stage_llama(tmp):
    src = os.path.join(BIN, "llama")
    for fn in os.listdir(src):
        if not fn.lower().startswith(LLAMA_SKIP):
            shutil.copy2(os.path.join(src, fn), tmp)
    r = subprocess.run([os.path.join(tmp, "llama-server.exe"), "--version"], capture_output=True, timeout=60)
    if r.returncode != 0:
        raise SystemExit("줄인 llama 묶음에서 llama-server.exe 가 실행되지 않습니다:\n" + r.stderr.decode("utf-8", "replace"))


def stage_stt(tmp):
    r = subprocess.run([PY, "-I", "-c", TRACE, SITE], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONPATH": ROOT})
    if r.returncode != 0:
        raise SystemExit("받아쓰기 라이브러리 추적에 실패했습니다:\n" + r.stderr)
    found = json.loads(r.stdout.strip().splitlines()[-1])
    # 설치본(PyInstaller)에는 앱이 직접 안 쓰는 표준 라이브러리가 빠져 있으므로, 받아쓰기 라이브러리가 쓰는 것을 목록으로 남겨
    # NoAdPlayer.spec 이 hiddenimports 로 넣게 한다.
    with open(os.path.join(ROOT, "tools", "stt_stdlib.txt"), "w", encoding="utf-8") as f:
        f.write(chr(10).join(found["stdlib"]) + chr(10))
    for name in found["tops"]:
        src = os.path.join(SITE, name)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(tmp, name),
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "tests", "test"))
        elif os.path.isfile(src):
            shutil.copy2(src, tmp)
        else:
            print("  (건너뜀: 없음)", name)


def stage_codecs(tmp):
    src = os.path.join(BIN, "libmpv-full", "libmpv-2.dll")
    if not os.path.isfile(src):
        raise SystemExit("bin\\libmpv-full\\libmpv-2.dll 이 없습니다 (확장 코덱용 풀옵션 libmpv)")
    shutil.copy2(src, tmp)


STAGERS = {"ffmpeg": stage_ffmpeg, "llama": stage_llama, "stt": stage_stt, "codecs": stage_codecs}


def main():
    names = [a for a in sys.argv[1:] if a in STAGERS] or list(STAGERS)
    os.makedirs(OUT, exist_ok=True)
    mpath = os.path.join(ROOT, "release", "addons.json")
    os.makedirs(os.path.dirname(mpath), exist_ok=True)
    try:
        with open(mpath, encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError):
        manifest = {}
    manifest.update(tag=TAG, abi=f"cp{sys.version_info.major}{sys.version_info.minor}")
    manifest.setdefault("addons", {})
    for name in names:
        print(f"[{name}] 모으는 중…")
        tmp = tempfile.mkdtemp(prefix=f"noad_addon_{name}_")
        try:
            STAGERS[name](tmp)
            zpath = os.path.join(OUT, f"{name}.zip")
            count = zip_tree(tmp, zpath)
            digest = sha256(zpath)
            final = os.path.join(OUT, f"{name}-{digest[:8]}.zip")
            os.replace(zpath, final)
            manifest["addons"][name] = {"version": digest[:8], "asset": os.path.basename(final),
                                        "size": os.path.getsize(final), "sha256": digest}
            print(f"  {count}개 파일 → {os.path.basename(final)} ({os.path.getsize(final) / 1e6:.1f}MB)")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("목록:", mpath)


if __name__ == "__main__":
    sys.exit(main())
