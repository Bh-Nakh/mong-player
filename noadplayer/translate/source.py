"""번역할 자막 원문 가져오기 — 외부 자막 파일이든 영상 내장 트랙이든 ffmpeg 로 SRT 로 바꿔 읽는다."""
import os
import re
import subprocess
import tempfile

from ..stt.srt import Cue, parse_srt

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
# 그림으로 된 자막 — 글자가 없어 번역할 수 없다
BITMAP_CODECS = {"dvd_subtitle", "hdmv_pgs_subtitle", "dvb_subtitle", "xsub", "dvb_teletext"}


class SourceError(RuntimeError):
    pass


def selected_track(player):
    """현재 화면에 나오는 자막 트랙 → {"kind": "external"|"embedded", "path", "ff_index", "title"} 또는 None"""
    for t in player.track_list or []:
        if t.get("type") == "sub" and t.get("selected"):
            if t.get("codec") in BITMAP_CODECS:
                raise SourceError("그림으로 된 자막(VobSub·블루레이 자막)은 글자가 없어 번역할 수 없습니다.")
            title = " · ".join(str(x) for x in (t.get("title"), t.get("lang")) if x) or f"트랙 {t['id']}"
            if t.get("external"):
                path = t.get("external-filename")
                return {"kind": "external", "path": path, "ff_index": None,
                        "title": os.path.basename(path or "") or title}
            return {"kind": "embedded", "path": player.path, "ff_index": t.get("ff-index"), "title": f"내장 자막 ({title})"}
    return None


def _charenc(path):
    """텍스트 자막의 인코딩 — UTF-8 이 아니면 한국 자막에 흔한 CP949 로 본다."""
    try:
        with open(path, "rb") as f:
            f.read().decode("utf-8")
        return None
    except UnicodeDecodeError:
        return "CP949"
    except OSError as e:
        raise SourceError(f"자막 파일을 읽지 못했습니다: {e}") from e


_TAGS = re.compile(r"<[^>]+>|\{[^}]*\}")


def clean_text(text):
    """서식 태그(<i>, {\\an8} 등)와 ASS 줄바꿈(\\N)을 정리."""
    text = _TAGS.sub("", text.replace("\\N", "\n").replace("\\n", "\n").replace("&nbsp;", " "))
    return "\n".join(s.strip() for s in text.splitlines() if s.strip())


def load_cues(src, ffmpeg):
    """→ [Cue] (빈 줄 제외, 태그 정리)"""
    with tempfile.TemporaryDirectory(prefix="noad_tr_") as tmp:
        out = os.path.join(tmp, "src.srt")
        cmd = [ffmpeg, "-nostdin", "-y", "-v", "error"]
        if src["kind"] == "external":
            enc = _charenc(src["path"])
            if enc:
                cmd += ["-sub_charenc", enc]
            cmd += ["-i", src["path"], "-map", "0:s:0"]
        else:
            cmd += ["-i", src["path"], "-map", f"0:{src['ff_index']}"]
        cmd += ["-c:s", "srt", out]
        r = subprocess.run(cmd, capture_output=True, creationflags=NO_WINDOW)
        if r.returncode != 0 or not os.path.isfile(out):
            raise SourceError("자막을 읽지 못했습니다: " + r.stderr.decode("utf-8", "replace").strip()[-300:])
        cues = []
        for c in parse_srt(out):
            t = clean_text(c.text)
            if t:
                cues.append(Cue(c.start_ms, c.end_ms, t))
    if not cues:
        raise SourceError("자막에 번역할 글자가 없습니다.")
    return cues


def hangul_ratio(cues):
    letters = hangul = 0
    for c in cues:
        for ch in c.text:
            if ch.isalpha():
                letters += 1
                hangul += "가" <= ch <= "힣"
    return hangul / letters if letters else 0.0
