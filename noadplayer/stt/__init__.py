"""AI 자막 생성 — matcher(J:\\클로드워크\\유튜브 스튜디오\\matcher\\stt)의 전/후처리를 그대로 옮기고
엔진만 faster-whisper 패키지(MIT)로 바꿨다. cleanup·timing·srt·extract 는 matcher 원본 복사본.

받아쓰기 라이브러리(numpy·ctranslate2 등)는 설치 파일에 없고 처음 쓸 때 받는 'stt' 추가 기능이다
(noadplayer/addons.py) → core·engine 은 transcribe 를 부를 때 비로소 불러온다.

    from noadplayer.stt import transcribe, model
    addons.ensure("stt"); addons.ensure("ffmpeg")
    if not model.installed(): model.download(progress)
    r = transcribe("영상.mp4", ffmpeg_path)
"""
from . import gpu, model  # noqa: F401
from .download import Cancelled  # noqa: F401


def transcribe(*args, **kwargs):
    from .core import transcribe as _transcribe
    return _transcribe(*args, **kwargs)


def __getattr__(name):
    if name == "SttError":
        from .core import SttError
        return SttError
    raise AttributeError(name)
