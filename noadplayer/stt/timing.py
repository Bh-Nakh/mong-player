"""④⑤⑥⑧ 시간 보정.

Ported from Subtitle Edit (MIT, © Nikolaj Olsson) —
  SpeechToTextTimingFixer.cs: FindPercentage, ShortenViaWavePeaks, SortAndRemoveOverlaps, ShortenLongDuration
원본: J:\\클로드워크\\STT\\reference\\se_source\\SpeechToTextTimingFixer.cs. 로직은 바꾸지 않는다.
시간 계산은 SE 와 같이 밀리초(double)에 초 단위로 읽고 쓴다 (stt.srt.Cue).
"""
import math
import wave

import numpy as np


# ───────────────────────── 파형 피크 ─────────────────────────
class WavePeaks:
    """16kHz mono s16 WAV → 초당 128개 피크 (125샘플마다 max(|max|,|min|)). SE WavePeakData2 에 맞춘 값."""

    def __init__(self, wav_path, peaks_per_sec=128):
        with wave.open(wav_path, "rb") as w:
            if w.getsampwidth() != 2 or w.getnchannels() != 1:
                raise ValueError("16bit mono WAV 가 필요합니다")
            sr = w.getframerate()
            data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.int32)
        chunk = sr // peaks_per_sec
        n = int(np.ceil(len(data) / chunk))
        data = np.pad(data, (0, n * chunk - len(data)))
        blocks = data.reshape(n, chunk)
        self.peaks = np.maximum(np.abs(blocks.max(1)), np.abs(blocks.min(1)))
        self.rate = peaks_per_sec
        self.highest = max(int(self.peaks.max()), 1) if n else 1

    def _index(self, seconds):
        # C# Math.Round(x, MidpointRounding.AwayFromZero)
        x = seconds * self.rate
        return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))

    def pct(self, start_s, end_s):
        """FindPercentage: (평균% + 최대% + 최대%) / 3, 범위 밖이면 -1"""
        lo = max(0, self._index(start_s))
        hi = min(len(self.peaks), self._index(end_s))
        if hi <= lo:
            return -1.0
        seg = self.peaks[lo:hi]
        total = int(seg.sum())
        avg = (total / float(len(seg))) * 100.0 / self.highest
        mx = int(seg.max()) * 100.0 / self.highest
        return (avg + mx + mx) / 3.0


def _is_minus1(v):
    return abs(v - (-1)) < 0.01


# ───────────────────────── ④ 정렬 + 겹침 제거 ─────────────────────────
def sort_and_remove_overlaps(cues):
    s = [c.copy() for c in cues]
    if len(s) < 2:
        return s
    s.sort(key=lambda c: (c.start_ms, c.end_ms))
    for i in range(1, len(s)):
        prev, p = s[i - 1], s[i]
        if p.start_ms >= prev.end_ms:
            continue
        if p.start_ms > prev.start_ms:
            prev.end_ms = p.start_ms
        else:
            d = p.dur_ms
            p.start_ms = prev.end_ms
            p.end_ms = p.start_ms + max(0.0, d)
    return s


# ───────────────────────── ⑤ 너무 긴 줄: 시작을 당김 ─────────────────────────
def shorten_long_duration(cues, max_ms=8000):
    s = [c.copy() for c in cues]
    for p in s:
        if p.dur_ms > max_ms:
            p.start_ms = p.end_ms - max_ms
    return s


# ───────────────────────── ⑥ 파형으로 시작점 보정 (싱크 핵심) ─────────────────────────
def shorten_via_wave_peaks(cues, wp):
    """ShortenViaWavePeaks 를 줄 단위로 옮긴 것. 끝 시간은 건드리지 않는다.
    범위 밖(-1)을 만나면 원본처럼 이후 줄은 손대지 않고 끝낸다."""
    min_duration_ms = 600
    percentage_max = 7.0
    s = [c.copy() for c in cues]

    for index in range(len(s)):
        p = s[index]
        old_p = p.copy()
        prev_end_secs = s[index - 1].end if index > 0 else -1.0

        def restore_and_stop(limit_ms=min_duration_ms):
            if p.dur_ms < limit_ms:
                s[index] = old_p
            return s

        # Find nearest silence
        start_pos = p.start
        pct_here = wp.pct(start_pos - 0.05, start_pos + 0.05)
        if _is_minus1(pct_here):
            return restore_and_stop()

        if pct_here > percentage_max:
            start_pos_back = start_pos
            start_pos_forward = start_pos
            for _ms in range(50, 255, 50):
                pct = wp.pct(start_pos_back - 0.05, start_pos_back + 0.05)
                if _is_minus1(pct):
                    return restore_and_stop()

                if pct < percentage_max + 1 and p.dur_ms / 1000.0 < 5:
                    start_pos_back -= 0.025
                    pct2 = wp.pct(start_pos_back - 0.05, start_pos_back + 0.05)
                    if pct2 < pct and pct2 >= 0:
                        x = start_pos_back
                        if x < 0:
                            x = 0
                        if x > prev_end_secs:
                            p.start = x
                    else:
                        x = start_pos_back + 0.025
                        if x < 0:
                            x = 0
                        if x > prev_end_secs:
                            p.start = x
                    break

                start_pos_back -= 0.05

                pct_f = wp.pct(start_pos_forward - 0.05, start_pos_forward + 0.05)
                if _is_minus1(pct_f):
                    return restore_and_stop()

                if pct_f < percentage_max:
                    start_pos_forward -= 0.025
                    pct2 = wp.pct(start_pos_forward - 0.05, start_pos_forward + 0.05)
                    if pct2 < pct_f and pct2 >= 0:
                        p.start = start_pos_forward
                    else:
                        p.start = start_pos_forward + 0.025
                    break

                start_pos_forward += 0.05

        # find next non-silence
        start_pos = p.start
        pct_here = wp.pct(start_pos - 0.05, start_pos + 0.05)
        if _is_minus1(pct_here):
            return restore_and_stop()

        if pct_here < percentage_max:
            start_pos_forward = p.start
            while pct_here < percentage_max and start_pos_forward < p.end - 1:
                pct_here = wp.pct(start_pos_forward - 0.05, start_pos_forward + 0.05)
                if _is_minus1(pct_here):
                    return restore_and_stop(1000)

                p.start = start_pos_forward
                if pct_here >= percentage_max:
                    start_pos_forward -= 0.025
                    pct2 = wp.pct(start_pos_forward - 0.05, start_pos_forward + 0.05)
                    if pct2 < pct_here and pct2 >= 0:
                        p.start = p.start - 0.025
                        pct_here = pct2
                        start_pos_forward -= 0.025
                        pct2 = wp.pct(start_pos_forward - 0.05, start_pos_forward + 0.05)
                        if pct2 < pct_here and pct2 >= 0:
                            p.start = p.start - 0.025
                    break

                start_pos_forward += 0.05

        if p.dur_ms < min_duration_ms:
            s[index] = old_p

    return s


# ───────────────────────── ⑧ 짧은 줄 늘리기 + 겹침 ─────────────────────────
def fix_short_duration(cues, min_ms=1000, min_gap_ms=24):
    """짧은 줄은 '시작 + 최소 표시시간'까지 늘린다 — 다음 줄 시작보다 최소 간격(24ms) 이상 앞에서 끝날 때만.
    다 못 늘리면 그대로 둔다. SE 가 저장한 Base.srt 로 확인한 동작:
      '이러지.' 0.46초 → 1.00초 (다음 줄까지 여유),  '안 됐다.' 0.42초 → 그대로 (다음 줄까지 0.2초뿐),
      '아니, 뭐 그런 건 있지.' 0.8초 → 그대로 (늘리면 다음 줄 시작과 딱 붙음 — 24ms 간격 필요)
    마지막 줄은 제한 없이 늘린다."""
    s = [c.copy() for c in cues]
    for i, p in enumerate(s):
        if p.dur_ms >= min_ms:
            continue
        want = p.start_ms + min_ms
        nxt = s[i + 1] if i + 1 < len(s) else None
        if nxt is None or want <= nxt.start_ms - min_gap_ms:
            p.end_ms = want
    return s
