"""탐색기 우클릭 메뉴·'연결 프로그램' 등록 (HKCU 만 사용 — 관리자 권한 불필요).

- 미디어 파일 우클릭 → "노애드플레이어로 재생" (아이콘 포함, 바로 실행)
- 우클릭 → 연결 프로그램 목록에 "노애드플레이어" 이름·아이콘으로 표시
- 설정 > 기본 앱 목록에도 나타남 (기본 앱 지정 자체는 Windows 정책상 사용자가 직접 고른다)

설치본(exe) 실행 때만 자동 등록하고, 실행 파일 위치가 바뀌면 다시 등록한다.
    몽플레이어.exe --register / --unregister   로 수동 등록·해제도 가능.
"""
import ctypes
import os
import sys
import winreg

from . import APP_NAME

DISPLAY_NAME = "몽플레이어"
MENU_TEXT = "몽플레이어로 재생"
EXE_NAME = "몽플레이어.exe"
LEGACY_EXE_NAME = "NoAdPlayer.exe"      # 이름이 바뀌기 전 등록한 항목은 지운다
PROG_ID = f"{APP_NAME}.Media"
CLASSES = r"Software\Classes"
VIDEO_EXT = ("mp4 mkv avi mov wmv flv webm m4v ts m2ts mts mpg mpeg vob 3gp ogv rm rmvb asf divx f4v")
AUDIO_EXT = "mp3 flac wav m4a aac ogg opus wma ape"
EXTENSIONS = ["." + e for e in (VIDEO_EXT + " " + AUDIO_EXT).split()]


def _set(root, path, value="", name=""):
    with winreg.CreateKeyEx(root, path, 0, winreg.KEY_WRITE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)


def _delete_tree(root, path):
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as k:
            while True:
                try:
                    sub = winreg.EnumKey(k, 0)
                except OSError:
                    break
                _delete_tree(root, path + "\\" + sub)
        winreg.DeleteKey(root, path)
    except FileNotFoundError:
        pass


def _read(root, path, name=""):
    try:
        with winreg.OpenKey(root, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def _notify():
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)      # SHCNE_ASSOCCHANGED


def is_registered(exe, classes=CLASSES, root=winreg.HKEY_CURRENT_USER):
    return _read(root, rf"{classes}\Applications\{EXE_NAME}\shell\open\command") == f'"{exe}" "%1"'


def register(exe, classes=CLASSES, root=winreg.HKEY_CURRENT_USER, notify=True):
    exe = os.path.abspath(exe)
    cmd = f'"{exe}" "%1"'
    icon = f'"{exe}",0'

    _delete_tree(root, rf"{classes}\Applications\{LEGACY_EXE_NAME}")
    app = rf"{classes}\Applications\{EXE_NAME}"                          # 연결 프로그램 목록
    _set(root, app, name="FriendlyAppName", value=DISPLAY_NAME)
    _set(root, app + r"\DefaultIcon", icon)
    _set(root, app + r"\shell\open", MENU_TEXT)
    _set(root, app + r"\shell\open\command", cmd)
    for ext in EXTENSIONS:
        _set(root, app + r"\SupportedTypes", "", ext)

    _set(root, rf"{classes}\{PROG_ID}", f"{DISPLAY_NAME} 미디어 파일")    # 기본 앱 후보
    _set(root, rf"{classes}\{PROG_ID}\DefaultIcon", icon)
    _set(root, rf"{classes}\{PROG_ID}\shell\open\command", cmd)

    cap = rf"Software\{APP_NAME}\Capabilities"
    if classes == CLASSES:                                                # 시험용 기반 키에서는 건너뜀
        _set(root, cap, DISPLAY_NAME, "ApplicationName")
        _set(root, cap, "무광고 동영상 재생기 + AI 자막", "ApplicationDescription")
        for ext in EXTENSIONS:
            _set(root, cap + r"\FileAssociations", PROG_ID, ext)
        _set(root, r"Software\RegisteredApplications", cap, APP_NAME)

    for ext in EXTENSIONS:                                               # 우클릭 메뉴 + 연결 프로그램 후보
        verb = rf"{classes}\SystemFileAssociations\{ext}\shell\{APP_NAME}"
        _set(root, verb, MENU_TEXT)
        _set(root, verb, icon, "Icon")
        _set(root, verb + r"\command", cmd)
        with winreg.CreateKeyEx(root, rf"{classes}\{ext}\OpenWithProgids", 0, winreg.KEY_WRITE) as k:
            winreg.SetValueEx(k, PROG_ID, 0, winreg.REG_NONE, b"")
    if notify:
        _notify()


def unregister(classes=CLASSES, root=winreg.HKEY_CURRENT_USER, notify=True):
    _delete_tree(root, rf"{classes}\Applications\{EXE_NAME}")
    _delete_tree(root, rf"{classes}\Applications\{LEGACY_EXE_NAME}")
    _delete_tree(root, rf"{classes}\{PROG_ID}")
    for ext in EXTENSIONS:
        _delete_tree(root, rf"{classes}\SystemFileAssociations\{ext}\shell\{APP_NAME}")
        try:
            with winreg.OpenKey(root, rf"{classes}\{ext}\OpenWithProgids", 0, winreg.KEY_WRITE) as k:
                winreg.DeleteValue(k, PROG_ID)
        except OSError:
            pass
    if classes == CLASSES:
        _delete_tree(root, rf"Software\{APP_NAME}")
        try:
            with winreg.OpenKey(root, r"Software\RegisteredApplications", 0, winreg.KEY_WRITE) as k:
                winreg.DeleteValue(k, APP_NAME)
        except OSError:
            pass
    if notify:
        _notify()


def ensure_registered():
    """설치본으로 실행 중일 때만, 아직 안 했거나 위치가 바뀌었으면 등록. 실패해도 재생에는 영향 없음."""
    if not getattr(sys, "frozen", False):
        return
    try:
        if not is_registered(sys.executable):
            register(sys.executable)
    except OSError:
        pass
