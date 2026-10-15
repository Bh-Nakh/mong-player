"""자막 한국어 번역.

    engine = make_engine("local", settings)      # 또는 deepl / google / azure (사용자 본인 키)
    path = translate_subtitle(src, out_path, engine, ffmpeg, progress, cancelled)
"""
from .. import secret
from ..stt.srt import Cue, write_srt
from . import cloud, model, source  # noqa: F401
from .local import LocalTranslator

ENGINES = [("local", "내 PC (무료, 인터넷으로 보내지 않음)"), ("deepl", "DeepL (본인 API 키)"),
           ("google", "Google (본인 API 키)"), ("azure", "Microsoft (본인 API 키)")]
FREE_QUOTA = {"deepl": "무료 키: 매달 50만 자", "google": "매달 50만 자 무료", "azure": "무료(F0) 등급: 매달 200만 자"}


class AlreadyKorean(Exception):
    pass


def api_key(settings, name):
    return secret.unprotect(settings["api_keys"].get(name, ""))


def has_key(settings, name):
    return bool(api_key(settings, name))


def make_engine(name, settings, log=print):
    if name == "local":
        return LocalTranslator(log)
    if name == "deepl":
        return cloud.DeepL(api_key(settings, "deepl"))
    if name == "google":
        return cloud.Google(api_key(settings, "google"))
    if name == "azure":
        return cloud.Azure(api_key(settings, "azure"), settings["api_keys"].get("azure_region", ""))
    raise ValueError(name)


def translate_subtitle(src, out_path, engine, ffmpeg, progress=lambda d, t: None, cancelled=lambda: False,
                       allow_korean=False):
    """src(source.selected_track 형식, 또는 {"kind": "external", "path": srt}) → 한국어 SRT 저장, 줄 수 반환."""
    cues = source.load_cues(src, ffmpeg)
    if not allow_korean and source.hangul_ratio(cues) >= 0.5:
        raise AlreadyKorean()
    lines = [" ".join(c.text.splitlines()) for c in cues]             # 여러 줄 대사는 한 줄로 합쳐 번역
    engine.start(cancelled)
    try:
        ko = engine.translate(lines, progress, cancelled)
    finally:
        engine.close()
    write_srt([Cue(c.start_ms, c.end_ms, t) for c, t in zip(cues, ko)], out_path)
    return len(cues)
