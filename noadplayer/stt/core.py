"""AI 자막 전체 흐름 — matcher 의 STT 와 같은 전/후처리.

① ffmpeg 16kHz mono WAV (extract)  ② faster-whisper (engine)  ③ 단어 → 줄 (lines)
④ 정렬·겹침 제거  ⑤ 최대 표시시간  ⑥ 파형 시작점 보정  ⑦ 텍스트 정리  ⑧ 최소 표시시간 + 겹침 제거
"""
import os
import shutil
import tempfile

from . import cleanup, engine, extract, lines, model, timing
from .srt import to_srt

DEFAULTS = dict(
    auto_adjust_timings=True,
    max_duration=8.0,
    min_duration=1.0,
    min_gap=0.024,
    remove_repeated=True,
    remove_non_speech=True,
    post_processing=True,
    fix_short_duration=True,
)


class SttError(RuntimeError):
    pass


def post_process(cues, wav, o=DEFAULTS):
    """④~⑧ — matcher stt.core.post_process 와 같다."""
    cues = timing.sort_and_remove_overlaps(cues)
    cues = timing.shorten_long_duration(cues, o["max_duration"] * 1000)
    if o["auto_adjust_timings"]:
        cues = timing.shorten_via_wave_peaks(cues, timing.WavePeaks(wav))
    if o["post_processing"]:
        cues = cleanup.clean(cues, o["remove_non_speech"], o["remove_repeated"])
        if o["fix_short_duration"]:
            cues = timing.fix_short_duration(cues, o["min_duration"] * 1000, o["min_gap"] * 1000)
            cues = timing.sort_and_remove_overlaps(cues)
    return cues


def transcribe(path, ffmpeg, language="ko", device=None, progress=lambda t, total: None,
               cancelled=lambda: False, log=print):
    """영상·오디오 파일 → {"srt", "segments", "words", "language", "device"}. 모델이 없으면 SttError."""
    if not model.installed():
        raise SttError("자막 모델이 설치되지 않았습니다.")
    work = tempfile.mkdtemp(prefix="noad_stt_")
    try:
        wav = os.path.join(work, "audio.wav")
        try:
            extract.extract_wav(path, wav, ffmpeg)
        except RuntimeError as e:
            raise SttError(str(e)) from e
        words, lang, dev = engine.run(wav, model.DIR, language, device, progress, cancelled, log)
        cues = post_process(lines.build(words), wav)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return {"srt": to_srt(cues), "segments": [c.as_dict() for c in cues], "words": words,
            "language": lang, "device": dev}
