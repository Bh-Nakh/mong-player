"""자막 한 줄(Cue)과 SRT 읽기/쓰기.

SE 는 시간을 밀리초(double)로 들고 있고, 초 단위로 읽고 쓸 때 /1000, *1000 을 한다.
파형 보정에서 0.025초씩 더하고 빼면 32659.999… 같은 값이 생기는데, SE 는 SRT 에 쓸 때 이를 버림해서
00:00:32,659 로 적는다 (SE 가 저장한 Base.srt 와 같게 하려고 똑같이 처리).
"""
import re


class Cue:
    __slots__ = ("start_ms", "end_ms", "text")

    def __init__(self, start_ms, end_ms, text=""):
        self.start_ms = float(start_ms)
        self.end_ms = float(end_ms)
        self.text = text

    # SE Paragraph.StartTime.TotalSeconds 와 같은 변환
    @property
    def start(self):
        return self.start_ms / 1000.0

    @start.setter
    def start(self, s):
        self.start_ms = s * 1000.0

    @property
    def end(self):
        return self.end_ms / 1000.0

    @end.setter
    def end(self, s):
        self.end_ms = s * 1000.0

    @property
    def dur_ms(self):
        return self.end_ms - self.start_ms

    def copy(self):
        return Cue(self.start_ms, self.end_ms, self.text)

    def as_dict(self):
        return {"start": round(self.start_ms) / 1000.0, "end": round(self.end_ms) / 1000.0, "text": self.text}

    def __repr__(self):
        return f"Cue({fmt_time(self.start_ms)} --> {fmt_time(self.end_ms)} {self.text!r})"


_TC = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)")


def parse_srt(path):
    """SRT → [Cue] (빈 줄은 버림, 여러 줄 텍스트는 \\n 으로 유지)."""
    with open(path, encoding="utf-8-sig") as f:
        blocks = re.split(r"\n\s*\n", f.read().replace("\r\n", "\n").strip())
    out = []
    for b in blocks:
        lines = [x for x in b.split("\n")]
        ti = next((i for i, x in enumerate(lines) if "-->" in x), None)
        if ti is None:
            continue
        m = _TC.findall(lines[ti])
        if len(m) < 2:
            continue
        ms = [((int(h) * 60 + int(mi)) * 60 + int(s)) * 1000 + int(f.ljust(3, "0")[:3]) for h, mi, s, f in m[:2]]
        text = "\n".join(x.strip() for x in lines[ti + 1:] if x.strip())
        if text:
            out.append(Cue(ms[0], ms[1], text))
    return out


def fmt_time(ms):
    """밀리초 → 'HH:MM:SS,mmm' (SE 처럼 버림: TimeSpan 틱으로 바꾼 뒤 ms 자리)."""
    ticks = int(ms * 10000)                 # .NET TimeSpan 틱(100ns), 소수 버림
    total = max(0, ticks // 10000)
    h, rem = divmod(total, 3600000)
    m, rem = divmod(rem, 60000)
    s, msec = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{msec:03d}"


def to_srt(cues):
    return "".join(f"{i}\n{fmt_time(c.start_ms)} --> {fmt_time(c.end_ms)}\n{c.text}\n\n"
                   for i, c in enumerate(cues, 1))


def write_srt(cues, path):
    with open(path, "w", encoding="utf-8-sig") as f:
        f.write(to_srt(cues))
    return path
