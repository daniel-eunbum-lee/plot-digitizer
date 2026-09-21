"""Dialog for calibrating both axes against known reference values."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
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
from plot_digitizer.gui.overlays import (
    make_horizontal_reference_line,
    make_reference_label,
    make_vertical_reference_line,
    set_reference_line_highlighted,
)
from plot_digitizer.imaging.axis_detection import (
    LineCandidate,
    detect_horizontal_lines,
    detect_plot_area,
    detect_vertical_lines,
    suggest_extremes,
)
from plot_digitizer.imaging.tick_ocr import read_tick_label, tick_label_region

_PIXEL_COLUMN = 0
_VALUE_COLUMN = 1
_MAX_AUTO_DETECT_CANDIDATES = 6
_X_OVERLAY_COLOR = QColor("red")
_Y_OVERLAY_COLOR = QColor("blue")
_SUGGESTED_ROW_COLOR = QColor("#fff2b2")
_DEFAULT_VALUE_TEXT = "0.0"


class _AxisPanel(QGroupBox):
    """One axis's scale selector plus its reference-point table.

    Each table row owns a matching pair of temporary scene overlays -- a
    dashed line at the row's pixel position plus a numbered label -- kept in
    `overlay_rows` at the *same index as the table row*. The overlays exist
    only while the dialog is open; the permanent ones are redrawn by the main
    window from the committed calibration after accept.
    """

    def __init__(
        self,
        title: str,
        *,
        axis: str = "x",
        scene: QGraphicsScene | None = None,
        image: np.ndarray | None = None,
    ) -> None:
        super().__init__(title)
        self._axis = axis
        self._scene = scene
        self._image = image
        self._plot_area: tuple[float, float, float, float] | None = None
        self._overlay_color = _X_OVERLAY_COLOR if axis == "x" else _Y_OVERLAY_COLOR
        self.overlay_rows: list[tuple[QGraphicsLineItem, QGraphicsSimpleTextItem]] = []

        self.scale_combo = QComboBox()
        self.scale_combo.addItem("Linear", AxisScale.LINEAR)
        self.scale_combo.addItem("Log", AxisScale.LOG)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Pixel", "Value"])
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

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

    def add_reference_row(self, pixel: float, value: float | None = None) -> None:
        """Append a reference row, optionally pre-filling the (still editable) Value cell.

        `value` is only ever a suggestion -- an OCR'd tick label -- so the cell
        stays a plain editable item either way; omitting it keeps the neutral
        "0.0" placeholder a manually picked point gets.
        """
        row = self.table.rowCount()
        self.table.insertRow(row)
        pixel_item = QTableWidgetItem(f"{pixel:.2f}")
        pixel_item.setFlags(pixel_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, _PIXEL_COLUMN, pixel_item)
        value_text = _DEFAULT_VALUE_TEXT if value is None else f"{value:g}"
        self.table.setItem(row, _VALUE_COLUMN, QTableWidgetItem(value_text))
        self._add_overlay(pixel)

    def add_candidate_rows(self, candidates: list[LineCandidate]) -> None:
        """Add detected-line candidates as ordinary, editable, removable rows.

        These are proposals, not commitments: the user still must review
        each one, delete any that are wrong (gridlines, legend, the curve
        itself), and always type in the real value -- nothing here is
        auto-applied to the calibration. The two candidates `suggest_extremes`
        picks are only *highlighted* for the same reason: they stay ordinary
        rows the user can edit or delete. Likewise an OCR'd tick label only
        changes which number the editable Value cell starts out showing.
        """
        shown = candidates[:_MAX_AUTO_DETECT_CANDIDATES]
        first_row = self.table.rowCount()
        for candidate in shown:
            self.add_reference_row(candidate.position, value=self._ocr_value(candidate))

        suggested = suggest_extremes(candidates, top_k=_MAX_AUTO_DETECT_CANDIDATES)
        if suggested is None:
            return
        for candidate in suggested:
            if candidate in shown:
                self._mark_row_suggested(first_row + shown.index(candidate))

    def _ocr_value(self, candidate: LineCandidate) -> float | None:
        """Try to read `candidate`'s tick label off the image; None if unavailable.

        Returns None whenever anything is missing -- no image, no inferable
        plot area, no Tesseract binary, an unreadable crop -- so the caller
        falls back to the plain "0.0" default rather than the dialog failing.
        """
        if self._image is None:
            return None
        plot_area = self._cached_plot_area()
        if plot_area is None:
            return None
        region = tick_label_region(
            candidate,
            axis=self._axis,
            plot_area=plot_area,
            image_shape=self._image.shape[:2],
        )
        return read_tick_label(self._image, region)

    def _cached_plot_area(self) -> tuple[float, float, float, float] | None:
        # detect_plot_area re-runs Hough detection over the whole image, so
        # memoize it rather than paying for it once per candidate row.
        if self._image is None:
            return None
        if self._plot_area is None:
            self._plot_area = detect_plot_area(self._image)
        return self._plot_area

    def _mark_row_suggested(self, row: int) -> None:
        for column in (_PIXEL_COLUMN, _VALUE_COLUMN):
            item = self.table.item(row, column)
            if item is None:
                continue
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setBackground(_SUGGESTED_ROW_COLOR)
        pixel_item = self.table.item(row, _PIXEL_COLUMN)
        if pixel_item is not None:
            pixel_item.setToolTip("Suggested axis extreme")

    def _add_overlay(self, pixel: float) -> None:
        if self._scene is None:
            return
        rect = self._scene.sceneRect()
        if self._axis == "x":
            line = make_vertical_reference_line(pixel, rect.height(), self._overlay_color)
            label_x, label_y = pixel, rect.top()
        else:
            line = make_horizontal_reference_line(pixel, rect.width(), self._overlay_color)
            label_x, label_y = rect.left(), pixel
        label = make_reference_label(
            self._label_text(len(self.overlay_rows)), label_x, label_y, self._overlay_color
        )
        self._scene.addItem(line)
        self._scene.addItem(label)
        self.overlay_rows.append((line, label))

    def _label_text(self, index: int) -> str:
        return f"{self._axis.upper()}{index + 1}"

    def _remove_overlay_row(self, row: int) -> None:
        if self._scene is None or not (0 <= row < len(self.overlay_rows)):
            return
        line, label = self.overlay_rows.pop(row)
        self._scene.removeItem(line)
        self._scene.removeItem(label)

    def _renumber_overlay_labels(self) -> None:
        for index, (_line, label) in enumerate(self.overlay_rows):
            label.setText(self._label_text(index))

    def clear_overlays(self) -> None:
        """Drop every temporary overlay this panel put on the scene."""
        if self._scene is not None:
            for line, label in self.overlay_rows:
                self._scene.removeItem(line)
                self._scene.removeItem(label)
        self.overlay_rows = []

    def _on_selection_changed(self) -> None:
        selected = {index.row() for index in self.table.selectedIndexes()}
        for row, (line, _label) in enumerate(self.overlay_rows):
            set_reference_line_highlighted(
                line, highlighted=row in selected, base_color=self._overlay_color
            )

    def _remove_selected(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)
            self._remove_overlay_row(row)
        self._renumber_overlay_labels()
        # removeRow() emits itemSelectionChanged while overlay_rows is still
        # mid-update, so restyle once more now that rows and overlays line up
        # again -- otherwise a deleted row's highlight can stick to its
        # successor.
        self._on_selection_changed()

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

    def __init__(
        self,
        parent: QWidget | None = None,
        image: np.ndarray | None = None,
        scene: QGraphicsScene | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calibrate Axes")
        self._image = image

        self.x_panel = _AxisPanel("X Axis", axis="x", scene=scene, image=image)
        self.y_panel = _AxisPanel("Y Axis", axis="y", scene=scene, image=image)
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

    def clear_overlays(self) -> None:
        """Remove every temporary overlay this dialog session added to the scene.

        Called on both accept and reject so the scene is back to its
        pre-dialog state before the main window redraws the permanent
        calibration overlays -- otherwise the temporary items would be
        orphaned on top of the identical permanent ones.
        """
        self.x_panel.clear_overlays()
        self.y_panel.clear_overlays()

    def reject(self) -> None:
        self.clear_overlays()
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.clear_overlays()
        super().closeEvent(event)

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
        self.clear_overlays()
        self.accept()
