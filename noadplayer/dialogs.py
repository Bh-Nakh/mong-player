import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFontComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton, QSlider, QSpinBox, QVBoxLayout)

from . import APP_NAME_KO, VERSION, addons, secret, stt, translate
from .filters import Filters
from .paths import FFMPEG, ROOT
from .worker import Worker

STT_LANGUAGES = [("ko", "한국어"), ("en", "영어"), ("ja", "일본어"), ("zh", "중국어"), ("auto", "자동 감지")]


def fmt_size(n):
    """바이트 → 'MB'/'GB' 글자 (내려받기 진행 표시용)."""
    return f"{n / 1e9:.2f}GB" if n >= 1e9 else f"{n / 1e6:.0f}MB"


def needed_addons(names):
    """아직 없는 추가 기능 → 안내 문구 (없으면 빈 글자). 예: '영상 처리 도구(ffmpeg) 약 45MB, …'"""
    todo = [n for n in names if not addons.present(n)]
    if not todo:
        return ""
    return ", ".join(f"{addons.label(n)} 약 {addons.approx_mb(n)}MB" for n in todo)


def ensure_addons(w: Worker, names):
    """작업 스레드에서: 없는 추가 기능을 받는다. 진행은 'download:<이름>' 메시지 + progress 시그널."""
    for n in names:
        if not addons.present(n):
            w.message.emit("download:" + addons.label(n))
        addons.ensure(n, lambda d, t: w.progress.emit(d, t), w.cancelled)


def _slider(lo, hi, val, on_change):
    s = QSlider(Qt.Horizontal)
    s.setRange(lo, hi)
    s.setValue(val)
    lab = QLabel(str(val))
    lab.setMinimumWidth(32)
    s.valueChanged.connect(lambda v: (lab.setText(str(v)), on_change()))
    row = QHBoxLayout()
    row.addWidget(s, 1)
    row.addWidget(lab)
    return s, row


class FilterDialog(QDialog):
    """화질 필터 — 바꾸는 즉시 적용 (창을 띄운 채로 재생 가능)."""

    def __init__(self, filters: Filters, on_apply, parent=None):
        super().__init__(parent)
        self.setWindowTitle("화질 필터")
        self.on_apply = on_apply
        self.f = filters
        form = QFormLayout()
        self.color = {}
        for key, label in (("brightness", "밝기"), ("contrast", "대비"), ("saturation", "채도"),
                           ("gamma", "감마"), ("hue", "색조")):
            self.color[key], row = _slider(-100, 100, getattr(filters, key), self._changed)
            form.addRow(label, row)
        self.sharpen, row = _slider(0, 10, filters.sharpen, self._changed)
        form.addRow("샤프닝", row)
        self.blur, row = _slider(0, 10, filters.blur, self._changed)
        form.addRow("블러", row)
        self.denoise = QComboBox()
        self.denoise.addItems(["끔", "약하게", "보통", "강하게"])
        self.denoise.setCurrentIndex(filters.denoise)
        self.denoise.currentIndexChanged.connect(self._changed)
        form.addRow("노이즈 제거", self.denoise)
        self.rotate = QComboBox()
        self.rotate.addItems(["0°", "90°", "180°", "270°"])
        self.rotate.setCurrentIndex(filters.rotate // 90)
        self.rotate.currentIndexChanged.connect(self._changed)
        form.addRow("회전", self.rotate)
        flips = QHBoxLayout()
        self.hflip = QCheckBox("좌우 반전")
        self.vflip = QCheckBox("상하 반전")
        for c, v in ((self.hflip, filters.hflip), (self.vflip, filters.vflip)):
            c.setChecked(v)
            c.toggled.connect(self._changed)
            flips.addWidget(c)
        form.addRow("반전", flips)
        note = QLabel("모든 필터는 그래픽카드에서 처리합니다. 화면 캡처는 필터 적용 전 원본 화면으로 저장됩니다.")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray")
        reset = QPushButton("모두 초기화")
        reset.clicked.connect(self.reset)
        close = QPushButton("닫기")
        close.clicked.connect(self.close)
        btns = QHBoxLayout()
        btns.addWidget(reset)
        btns.addStretch(1)
        btns.addWidget(close)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(note)
        lay.addLayout(btns)
        self.resize(420, self.sizeHint().height())

    def _changed(self, *_):
        f = Filters(**{k: s.value() for k, s in self.color.items()}, sharpen=self.sharpen.value(),
                    blur=self.blur.value(), denoise=self.denoise.currentIndex(),
                    rotate=self.rotate.currentIndex() * 90, hflip=self.hflip.isChecked(),
                    vflip=self.vflip.isChecked())
        self.f = f
        self.on_apply(f)

    def reset(self):
        d = Filters()
        for w in (*self.color.values(), self.sharpen, self.blur, self.denoise, self.rotate, self.hflip, self.vflip):
            w.blockSignals(True)
        for k, s in self.color.items():
            s.setValue(0)
        self.sharpen.setValue(0)
        self.blur.setValue(0)
        self.denoise.setCurrentIndex(0)
        self.rotate.setCurrentIndex(0)
        self.hflip.setChecked(False)
        self.vflip.setChecked(False)
        for w in (*self.color.values(), self.sharpen, self.blur, self.denoise, self.rotate, self.hflip, self.vflip):
            w.blockSignals(False)
        self.f = d
        self.on_apply(d)


class ColorButton(QPushButton):
    def __init__(self, color, on_change):
        super().__init__()
        self.on_change = on_change
        self.set_color(color)
        self.clicked.connect(self._pick)

    def set_color(self, color):
        self.color = color
        self.setStyleSheet(f"background:{color}; min-width:48px; min-height:20px")

    def _pick(self):
        c = QColorDialog.getColor(QColor(self.color), self, "색 고르기")
        if c.isValid():
            self.set_color(c.name())
            self.on_change()


class SubtitleStyleDialog(QDialog):
    """자막 모양 — 바꾸는 즉시 적용, 설정에 저장."""

    def __init__(self, style: dict, on_apply, parent=None):
        super().__init__(parent)
        self.setWindowTitle("자막 모양")
        self.style = dict(style)
        self.on_apply = on_apply
        form = QFormLayout()
        self.font = QFontComboBox()
        self.font.setCurrentText(style["font"])
        self.font.currentTextChanged.connect(self._changed)
        form.addRow("글꼴", self.font)
        self.size = QSpinBox()
        self.size.setRange(10, 150)
        self.size.setValue(style["size"])
        self.size.valueChanged.connect(self._changed)
        form.addRow("크기", self.size)
        self.bold = QCheckBox("굵게")
        self.bold.setChecked(style["bold"])
        self.bold.toggled.connect(self._changed)
        form.addRow("", self.bold)
        self.color = ColorButton(style["color"], self._changed)
        form.addRow("글자 색", self.color)
        self.border_color = ColorButton(style["border_color"], self._changed)
        form.addRow("테두리 색", self.border_color)
        self.border = QDoubleSpinBox()
        self.border.setRange(0, 10)
        self.border.setSingleStep(0.5)
        self.border.setValue(style["border_size"])
        self.border.valueChanged.connect(self._changed)
        form.addRow("테두리 두께", self.border)
        self.pos, row = _slider(0, 100, style["pos"], self._changed)
        form.addRow("세로 위치 (%)", row)
        self.override = QCheckBox("ASS/SSA 자막에도 이 모양 적용")
        self.override.setChecked(style["override_ass"])
        self.override.toggled.connect(self._changed)
        form.addRow("", self.override)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.close)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(close)

    def _changed(self, *_):
        self.style.update(font=self.font.currentText(), size=self.size.value(), bold=self.bold.isChecked(),
                          color=self.color.color, border_color=self.border_color.color,
                          border_size=self.border.value(), pos=self.pos.value(),
                          override_ass=self.override.isChecked())
        self.on_apply(self.style)


class SttDialog(QDialog):
    """AI 자막 만들기 — 필요한 추가 기능·모델이 없으면 먼저 내려받고(처음 한 번), 음성 인식 후 SRT 를 돌려준다."""
    ADDONS = ("ffmpeg", "stt")

    def __init__(self, media_path, language, auto_translate=True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 자막 만들기")
        self.translate_check = QCheckBox("자막이 한국어가 아니면 이어서 한국어로 번역")
        self.translate_check.setChecked(auto_translate)
        self.media = media_path
        self.result = None
        self.worker = None
        self.lang = QComboBox()
        for code, name in STT_LANGUAGES:
            self.lang.addItem(name, code)
        self.lang.setCurrentIndex(max(0, self.lang.findData(language)))
        has_gpu, gpu_ready = stt.gpu.has_nvidia_gpu(), stt.gpu.installed()
        device = ("GPU (빠름)" if has_gpu and gpu_ready else
                  "NVIDIA GPU 있음" if has_gpu else "CPU (NVIDIA GPU 가 없어 시간이 걸립니다)")
        info = QLabel(f"파일: {os.path.basename(media_path)}\n처리 장치: {device}")
        todo = []
        if needed_addons(self.ADDONS):
            todo.append(needed_addons(self.ADDONS))
        if not stt.model.installed():
            todo.append(f"자막 모델 {stt.model.TOTAL / 1e9:.1f}GB")
        if todo:
            info.setText(info.text() + "\n\n처음 한 번 내려받습니다: " + ", ".join(todo))
            info.setWordWrap(True)
        self.gpu_check = QCheckBox(f"GPU 가속 구성요소도 받기 ({stt.gpu.WHEEL_SIZE / 1e9:.2f}GB, 처음 한 번) — "
                                   "자막을 훨씬 빨리 만듭니다")
        self.gpu_check.setChecked(True)
        self.gpu_check.setVisible(has_gpu and not gpu_ready)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        self.status = QLabel("준비")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(80)
        self.log.hide()
        self.start_btn = QPushButton("시작")
        self.start_btn.clicked.connect(self.start)
        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.clicked.connect(self.cancel)
        row = QHBoxLayout()
        row.addWidget(QLabel("언어"))
        row.addWidget(self.lang, 1)
        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.start_btn)
        btns.addWidget(self.cancel_btn)
        lay = QVBoxLayout(self)
        lay.addWidget(info)
        lay.addWidget(self.gpu_check)
        lay.addLayout(row)
        lay.addWidget(self.translate_check)
        lay.addWidget(self.bar)
        lay.addWidget(self.status)
        lay.addWidget(self.log)
        lay.addLayout(btns)
        self.resize(440, self.sizeHint().height())

    @property
    def language(self):
        return self.lang.currentData()

    def _job(self, w: Worker):
        report = lambda d, t: w.progress.emit(d, t)  # noqa: E731
        ensure_addons(w, self.ADDONS)
        if not stt.model.installed():
            w.message.emit("download:자막 모델")
            stt.model.download(report, w.cancelled)
        if self.want_gpu and not stt.gpu.installed():
            w.message.emit("download:GPU 가속 구성요소")
            stt.gpu.download(report, w.cancelled)
        w.message.emit("transcribe")
        return stt.transcribe(self.media, FFMPEG, self.language, device=None if self.want_gpu else "cpu",
                              progress=report, cancelled=w.cancelled, log=lambda m: w.message.emit("log:" + m))

    def start(self):
        self.want_gpu = stt.gpu.has_nvidia_gpu() and (stt.gpu.installed() or self.gpu_check.isChecked())
        self.start_btn.setEnabled(False)
        self.lang.setEnabled(False)
        self.gpu_check.setEnabled(False)
        self.phase = ""
        self.status.setText("오디오 준비 중…")
        self.worker = Worker(self._job, self)
        self.worker.progress.connect(self._progress)
        self.worker.message.connect(self._message)
        self.worker.done.connect(self._done)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _message(self, m):
        if m.startswith("log:"):
            self.log.show()
            self.log.appendPlainText(m[4:])
            return
        self.phase = m
        self.bar.setValue(0)
        self.status.setText(f"{m[9:]} 내려받는 중…" if m.startswith("download:") else "음성 인식 중…")

    def _progress(self, done, total):
        if total > 0:
            self.bar.setValue(int(done / total * 1000))
            if self.phase.startswith("download:"):
                self.status.setText(f"{self.phase[9:]} 내려받는 중… {fmt_size(done)} / {fmt_size(total)}")
            else:
                self.status.setText(f"음성 인식 중… {int(done) // 60}:{int(done) % 60:02d} / "
                                    f"{int(total) // 60}:{int(total) % 60:02d}")

    def _done(self, r):
        self.result = r
        self.accept()

    def _failed(self, msg):
        if msg:
            QMessageBox.warning(self, "AI 자막", f"자막을 만들지 못했습니다.\n\n{msg}")
        self.reject()

    def cancel(self):
        if self.worker and self.worker.isRunning():
            self.status.setText("취소하는 중…")
            self.cancel_btn.setEnabled(False)
            self.worker.cancel()
        else:
            self.reject()

    def closeEvent(self, e):
        if self.worker and self.worker.isRunning():
            self.cancel()
            e.ignore()
        else:
            super().closeEvent(e)


class TranslateSettingsDialog(QDialog):
    """온라인 번역용 본인 API 키 — Windows 계정 단위로 암호화해 저장."""
    SIGNUP = {"deepl": "https://www.deepl.com/pro-api", "google": "https://cloud.google.com/translate",
              "azure": "https://azure.microsoft.com/products/ai-services/ai-translator"}

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("번역 설정")
        self.settings = settings
        form = QFormLayout()
        self.keys = {}
        for name, label in (("deepl", "DeepL"), ("google", "Google"), ("azure", "Microsoft")):
            e = QLineEdit(translate.api_key(settings, name))
            e.setEchoMode(QLineEdit.Password)
            e.setPlaceholderText("API 키 (비워 두면 사용 안 함)")
            self.keys[name] = e
            hint = QLabel(f"{translate.FREE_QUOTA[name]} · 가입: <a href='{self.SIGNUP[name]}'>{self.SIGNUP[name]}</a>")
            hint.setOpenExternalLinks(True)
            hint.setStyleSheet("color: gray")
            form.addRow(label, e)
            form.addRow("", hint)
        self.region = QLineEdit(settings["api_keys"].get("azure_region", ""))
        self.region.setPlaceholderText("예: koreacentral (Azure 리소스의 지역)")
        form.addRow("Microsoft 지역", self.region)
        show = QCheckBox("키 보이기")
        show.toggled.connect(lambda on: [e.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password)
                                         for e in self.keys.values()])
        note = QLabel("키는 이 PC 의 Windows 계정으로 암호화해 저장합니다. 온라인 번역을 쓰면 자막 내용이 "
                      "해당 회사 서버로 전송됩니다.")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray")
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(show)
        lay.addWidget(note)
        lay.addWidget(btns)
        self.resize(560, self.sizeHint().height())

    def _save(self):
        ak = self.settings["api_keys"]
        for name, e in self.keys.items():
            ak[name] = secret.protect(e.text().strip())
        ak["azure_region"] = self.region.text().strip()
        self.settings.save()
        self.accept()


class TranslateDialog(QDialog):
    """자막 → 한국어 SRT. 내 PC 번역은 처음 한 번 번역 모델을 내려받는다."""

    def __init__(self, src, out_path, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("자막 한국어로 번역")
        self.src, self.out_path, self.settings = src, out_path, settings
        self.count = 0
        self.worker = None
        self.engine_box = QComboBox()
        self.engine_box.currentIndexChanged.connect(self._engine_changed)
        setup = QPushButton("번역 설정…")
        setup.clicked.connect(self._open_settings)
        row = QHBoxLayout()
        row.addWidget(QLabel("번역 방법"))
        row.addWidget(self.engine_box, 1)
        row.addWidget(setup)
        info = QLabel(f"번역할 자막: {src['title']}\n저장: {os.path.basename(out_path)}")
        info.setWordWrap(True)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color: gray")
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        self.status = QLabel("준비")
        self.start_btn = QPushButton("번역 시작")
        self.start_btn.clicked.connect(self.start)
        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.clicked.connect(self.cancel)
        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.start_btn)
        btns.addWidget(self.cancel_btn)
        lay = QVBoxLayout(self)
        lay.addWidget(info)
        lay.addLayout(row)
        lay.addWidget(self.note)
        lay.addWidget(self.bar)
        lay.addWidget(self.status)
        lay.addLayout(btns)
        self._fill_engines()
        self.resize(500, self.sizeHint().height())

    def _fill_engines(self):
        want = self.settings["translate_engine"]
        self.engine_box.blockSignals(True)
        self.engine_box.clear()
        for code, label in translate.ENGINES:
            ok = code == "local" or translate.has_key(self.settings, code)
            self.engine_box.addItem(label if ok else f"{label} — 키 없음", code)
            self.engine_box.model().item(self.engine_box.count() - 1).setEnabled(ok)
        i = self.engine_box.findData(want)
        self.engine_box.setCurrentIndex(i if i >= 0 and self.engine_box.model().item(i).isEnabled() else 0)
        self.engine_box.blockSignals(False)
        self._engine_changed()

    def _engine_changed(self, *_):
        code = self.engine_box.currentData()
        if code == "local":
            txt = "내 PC 에서 번역합니다 (인터넷으로 보내지 않음, 무료)."
            todo = [needed_addons(self._addons_for(code))] if needed_addons(self._addons_for(code)) else []
            if not translate.model.installed():
                todo.append(f"번역 모델 {translate.model.SIZE / 1e9:.2f}GB")
            if todo:
                txt += " 처음 한 번 내려받습니다: " + ", ".join(todo)
        else:
            txt = f"본인 API 키로 온라인 번역합니다 ({translate.FREE_QUOTA[code]}). 자막 내용이 외부로 전송됩니다."
            if needed_addons(self._addons_for(code)):
                txt += f" 처음 한 번 {needed_addons(self._addons_for(code))}을(를) 내려받습니다."
        self.note.setText(txt)

    @staticmethod
    def _addons_for(code):
        """자막을 읽는 데 ffmpeg 가 늘 필요하고, 내 PC 번역은 번역 엔진도 필요하다."""
        return ("ffmpeg", "llama") if code == "local" else ("ffmpeg",)

    def _open_settings(self):
        if TranslateSettingsDialog(self.settings, self).exec():
            self._fill_engines()

    def _job(self, w: Worker):
        code = self.code
        report = lambda d, t: w.progress.emit(d, t)  # noqa: E731
        ensure_addons(w, self._addons_for(code))
        if code == "local" and not translate.model.installed():
            w.message.emit("download:번역 모델")
            translate.model.download(report, w.cancelled)
        w.message.emit("translate")
        engine = translate.make_engine(code, self.settings, log=lambda m: w.message.emit("log:" + m))
        return translate.translate_subtitle(self.src, self.out_path, engine, FFMPEG, report, w.cancelled)

    def start(self):
        self.code = self.engine_box.currentData()
        self.settings["translate_engine"] = self.code
        self.phase = ""
        for wdg in (self.start_btn, self.engine_box):
            wdg.setEnabled(False)
        self.status.setText("자막 읽는 중…")
        self.worker = Worker(self._job, self)
        self.worker.progress.connect(self._progress)
        self.worker.message.connect(self._message)
        self.worker.done.connect(self._done)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _message(self, m):
        if m.startswith("log:"):
            self.status.setText(m[4:])
            return
        self.phase = m
        self.bar.setValue(0)
        self.status.setText(f"{m[9:]} 내려받는 중…" if m.startswith("download:") else "번역 준비 중…")

    def _progress(self, done, total):
        if total > 0:
            self.bar.setValue(int(done / total * 1000))
            self.status.setText(f"{self.phase[9:]} 내려받는 중… {fmt_size(done)} / {fmt_size(total)}"
                                if self.phase.startswith("download:") else f"번역 중… {int(done)} / {int(total)}줄")

    def _done(self, n):
        self.count = n
        self.accept()

    def _failed(self, msg):
        if msg == "AlreadyKorean":
            QMessageBox.information(self, "자막 번역", "이미 한국어 자막입니다.")
        elif msg:
            QMessageBox.warning(self, "자막 번역", f"번역하지 못했습니다.\n\n{msg}")
        self.reject()

    def cancel(self):
        if self.worker and self.worker.isRunning():
            self.status.setText("취소하는 중…")
            self.cancel_btn.setEnabled(False)
            self.worker.cancel()
        else:
            self.reject()

    def closeEvent(self, e):
        if self.worker and self.worker.isRunning():
            self.cancel()
            e.ignore()
        else:
            super().closeEvent(e)


def show_about(parent):
    lic = os.path.join(ROOT, "THIRD_PARTY_LICENSES.txt")
    QMessageBox.about(parent, f"{APP_NAME_KO} 정보",
                      f"<b>{APP_NAME_KO}</b> {VERSION}<br><br>광고 없는 동영상 플레이어<br><br>"
                      "사용한 오픈소스: mpv(LGPL), FFmpeg(LGPL), Qt/PySide6(LGPL), "
                      "faster-whisper·CTranslate2(MIT), Whisper 모델(MIT), llama.cpp(MIT), "
                      "Tencent Hy-MT2 번역 모델(Apache-2.0)<br>"
                      f"라이선스 전문: {lic}<br><br>"
                      "저작권으로 보호되는 콘텐츠를 캡처·배포할 책임은 사용자에게 있습니다.")


SEEK_KEYS = (("normal", "왼쪽/오른쪽 방향키:"), ("ctrl", "Ctrl + 왼쪽/오른쪽 방향키:"),
             ("shift", "Shift + 왼쪽/오른쪽 방향키:"), ("ctrl_alt", "Ctrl + Alt + 왼쪽/오른쪽 방향키:"))
SEEK_DEFAULTS = {"normal": 3, "ctrl": 1, "shift": 60, "ctrl_alt": 300}


class SeekStepsDialog(QDialog):
    """방향키로 재생 위치를 옮길 때의 시간(초). 값을 바꾸는 즉시 저장·적용한다."""

    def __init__(self, settings, on_change, parent=None):
        super().__init__(parent)
        self.setWindowTitle("이동 시간 설정")
        self.settings, self.on_change = settings, on_change
        self.spins = {}
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("재생 시 이동할 시간의 단위를 설정할 수 있습니다."))
        for key, label in SEEK_KEYS:
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(QLabel(label))
            sp = QSpinBox()
            sp.setRange(1, 36000)
            sp.setValue(int(settings["seek_steps"].get(key, SEEK_DEFAULTS[key])))
            sp.setMinimumWidth(70)
            sp.valueChanged.connect(lambda _v, k=key: self._changed(k))
            self.spins[key] = sp
            row.addWidget(sp)
            row.addWidget(QLabel("초"))
            reset = QPushButton("기본값")
            reset.clicked.connect(lambda _c=False, k=key: self.spins[k].setValue(SEEK_DEFAULTS[k]))
            row.addWidget(reset)
            lay.addLayout(row)
        close = QPushButton("닫기")
        close.clicked.connect(self.accept)
        lay.addWidget(close, 0, Qt.AlignRight)

    def _changed(self, key):
        steps = dict(self.settings["seek_steps"])
        steps[key] = self.spins[key].value()
        self.settings["seek_steps"] = steps                   # 바뀌는 즉시 저장
        self.on_change()
