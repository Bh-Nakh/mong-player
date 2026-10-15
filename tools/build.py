"""최종 실행 파일 만들기 → dist\\몽플레이어\\몽플레이어.exe (바로 실행 가능한 폴더, 설치 불필요).

    .venv\\Scripts\\python.exe tools\\build.py

dist\\몽플레이어 폴더를 통째로 원하는 곳에 두고 몽플레이어.exe 를 실행하면 된다.
처음 실행할 때 탐색기 우클릭 메뉴가 자동 등록된다 (noadplayer/shell_register.py).
"""
import glob
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "app.name"), encoding="utf-8") as _f:
    APP = _f.read().strip()          # 앱 이름은 app.name 한 곳에서
DIST_ROOT = os.path.abspath(sys.argv[sys.argv.index("--dist") + 1]) if "--dist" in sys.argv else os.path.join(ROOT, "dist")
DIST = os.path.join(DIST_ROOT, APP)
BIN_FILES = ["libmpv-2.dll", "versions.json"]               # 기본 설치에 넣는 bin\ 파일 (나머지는 tools/build_addons.py)


def main():
    _build()


def _prune():
    """tools/prune.txt 에 적은 PySide6 파일을 지운다 (쓰지 않는 Qt 구성요소)."""
    base = os.path.join(DIST, "_internal", "PySide6")
    freed = 0
    with open(os.path.join(ROOT, "tools", "prune.txt"), encoding="utf-8") as f:
        patterns = [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    for pat in patterns:
        for p in glob.glob(os.path.join(base, *pat.split("/"))):
            if os.path.isdir(p):
                freed += sum(os.path.getsize(os.path.join(b, n)) for b, _d, fs in os.walk(p) for n in fs)
                shutil.rmtree(p)
            else:
                freed += os.path.getsize(p)
                os.remove(p)
    print(f"PySide6 군살 제거: {freed / 1e6:.1f}MB")


def _pack_7z():
    """배포용 7z(LZMA2) — 7z 명령(7-Zip·NanaZip)이 있을 때만. 설치 파일 크기의 기준."""
    seven = shutil.which("7z") or shutil.which("7za")
    if not seven:
        print("7z 명령이 없어 배포용 압축은 건너뜀")
        return
    with open(os.path.join(ROOT, "VERSION"), encoding="utf-8") as f:
        ver = f.read().strip()
    out = os.path.join(DIST_ROOT, f"{APP}-{ver}.7z")
    if os.path.isfile(out):
        os.remove(out)
    subprocess.check_call([seven, "a", "-t7z", "-mx=9", out, os.path.join(DIST, "*")], stdout=subprocess.DEVNULL)
    print(f"배포용 압축: {out} ({os.path.getsize(out) / 1e6:.1f}MB)")


def _build():
    subprocess.check_call([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                           "--distpath", DIST_ROOT, "--workpath", os.path.join(ROOT, "build"),
                           os.path.join(ROOT, "NoAdPlayer.spec")], cwd=ROOT)
    _prune()
    bin_dst = os.path.join(DIST, "bin")                       # libmpv 는 exe 옆 bin\ (paths.py)
    shutil.rmtree(bin_dst, ignore_errors=True)                # ffmpeg·llama.cpp 는 '추가 기능'으로 처음 쓸 때 받는다
    os.makedirs(bin_dst)
    for name in BIN_FILES:
        shutil.copy2(os.path.join(ROOT, "bin", name), bin_dst)
    shutil.copy2(os.path.join(ROOT, "THIRD_PARTY_LICENSES.txt"), DIST)
    print("완성:", os.path.join(DIST, APP + ".exe"))
    _pack_7z()


if __name__ == "__main__":
    main()
