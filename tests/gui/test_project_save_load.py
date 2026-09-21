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


def test_save_then_open_project_restores_calibration_and_points(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window_with_image(qtbot, tmp_path)
    assert window.project is not None
    window.project.x_axis.add_reference(pixel=0.0, value=0.0)
    window.project.x_axis.add_reference(pixel=200.0, value=20.0)
    window.project.y_axis.add_reference(pixel=0.0, value=10.0)
    window.project.y_axis.add_reference(pixel=100.0, value=0.0)
    window._pick_points_action.setChecked(True)
    window._on_canvas_clicked(100.0, 50.0)

    project_path = tmp_path / "session.json"
    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(project_path), "Plot Digitizer Project (*.json)"),
    )
    window.save_project_dialog()
    assert project_path.exists()

    fresh_window = MainWindow()
    qtbot.addWidget(fresh_window)
    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(project_path), "Plot Digitizer Project (*.json)"),
    )
    fresh_window.open_project_dialog()

    assert fresh_window.project is not None
    assert fresh_window.project.is_calibrated()
    assert len(fresh_window.project.active_curve.points) == 1  # type: ignore[union-attr]
    data_point = fresh_window.project.transform().pixel_to_data(
        fresh_window.project.active_curve.points[0]  # type: ignore[union-attr]
    )
    assert data_point.x == pytest.approx(10.0)
    assert data_point.y == pytest.approx(5.0)
    assert fresh_window._curve_panel.list_widget.count() == 1
