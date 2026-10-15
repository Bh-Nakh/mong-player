"""⑦ 텍스트 정리 — SE SpeechToTextPostProcessor.Fix 의 첫 반복문 중 한국어에 의미 있는 것.

Ported from Subtitle Edit (MIT, © Nikolaj Olsson) — SpeechToTextPostProcessor.cs
- 비발화 줄 제거: 텍스트 전체가 [..] (..) ♪ 류뿐인 줄
- 반복 줄 제거: 직전에 '남긴' 줄과 같은 텍스트 (같은 줄 5번 → 1줄)
- "(" "(." 만 있는 줄 제거
- 공백 정리 (RemoveUnneededSpaces 중 연속 공백·앞뒤 공백)
- "." 로 시작하고 ")." 로 끝나면 끝의 마침표 제거
- 앞 줄 끝 == 다음 줄 시작이면 다음 줄 시작 +1ms (다음 줄 길이가 1ms 넘을 때)
AddPeriods·FixCasing 은 한국어에 불필요(SE 설정에서도 꺼짐), 줄 나누기·합치기는 엔진 옵션으로 대신한다.
"""
import re

_NON_SPEECH_PART = re.compile(r"^\s*(\[[^\]]*\]|\([^)]*\)|[♪♫♬#*\s]+)\s*$")


def is_non_speech(text):
    t = (text or "").strip()
    if not t:
        return True
    parts = [x for x in re.split(r"(\[[^\]]*\]|\([^)]*\))", t) if x and x.strip()]
    return all(_NON_SPEECH_PART.match(x) for x in parts)


def _norm(text):
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def is_repeat_of(text, prev_text):
    return _norm(text) != "" and _norm(text) == _norm(prev_text)


def remove_unneeded_spaces(text):
    lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in (text or "").split("\n")]
    return "\n".join(ln for ln in lines if ln)


def clean(cues, remove_non_speech=True, remove_repeated=True):
    """입력은 시간 보정이 끝난 [Cue]. 원본처럼 '다음 줄' 시작 +1ms 는 입력 목록을 직접 고친다."""
    s = [c.copy() for c in cues]
    out = []
    for index, p in enumerate(s):
        if remove_non_speech and is_non_speech(p.text):
            continue
        if remove_repeated and out and is_repeat_of(p.text, out[-1].text):
            continue
        if p.text in ("(.", "("):
            continue
        p.text = remove_unneeded_spaces(p.text)
        if p.text.startswith(".") and p.text.endswith(")."):
            p.text = p.text.rstrip(".")
        nxt = s[index + 1] if index + 1 < len(s) else None
        if nxt is not None and abs(p.end_ms - nxt.start_ms) < 0.01:
            if nxt.end_ms - nxt.start_ms > 1:
                nxt.start_ms += 1
        out.append(p)
    return out
