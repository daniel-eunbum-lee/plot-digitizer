"""Undo/redo commands for point-picking edits.

Scoped to point add/remove only for v1 -- the highest-value case for a
digitizing tool, where an accidental misclick is the most common thing a
user wants to undo. Calibration and curve-management edits are not
undoable yet; see PLAN.md.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QUndoCommand

from plot_digitizer.model.curve import Curve
from plot_digitizer.model.point import Point


class AddPointCommand(QUndoCommand):
    def __init__(self, curve: Curve, point: Point, on_changed: Callable[[], None]) -> None:
        super().__init__("Add point")
        self._curve = curve
        self._point = point
        self._on_changed = on_changed

    def redo(self) -> None:
        self._curve.add_point(self._point)
        self._on_changed()

    def undo(self) -> None:
        self._curve.remove_point(len(self._curve.points) - 1)
        self._on_changed()


class ResampleCurveCommand(QUndoCommand):
    """Replaces a curve's whole point list with a resampled one, reversibly."""

    def __init__(
        self,
        curve: Curve,
        new_points: list[Point],
        on_changed: Callable[[], None],
    ) -> None:
        super().__init__("Resample curve")
        self._curve = curve
        self._old_points = list(curve.points)
        self._new_points = list(new_points)
        self._on_changed = on_changed

    def redo(self) -> None:
        self._curve.points = list(self._new_points)
        self._on_changed()

    def undo(self) -> None:
        self._curve.points = list(self._old_points)
        self._on_changed()
