"""내 PC 번역 — llama.cpp(llama-server) + Tencent Hy-MT2 1.8B.

번역할 때만 서버를 127.0.0.1 빈 포트로 띄우고 끝나면 내린다. 앱이 비정상 종료돼도 서버가 남지 않게
Windows 작업 개체(KILL_ON_JOB_CLOSE)에 묶는다.
지시문은 모델 공식 README 의 '구분자 유지'·'배경 정보' 형식을 그대로 쓴다.
"""
import ctypes
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from ctypes import wintypes

from ..paths import DATA, LLAMA_SERVER
from ..stt.download import Cancelled
from . import model

SERVER = LLAMA_SERVER                                        # 처음 쓸 때 받는 'llama' 추가 기능 (noadplayer/addons.py)
LOG = os.path.join(DATA, "logs", "llama-server.log")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
BATCH = 12                   # 한 번에 번역할 자막 줄 수
CONTEXT = 3                  # 한 줄씩 다시 번역할 때 넣는 앞 대사 수
DELIM = "|||"
TARGET = "Korean"
# 모델 카드 권장 샘플링 값
SAMPLING = {"temperature": 0.7, "top_p": 0.6, "top_k": 20, "repeat_penalty": 1.05}

PROMPT_DELIM = ("Please accurately translate the following text into {lang}.\n"
                "You must retain the exact same number of delimiters in the translation. Strictly do not omit, "
                "escape, or translate these symbols, and pay close attention to their placement.\n\n{text}")
PROMPT_CONTEXT = ("[Background Information]\n{context}\n\n"
                  "Please translate the following text into {lang}, taking the provided background information "
                  "into consideration.\n\n[Source Text]\n{text}")
PROMPT_PLAIN = ("Translate the following text into {lang}. Note that you should only output the translated result "
                "without any additional explanation:\n\n{text}")


# ───────────────────────── 작업 개체 (부모가 죽으면 자식도 정리) ─────────────────────────
class _JobLimit(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD)]


class _JobExtLimit(ctypes.Structure):
    _fields_ = [("Basic", _JobLimit), ("IoInfo", ctypes.c_uint64 * 6),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.CreateJobObjectW.restype = wintypes.HANDLE
_k32.OpenProcess.restype = wintypes.HANDLE
_job = None


def _attach_to_job(pid):
    global _job
    if _job is None:
        _job = _k32.CreateJobObjectW(None, None)
        info = _JobExtLimit()
        info.Basic.LimitFlags = 0x2000                      # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        _k32.SetInformationJobObject(wintypes.HANDLE(_job), 9, ctypes.byref(info), ctypes.sizeof(info))
    h = _k32.OpenProcess(0x0101, False, pid)                # PROCESS_SET_QUOTA | PROCESS_TERMINATE
    if h:
        _k32.AssignProcessToJobObject(wintypes.HANDLE(_job), wintypes.HANDLE(h))
        _k32.CloseHandle(wintypes.HANDLE(h))


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LocalTranslator:
    name = "내 PC (Hy-MT2)"

    def __init__(self, log=print):
        self.log = log
        self.proc = None
        self.port = None
        self.device = ""

    # ── 서버 ──
    def start(self, cancelled=lambda: False):
        if not model.installed():
            raise RuntimeError("번역 모델이 설치되지 않았습니다.")
        for gpu in (True, False):                            # GPU(Vulkan) 로 먼저, 안 되면 CPU
            if self._launch(gpu, cancelled):
                self.device = "GPU" if gpu else "CPU"
                return
            self.log("GPU 로 번역 엔진을 띄우지 못해 CPU 로 다시 시도합니다.")
        raise RuntimeError(f"번역 엔진을 시작하지 못했습니다. 기록: {LOG}")

    def _launch(self, gpu, cancelled):
        self.port = _free_port()
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        cmd = [SERVER, "-m", model.PATH, "--host", "127.0.0.1", "--port", str(self.port), "-c", "4096",
               "-ngl", "99" if gpu else "0", "--no-webui"]
        logf = open(LOG, "w", encoding="utf-8")
        try:
            self.proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                         cwd=os.path.dirname(SERVER), creationflags=NO_WINDOW)
        finally:
            logf.close()
        _attach_to_job(self.proc.pid)
        t = time.time()
        while time.time() - t < 120:
            if cancelled():
                self.stop()
                raise Cancelled()
            if self.proc.poll() is not None:
                return False
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=2) as r:
                    if r.status == 200:
                        return True
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(0.3)
        self.stop()
        return False

    def stop(self):
        """서버 내리기. llama-server 는 Ctrl+C 외의 종료 신호를 받지 않아 프로세스를 끝내고 기다린다
        (읽기 전용으로 모델만 열고 있어 남는 파일·데이터는 없다)."""
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                pass
        self.proc = None

    # ── 번역 ──
    def _ask(self, prompt, max_tokens):
        body = json.dumps({"messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
                           "stream": False, **SAMPLING}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/chat/completions", body,
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)["choices"][0]["message"]["content"].strip()

    def _batch(self, lines):
        text = f" {DELIM} ".join(lines)
        out = self._ask(PROMPT_DELIM.format(lang=TARGET, text=text), max_tokens=len(text) * 3 + 64)
        parts = [p.strip() for p in out.split(DELIM)]
        return parts if len(parts) == len(lines) and all(parts) else None

    def _single(self, line, context):
        if context:
            prompt = PROMPT_CONTEXT.format(context="\n".join(context), lang=TARGET, text=line)
        else:
            prompt = PROMPT_PLAIN.format(lang=TARGET, text=line)
        return self._ask(prompt, max_tokens=len(line) * 4 + 64)

    def translate(self, lines, progress=lambda done, total: None, cancelled=lambda: False):
        """[원문 한 줄] → [번역]. 여러 줄 대사는 미리 한 줄로 합쳐서 넘긴다."""
        out = []
        for i in range(0, len(lines), BATCH):
            if cancelled():
                raise Cancelled()
            chunk = lines[i:i + BATCH]
            res = self._batch(chunk)
            if res is None:                                   # 구분자 수가 어긋남 → 이 묶음만 한 줄씩
                res = []
                for j, line in enumerate(chunk):
                    if cancelled():
                        raise Cancelled()
                    res.append(self._single(line, lines[max(0, i + j - CONTEXT):i + j]))
            out += res
            progress(len(out), len(lines))
        return out

    def close(self):
        self.stop()
