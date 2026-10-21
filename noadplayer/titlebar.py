"""팟플레이어식 제목 표시줄 — 메뉴 막대 없이 [앱 아이콘 몽플레이어 ▾](주 메뉴) · 제목 · [항상 위][_][□][X].

창 테두리는 Windows 의 것을 쓰지 않고 직접 그리지만, 창 스타일(WS_THICKFRAME·WS_CAPTION)은 남겨 두고
WM_NCCALCSIZE / WM_NCHITTEST 만 가로챈다 → 가장자리 크기 조절, 끌어서 화면 가장자리에 붙이기(Aero Snap),
제목 더블클릭 최대화, 최소화·최대화 애니메이션을 Windows 가 그대로 처리한다.
"""
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QCursor, QFont, QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QToolButton, QWidget

HEIGHT = 30
EDGE = 6                                   # 크기 조절로 잡히는 가장자리 폭 (논리 px)
GLYPH = {"pin": "", "pinned": "", "min": "", "max": "", "restore": "", "close": ""}

WM_NCCALCSIZE, WM_NCHITTEST = 0x0083, 0x0084
HTCLIENT, HTCAPTION = 1, 2
HTLEFT, HTRIGHT, HTTOP, HTTOPLEFT, HTTOPRIGHT, HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT = 10, 11, 12, 13, 14, 15, 16, 17
GWL_STYLE = -16
WS_CAPTION, WS_THICKFRAME, WS_MINIMIZEBOX, WS_MAXIMIZEBOX, WS_SYSMENU = 0xC00000, 0x40000, 0x20000, 0x10000, 0x80000
SWP_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020          # NOSIZE NOMOVE NOZORDER NOACTIVATE FRAMECHANGED
HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
SM_CXSIZEFRAME, SM_CYSIZEFRAME, SM_CXPADDEDBORDER = 32, 33, 92

user32 = ctypes.windll.user32
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                ctypes.c_uint]
user32.IsZoomed.argtypes = [wintypes.HWND]


class NCCALCSIZE_PARAMS(ctypes.Structure):
    _fields_ = [("rgrc", wintypes.RECT * 3), ("lppos", ctypes.c_void_p)]


def _frame(hwnd):
    """최대화하면 Windows 가 창을 화면보다 테두리 두께만큼 크게 잡으므로 그만큼 안쪽으로 줄인다 (물리 px)."""
    try:
        dpi = user32.GetDpiForWindow(hwnd)
        m = lambda i: user32.GetSystemMetricsForDpi(i, dpi)  # noqa: E731
    except AttributeError:
        m = user32.GetSystemMetrics
    pad = m(SM_CXPADDEDBORDER)
    return m(SM_CXSIZEFRAME) + pad, m(SM_CYSIZEFRAME) + pad


def enable_native_frame(win):
    """FramelessWindowHint 로 지워진 크기 조절·최대화 스타일을 되돌린다 (그리는 건 여전히 우리가)."""
    hwnd = int(win.winId())
    style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
    user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style | WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)
    user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, SWP_FLAGS)


def refresh_frame(win):
    """창 크기는 그대로 두고 WM_NCCALCSIZE 를 다시 받아 안쪽 영역을 새로 계산하게 한다."""
    user32.SetWindowPos(int(win.winId()), None, 0, 0, 0, 0, SWP_FLAGS)


def set_topmost(win, on):
    """항상 위 — Qt 창 플래그를 바꾸면 창을 새로 만들어 영상 출력이 끊기므로 Win32 로 직접."""
    user32.SetWindowPos(int(win.winId()), HWND_TOPMOST if on else HWND_NOTOPMOST, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)


def native_event(win, titlebar, message):
    """MainWindow.nativeEvent 에서 부른다. 처리했으면 (True, 결과), 아니면 None."""
    msg = wintypes.MSG.from_address(int(message))
    if msg.message == WM_NCCALCSIZE and msg.wParam:
        # 전체화면은 Qt 가 최대화 스타일을 떼므로 IsZoomed 만 본다. isFullScreen() 은 전체화면을 빠져나오는 도중에
        # 아직 참이라, 그 순간 계산된 안쪽 영역이 테두리만큼 줄지 않은 채 남아 내용이 밀리고 클릭이 어긋났다.
        if user32.IsZoomed(msg.hWnd):
            fx, fy = _frame(msg.hWnd)
            r = NCCALCSIZE_PARAMS.from_address(msg.lParam).rgrc[0]
            r.left += fx
            r.top += fy
            r.right -= fx
            r.bottom -= fy
        return True, 0                                   # 창 전체를 우리 영역으로 (Windows 테두리·제목 없음)
    if msg.message == WM_NCHITTEST:
        if win.isFullScreen():
            return True, HTCLIENT
        p = win.mapFromGlobal(QCursor.pos())
        x, y, w, h = p.x(), p.y(), win.width(), win.height()
        if not win.isMaximized():
            left, right, top, bottom = x < EDGE, x >= w - EDGE, y < EDGE, y >= h - EDGE
            hit = {(True, False, True, False): HTTOPLEFT, (False, True, True, False): HTTOPRIGHT,
                   (True, False, False, True): HTBOTTOMLEFT, (False, True, False, True): HTBOTTOMRIGHT,
                   (True, False, False, False): HTLEFT, (False, True, False, False): HTRIGHT,
                   (False, False, True, False): HTTOP, (False, False, False, True): HTBOTTOM}.get((left, right, top, bottom))
            if hit:
                return True, hit
        if titlebar.isVisible() and titlebar.is_caption(titlebar.mapFromGlobal(QCursor.pos())):
            return True, HTCAPTION                       # 끌기·더블클릭 최대화·화면 가장자리에 붙이기는 Windows 가
        return True, HTCLIENT                            # 버튼·영상 등은 Qt 가 그대로 받는다
    return None


class TitleBar(QWidget):
    pin_toggled = Signal(bool)

    def __init__(self, win, menu, app_name, pinned=False):
        super().__init__(win)
        self.win = win
        self.setObjectName("titlebar")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setFixedHeight(HEIGHT)
        self.menu_btn = QToolButton(self)
        self.menu_btn.setObjectName("appMenu")
        self.menu_btn.setIcon(win.windowIcon())
        self.menu_btn.setIconSize(QSize(16, 16))
        self.menu_btn.setText(f"{app_name} ▾")
        self.menu_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.menu_btn.setToolTip("주 메뉴")
        self.menu_btn.setFocusPolicy(Qt.NoFocus)
        self.menu_btn.clicked.connect(lambda: menu.exec(self.menu_btn.mapToGlobal(QPoint(0, self.menu_btn.height()))))
        self.title = QLabel(app_name, self)
        self.title.setObjectName("title")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.title.setAttribute(Qt.WA_TransparentForMouseEvents)
        glyph = QFont("Segoe MDL2 Assets", 8)
        self.buttons = {}
        for key, tip, slot in (("pin", "항상 위", self._toggle_pin), ("min", "최소화", win.showMinimized),
                               ("max", "최대화", self._toggle_max), ("close", "닫기", win.close)):
            b = QToolButton(self)
            b.setObjectName("wb_" + key)
            b.setFont(glyph)
            b.setText(GLYPH[key])
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.NoFocus)
            b.setFixedSize(40 if key != "pin" else 34, HEIGHT)
            b.clicked.connect(slot)
            self.buttons[key] = b
        self.buttons["pin"].setCheckable(True)
        self.buttons["pin"].setChecked(pinned)
        self._sync_pin()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.menu_btn)
        lay.addWidget(self.title, 1)
        for b in self.buttons.values():
            lay.addWidget(b)
        win.windowTitleChanged.connect(self.title.setText)
        self.title.setText(win.windowTitle())

    def is_caption(self, p):
        """끌어서 창을 옮길 수 있는 곳 = 버튼이 아닌 빈 곳과 제목 글씨."""
        if not self.rect().contains(p):
            return False
        child = self.childAt(p)
        return child is None or child is self.title

    def _toggle_max(self):
        self.win.showNormal() if self.win.isMaximized() else self.win.showMaximized()

    def _toggle_pin(self, on):
        self._sync_pin()
        self.pin_toggled.emit(on)

    def _sync_pin(self):
        on = self.buttons["pin"].isChecked()
        self.buttons["pin"].setText(GLYPH["pinned" if on else "pin"])
        self.buttons["pin"].setToolTip("항상 위 (켜짐)" if on else "항상 위")

    def sync_state(self):
        """최대화 여부에 맞춰 □ / ❐ 모양을 바꾼다."""
        mx = self.win.isMaximized()
        self.buttons["max"].setText(GLYPH["restore" if mx else "max"])
        self.buttons["max"].setToolTip("이전 크기로" if mx else "최대화")

    def set_active(self, active):
        self.title.setProperty("inactive", not active)
        self.title.style().unpolish(self.title)
        self.title.style().polish(self.title)

    def mouseDoubleClickEvent(self, e):                  # (Windows 가 HTCAPTION 으로 처리하지 못한 경우 대비)
        if self.is_caption(e.position().toPoint()):
            self._toggle_max()


STYLE = (
    " #titlebar{background:#2b2b33; border-bottom:1px solid #45454f}"
    " #titlebar #title{color:#ececf2; font-size:9pt} #titlebar #title[inactive=\"true\"]{color:#8a8a96}"
    " #titlebar QToolButton{background:transparent; color:#dcdce4; border:none}"
    " #titlebar QToolButton:hover{background:#4a4a58}"
    " #titlebar QToolButton:pressed{background:#3a3a46}"
    " #titlebar #appMenu{padding:2px 8px 2px 6px; margin:3px 0; border-radius:3px; font-weight:bold; color:#ececf2}"
    " #titlebar #appMenu::menu-indicator{image:none; width:0}"
    " #titlebar #wb_pin:checked{color:#a79eff}"
    " #titlebar #wb_close:hover{background:#e81123; color:white}"
    " #titlebar #wb_close:pressed{background:#a50e1a}"
)
