import ctypes
import locale
import os
import sys

from . import APP_NAME, mong_webcheck, paths, shell_register


def _gui_check(media):
    """창을 띄우고 영상이 실제로 재생되는지 본다 (빌드 검증용). 설정은 임시 파일을 쓴다."""
    import tempfile

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication

    from .settings import Settings
    from .video import set_default_gl_format
    from .window import MainWindow

    set_default_gl_format()
    app = QApplication([])
    locale.setlocale(locale.LC_NUMERIC, "C")
    win = MainWindow(Settings(os.path.join(tempfile.mkdtemp(prefix="noad_self_"), "settings.json")))
    win.setAttribute(Qt.WA_ShowWithoutActivating)
    win.setGeometry(30, -1040, 960, 540)
    win.show()
    win.open_path(media)
    result = {}

    def look():
        p = win.player
        result["pos"], result["vo"] = p.time_pos or 0, p.current_vo
        win.close()
        app.quit()

    QTimer.singleShot(3000, look)
    app.exec()
    if result.get("pos", 0) < 0.5:
        raise RuntimeError(f"영상이 재생되지 않았습니다 (pos={result.get('pos')})")
    return f"gui 재생 pos={result.get('pos', 0):.1f} vo={result.get('vo')}"


def _selftest(out):
    lines = []
    try:
        paths.setup_dll_paths()
        import mpv
        import PySide6.QtOpenGLWidgets  # noqa: F401
        from PySide6.QtWidgets import QApplication  # noqa: F401

        from . import addons, window  # noqa: F401
        m = mpv.MPV()                                         # libmpv-2.dll 실제 로딩
        from . import VERSION
        lines.append(f"version {VERSION} shell {os.environ.get('NOAD_SHELL_API')}")
        lines.append(f"mpv {m.mpv_version}")
        m.terminate()
        for n in filter(None, os.environ.get("NOAD_SELFTEST_INSTALL", "").split(",")):    # 빌드 검증: 내려받기 시험
            addons.ensure(n.strip())
        if addons.present("stt"):                             # 받아 둔 경우에만 — 기본 설치에는 없다
            addons.activate("stt")
            import ctranslate2
            import onnxruntime

            from .stt import engine
            engine._import_whisper()
            lines.append(f"ctranslate2 {ctranslate2.__version__}, onnxruntime {onnxruntime.__version__}")
        if os.environ.get("NOAD_SELFTEST_MEDIA"):             # 창을 실제로 띄워 재생 확인 (2번 모니터, 포커스 안 가져감)
            lines.append(_gui_check(os.environ["NOAD_SELFTEST_MEDIA"]))
        import subprocess
        for exe, flag in ((paths.FFMPEG, "-version"), (paths.LLAMA_SERVER, "--version")):
            if os.path.isfile(exe):
                r = subprocess.run([exe, flag], capture_output=True, creationflags=0x08000000, timeout=60)
                lines.append(f"{os.path.basename(exe)} 종료코드 {r.returncode}")
        lines.append("addons " + ", ".join(f"{n}={addons.present(n)}" for n in addons.INFO))
        lines.append(f"icon {os.path.isfile(paths.ICON)}, shaders {os.path.isdir(os.path.join(paths.RESOURCES, 'shaders'))}")
        lines.append("OK")
    except Exception as e:
        lines.append(f"FAIL {type(e).__name__}: {e}")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return 0 if lines[-1] == "OK" else 1


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ("--register", "--unregister"):    # 탐색기 우클릭 메뉴 수동 등록·해제
        if argv[0] == "--register":
            shell_register.register(sys.executable)
        else:
            shell_register.unregister()
        return 0
    if argv and argv[0] == "--selftest":                      # 창 없이 구성요소 로딩만 확인 (빌드 검증용)
        return _selftest(argv[1] if len(argv) > 1 else "selftest.txt")
    shell_register.ensure_registered()                        # 설치본 첫 실행 때 자동 등록
    paths.setup_dll_paths()                                 # mpv import 전에
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{APP_NAME}.Player")

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from .settings import Settings
    from .video import set_default_gl_format
    from .window import MainWindow

    set_default_gl_format()
    app = QApplication([sys.argv[0]])
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(QIcon(paths.ICON))
    locale.setlocale(locale.LC_NUMERIC, "C")                  # libmpv 요구사항 (Qt 가 바꿔 놓음)

    win = MainWindow(Settings())
    mong_webcheck.start("mongplayer", "몽플레이어", [47131, 47132, 47133])   # 웹페이지 설치 확인용
    win.show()
    if argv:
        p = argv[0]
        win.open_path(os.path.abspath(p) if os.path.exists(p) else p)
    return app.exec()
