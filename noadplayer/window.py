import os
import re
import sys
import tempfile
import time

import mpv
from PySide6.QtCore import QByteArray, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (QCheckBox, QDockWidget, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMenu,
                               QMessageBox, QSizePolicy, QStyle, QToolButton, QVBoxLayout, QWidget)

from . import APP_NAME_KO, VERSION, addons, capture, dialogs, filters, mong_update
from .paths import DATA, ICON, user_dir
from .playlist import PlaylistPanel
from .translate import source as translate_source
from .settings import Settings
from .ui import ActionOverlay, ControlBar, JumpSlider, SeekSlider, fmt_time, icon
from .video import VideoWidget
from .worker import Worker

VIDEO_EXT = ("mp4 mkv avi mov wmv flv webm m4v ts m2ts mts mpg mpeg vob 3gp ogv rm rmvb asf divx f4v")
AUDIO_EXT = ("mp3 flac wav m4a aac ogg opus wma ape alac")
SUB_EXT = ("smi srt ass ssa sub idx vtt sup")
MEDIA_SET = {"." + e for e in (VIDEO_EXT + " " + AUDIO_EXT).split()}
SUB_SET = {"." + e for e in SUB_EXT.split()}
VOLUME_MAX = 200                 # 100% 를 넘으면 소프트웨어로 증폭 (큰 소리는 찌그러질 수 있음)


def is_url(path):
    return bool(re.match(r"^[a-z][a-z0-9+.-]*://", path, re.I))


def sort_media(paths, mode):
    """이름순(자연 정렬) 또는 날짜순(수정 시각). mode 끝에 _desc 가 붙으면 내림차순(날짜는 최근 것부터)."""
    def mtime(p):
        try:
            return os.path.getmtime(p)
        except OSError:
            return float("inf")
    desc = mode.endswith("_desc")
    if mode.startswith("date"):
        return sorted(paths, key=lambda p: (mtime(p), _natural_key(os.path.basename(p))), reverse=desc)
    return sorted(paths, key=lambda p: _natural_key(os.path.basename(p)), reverse=desc)


def move_to_trash(path):
    """파일을 휴지통으로 보낸다 (되돌릴 수 있게). 성공하면 True."""
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]

    FO_DELETE, FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI = 3, 0x4, 0x10, 0x40, 0x400
    op = SHFILEOPSTRUCTW(None, FO_DELETE, os.path.abspath(path) + "\0", None,
                         FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI, False, None, None)
    return ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) == 0 and not op.fAnyOperationsAborted


def folder_media(path, mode="name"):
    folder = os.path.dirname(path)
    try:
        names = [f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in MEDIA_SET]
    except OSError:
        return [path]
    files = sort_media([os.path.join(folder, f) for f in names], mode)
    return files if any(os.path.normcase(f) == os.path.normcase(path) for f in files) else [path]


def _natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.filters = filters.Filters()
        self.ab = [None, None]
        self.workers = set()
        self._path = None
        self._was_maximized = False
        self._fs_dock_visible = False
        self._eof_handled = False
        self._last_sec = -1
        self._res_pos = self._res_dur = 0.0       # 이어 보기용 마지막 위치·길이
        self._res_saved = time.monotonic()
        self._dock_w = int(settings.get("playlist_width", 260))   # 재생 목록 폭 — 열고 닫을 때 창을 이만큼 늘리고 줄인다
        self._dock_lock = False                                    # 전체화면 오갈 때는 창 크기를 건드리지 않게
        self.seek_actions = {}
        self._ui_state = {}
        self.filter_dlg = None
        self.sub_dlg = None
        self.playlist = []                     # 재생 목록 (경로·주소)
        self.pl_index = -1

        self.setWindowTitle(APP_NAME_KO)
        self.setWindowIcon(QIcon(ICON))
        self.resize(1100, 680)
        self.player = mpv.MPV(
            vo="libmpv", hwdec="auto-safe", keep_open="yes", idle="yes", osc=False, ytdl=False,
            input_default_bindings=False, input_vo_keyboard=False, sub_auto="fuzzy", sub_codepage="auto",
            screenshot_format="png", osd_font="Malgun Gothic", osd_font_size=32, osd_bar_h=2.5,
            volume_max=VOLUME_MAX, volume=min(VOLUME_MAX, settings["volume"]), mute=settings["muted"],
            loglevel=os.environ.get("NOADPLAYER_MPV_LOG", "warn"),
            log_handler=lambda lvl, comp, msg: print(f"[mpv {lvl}] {comp}: {msg.rstrip()}", file=sys.stderr))
        self.apply_scalers(settings["hq_scale"])
        self._build_ui()
        self._build_menus()
        self.apply_sub_style(settings["subtitle"])
        self.player.sub_visibility = settings["sub_visible"]
        if settings["filters"]:
            self.apply_filters(filters.Filters(**{k: v for k, v in settings["filters"].items() if k in filters.Filters().as_dict()}))
        geo = settings.get("geometry")
        if geo:
            self.restoreGeometry(QByteArray.fromBase64(geo.encode()))
        state = settings.get("window_state")
        if state:
            self.restoreState(QByteArray.fromBase64(state.encode()))
        self.dock.setVisible(settings["playlist_visible"])

        self.tick = QTimer(self, interval=200)
        self.tick.timeout.connect(self._update)
        self.tick.start()
        if settings["auto_update"]:
            QTimer.singleShot(4000, lambda: self.check_update(False))     # 뜬 직후 재생을 방해하지 않게 늦게
        self.hide_timer = QTimer(self, singleShot=True, interval=2500)
        self.hide_timer.timeout.connect(self._hide_fs_controls)

    # ───────────────────────── UI ─────────────────────────
    def _tool(self, icon_name, tip, slot):
        b = QToolButton()
        b.setIcon(icon(icon_name))
        b.setIconSize(QSize(16, 16))
        b.setToolTip(tip)
        b.setAutoRaise(True)
        b.setFocusPolicy(Qt.NoFocus)
        b.clicked.connect(slot)
        return b

    def _build_ui(self):
        self.video = VideoWidget(self.player)
        self.video.setMinimumSize(0, 0)                       # 세로·가로로 영상이 안 보일 때까지 줄일 수 있게
        self.video.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.video.double_clicked.connect(self.toggle_pause)   # 더블클릭 = 재생/일시정지
        self.video.wheel.connect(lambda d: self.change_volume(5 * d))
        self.video.mouse_moved.connect(self._video_mouse_moved)
        self.video.context_menu.connect(lambda pos: self.context.exec(pos))
        self.video.files_dropped.connect(self.open_dropped)
        self.video.drag_started.connect(self._move_window)
        self.overlay = ActionOverlay(self.video)

        # 아래 조작부: 첫 줄은 전체 폭의 굵은 재생 막대, 둘째 줄은 버튼·시간·소리
        self.controls = ControlBar()
        self.controls.setObjectName("controls")
        self.controls.setAttribute(Qt.WA_StyledBackground)
        self.seek = SeekSlider(self.seek_to)
        self.play_btn = self._tool("play", "재생/일시정지 (Space)", self.toggle_pause)
        self.play_btn.setObjectName("playBtn")
        self.play_btn.setIconSize(QSize(18, 18))
        stop_btn = self._tool("stop", "정지 (S)", self.stop)
        prev_btn = self._tool("prev", "이전 파일 (PgUp)", lambda: self.play_sibling(-1))
        next_btn = self._tool("next", "다음 파일 (PgDn)", lambda: self.play_sibling(1))
        self.time_label = QLabel("00:00 / 00:00")
        self.ab_label = QLabel("")
        self.ab_label.setStyleSheet("color:#ffc447")
        self.mute_btn = self._tool("volume", "음소거 (M)", self.toggle_mute)
        self.vol = JumpSlider(6, 14)
        self.vol.setRange(0, VOLUME_MAX)
        self.vol.setSingleStep(5)
        self.vol.setValue(min(VOLUME_MAX, self.settings["volume"]))
        self.vol.setFixedSize(80, 18)
        self.vol.valueChanged.connect(self.set_volume)
        self._show_volume(self.vol.value())
        self.pl_btn = self._tool("list", "재생 목록 (F6)", lambda: self.dock.toggleViewAction().trigger())
        self.pl_btn.setCheckable(True)
        self.fs_btn = self._tool("fullscreen", "전체화면 (Enter)", self.toggle_fullscreen)
        # 팟플레이어와 같은 배치: 윗줄 = 재생 막대 + 소리 / 아랫줄 = 버튼·시간·목록 (넓을 때만 A-B·전체화면)
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(2)
        row1.addWidget(self.seek, 1)
        row1.addSpacing(4)
        row1.addWidget(self.mute_btn)
        row1.addWidget(self.vol)
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(2)
        for w in (self.play_btn, stop_btn, prev_btn, next_btn):
            row2.addWidget(w)
        row2.addSpacing(6)
        row2.addWidget(self.time_label)
        row2.addStretch(1)
        row2.addWidget(self.ab_label)                         # 넓을 때만 보이는 것들은 시간과 목록 사이에
        row2.addWidget(self.fs_btn)
        row2.addWidget(self.pl_btn)                           # 목록 버튼은 맨 오른쪽
        col = QVBoxLayout(self.controls)
        col.setContentsMargins(*self.controls.margins)
        col.setSpacing(2)
        col.addLayout(row1)
        col.addLayout(row2)
        self.controls.row1 = [self.mute_btn, self.vol]
        self.controls.row2 = [self.play_btn, stop_btn, prev_btn, next_btn, self.time_label, self.pl_btn]
        self.controls.optional_changed = self._optional_controls
        self._wide_controls = True

        central = QWidget()
        self.central_layout = QVBoxLayout(central)
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)
        self.central_layout.addWidget(self.video, 1)
        self.central_layout.addWidget(self.controls)
        self.setCentralWidget(central)

        self.pl_panel = PlaylistPanel(self.settings["auto_next"], self.settings["playlist_sort"])
        self.pl_panel.play_requested.connect(self.play_index)
        self.pl_panel.add_requested.connect(self.add_files_dialog)
        self.pl_panel.remove_requested.connect(self.remove_from_playlist)
        self.pl_panel.delete_files_requested.connect(self.delete_files_from_playlist)
        self.pl_panel.clear_requested.connect(self.clear_playlist)
        self.pl_panel.files_dropped.connect(lambda fs: self.add_to_playlist(fs))
        self.pl_panel.sort_changed.connect(self.set_playlist_sort)
        self.pl_panel.auto_next.toggled.connect(lambda v: self.settings.__setitem__("auto_next", v))
        self.dock = QDockWidget("재생 목록", self)
        self.dock.setObjectName("playlist_dock")
        self.dock.setWidget(self.pl_panel)
        self.dock.setFeatures(QDockWidget.DockWidgetClosable)
        self.dock.setAllowedAreas(Qt.RightDockWidgetArea)
        self.dock.setMinimumWidth(200)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.dock.visibilityChanged.connect(self._dock_visibility)

        self.setStyleSheet(
            "QMainWindow{background:#101010}"
            " #controls{background:#2b2b33; border-top:1px solid #45454f} #controls QLabel{color:#ececf2}"
            " #controls QToolButton{background:#383842; border:1px solid #6a6a78; border-radius:3px; padding:3px}"
            " #controls QToolButton:hover{background:#4a4a58; border-color:#9a9aae}"
            " #controls QToolButton:pressed{background:#2a2a32; border-color:#8a7dff}"
            " #controls QToolButton:checked{background:#4b4488; border-color:#8a7dff}"
            " #controls #playBtn{background:#5b4ee6; border:1px solid #a79eff; padding:3px 8px}"
            " #controls #playBtn:hover{background:#7266ff; border-color:#c8c2ff}"
            " #controls #playBtn:pressed{background:#4538c4}"
            " QDockWidget{color:#ddd} QDockWidget::title{background:#232323; padding:4px}"
            " #playlist{background:#181818} #playlist QListWidget{background:#141414; color:#ccc; border:none}"
            " #playlist QListWidget::item:selected{background:#3b3570}"
            " #playlist #sortLabel{color:#bbb} #playlist QComboBox{background:#2a2a2a; color:#ddd; border:1px solid #3a3a3a;"
            " padding:2px 6px} #playlist QComboBox QAbstractItemView{background:#2a2a2a; color:#ddd}"
            " #playlist QCheckBox{color:#bbb} #playlist QPushButton{background:#2a2a2a; color:#ddd;"
            " border:1px solid #3a3a3a; padding:3px 8px}")
        self.video.setFocus()

    def _action(self, menu, text, slot, shortcut=None, checkable=False):
        a = QAction(text, self)
        if shortcut:
            a.setShortcuts([QKeySequence(s) for s in (shortcut if isinstance(shortcut, (list, tuple))
                                                      else [shortcut])])
            a.setShortcutContext(Qt.WindowShortcut)
        a.setCheckable(checkable)
        a.triggered.connect(slot)
        menu.addAction(a)
        self.addAction(a)                      # 메뉴를 숨긴 전체화면에서도 단축키가 듣게
        return a

    def _build_menus(self):
        mb = self.menuBar()
        m = mb.addMenu("파일(&F)")
        self._action(m, "파일 열기…", self.open_file_dialog, "Ctrl+O")
        self._action(m, "주소 열기 (URL·FTP)…", self.open_url_dialog, "Ctrl+U")
        self.recent_menu = m.addMenu("최근 파일")
        self.recent_menu.aboutToShow.connect(self._fill_recent)
        self._action(m, "재생 목록에 파일 추가…", self.add_files_dialog, "Ctrl+Shift+O")
        m.addSeparator()
        self._action(m, "이전 파일", lambda: self.play_sibling(-1), "PgUp")
        self._action(m, "다음 파일", lambda: self.play_sibling(1), "PgDown")
        pl = self.dock.toggleViewAction()
        pl.setText("재생 목록 보이기")
        pl.setShortcut(QKeySequence("F6"))
        m.addAction(pl)
        self.addAction(pl)
        m.addSeparator()
        a = self._action(m, "재생 목록 Shift+Delete 로 실제 파일도 휴지통에 삭제", self._set_shift_delete, checkable=True)
        a.setChecked(self.settings["shift_delete_files"])
        self.confirm_delete_action = self._action(m, "파일 삭제 전 확인창 보이기", self._set_shift_delete_confirm,
                                                  checkable=True)
        self.confirm_delete_action.setChecked(self.settings["shift_delete_confirm"])
        m.addSeparator()
        self._action(m, "끝내기", self.close)

        m = mb.addMenu("재생(&P)")
        self._action(m, "재생 / 일시정지", self.toggle_pause, "Space")
        self._action(m, "정지", self.stop, "S")
        m.addSeparator()
        for tier, mod in (("normal", ""), ("ctrl", "Ctrl+"), ("shift", "Shift+"), ("ctrl_alt", "Ctrl+Alt+")):
            for sign, key in ((-1, "Left"), (1, "Right")):
                self.seek_actions[tier, sign] = self._action(
                    m, "", lambda _c=False, t=tier, sg=sign: self.seek_rel(sg * self.seek_step(t)), mod + key)
        self._refresh_seek_menu()
        self._action(m, "이동 시간 설정…", self.show_seek_steps)
        self._action(m, "이전 프레임", lambda: self._cmd("frame-back-step"), "D")
        self._action(m, "다음 프레임", lambda: self._cmd("frame-step"), "F")
        m.addSeparator()
        self._action(m, "빠르게 (+0.1배)", lambda: self.change_speed(0.1), "C")
        self._action(m, "느리게 (-0.1배)", lambda: self.change_speed(-0.1), "X")
        self._action(m, "보통 속도", lambda: self.change_speed(None), "Z")

        m = mb.addMenu("영상(&V)")
        self._action(m, "전체화면", self.toggle_fullscreen, ["Return", "Enter"])
        self._action(m, "전체화면 끝내기", lambda: self.isFullScreen() and self.toggle_fullscreen(), "Esc")
        m.addSeparator()
        self._action(m, "화질 필터…", self.show_filters, "Ctrl+F")
        self._action(m, "90° 회전", self.rotate_90, "Ctrl+R")
        self._action(m, "화질 필터 모두 끄기", self.reset_filters)
        m.addSeparator()
        a = self._action(m, "고화질 확대/축소 (선명하게)", self._set_hq_scale, checkable=True)
        a.setChecked(self.settings["hq_scale"])

        m = mb.addMenu("소리(&A)")
        self._action(m, "소리 크게", lambda: self.change_volume(5), "Up")
        self._action(m, "소리 작게", lambda: self.change_volume(-5), "Down")
        self._action(m, "음소거", self.toggle_mute, "M")
        self.audio_menu = m.addMenu("오디오 트랙")
        self.audio_menu.aboutToShow.connect(lambda: self._fill_tracks(self.audio_menu, "audio", "aid"))
        m.addSeparator()
        self._action(m, "소리 싱크 +0.1초", lambda: self.shift_delay("audio_delay", 0.1, "소리"), "Ctrl+.")
        self._action(m, "소리 싱크 -0.1초", lambda: self.shift_delay("audio_delay", -0.1, "소리"), "Ctrl+,")

        m = mb.addMenu("자막(&S)")
        self._action(m, "자막 파일 열기…", self.open_sub_dialog, "Alt+O")
        self.sub_menu = m.addMenu("자막 선택")
        self.sub_menu.aboutToShow.connect(lambda: self._fill_tracks(self.sub_menu, "sub", "sid"))
        self._action(m, "자막 보이기 / 숨기기", self.toggle_sub_visibility, "H")
        m.addSeparator()
        self._action(m, "자막 싱크 +0.5초 (늦게)", lambda: self.shift_delay("sub_delay", 0.5, "자막"), ".")
        self._action(m, "자막 싱크 -0.5초 (빠르게)", lambda: self.shift_delay("sub_delay", -0.5, "자막"), ",")
        self._action(m, "자막 싱크 초기화", lambda: self.shift_delay("sub_delay", None, "자막"), "/")
        self._action(m, "자막 모양…", self.show_sub_style, "Alt+S")
        m.addSeparator()
        self._action(m, "AI 자막 만들기…", self.make_ai_subtitle, "Ctrl+T")
        self._action(m, "자막 한국어로 번역…", self.translate_current_subtitle, "Ctrl+Shift+T")
        self._action(m, "번역 설정 (API 키)…", self.show_translate_settings)

        m = mb.addMenu("캡처(&C)")
        self._action(m, "화면 캡처 (자막 포함)", lambda: self.take_screenshot(True), "Ctrl+E")
        self._action(m, "화면 캡처 (영상만)", lambda: self.take_screenshot(False), "Ctrl+Shift+E")
        m.addSeparator()
        self._action(m, "구간 시작(A) 지정", lambda: self.set_ab(0), "[")
        self._action(m, "구간 끝(B) 지정", lambda: self.set_ab(1), "]")
        self._action(m, "구간 지우기", self.clear_ab, "\\")
        self._action(m, "구간 영상 저장", lambda: self.save_clip("video"), "Ctrl+Shift+V")
        self._action(m, "구간 소리 저장", lambda: self.save_clip("audio"), "Ctrl+Shift+A")
        fmt_menu = m.addMenu("소리 저장 형식")
        for f in capture.AUDIO_FORMATS:
            a = fmt_menu.addAction(f.upper())
            a.setCheckable(True)
            a.setChecked(self.settings["audio_format"] == f)
            a.triggered.connect(lambda _c, f=f: self._set_audio_format(f, fmt_menu))
        m.addSeparator()
        self._action(m, "캡처 폴더 열기", lambda: os.startfile(user_dir("image")))
        self._action(m, "구간 저장 폴더 열기", lambda: os.startfile(user_dir("video")))

        m = mb.addMenu("도움말(&H)")
        self._action(m, "업데이트 확인…", lambda: self.check_update(True))
        a = self._action(m, "시작할 때 업데이트 자동 확인", self._set_auto_update, checkable=True)
        a.setChecked(self.settings["auto_update"])
        m.addSeparator()
        self._action(m, "몽플레이어 정보", lambda: dialogs.show_about(self))

        self.context = QMenu(self)
        for menu in mb.findChildren(QMenu):
            if menu.parent() is mb:
                self.context.addMenu(menu)

    # ───────────────────────── 열기 ─────────────────────────
    def open_path(self, path):
        """파일 하나 열기 — 재생 목록은 그 파일이 있는 폴더의 동영상·음악으로 채운다 (주소는 그것 하나)."""
        if not is_url(path):
            path = os.path.normpath(path)
        self.set_playlist([path] if is_url(path) else folder_media(path, self.settings["playlist_sort"]), path)

    def set_playlist(self, items, start):
        self.playlist = list(items)
        self.pl_panel.set_items(self.playlist, -1)
        self.play_index(self.playlist.index(start) if start in self.playlist else 0)

    def play_index(self, i):
        if not 0 <= i < len(self.playlist):
            return
        path = self.playlist[i]
        self.pl_index = i
        self.pl_panel.set_current(i)
        self._eof_handled = False
        self.player["start"] = f"{self.settings['resume'].get(path, 0):.1f}"     # 봤던 영상이면 보던 위치부터
        self.player.play(path)
        self.player.pause = False
        if self.settings["resume"].get(path):
            self.osd(f"{fmt_time(self.settings['resume'][path])} 부터 이어서 재생")
        if not is_url(path):
            self.settings["last_dir"] = os.path.dirname(path)
        self.settings.add_recent(path)

    def set_playlist_sort(self, mode):
        """정렬 기준을 바꾸면 목록을 다시 정렬하고(재생 중인 항목은 그대로) 기준을 기억한다."""
        self.settings["playlist_sort"] = mode
        playing = self.playlist[self.pl_index] if 0 <= self.pl_index < len(self.playlist) else None
        local = [p for p in self.playlist if not is_url(p)]
        urls = [p for p in self.playlist if is_url(p)]
        self.playlist = sort_media(local, mode) + urls
        self.pl_index = self.playlist.index(playing) if playing in self.playlist else -1
        self.pl_panel.set_items(self.playlist, self.pl_index)

    def add_to_playlist(self, files):
        media = [os.path.normpath(f) if not is_url(f) else f for f in files
                 if is_url(f) or os.path.splitext(f)[1].lower() in MEDIA_SET]
        if not media:
            return
        was_empty = not self.playlist
        self.playlist += [m for m in media if m not in self.playlist]
        self.pl_panel.set_items(self.playlist, self.pl_index)
        if was_empty:
            self.play_index(0)
        self.osd(f"재생 목록에 {len(media)}개 추가")

    def add_files_dialog(self):
        flt = f"동영상·음악 ({' '.join('*.' + e for e in (VIDEO_EXT + ' ' + AUDIO_EXT).split())})"
        paths, _ = QFileDialog.getOpenFileNames(self, "재생 목록에 추가", self.settings["last_dir"], flt)
        self.add_to_playlist(paths)

    def remove_from_playlist(self, rows):
        playing = self.playlist[self.pl_index] if 0 <= self.pl_index < len(self.playlist) else None
        self.playlist = [p for i, p in enumerate(self.playlist) if i not in set(rows)]
        self.pl_index = self.playlist.index(playing) if playing in self.playlist else -1
        self.pl_panel.set_items(self.playlist, self.pl_index)

    def _set_shift_delete(self, on):
        self.settings["shift_delete_files"] = bool(on)

    def _set_shift_delete_confirm(self, on):
        self.settings["shift_delete_confirm"] = bool(on)

    def delete_files_from_playlist(self, rows):
        """Shift+Delete — 목록에서 지우고 실제 파일도 휴지통으로 보낸다. 옵션이 꺼져 있으면 목록에서만 지운다."""
        if not self.settings["shift_delete_files"]:
            self.remove_from_playlist(rows)
            return
        targets = [self.playlist[i] for i in rows if 0 <= i < len(self.playlist)]
        files = [p for p in targets if not is_url(p)]
        if self.settings["shift_delete_confirm"] and files:
            box = QMessageBox(QMessageBox.Warning, "파일 삭제",
                              f"선택한 {len(files)}개 파일을 실제로 삭제합니다 (휴지통으로 이동).\n\n"
                              + "\n".join(os.path.basename(p) for p in files[:5]) + ("\n…" if len(files) > 5 else "")
                              + "\n\n이 동작은 상단 [파일] 메뉴에서 켜고 끌 수 있습니다.", parent=self)
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
            box.button(QMessageBox.Yes).setText("삭제")
            box.button(QMessageBox.Cancel).setText("취소")
            box.setDefaultButton(QMessageBox.Cancel)
            ask = QCheckBox("다시 묻지 않기 (이후에는 바로 삭제)")
            box.setCheckBox(ask)
            if box.exec() != QMessageBox.Yes:
                return
            if ask.isChecked():
                self.settings["shift_delete_confirm"] = False
                self.confirm_delete_action.setChecked(False)
        if self._path and any(os.path.normcase(self._path) == os.path.normcase(p) for p in files):
            self._cmd("stop")                                    # 재생 중인 파일은 잡고 있으므로 먼저 놓는다
            time.sleep(0.3)
        failed = [p for p in files if os.path.exists(p) and not move_to_trash(p)]
        done = set(targets) - set(failed)
        for p in done:
            if p in self.settings["resume"]:
                self.settings.set_resume(p, None)
        self.remove_from_playlist([i for i in rows if 0 <= i < len(self.playlist) and self.playlist[i] in done])
        self.osd(f"{len(files) - len(failed)}개 파일을 휴지통으로 보냈습니다" + (f" (실패 {len(failed)}개)" if failed else ""))

    def clear_playlist(self):
        self.playlist, self.pl_index = [], -1
        self.pl_panel.set_items([], -1)

    def _dock_visibility(self, visible):
        self.pl_btn.setChecked(visible)
        if not self.isFullScreen():
            self.settings["playlist_visible"] = visible
        if self._dock_lock or not self.isVisible() or self.isFullScreen() or self.isMaximized():
            return                                        # 꽉 찬 화면일 때만 영상 칸이 줄고 늘어난다
        delta = self._dock_w + self.style().pixelMetric(QStyle.PM_DockWidgetSeparatorExtent)
        g = self.geometry()
        width = g.width() + (delta if visible else -delta)
        x = g.x()
        if visible:                                       # 늘어난 창이 화면 밖으로 나가면 왼쪽으로 당긴다
            area = self.screen().availableGeometry()
            x = max(area.left(), min(x, area.right() - width + 1))
        self.setGeometry(x, g.y(), width, g.height())

    def _move_window(self):
        if not self.isFullScreen() and self.windowHandle():
            self.windowHandle().startSystemMove()

    def open_file_dialog(self):
        flt = (f"동영상·음악 ({' '.join('*.' + e for e in (VIDEO_EXT + ' ' + AUDIO_EXT).split())});;"
               "모든 파일 (*.*)")
        paths, _ = QFileDialog.getOpenFileNames(self, "파일 열기", self.settings["last_dir"], flt)
        if len(paths) == 1:
            self.open_path(paths[0])
        elif paths:
            self.set_playlist([os.path.normpath(p) for p in paths], os.path.normpath(paths[0]))

    def open_url_dialog(self):
        url, ok = QInputDialog.getText(self, "주소 열기", "동영상 주소 (http://, https://, ftp://, rtsp:// …)")
        if ok and url.strip():
            self.open_path(url.strip())

    def open_sub_dialog(self):
        start = os.path.dirname(self._path) if self._path and os.path.isfile(self._path) else self.settings["last_dir"]
        path, _ = QFileDialog.getOpenFileName(self, "자막 열기", start,
                                              f"자막 ({' '.join('*.' + e for e in SUB_EXT.split())})")
        if path:
            self.add_subtitle(os.path.normpath(path))

    def add_subtitle(self, path, title=None):
        if not self._path:
            self.osd("먼저 동영상을 여세요")
            return
        args = ["sub-add", path, "select"] + ([title] if title else [])
        self.player.command(*args)
        self.osd(f"자막: {os.path.basename(path)}")

    def open_dropped(self, files):
        subs = [f for f in files if os.path.splitext(f)[1].lower() in SUB_SET]
        media = [f for f in files if f not in subs and (is_url(f) or os.path.splitext(f)[1].lower() in MEDIA_SET)]
        if len(media) == 1:
            self.open_path(media[0])
        elif media:
            media = [os.path.normpath(m) if not is_url(m) else m for m in media]
            self.set_playlist(media, media[0])
        for s in subs:
            if media:
                QTimer.singleShot(500, lambda s=s: self.add_subtitle(s))
            else:
                self.add_subtitle(s)

    def _fill_recent(self):
        self.recent_menu.clear()
        for p in self.settings["recent"]:
            a = self.recent_menu.addAction(p)
            a.triggered.connect(lambda _c, p=p: self.open_path(p))
        if not self.settings["recent"]:
            self.recent_menu.addAction("(없음)").setEnabled(False)

    def play_sibling(self, step):
        i = self.pl_index + step
        if 0 <= i < len(self.playlist):
            self.play_index(i)
            self.flash("next" if step > 0 else "prev")
        elif self.playlist:
            self.osd("첫 파일입니다" if step < 0 else "마지막 파일입니다")

    # ───────────────────────── 재생 ─────────────────────────
    def _cmd(self, *args):
        try:
            self.player.command(*args)
        except SystemError:
            pass

    def osd(self, text, ms=1800):
        self._cmd("show-text", text, str(ms))

    def flash(self, name, text=""):
        """영상 위에 동작 아이콘을 잠깐 보인다."""
        self.overlay.flash(name, text)

    def toggle_pause(self):
        if not self._path:                                   # 정지한 뒤 재생 → 현재 항목을 다시 재생
            if self.playlist:
                self.play_index(max(self.pl_index, 0))
                self.flash("play")
            return
        if self.player.eof_reached:                          # 끝까지 본 뒤 재생 → 처음부터
            self._cmd("seek", "0", "absolute")
            self.player.pause = False
            self.flash("play")
            return
        paused = not self.player.pause
        self.player.pause = paused
        self._sync_play_icon(paused)
        self.flash("pause" if paused else "play")

    # ── 방향키 이동 시간 (설정에서 선택, 즉시 저장)
    @staticmethod
    def fmt_step(n):
        return f"{n // 60}분" if n % 60 == 0 else f"{n}초"

    def seek_step(self, tier):
        return int(self.settings["seek_steps"].get(tier, 1))

    def _refresh_seek_menu(self):
        for (tier, sign), a in self.seek_actions.items():
            a.setText(f"{self.fmt_step(self.seek_step(tier))} {'앞으로' if sign > 0 else '뒤로'}")

    def show_seek_steps(self):
        dialogs.SeekStepsDialog(self.settings, self._refresh_seek_menu, self).exec()

    # ── 고화질 확대/축소
    def apply_scalers(self, hq):
        p = self.player
        try:
            if hq:
                p.scale, p.cscale, p.dscale = "ewa_lanczossharp", "spline36", "lanczos"
                p.scale_antiring = 0.6
                p.correct_downscaling = True
                p.linear_downscaling = True
                p.sigmoid_upscaling = True
            else:
                p.scale, p.cscale, p.dscale = "bilinear", "bilinear", "bilinear"
                p.scale_antiring = 0
        except (AttributeError, TypeError, SystemError):
            pass

    def _set_hq_scale(self, on):
        self.settings["hq_scale"] = bool(on)
        self.apply_scalers(on)

    def stop(self):
        self._cmd("stop")
        self.flash("stop")

    def seek_to(self, sec, exact=True):
        if self._path:
            self._cmd("no-osd", "seek", f"{sec:.3f}", "absolute+exact" if exact else "absolute+keyframes")

    def seek_rel(self, sec):
        if self._path:
            self._cmd("no-osd", "seek", str(sec), "relative")
            self.seek.hold_until = time.monotonic() + SeekSlider.HOLD_S
            self.flash("forward" if sec > 0 else "back", self.fmt_step(abs(int(sec))))

    def change_speed(self, d):
        sp = 1.0 if d is None else min(4.0, max(0.25, round((self.player.speed or 1.0) + d, 2)))
        self.player.speed = sp
        self.osd(f"속도 {sp:.2f}배")

    def set_volume(self, v):
        self.player.volume = v
        self.settings["volume"] = v
        self._show_volume(v)

    def _show_volume(self, v):
        self.vol.setToolTip(f"소리 {v}%" + (" (증폭)" if v > 100 else "") + " — 최대 200%")

    def change_volume(self, d):
        v = min(VOLUME_MAX, max(0, round(self.player.volume or 0) + d))
        self.vol.setValue(v)
        self.osd(f"소리 {v}%" + (" (증폭)" if v > 100 else ""))

    def toggle_mute(self):
        self.player.mute = not self.player.mute
        self.settings["muted"] = bool(self.player.mute)
        self.flash("muted" if self.player.mute else "volume")

    def shift_delay(self, prop, d, label):
        v = 0.0 if d is None else round((getattr(self.player, prop) or 0) + d, 2)
        setattr(self.player, prop, v)
        self.osd(f"{label} 싱크 {v:+.1f}초")

    def _fill_tracks(self, menu, kind, prop):
        menu.clear()
        cur = getattr(self.player, prop)
        if kind == "sub":
            off = menu.addAction("끄기")
            off.setCheckable(True)
            off.setChecked(cur in (False, "no", None))
            off.triggered.connect(lambda: setattr(self.player, prop, "no"))
        tracks = [t for t in (self.player.track_list or []) if t.get("type") == kind]
        for t in tracks:
            name = " · ".join(str(x) for x in (t.get("title"), t.get("lang"), t.get("codec")) if x)
            if t.get("external"):
                name += " (외부)"
            a = menu.addAction(f"{t['id']}. {name or '트랙'}")
            a.setCheckable(True)
            a.setChecked(bool(t.get("selected")))
            a.triggered.connect(lambda _c, i=t["id"]: setattr(self.player, prop, i))
        if not tracks:
            menu.addAction("(없음)").setEnabled(False)

    def toggle_sub_visibility(self):
        self.player.sub_visibility = not self.player.sub_visibility
        self.settings["sub_visible"] = bool(self.player.sub_visibility)
        self.osd("자막 보이기" if self.player.sub_visibility else "자막 숨기기")

    # ───────────────────────── 화면 ─────────────────────────
    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.central_layout.addWidget(self.controls)
            self.controls.show()
            self.menuBar().show()
            self.video.unsetCursor()
            self.hide_timer.stop()
            self._dock_lock = True
            self.showMaximized() if self._was_maximized else self.showNormal()
            self.dock.setVisible(self._fs_dock_visible)
            self._dock_lock = False
        else:
            self._was_maximized = self.isMaximized()
            self._fs_dock_visible = self.dock.isVisible()
            self.menuBar().hide()
            self.controls.setParent(self.video)       # 영상 위에 겹쳐 띄우는 컨트롤
            self.controls.hide()
            self.showFullScreen()
            self.dock.hide()                          # 전체화면이 된 뒤 숨겨야 '보이기' 설정이 안 바뀐다
        self.video.setFocus()

    def _video_mouse_moved(self, pos):
        if not self.isFullScreen():
            return
        self.video.unsetCursor()
        if pos.y() > self.video.height() - 110:
            h = self.controls.sizeHint().height()
            self.controls.setGeometry(0, self.video.height() - h, self.video.width(), h)
            self.controls.show()
            self.controls.raise_()
        self.hide_timer.start()

    def _hide_fs_controls(self):
        if self.isFullScreen() and not self.controls.underMouse():
            self.controls.hide()
            self.video.setCursor(Qt.BlankCursor)
        elif self.isFullScreen():
            self.hide_timer.start()

    def apply_filters(self, f):
        self.filters = f
        self.settings["filters"] = f.as_dict()
        try:
            filters.apply(self.player, f)
        except Exception as e:  # noqa: BLE001
            self.osd(f"필터 적용 실패: {e}")

    def show_filters(self):
        if not self.filter_dlg:
            self.filter_dlg = dialogs.FilterDialog(self.filters, self.apply_filters, self)
        self.filter_dlg.show()
        self.filter_dlg.raise_()

    def _drop_filter_dlg(self):
        """메뉴로 필터를 바꾸면 열린 필터 창의 값이 낡으므로 닫고 다음에 새로 만든다."""
        if self.filter_dlg:
            self.filter_dlg.close()
            self.filter_dlg.deleteLater()
            self.filter_dlg = None

    def rotate_90(self):
        f = filters.Filters(**{**self.filters.as_dict(), "rotate": (self.filters.rotate + 90) % 360})
        self.apply_filters(f)
        self._drop_filter_dlg()
        self.osd(f"회전 {f.rotate}°")

    def reset_filters(self):
        self.apply_filters(filters.Filters())
        self._drop_filter_dlg()
        self.osd("화질 필터 끔")

    def apply_sub_style(self, style):
        self.settings["subtitle"] = dict(style)
        p = self.player
        p.sub_font = style["font"]
        p.sub_font_size = style["size"]
        p.sub_bold = style["bold"]
        p.sub_color = style["color"]
        p.sub_pos = style["pos"]
        p.sub_ass_override = "force" if style["override_ass"] else "scale"
        for name, val in (("sub_outline_color", style["border_color"]), ("sub_outline_size", style["border_size"])):
            try:
                setattr(p, name, val)
            except (AttributeError, TypeError, SystemError):           # mpv 0.38 이전 이름
                setattr(p, name.replace("outline", "border"), val)

    def show_sub_style(self):
        if not self.sub_dlg:
            self.sub_dlg = dialogs.SubtitleStyleDialog(self.settings["subtitle"], self.apply_sub_style, self)
        self.sub_dlg.show()
        self.sub_dlg.raise_()

    # ───────────────────────── 캡처 ─────────────────────────
    def take_screenshot(self, with_subs):
        if not self._path:
            return
        try:
            out = capture.screenshot(self.player, with_subs)
            self.osd(f"캡처 저장: {os.path.basename(out)}")
        except Exception as e:  # noqa: BLE001
            self.osd(f"캡처 실패: {e}")

    def set_ab(self, i):
        if not self._path:
            return
        self.ab[i] = self.player.time_pos or 0.0
        if self.ab[0] is not None and self.ab[1] is not None and self.ab[1] < self.ab[0]:
            self.ab.reverse()
        self._show_ab()
        self.osd(f"구간 {'AB'[i]}: {fmt_time(self.ab[i])}")

    def clear_ab(self):
        self.ab = [None, None]
        self._show_ab()

    def _show_ab(self):
        a, b = self.ab
        self.ab_label.setText("" if a is None and b is None else
                              f"A {fmt_time(a) if a is not None else '-'} ~ B {fmt_time(b) if b is not None else '-'}")
        self.ab_label.setVisible(self._wide_controls and not (a is None and b is None))
        self.seek.markers = (a, b)
        self.seek.update()

    def _set_audio_format(self, f, menu):
        self.settings["audio_format"] = f
        for a in menu.actions():
            a.setChecked(a.text().lower() == f)

    def save_clip(self, kind):
        if not self._path:
            return
        a, b = self.ab
        if a is None or b is None or b - a < 0.1:
            QMessageBox.information(self, "구간 저장", "먼저 구간 시작(A, [ 키)과 끝(B, ] 키)을 지정하세요.")
            return
        if not addons.present("ffmpeg"):
            if QMessageBox.question(self, "구간 저장", f"구간 저장에는 {addons.label('ffmpeg')}(약 {addons.approx_mb('ffmpeg')}MB)가 "
                                    "필요합니다. 지금 한 번 내려받을까요?") != QMessageBox.Yes:
                return
        cmd, out = capture.clip_command(self._path, a, b, kind, self.settings["audio_format"])

        def job(w):
            addons.ensure("ffmpeg", lambda d, t: w.progress.emit(d, t), w.cancelled)
            return capture.run_clip(cmd, out)

        w = Worker(job, self)
        self.workers.add(w)
        w.progress.connect(lambda d, t: self.osd(f"{addons.label('ffmpeg')} 내려받는 중… {int(d * 100 / t) if t else 0}%", 60000))
        w.done.connect(lambda r: self.osd(f"저장 완료: {os.path.basename(r[0])}", 3000))
        w.failed.connect(lambda m: QMessageBox.warning(self, "구간 저장", f"저장하지 못했습니다.\n\n{m}"))
        w.finished.connect(lambda: self.workers.discard(w))
        w.start()
        self.osd("구간 저장 중…")

    # ───────────────────────── AI 자막 ─────────────────────────
    def make_ai_subtitle(self):
        if not self._path or not os.path.isfile(self._path):
            QMessageBox.information(self, "AI 자막", "내 PC 에 있는 동영상·음악 파일을 연 상태에서 쓸 수 있습니다.")
            return
        media = self._path
        dlg = dialogs.SttDialog(media, self.settings["stt_language"], self.settings["stt_auto_translate"], self)
        if not dlg.exec() or not dlg.result:
            return
        self.settings["stt_language"] = dlg.language
        self.settings["stt_auto_translate"] = dlg.translate_check.isChecked()
        out = self.sub_out_path(media, ".AI.srt")
        with open(out, "w", encoding="utf-8-sig") as f:
            f.write(dlg.result["srt"])
        if self._path == media:
            self.add_subtitle(out, "AI 자막")
        self.osd(f"AI 자막 {len(dlg.result['segments'])}줄 완료 ({os.path.basename(out)})", 3000)
        if dlg.translate_check.isChecked() and dlg.result["language"] != "ko":
            self.translate_subtitle({"kind": "external", "path": out, "ff_index": None,
                                     "title": f"{os.path.basename(out)} (AI 자막)"}, media)

    @staticmethod
    def sub_out_path(media, suffix):
        """만든 자막을 둘 곳: 영상 옆(이름+suffix) — 쓸 수 없는 폴더나 인터넷 주소면 앱 데이터 폴더."""
        name = os.path.splitext(os.path.basename(media.split("?")[0].rstrip("/\\")))[0] or "subtitle"
        name = "".join("_" if c in '\\/:*?"<>|' else c for c in name) + suffix
        folder = os.path.dirname(media) if not is_url(media) else ""
        if folder:
            try:
                with tempfile.TemporaryFile(dir=folder):
                    pass
                return os.path.join(folder, name)
            except OSError:
                pass
        d = os.path.join(DATA, "subtitles")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, name)

    # ───────────────────────── 자막 번역 ─────────────────────────
    def translate_current_subtitle(self):
        if not self._path:
            QMessageBox.information(self, "자막 번역", "먼저 동영상을 여세요.")
            return
        try:
            src = translate_source.selected_track(self.player)
        except translate_source.SourceError as e:
            QMessageBox.information(self, "자막 번역", str(e))
            return
        if not src:
            QMessageBox.information(self, "자막 번역", "번역할 자막이 없습니다. 자막 파일을 열거나 '자막 선택'에서 "
                                                   "자막을 고른 뒤 다시 시도하세요. 자막이 없으면 'AI 자막 만들기'를 먼저 쓰세요.")
            return
        self.translate_subtitle(src, self._path)

    def translate_subtitle(self, src, media):
        out = self.sub_out_path(media, ".ko.srt")
        if src["kind"] == "external" and os.path.normcase(src["path"] or "") == os.path.normcase(out):
            QMessageBox.information(self, "자막 번역", "이미 번역된 한국어 자막입니다.")
            return
        dlg = dialogs.TranslateDialog(src, out, self.settings, self)
        if dlg.exec() and dlg.count:
            if self._path == media:
                self.add_subtitle(out, "한국어 번역")
            self.osd(f"번역 완료 {dlg.count}줄 ({os.path.basename(out)})", 3000)

    def show_translate_settings(self):
        dialogs.TranslateSettingsDialog(self.settings, self).exec()

    # ───────────────────────── 업데이트 ─────────────────────────
    def _set_auto_update(self, on):
        self.settings["auto_update"] = bool(on)

    def check_update(self, manual):
        """새 버전 확인(작업 스레드). manual=False 면 새 버전이 없거나 실패해도 조용히 넘어간다."""
        if getattr(self, "_updating", False):
            return
        self._updating = True

        def work(_w):
            ok, info = mong_update.check("mongplayer", VERSION)      # 공개 배포 저장소에서 확인(토큰 불필요)
            if not ok:
                raise RuntimeError(mong_update.last_error or "업데이트 정보를 읽지 못했습니다.")
            return info                                              # 새 버전이 없으면 None

        w = Worker(work, self)
        self.workers.add(w)
        w.done.connect(lambda info: self._update_checked(info, manual))
        w.failed.connect(lambda m: self._update_failed(m, manual))
        w.finished.connect(lambda: self.workers.discard(w))
        w.start()
        if manual:
            self.osd("업데이트 확인 중…")

    def _update_failed(self, msg, manual):
        self._updating = False
        if manual and msg:
            QMessageBox.warning(self, "업데이트", msg)

    def _update_checked(self, info, manual):
        self._updating = False
        if info is None:
            if manual:
                QMessageBox.information(self, "업데이트", f"최신 버전입니다 (v{VERSION}).")
            return
        note = f"\n\n변경: {info['note']}" if info["note"] else ""
        if QMessageBox.question(self, "업데이트", f"새 버전 v{info['version']} 이 있습니다 (현재 v{VERSION}).{note}\n\n"
                                                  "지금 업데이트할까요? (끝나면 자동으로 다시 시작합니다)") != QMessageBox.Yes:
            return
        self._updating = True
        w = Worker(lambda _w: mong_update.download(info), self)       # 받은 뒤 해시까지 확인
        self.workers.add(w)
        w.done.connect(lambda path: self._update_downloaded(info, path))
        w.failed.connect(lambda m: self._update_failed(m or "받기를 취소했습니다.", True))
        w.finished.connect(lambda: self.workers.discard(w))
        w.start()
        self.osd("업데이트 받는 중…", 4000)

    def _update_downloaded(self, info, path):
        self._updating = False
        try:
            args = f'"{self._path}"' if self._path else ""             # 지금 보던 파일을 다시 열게 한다
            mong_update.apply(info, path, args)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "업데이트", f"업데이트를 적용하지 못했습니다.\n\n{e}")
            return
        self.close()                                                   # 곧바로 새 버전이 다시 시작된다

    # ───────────────────────── 상태 갱신·종료 ─────────────────────────
    def _update(self):
        p = self.player
        try:
            path = p.path
            pos, dur, paused = p.time_pos or 0.0, p.duration or 0.0, bool(p.pause)
        except Exception:  # noqa: BLE001 — 종료 중
            return
        if self.dock.isVisible() and not self._dock_lock and self.dock.width() >= 150 \
                and self.dock.width() != self._dock_w:            # 사용자가 끌어 바꾼 목록 폭을 기억
            self._dock_w = self.dock.width()
            self.settings["playlist_width"] = self._dock_w
        if path != self._path:
            self._save_resume()                                   # 이전 영상의 보던 위치 기록
            self._res_pos = self._res_dur = 0.0
            self._res_saved = time.monotonic()
            self._path = path
            self.clear_ab()
            name = os.path.basename(path.rstrip("/")) if path else ""
            self.setWindowTitle(f"{name} - {APP_NAME_KO}" if name else APP_NAME_KO)
        sec = int(pos)
        if not self.seek.dragging and time.monotonic() >= self.seek.hold_until and \
                (sec != self._last_sec or self.seek.maximum() != int(dur * 1000)):
            self._last_sec = sec                                  # 막대·시간은 1초에 한 번만 움직인다
            if self.seek.maximum() != int(dur * 1000):
                self.seek.setRange(0, int(dur * 1000))
            self.seek.setValue(sec * 1000)
            self.time_label.setText(f"{fmt_time(pos)} / {fmt_time(dur)}")
        if path and dur > 0 and not p.eof_reached:
            self._res_pos, self._res_dur = pos, dur
            if time.monotonic() - self._res_saved >= 5:           # 5초마다 위치 기록 (갑자기 꺼져도 남게)
                self._save_resume()
        self._sync_play_icon(paused or not path)
        self._sync_icon("mute", self.mute_btn, "muted" if p.mute else "volume")
        eof = bool(path and p.eof_reached)
        if eof and not self._eof_handled:                         # 끝까지 재생 → 다음 파일 (한 번만)
            if self.pl_panel.auto_next.isChecked() and self.pl_index + 1 < len(self.playlist):
                self.play_index(self.pl_index + 1)
                return
        self._eof_handled = eof

    def _save_resume(self):
        """지금 보던 위치를 이어 보기용으로 저장한다. 처음 5초 이내거나 거의 끝(95%↑)까지 봤으면 기록을 지운다."""
        self._res_saved = time.monotonic()
        path = self._path
        if not path or is_url(path) or self._res_dur <= 0:
            return
        if self._res_pos < 5 or self._res_pos > self._res_dur * 0.95:
            if path in self.settings["resume"]:
                self.settings.set_resume(path, None)
        elif self.settings["resume"].get(path) != round(self._res_pos, 1):
            self.settings.set_resume(path, self._res_pos)

    def _optional_controls(self, wide):
        """조작부가 좁으면 A-B 표시·전체화면 버튼은 숨기고 꼭 필요한 것만 남긴다."""
        self._wide_controls = wide
        self.fs_btn.setVisible(wide)
        self.ab_label.setVisible(wide and bool(self.ab_label.text()))

    def _sync_icon(self, key, button, name):
        if self._ui_state.get(key) != name:                   # 바뀔 때만 아이콘을 갈아 끼운다
            self._ui_state[key] = name
            button.setIcon(icon(name))

    def _sync_play_icon(self, paused):
        self._sync_icon("play", self.play_btn, "play" if paused else "pause")

    def closeEvent(self, e):
        self.tick.stop()
        self._save_resume()
        for w in list(self.workers):
            w.wait(15000)                        # 구간 저장 중이면 끝날 때까지
        if self.isFullScreen():
            self.toggle_fullscreen()
        self.settings["geometry"] = bytes(self.saveGeometry().toBase64()).decode()
        self.settings["window_state"] = bytes(self.saveState().toBase64()).decode()
        self.settings.save()
        self.video.release()
        self.player.terminate()
        super().closeEvent(e)
