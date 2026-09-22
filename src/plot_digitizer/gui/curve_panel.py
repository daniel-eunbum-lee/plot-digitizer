"""Dock widget listing a project's curves/series: switch, add, or delete them."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QPushButton, QVBoxLayout, QWidget


class CurvePanel(QWidget):
    curveSelected = Signal(int)
    addCurveRequested = Signal()
    deleteCurveRequested = Signal()
    renameCurveRequested = Signal()
    resampleRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self.curveSelected)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self.renameCurveRequested.emit())

        add_button = QPushButton("Add Curve")
        add_button.clicked.connect(self.addCurveRequested)
        delete_button = QPushButton("Delete Curve")
        delete_button.clicked.connect(self.deleteCurveRequested)
        rename_button = QPushButton("Rename Curve...")
        rename_button.clicked.connect(self.renameCurveRequested)

        resample_button = QPushButton("Resample to Fixed X Step...")
        resample_button.clicked.connect(self.resampleRequested)

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(add_button)
        buttons_row.addWidget(delete_button)
        buttons_row.addWidget(rename_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.list_widget)
        layout.addLayout(buttons_row)
        layout.addWidget(resample_button)

    def set_curves(self, names: list[str], active_index: int) -> None:
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        self.list_widget.addItems(names)
        if 0 <= active_index < len(names):
            self.list_widget.setCurrentRow(active_index)
        self.list_widget.blockSignals(False)
