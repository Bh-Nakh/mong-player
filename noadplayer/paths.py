"""앱 경로와 네이티브 DLL 검색 경로.

- bin/        : libmpv-2.dll (tools/fetch_deps.py 로 받음, 배포 시 앱 옆에 동봉)
                개발 PC 에서는 ffmpeg.exe·llama/ 도 여기서 찾는다 (배포본에는 없음)
- 데이터 폴더 : %LOCALAPPDATA%\\NoAdPlayer (설정, 첫 사용 때 받는 자막 모델)
- addons/     : 첫 사용 때 받는 선택 기능 (ffmpeg·번역 엔진·받아쓰기 라이브러리·확장 코덱) — noadplayer/addons.py
"""
import os
import sys

from . import APP_NAME

if getattr(sys, "frozen", False):
    ROOT = os.path.dirname(sys.executable)
else:
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BIN = os.path.join(ROOT, "bin")
RESOURCES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources")
ICON = os.path.join(RESOURCES, "icon.ico")

DATA = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), APP_NAME)
MODELS = os.path.join(DATA, "models")
SETTINGS = os.path.join(DATA, "settings.json")
ADDONS = os.path.join(DATA, "addons")


def _addon_or_dev(addon_path, dev_path):
    """받아 둔 선택 기능을 우선, 없으면 개발 PC 의 bin\\ 것. 둘 다 없으면 받을 위치를 돌려준다."""
    if os.path.isfile(addon_path) or not os.path.isfile(dev_path):
        return addon_path
    return dev_path


FFMPEG = _addon_or_dev(os.path.join(ADDONS, "ffmpeg", "ffmpeg.exe"), os.path.join(BIN, "ffmpeg.exe"))
LLAMA_SERVER = _addon_or_dev(os.path.join(ADDONS, "llama", "llama-server.exe"),
                             os.path.join(BIN, "llama", "llama-server.exe"))


def user_dir(kind):
    """캡처 저장 폴더: 사진 → Pictures\\NoAdPlayer, 영상·소리 → Videos\\NoAdPlayer."""
    base = os.path.join(os.path.expanduser("~"), "Pictures" if kind == "image" else "Videos")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def setup_dll_paths():
    """libmpv 와 (받아 둔 경우) GPU 구성요소를 찾을 수 있게 한다. mpv·ctranslate2 import 전에 호출."""
    os.add_dll_directory(BIN)
    os.environ["PATH"] = BIN + os.pathsep + os.environ.get("PATH", "")
    from .stt import gpu
    gpu.activate()
