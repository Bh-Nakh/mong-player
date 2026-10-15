"""API 키 같은 비밀값을 Windows DPAPI 로 암호화 — 같은 Windows 사용자 계정에서만 풀린다."""
import base64
import ctypes
from ctypes import wintypes

_crypt32 = ctypes.WinDLL("crypt32")
_kernel32 = ctypes.WinDLL("kernel32")
CRYPTPROTECT_UI_FORBIDDEN = 0x1
_ENTROPY = b"NoAdPlayer.api-key"


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _in(data):
    buf = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _out(blob):
    try:
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        _kernel32.LocalFree(blob.pbData)


def protect(text):
    if not text:
        return ""
    src, _b1 = _in(text.encode("utf-8"))
    ent, _b2 = _in(_ENTROPY)
    out = _Blob()
    if not _crypt32.CryptProtectData(ctypes.byref(src), None, ctypes.byref(ent), None, None,
                                     CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out)):
        raise OSError("키를 암호화하지 못했습니다")
    return base64.b64encode(_out(out)).decode()


def unprotect(token):
    if not token:
        return ""
    src, _b1 = _in(base64.b64decode(token))
    ent, _b2 = _in(_ENTROPY)
    out = _Blob()
    if not _crypt32.CryptUnprotectData(ctypes.byref(src), None, ctypes.byref(ent), None, None,
                                       CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out)):
        return ""                      # 다른 PC·계정에서 복사된 설정 → 키를 다시 넣어야 함
    return _out(out).decode("utf-8")
