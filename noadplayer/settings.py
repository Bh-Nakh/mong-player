"""설정 저장 (%LOCALAPPDATA%\\NoAdPlayer\\settings.json)."""
import copy
import json
import os
import threading

from .paths import SETTINGS

DEFAULTS = {
    "volume": 80,
    "muted": False,
    "last_dir": "",
    "recent": [],
    "subtitle": {
        "font": "맑은 고딕",
        "size": 46,
        "color": "#FFFFFF",
        "border_color": "#000000",
        "border_size": 3.0,
        "pos": 95,                  # 화면 위에서부터 % (100 = 맨 아래)
        "bold": True,
        "override_ass": False,      # ASS 자막에도 위 모양을 강제로 적용
    },
    "playlist_visible": True,
    "auto_next": True,
    "stt_language": "ko",
    "stt_auto_translate": True,         # AI 자막이 한국어가 아니면 이어서 번역
    "translate_engine": "local",
    "api_keys": {"deepl": "", "google": "", "azure": "", "azure_region": ""},   # 키는 DPAPI 암호화 값
    "audio_format": "mp3",
    "playlist_sort": "name",        # name / name_desc 이름순 / date / date_desc 날짜순 (_desc = 내림차순)
    "shift_delete_files": True,     # 재생 목록에서 Shift+Delete → 실제 파일도 휴지통으로
    "shift_delete_confirm": True,   # 위 동작 전에 확인창을 띄움 ("다시 묻지 않기"를 체크하면 False)
    "resume": {},                   # 이어 보기 위치 {파일 경로: 초}
    "sub_visible": True,
    "seek_steps": {"normal": 3, "ctrl": 1, "shift": 60, "ctrl_alt": 300},   # 방향키 이동 시간(초)
    "hq_scale": True,               # 고화질 확대/축소 (선명하게)
    "auto_update": True,            # 시작할 때 새 버전 확인
    "filters": {},                  # 화질 필터 값 (비면 기본)
}
RECENT_MAX = 10
RESUME_MAX = 200


class Settings(dict):
    def __init__(self, path=SETTINGS):
        super().__init__(copy.deepcopy(DEFAULTS))
        self.path = path
        self._lock = threading.Lock()
        self._timer = None
        try:
            with open(path, encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError):
            saved = {}
        for k, v in saved.items():
            if isinstance(v, dict) and isinstance(self.get(k), dict):
                self[k].update(v)
            else:
                dict.__setitem__(self, k, v)

    def __setitem__(self, key, value):
        changed = key not in self or self[key] != value
        super().__setitem__(key, value)
        if changed:
            self.save_soon()

    def save_soon(self, delay=0.25):
        """옵션이 바뀌면 곧바로(짧게 모아서) 저장한다 — 슬라이더를 끄는 동안 디스크를 매번 쓰지 않게."""
        with self._lock:
            if self._timer is None:
                self._timer = threading.Timer(delay, self._flush)
                self._timer.daemon = True
                self._timer.start()

    def _flush(self):
        with self._lock:
            self._timer = None
        try:
            self.save()
        except OSError:
            pass

    def add_recent(self, path):
        self["recent"] = [path] + [p for p in self["recent"] if p != path][:RECENT_MAX - 1]

    def set_resume(self, path, pos):
        """이어 보기 위치를 기억한다 (pos=None 이면 지움). 최근 RESUME_MAX 개까지만 남긴다."""
        r = dict(self["resume"])
        r.pop(path, None)
        if pos is not None:
            r[path] = round(pos, 1)
        while len(r) > RESUME_MAX:
            r.pop(next(iter(r)))
        self["resume"] = r

    def save(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dict(self), f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)
