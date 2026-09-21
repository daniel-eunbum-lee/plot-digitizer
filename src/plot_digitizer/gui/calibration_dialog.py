"""Dialog for calibrating both axes against known reference values."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from plot_digitizer.calibration.axis import AxisCalibration, AxisScale, CalibrationError
from plot_digitizer.imaging.axis_detection import (
    LineCandidate,
    detect_horizontal_lines,
    detect_vertical_lines,
)

_PIXEL_COLUMN = 0
_VALUE_COLUMN = 1
_MAX_AUTO_DETECT_CANDIDATES = 6


class _AxisPanel(QGroupBox):
    """One axis's scale selector plus its reference-point table."""

    def __init__(self, title: str) -> None:
        super().__init__(title)
        self.scale_combo = QComboBox()
        self.scale_combo.addItem("Linear", AxisScale.LINEAR)
        self.scale_combo.addItem("Log", AxisScale.LOG)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Pixel", "Value"])

        self.auto_detect_button = QPushButton("Auto-Detect Lines")
        remove_button = QPushButton("Remove Selected")
        remove_button.clicked.connect(self._remove_selected)

        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("Scale:"))
        scale_row.addWidget(self.scale_combo)

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(self.auto_detect_button)
        buttons_row.addWidget(remove_button)

        layout = QVBoxLayout(self)
        layout.addLayout(scale_row)
        layout.addWidget(self.table)
        layout.addLayout(buttons_row)

    def add_reference_row(self, pixel: float) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        pixel_item = QTableWidgetItem(f"{pixel:.2f}")
        pixel_item.setFlags(pixel_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, _PIXEL_COLUMN, pixel_item)
        self.table.setItem(row, _VALUE_COLUMN, QTableWidgetItem("0.0"))

    def add_candidate_rows(self, candidates: list[LineCandidate]) -> None:
        """Add detected-line candidates as ordinary, editable, removable rows.

        These are proposals, not commitments: the user still must review
        each one, delete any that are wrong (gridlines, legend, the curve
        itself), and always type in the real value -- nothing here is
        auto-applied to the calibration.
        """
        for candidate in candidates[:_MAX_AUTO_DETECT_CANDIDATES]:
            self.add_reference_row(candidate.position)

    def _remove_selected(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)

    def build_calibration(self) -> AxisCalibration:
        scale = self.scale_combo.currentData()
        calibration = AxisCalibration(scale=scale)
        for row in range(self.table.rowCount()):
            pixel_item = self.table.item(row, _PIXEL_COLUMN)
            value_item = self.table.item(row, _VALUE_COLUMN)
            # Both cells are always populated together in add_reference_row.
            assert pixel_item is not None and value_item is not None
            pixel_text = pixel_item.text()
            value_text = value_item.text()
            try:
                calibration.add_reference(float(pixel_text), float(value_text))
            except ValueError as exc:
                raise CalibrationError(f"row {row + 1}: value must be numeric") from exc
        return calibration


class AxisCalibrationDialog(QDialog):
    """Modal dialog: request a canvas click via `pickRequested`, receive it via `add_point`."""

    pickRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None, image: np.ndarray | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calibrate Axes")
        self._image = image

        self.x_panel = _AxisPanel("X Axis")
        self.y_panel = _AxisPanel("Y Axis")
        self.x_calibration: AxisCalibration | None = None
        self.y_calibration: AxisCalibration | None = None

        add_x_button = QPushButton("Add X Reference Point")
        add_x_button.clicked.connect(lambda: self.pickRequested.emit("x"))
        add_y_button = QPushButton("Add Y Reference Point")
        add_y_button.clicked.connect(lambda: self.pickRequested.emit("y"))
        self.x_panel.auto_detect_button.clicked.connect(self._auto_detect_x)
        self.y_panel.auto_detect_button.clicked.connect(self._auto_detect_y)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        x_column = QVBoxLayout()
        x_column.addWidget(self.x_panel)
        x_column.addWidget(add_x_button)
        y_column = QVBoxLayout()
        y_column.addWidget(self.y_panel)
        y_column.addWidget(add_y_button)

        panels_row = QHBoxLayout()
        panels_row.addLayout(x_column)
        panels_row.addLayout(y_column)

        layout = QVBoxLayout(self)
        layout.addLayout(panels_row)
        layout.addWidget(buttons)

    def add_point(self, axis: str, pixel: float) -> None:
        panel = self.x_panel if axis == "x" else self.y_panel
        panel.add_reference_row(pixel)

    def _auto_detect_x(self) -> None:
        if self._image is None:
            return
        candidates = detect_vertical_lines(self._image)
        self.x_panel.add_candidate_rows(candidates)

    def _auto_detect_y(self) -> None:
        if self._image is None:
            return
        candidates = detect_horizontal_lines(self._image)
        self.y_panel.add_candidate_rows(candidates)

    def _on_accept(self) -> None:
        try:
            x_calibration = self.x_panel.build_calibration()
            y_calibration = self.y_panel.build_calibration()
            if not x_calibration.is_valid() or not y_calibration.is_valid():
                raise CalibrationError("both axes need at least 2 valid reference points")
        except CalibrationError as exc:
            QMessageBox.critical(self, "Invalid calibration", str(exc))
            return
        self.x_calibration = x_calibration
        self.y_calibration = y_calibration
        self.accept()
