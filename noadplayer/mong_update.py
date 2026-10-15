"""몽 시리즈 공용 자동 업데이트 (파이썬판). 원본은 브랜딩\\앱연동\\mong_update.py, 파이썬 앱 패키지 안에 복사해 쓴다.

동작: 공개 배포 저장소(Bh-Nakh/mong-downloads)의 Release 에서 <앱ID>-latest.json 을 읽어 새 버전이 있는지 확인한다.
      토큰이 필요 없다(공개 주소). 받은 파일은 SHA-256 으로 확인한 뒤에만 적용한다.
latest.json 예:  {"version":"1.10","kind":"setup","file":"MongPlayer-Setup.exe","sha256":"...","note":"변경 내용"}
  kind = "exe"   : 받은 파일이 앱 본체(단일 exe). 실행 중인 exe 를 .old 로 바꾸고 새 파일을 그 자리에 둔 뒤 다시 시작한다.
  kind = "setup" : 받은 파일이 설치 프로그램(Inno Setup). 조용히 실행(/SILENT)해 설치한 뒤 앱을 다시 시작한다. (폴더형 앱은 이쪽)
시험용 환경변수: MONG_UPDATE_BASE=http://127.0.0.1:포트/  (기본 주소 대신 쓴다)

쓰는 법 (Qt 앱):
    from . import mong_update
    mong_update.cleanup_old()                                            # 앱 시작 때 한 번
    mong_update.check_at_startup(main_window, "mongplayer", "몽플레이어", VERSION)   # 창이 열린 뒤
    mong_update.check_now(main_window, "mongplayer", "몽플레이어", VERSION)          # 도움말 → 업데이트 확인
새 버전이 있으면 안내창을 띄우고, 사용자가 [예]를 눌러야 받는다. 받은 뒤 앱을 종료하고 새 버전으로 다시 시작한다.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import urllib.request

DEFAULT_BASE = "https://github.com/Bh-Nakh/mong-player/releases/latest/download/"

last_error = None          # 마지막 확인·받기 오류 문구 (성공하면 None)


def _base():
    e = os.environ.get("MONG_UPDATE_BASE")
    if not e:
        return DEFAULT_BASE
    return e if e.endswith("/") else e + "/"


def current_exe():
    return sys.executable


def cleanup_old(exe_path=None):
    """이전 업데이트가 남긴 .old 파일 정리. 앱 시작 때 한 번 호출한다."""
    try:
        old = (exe_path or current_exe()) + ".old"
        if os.path.exists(old):
            os.remove(old)
    except OSError:
        pass


def _parts(v):
    out = []
    for t in str(v or "").strip().lstrip("vV").split("."):
        m = re.match(r"\d+", t)
        out.append(int(m.group()) if m else 0)
    return out


def compare(a, b):
    """버전 비교 (1.10 > 1.9). a 가 크면 1, 같으면 0, 작으면 -1"""
    x, y = _parts(a), _parts(b)
    n = max(len(x), len(y))
    x += [0] * (n - len(x))
    y += [0] * (n - len(y))
    return (x > y) - (x < y)


def _request(url, timeout):
    return urllib.request.Request(url, headers={"User-Agent": "MongUpdate/1.0"})


def check(app_id, current_version):
    """새 버전 확인. (성공 여부, 정보 또는 None) 을 돌려준다. 새 버전이 없으면 (True, None), 오류면 (False, None)."""
    global last_error
    last_error = None
    try:
        with urllib.request.urlopen(_request(_base() + app_id + "-latest.json", 10), timeout=10) as r:
            data = json.loads(r.read().decode("utf-8-sig"))
        ver, file = data.get("version"), data.get("file")
        if not ver or not file:
            last_error = "업데이트 정보 형식이 올바르지 않습니다."
            return False, None
        if compare(ver, current_version) <= 0:
            return True, None
        info = {
            "app_id": app_id, "version": str(ver), "file": os.path.basename(str(file)),
            "kind": str(data.get("kind") or "exe").lower(),
            "sha256": str(data.get("sha256") or "").lower(),
            "note": str(data.get("note") or ""), "size": int(data.get("size") or 0),
        }
        info["url"] = _base() + info["file"]
        if len(info["sha256"]) != 64:
            last_error = "업데이트 정보에 올바른 해시가 없습니다."
            return False, None
        if info["kind"] not in ("exe", "setup"):
            last_error = "알 수 없는 업데이트 종류입니다: " + info["kind"]
            return False, None
        return True, info
    except Exception as e:                      # 인터넷 오류·형식 오류 모두
        last_error = str(e)
        return False, None


def download(info, progress=None):
    """새 파일을 임시 폴더에 받고 SHA-256 을 확인한다. 성공하면 받은 파일 경로, 실패하면 예외."""
    folder = os.path.join(tempfile.gettempdir(), "mong-update")
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, info["file"])
    if os.path.exists(dest):
        os.remove(dest)
    sha = hashlib.sha256()
    with urllib.request.urlopen(_request(info["url"], 30), timeout=30) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0) or info.get("size", 0)
        done, last = 0, -1
        while True:
            chunk = r.read(81920)
            if not chunk:
                break
            f.write(chunk)
            sha.update(chunk)
            done += len(chunk)
            if progress and total:
                pct = min(100, done * 100 // total)
                if pct != last:
                    last = pct
                    progress(pct)
    if sha.hexdigest() != info["sha256"]:
        try:
            os.remove(dest)
        except OSError:
            pass
        raise ValueError("받은 파일의 해시가 맞지 않아 업데이트를 취소했습니다.")
    return dest


def _run_detached(cmd_line):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    # 문자열 그대로 넘긴다 (목록으로 넘기면 따옴표가 변형되어 cmd 가 명령을 못 알아본다)
    subprocess.Popen('"%s" /c "%s"' % (os.environ.get("ComSpec", "cmd.exe"), cmd_line),
                     creationflags=flags, close_fds=True)


def apply(info, path, restart_args="", exe_path=None):
    """받은 파일을 적용하고 앱을 다시 시작하도록 예약한다. 호출한 쪽은 바로 앱을 종료해야 한다."""
    exe = exe_path or current_exe()
    args = (" " + restart_args) if restart_args else ""
    if info["kind"] == "setup":
        # 설치 프로그램을 조용히 실행(실행 중인 앱은 설치 프로그램이 닫는다) → 끝나면 앱 시작
        # 이 앱이 끝날 시간을 잠깐 준 뒤, 지금 설치된 폴더로 조용히 설치(남은 앱은 설치 프로그램이 닫는다) → 끝나면 앱 시작
        _run_detached('ping -n 3 127.0.0.1 >nul & "%s" /SILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS /DIR="%s" & start "" "%s"%s' % (path, os.path.dirname(exe), exe, args))
        return
    old = exe + ".old"                           # 실행 중인 exe 는 지울 수 없지만 이름은 바꿀 수 있다
    try:
        if os.path.exists(old):
            os.remove(old)
    except OSError:
        pass
    os.replace(exe, old)
    try:
        import shutil
        shutil.copyfile(path, exe)
    except Exception:
        try:
            os.replace(old, exe)                 # 실패하면 원래대로
        except OSError:
            pass
        raise
    _run_detached('ping -n 3 127.0.0.1 >nul & start "" "%s"%s' % (exe, args))


# ── Qt(PySide6) 화면 도우미 ─────────────────────────────────────────────

def _qt():
    from PySide6.QtCore import QObject, Qt, Signal
    from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog
    return QObject, Qt, Signal, QApplication, QMessageBox, QProgressDialog


_keep = []                                       # 시작한 도우미 객체를 살려 둔다


def _make_helper(parent, app_name, restart_args):
    QObject, Qt, Signal, QApplication, QMessageBox, QProgressDialog = _qt()

    class Helper(QObject):
        found = Signal(bool, object, str, bool)      # (확인 성공 여부, 정보, 오류, 결과를 항상 알릴지)
        progress = Signal(int)
        finished = Signal(object, str)               # (받은 파일 경로 또는 None, 오류)

        def __init__(self):
            super().__init__(parent)
            self._dlg = None
            self._info = None
            self.found.connect(self._on_found)
            self.progress.connect(self._on_progress)
            self.finished.connect(self._on_finished)

        def _on_found(self, ok, info, err, always):
            title = f"{app_name} 업데이트"
            if not ok:
                if always:
                    QMessageBox.warning(parent, title, "업데이트를 확인하지 못했습니다.\n\n" + err)
                return
            if info is None:
                if always:
                    QMessageBox.information(parent, title, "현재 최신 버전입니다.")
                return
            msg = f"{app_name} 새 버전 v{info['version']} 이(가) 있습니다."
            if info["note"]:
                msg += "\n\n" + info["note"]
            msg += "\n\n지금 업데이트할까요? (끝나면 자동으로 다시 시작합니다)"
            if QMessageBox.question(parent, title, msg) != QMessageBox.StandardButton.Yes:
                return
            self._info = info
            self._dlg = QProgressDialog("새 버전을 받는 중…", None, 0, 100, parent)
            self._dlg.setWindowTitle(title)
            self._dlg.setWindowModality(Qt.WindowModality.WindowModal)
            self._dlg.setMinimumDuration(0)
            self._dlg.setAutoClose(False)
            self._dlg.setAutoReset(False)
            self._dlg.show()

            def work():
                try:
                    path = download(info, lambda p: self.progress.emit(p))
                    self.finished.emit(path, "")
                except Exception as e:
                    self.finished.emit(None, str(e))
            threading.Thread(target=work, daemon=True).start()

        def _on_progress(self, pct):
            if self._dlg:
                self._dlg.setValue(pct)

        def _on_finished(self, path, err):
            if self._dlg:
                self._dlg.close()
            title = f"{app_name} 업데이트"
            if not path:
                QMessageBox.warning(parent, title, "업데이트를 받지 못했습니다.\n\n" + err)
                return
            try:
                apply(self._info, path, restart_args)
            except Exception as e:
                QMessageBox.warning(parent, title, "업데이트를 적용하지 못했습니다.\n\n" + str(e))
                return
            QApplication.quit()                  # 곧바로 새 버전이 다시 시작된다

    h = Helper()
    _keep.append(h)
    return h


def _check_in_thread(helper, app_id, current_version, always):
    def work():
        ok, info = check(app_id, current_version)
        helper.found.emit(ok, info, last_error or "", always)
    threading.Thread(target=work, daemon=True).start()


def check_at_startup(parent, app_id, app_name, current_version, restart_args=""):
    """앱을 실행할 때: 백그라운드로 확인해서 새 버전이 있을 때만 안내한다 (없거나 인터넷 오류면 조용히 넘어간다)."""
    _check_in_thread(_make_helper(parent, app_name, restart_args), app_id, current_version, False)


def check_now(parent, app_id, app_name, current_version, restart_args=""):
    """사용자가 메뉴·버튼을 눌렀을 때: 결과(새 버전 없음·오류 포함)를 항상 알려 준다."""
    _check_in_thread(_make_helper(parent, app_name, restart_args), app_id, current_version, True)
