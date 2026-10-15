"""① 오디오 추출: 16kHz mono s16 WAV — SE 가 엔진에 넘기는 것과 같은 인자.

SE(5.0 beta, Settings.json 의 FfmpegPath = <SE>\\ffmpeg\\ffmpeg.exe)는
    -i <입력> -vn -ar 16000 -ac 1 -ab 32k -af volume=1.75 -f wav <출력>
으로 뽑는다. 이 인자로 뽑은 WAV 를 엔진에 넣으면 SE 실행 로그와 24구간이 글자·시간까지 같았다.
(HANDOFF 의 'aresample=async=1:first_pts=0, volume 없음' 으로 뽑으면 단어 하나·시간 몇십 ms 가 달라짐)
ffmpeg 버전(6.1 / 8.0)에 따라 WAV 바이트는 조금 다르지만 인식 결과는 같았다 → 엔진 배포본의 ffmpeg(6.1)를 쓴다.
"""
import os
import subprocess

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

SE_ARGS = ["-vn", "-ar", "16000", "-ac", "1", "-ab", "32k", "-af", "volume=1.75", "-f", "wav"]


def extract_wav(src, out_wav, ffmpeg):
    """src(영상·오디오) → out_wav. 실패하면 RuntimeError."""
    cmd = [ffmpeg, "-nostdin", "-y", "-v", "error", "-i", src, *SE_ARGS, out_wav]
    r = subprocess.run(cmd, capture_output=True, creationflags=NO_WINDOW)
    if r.returncode != 0 or not os.path.isfile(out_wav):
        msg = r.stderr.decode("utf-8", "replace").strip()[-400:]
        raise RuntimeError(f"오디오 추출 실패: {msg}")
    return out_wav
