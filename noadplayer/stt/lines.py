"""단어 → 자막 줄. Purfview 엔진의 --standard(문장 단위, 한 줄 42자 × 최대 2줄, 쉼표 70%) 규칙을 따른다."""
from .srt import Cue

MAX_LINE = 42
MAX_LINES = 2
COMMA_CENT = 0.7
SENTENCE_END = (".", "?", "!", "…", "。", "？", "！")
PAUSE_SPLIT = 1.0          # 단어 사이가 이만큼(초) 비면 줄을 끊는다


def _wrap(text):
    if len(text) <= MAX_LINE:
        return text
    words = text.split(" ")
    best, best_diff = None, None
    for i in range(1, len(words)):                     # 두 줄 길이가 가장 비슷해지는 곳에서 나눈다
        a, b = " ".join(words[:i]), " ".join(words[i:])
        diff = abs(len(a) - len(b))
        if best_diff is None or diff < best_diff:
            best, best_diff = (a, b), diff
    return "\n".join(best) if best else text


def build(words):
    """words [{t0,t1,w}] → [Cue]"""
    limit = MAX_LINE * MAX_LINES
    cues, cur = [], []

    def flush():
        if cur:
            cues.append(Cue(cur[0]["t0"] * 1000, cur[-1]["t1"] * 1000, _wrap(" ".join(x["w"] for x in cur))))
            cur.clear()

    for i, w in enumerate(words):
        if cur and (len(" ".join(x["w"] for x in cur)) + 1 + len(w["w"]) > limit
                    or w["t0"] - cur[-1]["t1"] >= PAUSE_SPLIT):
            flush()
        cur.append(w)
        text_len = len(" ".join(x["w"] for x in cur))
        if w["w"].endswith(SENTENCE_END) or (w["w"].endswith(",") and text_len >= limit * COMMA_CENT):
            flush()
    flush()
    return cues
