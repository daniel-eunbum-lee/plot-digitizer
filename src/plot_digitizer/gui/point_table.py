"""Qt table model presenting a curve's points (pixel + derived data columns)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt

from plot_digitizer.calibration.transform import CoordinateTransform
from plot_digitizer.model.curve import Curve

_ModelIndex = QModelIndex | QPersistentModelIndex
_COLUMNS = ["Pixel X", "Pixel Y", "Data X", "Data Y"]


class PointTableModel(QAbstractTableModel):
    """Read-only view of a Curve's points; the Curve itself is the source of truth."""

    def __init__(self) -> None:
        super().__init__()
        self._curve: Curve | None = None
        self._transform: CoordinateTransform | None = None

    def set_source(self, curve: Curve | None, transform: CoordinateTransform | None) -> None:
        self.beginResetModel()
        self._curve = curve
        self._transform = transform
        self.endResetModel()

    def notify_points_changed(self) -> None:
        self.beginResetModel()
        self.endResetModel()

    def rowCount(self, parent: _ModelIndex | None = None) -> int:
        if (parent is not None and parent.isValid()) or self._curve is None:
            return 0
        return len(self._curve.points)

    def columnCount(self, parent: _ModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(_COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        return _COLUMNS[section]

    def data(self, index: _ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role != Qt.ItemDataRole.DisplayRole or self._curve is None:
            return None
        point = self._curve.points[index.row()]
        column = index.column()
        if column == 0:
            return f"{point.x:.2f}"
        if column == 1:
            return f"{point.y:.2f}"
        if self._transform is None:
            return "—"
        data_point = self._transform.pixel_to_data(point)
        return f"{data_point.x:.4g}" if column == 2 else f"{data_point.y:.4g}"
