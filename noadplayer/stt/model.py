"""자막 모델 (whisper large-v3-turbo, CTranslate2 변환본 — MIT) — 첫 사용 때 한 번 내려받는다.

matcher(stt/install.py)와 같은 모델·같은 파일 목록.
"""
import os

from ..paths import MODELS
from .download import Cancelled, DownloadError, fetch  # noqa: F401

NAME = "faster-whisper-large-v3-turbo"
DIR = os.path.join(MODELS, NAME)
URL = "https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo/resolve/main/"
# 파일 이름: (크기, sha256 — 큰 파일만 확인)
FILES = {
    "config.json": (2263, None),
    "model.bin": (1617884929, "e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da"),
    "preprocessor_config.json": (340, None),
    "tokenizer.json": (2710337, None),
    "vocabulary.json": (1068114, None),
}
TOTAL = sum(s for s, _h in FILES.values())


def installed():
    return all(os.path.isfile(os.path.join(DIR, n)) and os.path.getsize(os.path.join(DIR, n)) == size
               for n, (size, _h) in FILES.items())


def download(progress=lambda done, total: None, cancelled=lambda: False):
    done = 0
    for name, (size, digest) in FILES.items():
        fetch(URL + name, os.path.join(DIR, name), size, digest,
              lambda d, base=done: progress(base + d, TOTAL), cancelled)
        done += size
        progress(done, TOTAL)
    return DIR
