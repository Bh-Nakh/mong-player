# 제3자 구성요소 고지 (THIRD-PARTY NOTICES)

몽플레이어는 아래 제3자 구성요소를 사용하거나 함께 배포한다. 각 구성요소는 해당 저작권자의 라이선스를 따르며, 그 조건은 몽플레이어의 GPL-3.0 라이선스(`LICENSE`)와 별개로 유지된다.

(내부 코드 이름은 `NoAdPlayer`이며 기존 `THIRD_PARTY_LICENSES.txt`의 "노애드플레이어"와 같은 프로그램이다.)

## LGPL 구성요소의 교체 안내

LGPL 구성요소(PySide6·shiboken6, python-mpv, mpv의 `libmpv-2.dll`, FFmpeg, LAME)는 수정하지 않고 **동적 링크**(별도 DLL·파이썬 패키지)로 사용한다. 사용자는 같은 인터페이스를 가진 다른 버전으로 교체할 수 있다. 설치 폴더의 `bin\libmpv-2.dll`을 바꾸거나, 추가 기능으로 받은 `ffmpeg.exe`를 바꾸면 된다. PySide6·shiboken6 파일은 설치 폴더의 `_internal\` 아래에 있다. 각 소스 코드는 아래 표의 출처에서 받을 수 있다.

## 구성요소 목록

"배포 형태" 구분: **설치본** = 설치 프로그램에 들어 있음, **추가 기능** = 처음 쓸 때 공개 배포 저장소에서 내려받음, **내려받음** = 사용자 PC에서 외부 사이트로부터 받음, **개발용** = 빌드에만 쓰고 설치본에 없음.

### 재생 엔진·화면

| 구성요소 | 버전 | 라이선스 | 출처 | 배포 형태 | 고지 파일 위치 |
|---|---|---|---|---|---|
| mpv (`libmpv-2.dll`) | v0.41.0-1109-g36abaa32d | LGPL-2.1-or-later (lgpl 빌드) | https://github.com/mpv-player/mpv / 빌드: https://github.com/zhongfly/mpv-winbuild (mpv-dev-lgpl-x86_64) | 설치본 | `licenses/mpv/` |
| FFmpeg (libmpv 내장, 추가 기능 `ffmpeg.exe`) | n9.0.2-22-g46d8f462ee-20261007 | LGPL-3.0-or-later (`--enable-version3`, `--enable-gpl`·`--enable-nonfree` 없음) | https://ffmpeg.org/download.html / 빌드: https://github.com/BtbN/FFmpeg-Builds (win64-lgpl) | 설치본(libmpv 내장) · 추가 기능(`ffmpeg.exe`) | `licenses/ffmpeg/` |
| Qt for Python (PySide6, shiboken6) | 6.11.2 (설치본) | LGPL-3.0-only (LGPL/GPL 중 LGPL 선택) | https://code.qt.io/cgit/pyside/pyside-setup.git | 설치본 | `licenses/pyside6/` |
| python-mpv | 1.0.8 | LGPL-2.1-or-later (GPL-2.0+/LGPL-2.1+ 이중 라이선스 중 LGPL 선택) | https://github.com/jaseg/python-mpv | 설치본 | `licenses/python-mpv/` |
| LAME (MP3, `ffmpeg.exe` 내장) | - | LGPL-2.0-or-later | https://lame.sourceforge.io | 추가 기능 | `licenses/lame/` |
| FLAC (`ffmpeg.exe` 내장) | - | BSD-3-Clause | https://github.com/xiph/flac | 추가 기능 | `licenses/flac/` |

mpv·FFmpeg 안에 정적으로 들어 있는 libass, libplacebo, libdav1d, libaom, libvpx, libopus, libvorbis, libjxl, libwebp, SVT-AV1, rav1e, OpenH264, shaderc, SPIRV-Cross 등은 LGPL·BSD·MIT 계열이다(2026-10-13 바이너리 점검). x264, x265, Xvid, fdk-aac, rubberband, dvdnav 등 GPL·nonfree 구성요소는 포함하지 않는다.

### 파이썬·런타임 (설치본)

| 구성요소 | 버전 | 라이선스 | 출처 | 배포 형태 | 고지 파일 위치 |
|---|---|---|---|---|---|
| CPython | 3.11 | PSF-2.0 | https://www.python.org | 설치본 | `licenses/python/` |
| OpenSSL (`libcrypto-3.dll`, `libssl-3.dll`) | 3.x | Apache-2.0 | https://www.openssl.org | 설치본 | `licenses/openssl/` |
| libffi | 3.x | MIT | https://github.com/libffi/libffi | 설치본 | `licenses/libffi/` |
| MSVC 런타임 (`vcruntime140*.dll`, `msvcp140*.dll`) | - | Microsoft 재배포 조건 | https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files | 설치본 | - |

### AI 자막·번역 (추가 기능, 설치본에 넣지 않음)

| 구성요소 | 버전 | 라이선스 | 출처 | 배포 형태 | 고지 파일 위치 |
|---|---|---|---|---|---|
| faster-whisper | 1.2.1 | MIT | https://github.com/SYSTRAN/faster-whisper | 추가 기능 | `licenses/faster-whisper/` |
| CTranslate2 | 4.8.2 | MIT | https://github.com/OpenNMT/CTranslate2 | 추가 기능 | `licenses/ctranslate2/` |
| ONNX Runtime | 1.31.0 | MIT | https://github.com/microsoft/onnxruntime | 추가 기능 | `licenses/onnxruntime/` |
| flatbuffers | 25.12.19 | Apache-2.0 | https://github.com/google/flatbuffers | 추가 기능 | `licenses/flatbuffers/` |
| protobuf | 7.36.2 | BSD-3-Clause | https://github.com/protocolbuffers/protobuf | 추가 기능 | `licenses/protobuf/` |
| NumPy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | https://numpy.org | 추가 기능 | `licenses/numpy/` |
| tokenizers | 0.23.3 | Apache-2.0 | https://github.com/huggingface/tokenizers | 추가 기능 | `licenses/tokenizers/` |
| huggingface_hub | 2.2.0 | Apache-2.0 | https://github.com/huggingface/huggingface_hub | 추가 기능 | `licenses/huggingface_hub/` |
| hf-xet | 1.7.0 | Apache-2.0 | https://github.com/huggingface/xet-core | 추가 기능 | `licenses/hf-xet/` |
| httpx2 / httpcore2 | 2.13.1 | BSD-3-Clause | https://github.com/encode/httpx | 추가 기능 | `licenses/httpx/` |
| tqdm | - | MPL-2.0 AND MIT | https://github.com/tqdm/tqdm | 추가 기능 | `licenses/tqdm/` |
| llama.cpp (Vulkan 빌드) | b11496 | MIT | https://github.com/ggml-org/llama.cpp | 추가 기능 | `licenses/llama.cpp/` |
| LLVM OpenMP (`libomp.dll`) | 5.0 | Apache-2.0 WITH LLVM-exception | https://openmp.llvm.org | 추가 기능 | `bin\llama\LICENSE-LLVM-OpenMP` |
| Whisper large-v3-turbo 모델 (CTranslate2 변환본: mobiuslabsgmbh/faster-whisper-large-v3-turbo) | - | MIT (OpenAI) | https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo | 내려받음 | - |
| Tencent Hy-MT2-1.8B 번역 모델 (GGUF Q4_K_M) | - | Apache-2.0 | https://huggingface.co/tencent/Hy-MT2-1.8B-GGUF | 내려받음 | - |
| NVIDIA cuBLAS (`nvidia-cublas-cu12`) | - | NVIDIA 소프트웨어 라이선스 | https://pypi.org/project/nvidia-cublas-cu12/ | 내려받음 (NVIDIA GPU가 있는 PC에서 AI 자막 첫 사용 때 PyPI에서 받음. 몽플레이어가 재배포하지 않음) | - |

faster-whisper의 PyAV(GPL FFmpeg 포함) 의존성은 의도적으로 제외했다. DeepL·Google Cloud Translation·Microsoft Translator는 사용자가 본인 계정의 API 키를 넣었을 때만 쓰며, 이용 조건은 사용자와 각 회사 사이의 약관을 따른다.

주의: python-mpv·PySide6은 GPL 선택도 가능하지만 LGPL을 선택해 쓴다. PySide6은 동적 링크를 유지해야 한다. tqdm의 MPL-2.0 부분은 해당 파일을 고쳐 배포할 때 그 파일의 소스를 공개해야 한다.

### 개발용 (설치본에 없음)

PySide6_Pdf, PySide6_WebEngine(6.12.0.140, LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only)은 PySide6 설치 때 함께 깔리지만 `NoAdPlayer.spec`의 excludes로 설치본에서 제외된다. Pillow 등 빌드·개발용 패키지도 설치본에 들어가지 않는다.

## 라이선스 원문 보관 위치

각 구성요소의 라이선스 원문(저작권 표시 포함)은 저장소의 아래 위치에 그대로 보관한다.

- 저장소 기준 `licenses/{구성요소}/` 폴더: 구성요소별 `LICENSE`(또는 `COPYING`, `NOTICE`) 파일
- 설치본에도 같은 폴더를 포함해 사용자가 열람할 수 있게 한다.
- Apache-2.0 구성요소에 `NOTICE` 파일이 있으면 함께 보관한다.
- 원문은 수정하지 않고 받은 그대로 저장한다.

(현재 `licenses/` 폴더는 아직 만들어지지 않았다. 표의 경로는 채워야 할 목표 위치이며, 원문은 위 출처 저장소에서 받아 보관한다.)
