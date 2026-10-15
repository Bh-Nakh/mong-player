from PySide6.QtCore import QThread, Signal

from .stt.download import Cancelled


class Worker(QThread):
    """fn(worker) 를 작업 스레드에서 실행. 진행·결과는 시그널로 UI 스레드에 전달."""
    progress = Signal(float, float)
    message = Signal(str)
    done = Signal(object)
    failed = Signal(str)          # 빈 문자열 = 취소

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def cancelled(self):
        return self._cancel

    def run(self):
        try:
            r = self.fn(self)
        except Cancelled:
            self.failed.emit("")
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e) or type(e).__name__)
        else:
            self.done.emit(r)
