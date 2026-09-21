from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from pytestqt.qtbot import QtBot

from plot_digitizer.gui.main_window import MainWindow

pytestmark = pytest.mark.gui


def _window_with_image(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)
    image_path = tmp_path / "chart.png"
    cv2.imwrite(str(image_path), np.full((100, 200, 3), 255, dtype=np.uint8))
    window.open_image(image_path)
    return window


def test_undo_removes_last_added_point(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window_with_image(qtbot, tmp_path)
    window._pick_points_action.setChecked(True)

    window._on_canvas_clicked(10.0, 10.0)
    window._on_canvas_clicked(20.0, 20.0)
    assert window.project is not None
    assert len(window.project.active_curve.points) == 2  # type: ignore[union-attr]

    window._undo_stack.undo()

    assert len(window.project.active_curve.points) == 1  # type: ignore[union-attr]
    assert window.project.active_curve.points[0].x == pytest.approx(10.0)  # type: ignore[union-attr]
    assert window._point_table_model.rowCount() == 1


def test_redo_reapplies_the_point(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window_with_image(qtbot, tmp_path)
    window._pick_points_action.setChecked(True)
    window._on_canvas_clicked(10.0, 10.0)

    window._undo_stack.undo()
    assert window.project is not None
    assert window.project.active_curve.points == []  # type: ignore[union-attr]

    window._undo_stack.redo()

    assert len(window.project.active_curve.points) == 1  # type: ignore[union-attr]
