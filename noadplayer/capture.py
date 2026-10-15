"""캡처: 스크린샷(mpv), 구간 영상·소리 저장(ffmpeg).

구간 영상은 다시 인코딩하지 않고 스트림 복사(-c copy)로 자른다 — 화질 손실이 없고 빠르며,
H.264/HEVC 인코더(특허·GPL 문제)가 필요 없다. 대신 시작점이 가장 가까운 키프레임에 맞춰진다.
"""
import os
import subprocess
import time

from .paths import FFMPEG, user_dir

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CLIP_CONTAINERS = {".mp4", ".mkv", ".mov", ".webm", ".ts", ".m4v"}
AUDIO_FORMATS = {
    "mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
    "flac": ["-c:a", "flac"],
    "wav": ["-c:a", "pcm_s16le"],
}


def _stem(src):
    name = os.path.splitext(os.path.basename(src.split("?")[0].rstrip("/")))[0] or "capture"
    return "".join("_" if c in '\\/:*?"<>|' else c for c in name)[:80]


def _stamp(sec):
    sec = max(0.0, sec or 0.0)
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}{m:02d}{s:02d}"


def _unique(path):
    base, ext = os.path.splitext(path)
    n = 1
    while os.path.exists(path):
        path = f"{base} ({n}){ext}"
        n += 1
    return path


def screenshot(player, with_subs=True):
    src = player.path or "capture"
    out = _unique(os.path.join(user_dir("image"), f"{_stem(src)}_{_stamp(player.time_pos)}.png"))
    player.command("screenshot-to-file", out, "subtitles" if with_subs else "video")
    return out


def clip_command(src, a, b, kind, audio_format="mp3"):
    """→ (명령, 출력 경로). kind: 'video' | 'audio'"""
    dur = max(0.1, b - a)
    stem = f"{_stem(src)}_{_stamp(a)}-{_stamp(b)}"
    cmd = [FFMPEG, "-nostdin", "-y", "-v", "error", "-ss", f"{a:.3f}", "-i", src, "-t", f"{dur:.3f}"]
    if kind == "video":
        ext = os.path.splitext(src.split("?")[0])[1].lower()
        ext = ext if ext in CLIP_CONTAINERS else ".mkv"
        out = _unique(os.path.join(user_dir("video"), stem + ext))
        cmd += ["-map", "0:v:0?", "-map", "0:a?", "-c", "copy", "-avoid_negative_ts", "make_zero", out]
    else:
        out = _unique(os.path.join(user_dir("video"), f"{stem}.{audio_format}"))
        cmd += ["-vn", "-map", "0:a:0", *AUDIO_FORMATS[audio_format], out]
    return cmd, out


def run_clip(cmd, out):
    """ffmpeg 실행 (작업 스레드에서 부른다). 실패하면 RuntimeError."""
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, creationflags=NO_WINDOW)
    if r.returncode != 0 or not os.path.isfile(out) or os.path.getsize(out) == 0:
        if os.path.isfile(out):
            os.remove(out)
        raise RuntimeError(r.stderr.decode("utf-8", "replace").strip()[-300:] or f"ffmpeg 종료 코드 {r.returncode}")
    return out, time.time() - t
