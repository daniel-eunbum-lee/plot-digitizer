from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from pytestqt.qtbot import QtBot

from plot_digitizer.gui.calibration_dialog import AxisCalibrationDialog
from plot_digitizer.gui.main_window import MainWindow

pytestmark = pytest.mark.gui


def _window_with_image(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)
    image_path = tmp_path / "chart.png"
    cv2.imwrite(str(image_path), np.full((100, 200, 3), 255, dtype=np.uint8))
    window.open_image(image_path)
    return window


def test_open_calibration_dialog_without_image_shows_message(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    calls: list[str] = []
    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QMessageBox.information",
        lambda *args, **kwargs: calls.append("shown"),
    )

    window.open_calibration_dialog()

    assert calls == ["shown"]
    assert window._calibration_dialog is None


def test_canvas_click_forwards_pixel_to_pending_axis(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window_with_image(qtbot, tmp_path)
    dialog = AxisCalibrationDialog(window)
    qtbot.addWidget(dialog)
    window._calibration_dialog = dialog
    window._pending_calibration_axis = "x"

    window._on_canvas_clicked(123.0, 45.0)

    assert dialog.x_panel.table.rowCount() == 1
    assert dialog.x_panel.table.item(0, 0).text() == "123.00"
    assert window._pending_calibration_axis is None


def test_refresh_calibration_overlays_adds_one_line_per_reference_point(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window = _window_with_image(qtbot, tmp_path)
    assert window.project is not None
    window.project.x_axis.add_reference(pixel=10.0, value=0.0)
    window.project.x_axis.add_reference(pixel=190.0, value=10.0)
    window.project.y_axis.add_reference(pixel=10.0, value=0.0)
    window.project.y_axis.add_reference(pixel=90.0, value=10.0)

    window._refresh_calibration_overlays()

    assert len(window._calibration_overlay_items) == 4
    for item in window._calibration_overlay_items:
        assert item in window.canvas.scene().items()
