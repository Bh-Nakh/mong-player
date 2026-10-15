"""이어 받기·자동 재시도·크기/해시 확인이 되는 다운로드."""
import hashlib
import os
import time
import urllib.request

from .. import APP_NAME, VERSION


class Cancelled(Exception):
    pass


class DownloadError(RuntimeError):
    pass


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for buf in iter(lambda: f.read(1 << 22), b""):
            h.update(buf)
    return h.hexdigest()


def _once(url, part, size, progress, cancelled):
    have = os.path.getsize(part) if os.path.isfile(part) else 0
    if have > size:
        os.remove(part)
        have = 0
    if have == size:
        return
    req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{VERSION}"})
    if have:
        req.add_header("Range", f"bytes={have}-")
    with urllib.request.urlopen(req, timeout=30) as r:
        if have and r.status != 206:                         # 이어 받기를 안 받아 주면 처음부터
            have = 0
        with open(part, "ab" if have else "wb") as f:
            while buf := r.read(1 << 20):
                if cancelled():
                    raise Cancelled()
                f.write(buf)
                have += len(buf)
                progress(have)


def fetch(url, dest, size, digest=None, progress=lambda done: None, cancelled=lambda: False, tries=10):
    """url → dest. 끊기면 이어 받기로 다시 시도, 취소하면 Cancelled (받은 부분은 남겨 다음에 이어 받음)."""
    if os.path.isfile(dest) and os.path.getsize(dest) == size:
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    for n in range(1, tries + 1):
        try:
            _once(url, part, size, progress, cancelled)
            if os.path.getsize(part) == size:
                break
        except OSError as e:                                  # 연결 끊김·시간 초과
            if n == tries:
                raise DownloadError(f"다운로드 실패: {e}. 다시 시도하면 이어서 받습니다.") from e
            time.sleep(min(20, 2 * n))
    if os.path.getsize(part) != size:
        raise DownloadError("다운로드가 덜 됐습니다. 다시 시도하면 이어서 받습니다.")
    if digest and sha256(part) != digest:
        os.remove(part)
        raise DownloadError("받은 파일이 손상되었습니다. 다시 시도하세요.")
    os.replace(part, dest)
    return dest
