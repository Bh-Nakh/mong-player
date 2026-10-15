"""번역 모델 Tencent Hy-MT2 1.8B (Apache 2.0, 4비트 GGUF) — 첫 사용 때 한 번 내려받는다."""
import os

from ..paths import MODELS
from ..stt.download import fetch

FILE = "Hy-MT2-1.8B-Q4_K_M.gguf"
PATH = os.path.join(MODELS, FILE)
URL = "https://huggingface.co/tencent/Hy-MT2-1.8B-GGUF/resolve/main/" + FILE
SIZE = 1133080448
SHA256 = "dc5f44fcf1fa496ee7ad725982c0c8c553a4de00259b53af84c4b89fb0c06699"


def installed():
    return os.path.isfile(PATH) and os.path.getsize(PATH) == SIZE


def download(progress=lambda done, total: None, cancelled=lambda: False):
    return fetch(URL, PATH, SIZE, SHA256, lambda d: progress(d, SIZE), cancelled)
