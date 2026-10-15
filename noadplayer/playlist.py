import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QPushButton, QVBoxLayout, QWidget)


def display_name(path):
    return os.path.basename(path.rstrip("/\\")) or path


class PlaylistPanel(QWidget):
    """창 오른쪽에 붙는 재생 목록. 목록 내용은 창(MainWindow)이 들고 있고 여기는 보여 주기만 한다."""
    play_requested = Signal(int)
    add_requested = Signal()
    remove_requested = Signal(list)        # 지울 위치들
    delete_files_requested = Signal(list)  # Shift+Delete — 실제 파일도 지울 위치들
    clear_requested = Signal()
    files_dropped = Signal(list)
    sort_changed = Signal(str)             # 'name' | 'name_desc' | 'date' | 'date_desc'

    def __init__(self, auto_next, sort_mode="name", parent=None):
        super().__init__(parent)
        self.setObjectName("playlist")
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setFocusPolicy(Qt.ClickFocus)
        self.list.itemActivated.connect(lambda it: self.play_requested.emit(self.list.row(it)))
        self.list.setAcceptDrops(True)
        self.list.viewport().setAcceptDrops(True)
        self.list.dragEnterEvent = self._drag_enter
        self.list.dragMoveEvent = self._drag_enter
        self.list.dropEvent = self._drop
        add = QPushButton("추가")
        add.clicked.connect(self.add_requested.emit)
        rm = QPushButton("삭제")
        rm.clicked.connect(self._remove_selected)
        clr = QPushButton("비우기")
        clr.clicked.connect(self.clear_requested.emit)
        for b in (add, rm, clr):
            b.setFocusPolicy(Qt.NoFocus)
        self.sort_box = QComboBox()
        self.sort_box.addItem("이름순 ▲ 오름차순", "name")
        self.sort_box.addItem("이름순 ▼ 내림차순", "name_desc")
        self.sort_box.addItem("날짜순 ▲ 오름차순 (오래된 것부터)", "date")
        self.sort_box.addItem("날짜순 ▼ 내림차순 (최근 것부터)", "date_desc")
        self.sort_box.setCurrentIndex(max(0, self.sort_box.findData(sort_mode)))
        self.sort_box.setFocusPolicy(Qt.NoFocus)
        self.sort_box.currentIndexChanged.connect(lambda _i: self.sort_changed.emit(self.sort_box.currentData()))
        sort_row = QHBoxLayout()
        sort_row.setContentsMargins(0, 0, 0, 0)
        sort_label = QLabel("정렬")
        sort_label.setObjectName("sortLabel")
        sort_row.addWidget(sort_label)
        sort_row.addWidget(self.sort_box, 1)
        self.auto_next = QCheckBox("끝나면 다음 파일 재생")
        self.auto_next.setChecked(auto_next)
        self.auto_next.setFocusPolicy(Qt.NoFocus)
        btns = QHBoxLayout()
        btns.setContentsMargins(0, 0, 0, 0)
        for b in (add, rm, clr):
            btns.addWidget(b)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addLayout(sort_row)
        lay.addWidget(self.list, 1)
        lay.addWidget(self.auto_next)
        lay.addLayout(btns)

    def set_items(self, paths, current):
        self.list.clear()
        for i, p in enumerate(paths):
            it = QListWidgetItem(f"{i + 1}. {display_name(p)}")
            it.setToolTip(p)
            self.list.addItem(it)
        self.set_current(current)

    def set_current(self, current):
        for i in range(self.list.count()):
            it = self.list.item(i)
            f = QFont(it.font())
            f.setBold(i == current)
            it.setFont(f)
            it.setForeground(Qt.white if i == current else Qt.lightGray)
        if 0 <= current < self.list.count():
            self.list.scrollToItem(self.list.item(current))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Delete and e.modifiers() & Qt.ShiftModifier:
            rows = self._selected_rows()
            if rows:
                self.delete_files_requested.emit(rows)
        elif e.key() == Qt.Key_Delete:
            self._remove_selected()
        else:
            super().keyPressEvent(e)

    def _selected_rows(self):
        return sorted({self.list.row(it) for it in self.list.selectedItems()})

    def _remove_selected(self):
        rows = self._selected_rows()
        if rows:
            self.remove_requested.emit(rows)

    def _drag_enter(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def _drop(self, e):
        files = [u.toLocalFile() or u.toString() for u in e.mimeData().urls()]
        if files:
            self.files_dropped.emit(files)
