"""GPU(NVIDIA) 가속 구성요소 — 설치 파일에 넣지 않고, GPU 가 있는 PC 에서 첫 사용 때만 받는다.

자막 생성 중 실제로 불러오는 CUDA 파일은 cuBLAS 두 개뿐이다 (2026-10-08 확인: cuDNN·nvrtc 는 쓰지 않음).
NVIDIA 가 PyPI 에 올린 cuBLAS 배포본(재배포 허용)을 받아 그 두 DLL 만 꺼낸다.
"""
import ctypes
import os
import zipfile

from ..paths import DATA
from .download import Cancelled, fetch

DIR = os.path.join(DATA, "cuda")
WHEEL_URL = ("https://files.pythonhosted.org/packages/20/e2/fc9a0e985249d873150276d5afb02e39a66817fedbf1a385724393e505ed/"
             "nvidia_cublas_cu12-12.9.2.10-py3-none-win_amd64.whl")
WHEEL_SIZE = 553162896
WHEEL_SHA256 = "623f43027d40d44ceadf0043f002bd25cf353e8f13ce90b9a87057019f560661"
DLLS = ["cublas64_12.dll", "cublasLt64_12.dll"]


def has_nvidia_gpu():
    """NVIDIA 드라이버(nvcuda.dll)로 직접 센다 — 받아쓰기 라이브러리를 받기 전에도 알 수 있어야 한다."""
    try:
        cuda = ctypes.WinDLL("nvcuda.dll")
        count = ctypes.c_int(0)
        return cuda.cuInit(0) == 0 and cuda.cuDeviceGetCount(ctypes.byref(count)) == 0 and count.value > 0
    except Exception:  # noqa: BLE001 — 드라이버 없음
        return False


def installed():
    return all(os.path.isfile(os.path.join(DIR, n)) for n in DLLS)


def activate():
    """받은 DLL 폴더를 검색 경로에 넣는다 (앱 시작 때, 그리고 받은 직후)."""
    if installed():
        os.add_dll_directory(DIR)
        os.environ["PATH"] = DIR + os.pathsep + os.environ.get("PATH", "")


def download(progress=lambda done, total: None, cancelled=lambda: False):
    wheel = os.path.join(DIR, os.path.basename(WHEEL_URL))
    fetch(WHEEL_URL, wheel, WHEEL_SIZE, WHEEL_SHA256, lambda d: progress(d, WHEEL_SIZE), cancelled)
    with zipfile.ZipFile(wheel) as z:
        for name in DLLS:
            member = f"nvidia/cublas/bin/{name}"
            tmp = os.path.join(DIR, name + ".tmp")
            try:
                with z.open(member) as src, open(tmp, "wb") as dst:
                    while buf := src.read(1 << 22):
                        if cancelled():
                            raise Cancelled()
                        dst.write(buf)
            except Cancelled:
                os.remove(tmp)
                raise
            os.replace(tmp, os.path.join(DIR, name))
    os.remove(wheel)
    activate()
