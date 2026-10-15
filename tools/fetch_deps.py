"""개발·배포용 네이티브 바이너리 받기 → bin/
(ffmpeg·llama 는 설치본에 넣지 않고 tools/build_addons.py 가 추가 기능 묶음으로 만든다. libmpv 만 설치본에 들어간다)

- libmpv-2.dll : zhongfly/mpv-winbuild 의 LGPL 빌드 (상용 배포 가능 — GPL 빌드 쓰지 말 것)
- ffmpeg.exe   : BtbN/FFmpeg-Builds 의 LGPL 정적 빌드 (캡처·자막용 오디오 추출)
- llama/       : llama.cpp(MIT) Vulkan 빌드의 llama-server.exe (자막 번역)

    .venv\\Scripts\\python.exe tools\\fetch_deps.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")

MPV_REPO = "zhongfly/mpv-winbuild"
MPV_PREFIX = "mpv-dev-lgpl-x86_64-2"          # v3(AVX2 전용)·GPL 빌드 제외
FFMPEG_REPO = "BtbN/FFmpeg-Builds"
FFMPEG_SUFFIX = "-latest-win64-lgpl-9.0.zip"   # 9.0 안정 계열, 정적 LGPL
LLAMA_REPO = "ggml-org/llama.cpp"


def latest_asset(repo, match):
    """최근 릴리스부터 찾는다 (llama.cpp 는 새 릴리스에 윈도우 파일이 늦게 올라온다)."""
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases?per_page=10",
                                 headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req) as r:
        releases = json.load(r)
    for rel in releases:
        for a in rel["assets"]:
            if match(a["name"]):
                return a["name"], a["browser_download_url"]
    raise SystemExit(f"{repo}: 맞는 파일이 없습니다")


def download(url, dest):
    with urllib.request.urlopen(url) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {done * 100 // total}%", end="", flush=True)
    print()


def fetch_mpv(tmp):
    name, url = latest_asset(MPV_REPO, lambda n: n.startswith(MPV_PREFIX) and n.endswith(".7z"))
    print("libmpv:", name)
    arc = os.path.join(tmp, name)
    download(url, arc)
    seven = shutil.which("7z") or shutil.which("7za")
    if not seven:
        raise SystemExit("7z 명령이 필요합니다 (7-Zip 또는 NanaZip 설치)")
    subprocess.run([seven, "e", "-y", f"-o{tmp}", arc, "libmpv-2.dll"], check=True, stdout=subprocess.DEVNULL)
    shutil.copy2(os.path.join(tmp, "libmpv-2.dll"), BIN)
    return name


def fetch_ffmpeg(tmp):
    name, url = latest_asset(FFMPEG_REPO, lambda n: n.endswith(FFMPEG_SUFFIX))
    print("ffmpeg:", name)
    arc = os.path.join(tmp, name)
    download(url, arc)
    with zipfile.ZipFile(arc) as z:
        member = next(m for m in z.namelist() if m.endswith("/bin/ffmpeg.exe"))
        with z.open(member) as src, open(os.path.join(BIN, "ffmpeg.exe"), "wb") as dst:
            shutil.copyfileobj(src, dst)
    return name


def fetch_llama(tmp):
    """llama.cpp Vulkan 빌드 → bin/llama (llama-server.exe 와 DLL 만). NVIDIA·AMD·Intel GPU, 없으면 CPU."""
    name, url = latest_asset(LLAMA_REPO, lambda n: n.startswith("llama-b") and n.endswith("-bin-win-vulkan-x64.zip"))
    print("llama.cpp:", name)
    arc = os.path.join(tmp, name)
    download(url, arc)
    dest = os.path.join(BIN, "llama")
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    with zipfile.ZipFile(arc) as z:
        for m in z.namelist():
            base = os.path.basename(m)
            if base == "llama-server.exe" or base.lower().endswith(".dll") or base.upper().startswith("LICENSE"):
                with z.open(m) as src, open(os.path.join(dest, base), "wb") as dst:
                    shutil.copyfileobj(src, dst)
    return name


def main():
    os.makedirs(BIN, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="noad_deps_")
    try:
        versions = {"libmpv": fetch_mpv(tmp), "ffmpeg": fetch_ffmpeg(tmp), "llama.cpp": fetch_llama(tmp)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    with open(os.path.join(BIN, "versions.json"), "w", encoding="utf-8") as f:
        json.dump(versions, f, ensure_ascii=False, indent=2)
    print("완료:", BIN)


if __name__ == "__main__":
    sys.exit(main())
