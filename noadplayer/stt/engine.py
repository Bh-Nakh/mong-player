"""② 음성 인식: faster-whisper 파이썬 패키지 (MIT) — matcher 의 Purfview exe 대신.

Purfview exe 도 내부적으로 faster-whisper 를 쓰므로, 같은 모델과 주요 옵션(beam 5, patience 2, 단어 시간,
silero VAD)을 맞춰 결과를 최대한 같게 한다. GPU(CUDA) 가 없거나 실패하면 CPU(int8)로 다시 한다.
"""
import sys
import types
import wave

import numpy as np

from . import gpu
from .download import Cancelled


def _import_whisper():
    """faster-whisper 는 맨 위에서 PyAV(av)를 import 하지만, 오디오 파일을 직접 읽을 때만 쓴다.
    PyAV 휠의 FFmpeg 는 GPL(libx264/x265 포함)이라 배포본에서 뺐다 → 없으면 빈 모듈로 대신하고,
    오디오는 numpy 배열로 넘긴다."""
    try:
        import av  # noqa: F401
    except ImportError:
        sys.modules["av"] = types.ModuleType("av")
    from faster_whisper import WhisperModel
    return WhisperModel


def load_wav(path):
    """16kHz mono s16 WAV → float32 배열 (faster-whisper 입력 형식)."""
    with wave.open(path, "rb") as w:
        if w.getframerate() != 16000 or w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise RuntimeError("WAV 형식이 16kHz mono 16bit 가 아닙니다")
        data = w.readframes(w.getnframes())
    return np.frombuffer(data, np.int16).astype(np.float32) / 32768.0


def cuda_available():
    """NVIDIA GPU 가 있고 GPU 구성요소(cuBLAS)도 받아 둔 경우만 GPU 로 처리."""
    return gpu.has_nvidia_gpu() and gpu.installed()


def _run(wav, model_dir, language, device, progress, cancelled):
    WhisperModel = _import_whisper()
    model = WhisperModel(model_dir, device=device, compute_type="float16" if device == "cuda" else "int8")
    try:
        segments, info = model.transcribe(load_wav(wav), language=None if language == "auto" else language,
                                          beam_size=5, patience=2.0, word_timestamps=True, vad_filter=True)
        words = []
        for s in segments:
            if cancelled():
                raise Cancelled()
            for w in s.words or []:
                t = w.word.strip()
                if t:
                    words.append({"t0": round(w.start, 3), "t1": round(w.end, 3), "w": t,
                                  "p": round(w.probability, 3)})
            progress(s.end, info.duration)
        return words, info.language
    finally:
        del model                                   # 재생 중에도 쓰므로 GPU 메모리를 바로 돌려준다


def run(wav, model_dir, language="ko", device=None, progress=lambda t, total: None, cancelled=lambda: False,
        log=print):
    """→ (words [{t0,t1,w,p}], 감지 언어, 쓴 장치)"""
    device = device or ("cuda" if cuda_available() else "cpu")
    try:
        words, lang = _run(wav, model_dir, language, device, progress, cancelled)
    except Cancelled:
        raise
    except Exception as e:  # noqa: BLE001 — CUDA 라이브러리 문제 등
        if device != "cuda":
            raise
        log(f"GPU 로 실패해 CPU 로 다시 합니다: {e}")
        device = "cpu"
        words, lang = _run(wav, model_dir, language, device, progress, cancelled)
    return words, lang, device
