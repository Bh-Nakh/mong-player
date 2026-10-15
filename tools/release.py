"""업데이트 배포 파일 만들기 → VERSION, release\patch.json, release\mongplayer-patch.zip

    .venv\Scripts\python.exe tools\release.py [--min-shell N]

만든 뒤 커밋하고 GitHub Desktop 에서 Push 하면, 옛 버전(비공개 저장소·토큰 방식, 0.5.x 이하)을 쓰는 설치본이 시작할 때 새 버전을 알아보고 받아 가도록 한 것이다. 0.6.0 부터의 업데이트는 공개 배포 저장소의 설치 프로그램(mong_update.py)으로 한다.
min_shell 은 기본으로 tools\launcher.py 의 SHELL_API 값을 쓴다 — 새 라이브러리(PySide6·mpv 등)가 필요한 변경이면
설치본 구성이 바뀐 것이므로 SHELL_API 를 올리고 전체를 새로 빌드해 배포해야 한다.
"""
import hashlib
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_FILES = {"_embedded_token.py"}


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


def main():
    version = re.search(r'VERSION = "([^"]+)"', read("noadplayer/__init__.py")).group(1)
    shell = int(re.search(r"SHELL_API = (\d+)", read("tools/launcher.py")).group(1))
    min_shell = int(sys.argv[sys.argv.index("--min-shell") + 1]) if "--min-shell" in sys.argv else shell
    sec = re.search(rf"## {re.escape(version)}\n(.*?)(?=\n## |\Z)", read("CHANGELOG.md"), re.S)
    note = next((ln.lstrip("- ").strip() for ln in (sec.group(1).splitlines() if sec else []) if ln.strip()), "")

    out_dir = os.path.join(ROOT, "release")
    os.makedirs(out_dir, exist_ok=True)
    zpath = os.path.join(out_dir, "mongplayer-patch.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for base, dirs, files in os.walk(os.path.join(ROOT, "noadplayer")):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for fn in sorted(files):
                if fn.endswith(".pyc") or fn in SKIP_FILES:
                    continue
                full = os.path.join(base, fn)
                z.write(full, os.path.relpath(full, ROOT).replace(os.sep, "/"))
    with open(zpath, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    with open(os.path.join(out_dir, "patch.json"), "w", encoding="utf-8") as f:
        json.dump({"version": version, "min_shell": min_shell, "sha256": sha, "note": note}, f,
                  ensure_ascii=False, indent=2)
    with open(os.path.join(ROOT, "VERSION"), "w", encoding="utf-8") as f:
        f.write(version + "\n")
    print(f"배포 파일 완성: v{version} (min_shell {min_shell}, {os.path.getsize(zpath) // 1024} KB)")


if __name__ == "__main__":
    main()
