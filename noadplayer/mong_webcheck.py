"""몽 시리즈 공용: 웹페이지가 "이 앱이 설치·실행 중인가?"를 확인할 수 있게 해 주는 작은 로컬 서버.

- 127.0.0.1 에서만 듣는다 (외부 접속 불가). 관리자 권한 불필요.
- GET /ping -> {"app":"mongplayer","name":"몽Player","version":"1.0.0"}
- 허용 Origin: 로컬(localhost·127.0.0.1) 페이지 + 실행 파일 옆 webcheck_origins.txt 에 적은 주소(한 줄에 하나)
- 웹에서 앱을 깨울 수 있게 사용자 영역(HKCU)에 <id>:// 프로토콜을 등록한다 (설치본(frozen)일 때만).
원본은 브랜딩\\앱연동\\mong_webcheck.py. 파이썬 앱 패키지 안에 같은 파일을 복사해 쓴다.
환경변수(시험용): MONG_WEBCHECK_PORTS=포트,포트  MONG_WEBCHECK_NOREG=1 (프로토콜 등록 안 함)
"""
import json
import os
import socket
import sys
import threading
from urllib.parse import urlparse

_started = False
# 설치 확인 페이지가 올라간 공식 주소 (이 주소의 페이지만 허용). 정확히 일치해야 한다.
_extra_origins = ["https://mongtools.pages.dev"]


def _origins_file():
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.join(base, "webcheck_origins.txt")


def _load_origins():
    try:
        with open(_origins_file(), encoding="utf-8-sig") as f:
            for line in f:
                s = line.strip().rstrip("/").lower()
                if s and not s.startswith("#"):
                    _extra_origins.append(s)
    except OSError:
        pass


def _origin_allowed(origin):
    if not origin:
        return True                      # 브라우저가 아닌 직접 호출
    o = origin.strip().rstrip("/").lower()
    if o in _extra_origins:
        return True
    u = urlparse(o)
    return u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1", "::1")


def _register_protocol(app_id, name):
    if not getattr(sys, "frozen", False):          # 개발 실행(python.exe)을 등록하지 않는다
        return
    import winreg
    cmd = '"%s"' % sys.executable
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\%s" % app_id) as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "URL:" + name)
        winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(k, r"shell\open\command") as c:
            winreg.SetValueEx(c, "", 0, winreg.REG_SZ, cmd)


def _handle(conn, app_id, name, version):
    try:
        conn.settimeout(2)
        data = b""
        while b"\r\n\r\n" not in data and len(data) < 8192:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
        lines = data.decode("latin-1").split("\r\n")
        first = lines[0].split(" ")
        method = first[0] if first else ""
        path = (first[1] if len(first) > 1 else "").split("?")[0]
        origin, pna = None, False
        for ln in lines[1:]:
            if ":" not in ln:
                continue
            h, v = ln.split(":", 1)
            h = h.strip().lower()
            if h == "origin":
                origin = v.strip()
            elif h == "access-control-request-private-network":
                pna = True
        if not _origin_allowed(origin):
            status, body = 403, {"error": "origin"}
        elif method == "OPTIONS":
            status, body = 204, None
        elif method == "GET" and path == "/ping":
            status, body = 200, {"app": app_id, "name": name, "version": version}
        else:
            status, body = 404, {"error": "not found"}
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else b""
        reason = {200: "OK", 204: "No Content", 403: "Forbidden", 404: "Not Found"}[status]
        head = ["HTTP/1.1 %d %s" % (status, reason)]
        if status != 403 and origin:
            head += ["Access-Control-Allow-Origin: " + origin, "Vary: Origin",
                     "Access-Control-Allow-Methods: GET, OPTIONS", "Access-Control-Allow-Headers: *"]
            if pna:
                head.append("Access-Control-Allow-Private-Network: true")
        head += ["Cache-Control: no-store", "Content-Type: application/json; charset=utf-8",
                 "Content-Length: %d" % len(payload), "Connection: close", "", ""]
        conn.sendall("\r\n".join(head).encode("latin-1") + payload)
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except OSError:
            pass


def start(app_id, name, ports, version=""):
    """메인 창을 띄우기 직전에 한 번 호출한다. 실패해도 앱 동작에는 영향이 없다."""
    global _started
    try:
        if _started:
            return
        _load_origins()
        env_ports = os.environ.get("MONG_WEBCHECK_PORTS")
        if env_ports:
            ports = [int(p) for p in env_ports.split(",") if p.strip().isdigit()]
        if os.environ.get("MONG_WEBCHECK_NOREG") != "1":
            try:
                _register_protocol(app_id, name)
            except Exception:
                pass
        srv = None
        for port in ports:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)   # 포트 가로채기 방지
                s.bind(("127.0.0.1", port))
                s.listen(8)
                srv = s
                break
            except OSError:
                s.close()
        if srv is None:
            return

        def loop():
            while True:
                try:
                    conn, _ = srv.accept()
                except OSError:
                    return
                threading.Thread(target=_handle, args=(conn, app_id, name, version), daemon=True).start()

        threading.Thread(target=loop, daemon=True, name="MongWebCheck").start()
        _started = True
    except Exception:
        pass
