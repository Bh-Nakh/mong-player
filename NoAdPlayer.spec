# PyInstaller 설정 — 폴더형(onedir). LGPL 구성요소(PySide6·libmpv)를 사용자가 교체할 수 있게 별도 파일로 둔다.
# 빌드:  .venv\Scripts\python.exe tools\build.py
#
# 기본 설치에는 재생·화면에 꼭 필요한 것만 넣는다. 받아쓰기 라이브러리(numpy·ctranslate2·onnxruntime 등),
# ffmpeg, 번역 엔진은 '추가 기능'으로 처음 쓸 때 내려받는다 (noadplayer/addons.py, tools/build_addons.py).

# 앱 이름(실행 파일·폴더 이름)은 app.name 한 곳에서 읽는다
with open("app.name", encoding="utf-8") as _f:
    APP = _f.read().strip()

datas = [("noadplayer/resources", "noadplayer/resources")]

# 'stt' 추가 기능으로 빠지는 것 — 소스가 import 하더라도 설치본에 넣지 않는다
STT_ADDON = ["numpy", "ctranslate2", "onnxruntime", "faster_whisper", "tokenizers", "huggingface_hub", "hf_xet",
             "tqdm", "yaml", "psutil", "certifi", "click", "httpx", "httpcore", "h11", "anyio", "idna", "filelock",
             "fsspec", "flatbuffers", "google", "colorama", "brotli", "backports", "sniffio", "packaging"]

# 받아쓰기 라이브러리가 쓰는 표준 라이브러리 목록 (tools/build_addons.py 가 만든다)
with open("tools/stt_stdlib.txt", encoding="utf-8") as _f:
    STT_STDLIB = [ln.strip() for ln in _f if ln.strip()]

a = Analysis(
    ["tools/launcher.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=["PySide6.QtOpenGLWidgets"] + STT_STDLIB,
    excludes=["av", "tkinter", "matplotlib", "PIL", "pytest",
              "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQuick", "PySide6.QtQml",
              "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtPdf",
              "PySide6.QtMultimedia", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtNetworkAuth"] + STT_ADDON,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name=APP,
    console=False,
    icon="noadplayer/resources/icon.ico",
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name=APP, upx=False)
