"""자동 시험 — 입력 흉내 없이 기능을 직접 호출. 창은 2번 모니터에 포커스 없이 띄우고, 설정·결과물은 임시 폴더만 쓴다.

    .venv\\Scripts\\python.exe tools\\smoke_test.py <동영상> <결과 폴더> [--stt] [--translate]
"""
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from noadplayer import paths  # noqa: E402

paths.setup_dll_paths()
import ctypes  # noqa: E402
import locale  # noqa: E402

from PIL import ImageGrab  # noqa: E402
from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from noadplayer import capture, dialogs, filters  # noqa: E402
from noadplayer.settings import Settings  # noqa: E402
from noadplayer.stt import gpu as stt_gpu  # noqa: E402
from noadplayer.video import set_default_gl_format  # noqa: E402
from noadplayer.window import MainWindow  # noqa: E402

SRC, OUT = sys.argv[1], os.path.abspath(sys.argv[2])
WITH_STT = "--stt" in sys.argv
WITH_TRANSLATE = "--translate" in sys.argv
os.makedirs(OUT, exist_ok=True)
MEDIA = os.path.join(OUT, "media" + os.path.splitext(SRC)[1])
shutil.copy2(SRC, MEDIA)
capture.user_dir = lambda kind: OUT                         # 실제 사진·동영상 폴더 대신

SMI = os.path.join(OUT, "media.smi")
with open(SMI, "w", encoding="cp949") as f:                 # 한국 SMI 는 보통 CP949
    f.write("<SAMI><HEAD><STYLE TYPE='text/css'><!-- .KRCC {Name:Korean; lang:ko-KR;} --></STYLE></HEAD><BODY>\n"
            "<SYNC Start=0><P Class=KRCC>시험 자막 첫 줄입니다\n"
            "<SYNC Start=30000><P Class=KRCC>&nbsp;\n</BODY></SAMI>\n")

set_default_gl_format()
app = QApplication([])
locale.setlocale(locale.LC_NUMERIC, "C")
win = MainWindow(Settings(os.path.join(OUT, "settings.json")))
win.setAttribute(Qt.WA_ShowWithoutActivating)
win.setGeometry(30, -1040, 1200, 640)
win.show()
p = win.player
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("OK   " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""), flush=True)


def shot(name):
    """실제 화면에서 창 영역을 캡처 (QWidget.grab 은 OpenGL 영상을 깨뜨려 찍는다)."""
    u = ctypes.windll.user32
    vx, vy = u.GetSystemMetrics(76), u.GetSystemMetrics(77)          # 가상 화면 왼쪽 위
    g = win.frameGeometry()
    x, y = g.x() - vx, g.y() - vy
    ImageGrab.grab(all_screens=True).crop((x, y, x + g.width(), y + g.height())).save(os.path.join(OUT, name))


def steps():
    win.open_path(MEDIA)
    yield 2500
    check("재생", (p.time_pos or 0) > 0.5, f"pos={p.time_pos:.1f} hwdec={p.hwdec_current} vo={p.current_vo}")
    shot("1_play.png")

    win.apply_filters(filters.Filters(sharpen=6, denoise=2, saturation=40, brightness=10))
    yield 2000
    check("화질 필터 (GPU 디코딩 유지)", len(p.glsl_shaders) == 2 and p.saturation == 40
          and "copy" not in str(p.hwdec_current),
          f"hwdec={p.hwdec_current} shaders={[os.path.basename(s) for s in p.glsl_shaders]} opts={p.glsl_shader_opts}")
    shot("2_filters.png")
    win.apply_filters(filters.Filters(blur=6, hflip=True))
    yield 1500
    shot("2b_blur_flip.png")
    win.reset_filters()
    yield 1000
    check("필터 끄기", not p.glsl_shaders and "copy" not in str(p.hwdec_current), f"hwdec={p.hwdec_current}")

    win.add_subtitle(SMI)
    yield 800
    win.seek_to(1.0)
    yield 1200
    check("SMI(CP949) 자막", p.sub_text == "시험 자막 첫 줄입니다", repr(p.sub_text))
    shot("3_smi.png")

    out = capture.screenshot(p, True)
    yield 1000
    check("스크린샷", os.path.isfile(out) and os.path.getsize(out) > 10000, out)

    win.seek_to(2.0)
    yield 600
    win.set_ab(0)
    win.seek_to(7.0)
    yield 600
    win.set_ab(1)
    before = set(os.listdir(OUT))
    win.save_clip("video")
    win.save_clip("audio")
    for _ in range(60):
        if not win.workers:
            break
        yield 250
    new = sorted(set(os.listdir(OUT)) - before)
    check("구간 영상·소리 저장", any(n.endswith((".mp4", ".mkv")) for n in new) and any(n.endswith(".mp3") for n in new),
          ", ".join(new))

    win.vol.setValue(150)
    yield 300
    check("볼륨 200% 범위·수치 표시", p.volume == 150 and win.vol_label.text() == "150%" and win.vol.maximum() == 200,
          f"volume={p.volume} label={win.vol_label.text()} max={p.volume_max}")
    win.vol.setValue(80)

    clip = os.path.join(OUT, next(n for n in new if n.endswith(".mp4")))
    win.set_playlist([MEDIA, clip], MEDIA)
    yield 1200
    check("재생 목록 표시", win.pl_panel.list.count() == 2 and win.dock.isVisible(),
          f"항목 {win.pl_panel.list.count()}개, 보임={win.dock.isVisible()}")
    win.seek_to((p.duration or 0) - 1.0)
    for _ in range(20):
        yield 250
        if p.path and os.path.normcase(p.path) == os.path.normcase(clip):
            break
    check("끝나면 다음 파일 자동 재생", p.path and os.path.normcase(p.path) == os.path.normcase(clip),
          f"현재={os.path.basename(p.path or '')} index={win.pl_index}")
    yield 1000
    shot("5_playlist.png")
    win.play_index(0)
    yield 1000

    if WITH_STT:
        dlg = dialogs.SttDialog(MEDIA, "ko", False, win)
        dlg.setAttribute(Qt.WA_ShowWithoutActivating)
        dlg.move(1000, -1040)
        dlg.show()
        dlg.start()
        t = time.time()
        while dlg.isVisible() and time.time() - t < 900:
            yield 500
        r = dlg.result
        check("AI 자막 생성", r and r["segments"], f"{len(r['segments']) if r else 0}줄 device={r and r['device']} "
              f"{time.time() - t:.0f}초 (GPU 구성요소 설치={stt_gpu.installed()})")
        if r:
            path = win.sub_out_path(MEDIA, ".AI.srt")
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write(r["srt"])
            win.add_subtitle(path, "AI 자막")
            win.seek_to(r["segments"][0]["start"] + 0.3)
            yield 1500
            check("AI 자막 표시", bool(p.sub_text), repr(p.sub_text))
            shot("4_ai_sub.png")

    if WITH_TRANSLATE:
        yield from translate_steps()

    win.close()


EN_LINES = ["Where were you last night?", "I was at the office.\nWorking late again.",
            "You promised you'd be home by eight.", "I know, I'm sorry.", "The client called at the last minute.",
            "It's always the client.", "Do you even remember what day it was?",
            "Of course I do. It was our anniversary.", "Then why didn't you call?", "My phone died. I swear.",
            "Let's not do this right now.", "The kids are asleep.", "Fine. But we're talking about this tomorrow.",
            "Okay. Tomorrow.", "Good night, Sarah.", "Good night."]


def write_en_srt(path):
    with open(path, "w", encoding="utf-8") as f:
        for i, t in enumerate(EN_LINES):
            f.write(f"{i + 1}\n00:00:{i * 3:02d},000 --> 00:00:{i * 3 + 2:02d},500\n<i>{t}</i>\n\n")


def run_translate_dialog(src, media):
    out = win.sub_out_path(media, ".ko.srt")
    dlg = dialogs.TranslateDialog(src, out, win.settings, win)
    dlg.setAttribute(Qt.WA_ShowWithoutActivating)
    dlg.move(1000, -1040)
    dlg.show()
    dlg.start()
    t = time.time()
    while dlg.isVisible() and time.time() - t < 900:
        yield 500
    return out, dlg.count, time.time() - t


def translate_steps():
    import subprocess

    from noadplayer import secret, translate
    from noadplayer.stt.srt import parse_srt
    from noadplayer.translate import source

    tok = secret.protect("test-key-123:fx")
    check("API 키 암호화·복원", tok and "test-key" not in tok and secret.unprotect(tok) == "test-key-123:fx")

    try:
        translate.translate_subtitle({"kind": "external", "path": SMI}, os.path.join(OUT, "x.srt"),
                                     translate.make_engine("local", win.settings), paths.FFMPEG)
        check("이미 한국어인 SMI(CP949) 건너뜀", False, "번역해 버림")
    except translate.AlreadyKorean:
        check("이미 한국어인 SMI(CP949) 건너뜀", True)

    # ① 외부 영어 SRT (서식 태그 포함)
    en = os.path.join(OUT, "media.en.srt")
    write_en_srt(en)
    win.play_index(0)
    yield 1500
    win.add_subtitle(en)
    yield 800
    src = source.selected_track(p)
    out, n, sec = yield from run_translate_dialog(src, MEDIA)
    ko = parse_srt(out) if os.path.isfile(out) else []
    check("외부 SRT 번역", n == len(EN_LINES) and len(ko) == n and source.hangul_ratio(ko) > 0.8,
          f"{n}줄 {sec:.0f}초 첫 줄='{ko[0].text if ko else ''}'")
    win.add_subtitle(out, "한국어 번역")
    win.seek_to(3.5)
    yield 1500
    check("번역 자막 표시", any("가" <= ch <= "힣" for ch in (p.sub_text or "")), repr(p.sub_text))
    shot("6_translated.png")

    # ② MKV 내장 영어 자막
    mkv = os.path.join(OUT, "embedded.mkv")
    subprocess.run([paths.FFMPEG, "-nostdin", "-y", "-v", "error", "-i", MEDIA, "-i", en, "-map", "0:v", "-map", "0:a",
                    "-map", "1:0", "-c", "copy", "-c:s", "srt", "-metadata:s:s:0", "language=eng", mkv], check=True)
    win.open_path(mkv)
    yield 2000
    sub = next((t for t in p.track_list if t["type"] == "sub" and not t.get("external")), None)
    p.sid = sub["id"] if sub else "no"
    yield 500
    src = source.selected_track(p)
    out, n, sec = yield from run_translate_dialog(src, mkv)
    ko = parse_srt(out) if os.path.isfile(out) else []
    check("MKV 내장 자막 번역", src and src["kind"] == "embedded" and len(ko) == len(EN_LINES)
          and source.hangul_ratio(ko) > 0.8, f"{len(ko)}줄 {sec:.0f}초")
    yield 500
    left = subprocess.run(["tasklist", "/FI", "IMAGENAME eq llama-server.exe"], capture_output=True, text=True).stdout
    check("번역 엔진 정리됨", "llama-server.exe" not in left)


gen = steps()


def advance():
    try:
        QTimer.singleShot(next(gen), advance)
    except StopIteration:
        app.quit()


QTimer.singleShot(500, advance)
app.exec()
fails = [n for n, ok, _ in results if not ok]
print("결과:", "모두 통과" if not fails else "실패 " + ", ".join(fails))
sys.exit(1 if fails else 0)
