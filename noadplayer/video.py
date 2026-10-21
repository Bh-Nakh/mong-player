"""mpv 렌더 API(OpenGL)로 Qt 위젯에 영상을 그린다.

mpv 를 자식 창(wid)으로 끼우면 그 창이 마우스·키보드를 가로채 Qt 가 받지 못한다.
렌더 API 를 쓰면 입력과 화면 위 컨트롤을 모두 Qt 가 다룬다.
"""
import ctypes

import mpv
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QApplication

_opengl32 = ctypes.WinDLL("opengl32")
_opengl32.wglGetProcAddress.restype = ctypes.c_void_p
_opengl32.wglGetProcAddress.argtypes = [ctypes.c_char_p]
_kernel32 = ctypes.WinDLL("kernel32")
_kernel32.GetProcAddress.restype = ctypes.c_void_p
_kernel32.GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]


def set_default_gl_format():
    """QApplication 생성 전에 호출 — mpv 가 쓰는 텍스처 형식을 지원하는 OpenGL 3.3 Core 컨텍스트."""
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setSwapInterval(1)
    QSurfaceFormat.setDefaultFormat(fmt)


def _get_proc_address(_ctx, name):
    # wglGetProcAddress 는 GL 1.1 함수에 대해 NULL(또는 1~3, -1)을 돌려준다 → opengl32.dll 에서 직접 찾는다
    addr = _opengl32.wglGetProcAddress(name)
    if addr in (None, 0, 1, 2, 3, ctypes.c_void_p(-1).value):
        addr = _kernel32.GetProcAddress(_opengl32._handle, name)
    return addr or 0


class VideoWidget(QOpenGLWidget):
    frame_ready = Signal()
    clicked = Signal()                 # 제자리 클릭 (놓는 즉시 — 더블클릭이면 이어서 double_clicked 가 온다)
    double_clicked = Signal()
    wheel = Signal(int)                # +1 위 / -1 아래
    mouse_moved = Signal(QPoint)
    resized = Signal()
    context_menu = Signal(QPoint)      # 화면 좌표
    files_dropped = Signal(list)
    drag_started = Signal()            # 누른 채로 끌기 시작 → 창 이동

    def __init__(self, player: mpv.MPV, parent=None):
        super().__init__(parent)
        self.player = player
        self.ctx = None
        self._proc = mpv.MpvGlGetProcAddressFn(_get_proc_address)
        self.frame_ready.connect(self.update, Qt.QueuedConnection)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAcceptDrops(True)
        self._press = None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._press is not None:
            self._press = None
            self.clicked.emit()
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press = None
            self.double_clicked.emit()

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        if self._press is not None and e.buttons() & Qt.LeftButton \
                and (pos - self._press).manhattanLength() >= QApplication.startDragDistance():
            self._press = None                 # 끌기였으니 클릭(일시정지)으로 치지 않는다
            self.drag_started.emit()
        self.mouse_moved.emit(pos)
        super().mouseMoveEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.resized.emit()

    def wheelEvent(self, e):
        d = e.angleDelta().y()
        if d:
            self.wheel.emit(1 if d > 0 else -1)

    def contextMenuEvent(self, e):
        self.context_menu.emit(e.globalPos())

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        files = [u.toLocalFile() or u.toString() for u in e.mimeData().urls()]
        if files:
            self.files_dropped.emit(files)

    def initializeGL(self):
        self.ctx = mpv.MpvRenderContext(self.player, "opengl",
                                        opengl_init_params={"get_proc_address": self._proc})
        self.ctx.update_cb = self.frame_ready.emit          # mpv 스레드에서 불림 → 시그널로 넘김

    def paintGL(self):
        if not self.ctx:
            return
        r = self.devicePixelRatioF()
        self.ctx.render(flip_y=True, opengl_fbo={"w": int(self.width() * r), "h": int(self.height() * r),
                                                 "fbo": self.defaultFramebufferObject()})

    def release(self):
        """종료 전에 GL 컨텍스트 안에서 렌더 컨텍스트를 푼다 (안 하면 mpv 종료가 멈출 수 있음)."""
        if self.ctx:
            self.makeCurrent()
            self.ctx.update_cb = None
            self.ctx.free()
            self.ctx = None
            self.doneCurrent()
