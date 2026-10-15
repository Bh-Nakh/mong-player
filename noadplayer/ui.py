"""화면 부품: 클릭하면 그 위치로 가는 슬라이더, 직접 그린 밝은 아이콘, 영상 위 동작 표시."""
import time

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QSlider, QStyle, QToolTip, QWidget

# ───────────────────────── 아이콘 ─────────────────────────
_BASE = 64          # 좌표계 (0~64)
_SCALE = 1.5        # 96px 로 그려 두면 축소 표시가 또렷하다


def _poly(*pts):
    return QPolygonF([QPointF(x, y) for x, y in pts])


def _paint_icon(name, color):
    px = QPixmap(int(_BASE * _SCALE), int(_BASE * _SCALE))
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(_SCALE, _SCALE)
    c = QColor(color)
    p.setPen(Qt.NoPen)
    p.setBrush(c)
    stroke = QPen(c, 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    if name == "play":
        p.drawPolygon(_poly((18, 10), (18, 54), (54, 32)))
    elif name == "pause":
        p.drawRoundedRect(QRectF(15, 11, 13, 42), 3, 3)
        p.drawRoundedRect(QRectF(36, 11, 13, 42), 3, 3)
    elif name == "stop":
        p.drawRoundedRect(QRectF(14, 14, 36, 36), 4, 4)
    elif name in ("prev", "next"):
        if name == "prev":
            p.drawRoundedRect(QRectF(9, 12, 7, 40), 2, 2)
            p.drawPolygon(_poly((54, 12), (54, 52), (20, 32)))
        else:
            p.drawRoundedRect(QRectF(48, 12, 7, 40), 2, 2)
            p.drawPolygon(_poly((10, 12), (10, 52), (44, 32)))
    elif name == "back":
        p.drawPolygon(_poly((31, 14), (31, 50), (6, 32)))
        p.drawPolygon(_poly((58, 14), (58, 50), (33, 32)))
    elif name == "forward":
        p.drawPolygon(_poly((33, 14), (33, 50), (58, 32)))
        p.drawPolygon(_poly((6, 14), (6, 50), (31, 32)))
    elif name in ("volume", "muted"):
        p.drawPolygon(_poly((6, 24), (18, 24), (32, 11), (32, 53), (18, 40), (6, 40)))
        p.setBrush(Qt.NoBrush)
        p.setPen(stroke)
        if name == "volume":
            for r in (10, 19):
                p.drawArc(QRectF(32 - r, 32 - r, 2 * r, 2 * r), -45 * 16, 90 * 16)
        else:
            p.drawLine(QPointF(42, 24), QPointF(58, 40))
            p.drawLine(QPointF(58, 24), QPointF(42, 40))
    elif name == "list":
        p.setPen(stroke)
        for y in (16, 32, 48):
            p.drawPoint(QPointF(10, y))
            p.drawLine(QPointF(22, y), QPointF(56, y))
    elif name == "fullscreen":
        p.setBrush(Qt.NoBrush)
        p.setPen(stroke)
        for (cx, cy, dx, dy) in ((10, 10, 1, 1), (54, 10, -1, 1), (10, 54, 1, -1), (54, 54, -1, -1)):
            path = QPainterPath(QPointF(cx + dx * 14, cy))
            path.lineTo(cx, cy)
            path.lineTo(cx, cy + dy * 14)
            p.drawPath(path)
    p.end()
    return px


_icon_cache = {}


def icon(name, color="#f2f2f7"):
    key = (name, color)
    if key not in _icon_cache:
        _icon_cache[key] = QIcon(_paint_icon(name, color))
    return _icon_cache[key]


# ───────────────────────── 슬라이더 ─────────────────────────
SLIDER_CSS = """
QSlider::groove:horizontal {{ height: {g}px; background: #5a5a68; border-radius: {r}px; }}
QSlider::sub-page:horizontal {{ background: #8a7dff; border-radius: {r}px; }}
QSlider::handle:horizontal {{ width: {h}px; height: {h}px; margin: -{m}px 0; border-radius: {hr}px;
                              background: #ffffff; }}
QSlider::handle:horizontal:hover {{ background: #e2deff; }}
"""


class JumpSlider(QSlider):
    """빈 곳을 클릭하면 그 위치로 바로 값이 적용되고, 그대로 끌 수도 있는 가로 슬라이더 (공통 규칙)."""

    def __init__(self, groove, handle):
        super().__init__(Qt.Horizontal)
        self._hw = handle
        self._in_press = False                 # 누르는 순간의 점프는 '끌기'로 치지 않는다
        self.setFocusPolicy(Qt.NoFocus)
        self.setStyleSheet(SLIDER_CSS.format(g=groove, r=groove // 2, h=handle, hr=handle // 2,
                                             m=(handle - groove) // 2))

    def value_at(self, x):
        """마우스 x 좌표 → 값 (손잡이 중앙이 마우스 아래에 오도록)."""
        span = max(1, self.width() - self._hw)
        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), int(x - self._hw / 2), span)

    def pos_of(self, value):
        span = max(1, self.width() - self._hw)
        return self._hw / 2 + QStyle.sliderPositionFromValue(self.minimum(), self.maximum(), int(value), span)

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            e.ignore()
            return
        self._in_press = True
        self.setSliderPosition(self.value_at(e.position().x()))      # 먼저 위치를 옮긴 뒤 눌림 신호를 보낸다
        self.setSliderDown(True)
        self._in_press = False
        e.accept()

    def mouseMoveEvent(self, e):
        if self.isSliderDown():
            self.setSliderPosition(self.value_at(e.position().x()))
            e.accept()
        else:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.isSliderDown():
            self.setSliderDown(False)
            e.accept()
        else:
            super().mouseReleaseEvent(e)


def fmt_time(sec):
    sec = int(max(0, sec or 0))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class SeekSlider(JumpSlider):
    """재생 막대 (값 단위: 밀리초). 클릭하면 정확히 한 번만 그 위치로 이동하고,
    끄는 동안은 가벼운 키프레임 이동, 놓을 때 정확한 위치로 한 번 더 맞춘다."""
    THROTTLE_MS = 60
    HOLD_S = 0.35                              # 이동 직후 낡은 재생 위치로 되돌아가 보이지 않게

    def __init__(self, on_seek):
        super().__init__(4, 10)
        self.on_seek = on_seek
        self.dragging = False
        self.hold_until = 0.0
        self.markers = (None, None)            # 구간 A·B (초)
        self._press_value = 0
        self._moved = False
        self._pending = None
        self._tt = QTimer(self, singleShot=True, interval=self.THROTTLE_MS)
        self._tt.timeout.connect(self._flush)
        self.setMouseTracking(True)
        self.setFixedHeight(18)
        self.sliderPressed.connect(self._pressed)
        self.sliderMoved.connect(self._drag)
        self.sliderReleased.connect(self._released)

    def _hold(self):
        self.hold_until = time.monotonic() + self.HOLD_S

    def _pressed(self):
        self.dragging = True
        self._moved = False
        self._press_value = self.sliderPosition()
        self._hold()
        self.on_seek(self.sliderPosition() / 1000)              # 클릭 = 정확한 이동 1회

    def _drag(self, v):
        if self._in_press:
            return
        self._moved = True
        self._pending = v
        if not self._tt.isActive():
            self._flush()

    def _flush(self):
        if self._pending is None:
            return
        v, self._pending = self._pending, None
        self.on_seek(v / 1000, exact=False)
        self._tt.start()

    def _released(self):
        self._tt.stop()
        self._pending = None
        self.dragging = False
        self._hold()
        if self._moved:                                         # 끌었을 때만 최종 위치로 맞춤
            self.on_seek(self.sliderPosition() / 1000)

    def mouseMoveEvent(self, e):
        super().mouseMoveEvent(e)
        if self.maximum() > 0:
            QToolTip.showText(e.globalPosition().toPoint(), fmt_time(self.value_at(e.position().x()) / 1000), self)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.maximum() <= 0 or self.markers == (None, None):
            return
        p = QPainter(self)
        p.setPen(QColor("#f0b030"))
        p.setBrush(QColor("#f0b030"))
        for label, sec in zip("AB", self.markers):
            if sec is not None:
                x = int(self.pos_of(sec * 1000))
                p.drawRect(x - 1, 2, 2, self.height() - 4)
                p.drawText(x + 3, 11, label)
        p.end()


# ───────────────────────── 조작부 ─────────────────────────
class ControlBar(QWidget):
    """아래 조작부. 좁아지면 꼭 필요한 부분(재생·정지·이전·다음·시간·목록 / 재생 막대·소리)만 남기고,
    넓을 때만 보이는 부분(전체화면 버튼 등)은 숨긴다. 최소 폭은 꼭 필요한 부분에서 정해진다."""
    OPTIONAL_MIN_W = 400

    def __init__(self, margins=(8, 4, 8, 4), spacing=2):
        super().__init__()
        self.margins, self.spacing = margins, spacing
        self.row1, self.row2 = [], []          # 꼭 필요한 부분의 위젯들 (최소 폭 계산용)
        self.optional_changed = None           # 콜백(넓은지 여부)
        self._wide = None

    def _row_width(self, widgets, seek_min=0):
        w = seek_min + sum(x.sizeHint().width() for x in widgets)
        n = len(widgets) + (1 if seek_min else 0)
        return w + self.spacing * max(0, n - 1)

    def minimumSizeHint(self):
        lay = self.layout()
        w = max(self._row_width(self.row1, 60), self._row_width(self.row2)) + self.margins[0] + self.margins[2]
        return QSize(w, lay.sizeHint().height() if lay else 0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        wide = self.width() >= self.OPTIONAL_MIN_W
        if wide != self._wide:
            self._wide = wide
            if self.optional_changed:
                self.optional_changed(wide)


# ───────────────────────── 영상 위 동작 표시 ─────────────────────────
class ActionOverlay(QWidget):
    """재생·일시정지 같은 동작이 일어나면 영상 한가운데에 반투명 아이콘을 잠깐 보였다가 사라진다."""
    SIZE = 124

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.SIZE, self.SIZE)
        self._name, self._text, self._alpha = None, "", 0.0
        self._anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=900)
        self._anim.valueChanged.connect(self._tick)
        self._anim.finished.connect(self.hide)
        parent.installEventFilter(self)
        self.hide()

    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.Resize, QEvent.Show):
            self._center()
        return False

    def _center(self):
        p = self.parentWidget()
        self.move((p.width() - self.width()) // 2, (p.height() - self.height()) // 2)

    def flash(self, name, text=""):
        self._name, self._text = name, text
        self._center()
        self._alpha = 1.0
        self.show()
        self.raise_()
        self._anim.stop()
        self._anim.start()
        self.update()

    def cancel(self):
        self._anim.stop()
        self.hide()

    def _tick(self, t):
        self._alpha = 1.0 if t < 0.3 else max(0.0, (1.0 - t) / 0.7)
        self.update()

    def paintEvent(self, e):
        if not self._name:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setOpacity(self._alpha * 0.62)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0))
        p.drawEllipse(self.rect())
        p.setOpacity(self._alpha * 0.92)
        side = 50
        top = 26 if self._text else (self.height() - side) // 2
        icon(self._name, "#ffffff").paint(p, (self.width() - side) // 2, top, side, side)
        if self._text:
            f = QFont(self.font())
            f.setPixelSize(15)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor("#ffffff"))
            p.drawText(QRectF(0, top + side + 2, self.width(), 24), Qt.AlignHCenter | Qt.AlignTop, self._text)
        p.end()
