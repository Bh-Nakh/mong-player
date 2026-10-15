"""설치본(exe) 진입점 — 패키지 안의 상대 import 를 쓰는 noadplayer.__main__ 대신 이 파일을 빌드한다.

자동 업데이트: %LOCALAPPDATA%\\NoAdPlayer\\patch 의 코드 패치(noadplayer 폴더)가 내장 코드보다 새로우면
그것을 먼저 불러 쓴다. 패치가 깨졌거나 실행에 실패하면 패치를 지우고 내장 코드로 돌아간다.
"""
import importlib.abc
import importlib.machinery
import json
import os
import shutil
import sys

SHELL_API = 2          # 설치본이 제공하는 라이브러리 구성 번호 — 패치의 min_shell 이 이보다 크면 쓰지 않는다
                       # (2: 받아쓰기 라이브러리·ffmpeg·번역 엔진이 설치본에서 빠지고 추가 기능으로 분리됨)
os.environ["NOAD_SHELL_API"] = str(SHELL_API)

_BASE = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "NoAdPlayer", "patch")
_CURRENT = os.path.join(_BASE, "current")
_PENDING = os.path.join(_BASE, "pending")


def _ver(v):
    return tuple(int("".join(c for c in p if c.isdigit()) or 0) for p in str(v).split("."))


class _PatchFinder(importlib.abc.MetaPathFinder):
    """noadplayer 패키지를 패치 폴더에서 먼저 찾는다 (없는 모듈은 내장판으로 넘어간다)."""

    def __init__(self, root):
        self.root = root

    def find_spec(self, name, path=None, target=None):
        if name == "noadplayer":
            return importlib.machinery.PathFinder.find_spec(name, [self.root])
        if name.startswith("noadplayer."):
            return importlib.machinery.PathFinder.find_spec(name, path)
        return None


def _drop_modules():
    for m in [m for m in sys.modules if m == "noadplayer" or m.startswith("noadplayer.")]:
        del sys.modules[m]


def _use_patch():
    """새 패치가 있으면 적용하고 import 경로를 패치 쪽으로. 쓸 수 있으면 True."""
    try:
        if os.path.isfile(os.path.join(_PENDING, "patch.json")):          # 받아 둔 업데이트 → 현재로
            shutil.rmtree(_CURRENT, ignore_errors=True)
            os.replace(_PENDING, _CURRENT)
        with open(os.path.join(_CURRENT, "patch.json"), encoding="utf-8") as f:
            meta = json.load(f)
        import noadplayer as built_in                                     # 내장판 (__init__ 만 불러옴)
        if _ver(meta["version"]) <= _ver(built_in.VERSION) or int(meta.get("min_shell", 1)) > SHELL_API:
            shutil.rmtree(_CURRENT, ignore_errors=True)                   # 새 설치본이 더 새롭다
            return False
        if not os.path.isfile(os.path.join(_CURRENT, "noadplayer", "__init__.py")):
            return False
        _drop_modules()
        sys.meta_path.insert(0, _PatchFinder(_CURRENT))
        return True
    except Exception:  # noqa: BLE001 — 패치 때문에 앱이 안 뜨는 일은 없어야 한다
        return False


def _run():
    from noadplayer.app import main
    return main()


if _use_patch():
    try:
        import noadplayer.app  # noqa: F401 — 패치 코드가 불러와지는지 먼저 확인
    except Exception:  # noqa: BLE001
        sys.meta_path[:] = [f for f in sys.meta_path if not isinstance(f, _PatchFinder)]
        _drop_modules()
        shutil.rmtree(_CURRENT, ignore_errors=True)

sys.exit(_run())
