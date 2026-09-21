from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from PySide6.QtWidgets import QDialog
from pytestqt.qtbot import QtBot

from plot_digitizer.gui.main_window import MainWindow
from plot_digitizer.gui.modes import InteractionMode
from plot_digitizer.model.point import Point

pytestmark = pytest.mark.gui


def _window_with_curve_image(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    image = np.full((100, 200, 3), 255, dtype=np.uint8)
    cv2.line(image, (0, 50), (199, 50), (0, 0, 255), 2)
    image_path = tmp_path / "chart.png"
    cv2.imwrite(str(image_path), image)

    window = MainWindow()
    qtbot.addWidget(window)
    window.open_image(image_path)
    return window


def test_start_auto_trace_pick_sets_mode(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window_with_curve_image(qtbot, tmp_path)
    window.start_auto_trace_pick()
    assert window.canvas.mode is InteractionMode.AUTO_TRACE_SAMPLE


def test_sample_and_trace_adds_new_auto_curve(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window_with_curve_image(qtbot, tmp_path)
    window.start_auto_trace_pick()

    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.ColorPickerDialog.exec",
        lambda self: QDialog.DialogCode.Accepted,
    )

    window._on_canvas_clicked(100.0, 50.0)

    assert window.canvas.mode is InteractionMode.PAN
    assert window.project is not None
    assert len(window.project.curves) == 2  # default "Curve 1" plus the new auto curve
    auto_curve = window.project.active_curve
    assert auto_curve is not None
    assert auto_curve.source == "auto"
    assert len(auto_curve.points) > 150
    assert all(abs(p.y - 50.0) < 3.0 for p in auto_curve.points)
    assert window._point_table_model.rowCount() == len(auto_curve.points)


def test_declining_color_dialog_does_not_add_curve(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window_with_curve_image(qtbot, tmp_path)
    window.start_auto_trace_pick()

    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.ColorPickerDialog.exec",
        lambda self: QDialog.DialogCode.Rejected,
    )

    window._on_canvas_clicked(100.0, 50.0)

    assert window.project is not None
    assert len(window.project.curves) == 1


def test_sample_and_trace_with_no_match_shows_message(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window_with_curve_image(qtbot, tmp_path)
    window.start_auto_trace_pick()

    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.ColorPickerDialog.exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    # An exact-pixel match always finds at least that one pixel in practice,
    # so the "no curve found" path is tested by forcing an empty result
    # directly rather than contriving an unreachable real-image scenario.
    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.trace_curve_by_color",
        lambda image, bgr, tolerance: [],
    )
    calls: list[str] = []
    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QMessageBox.information",
        lambda *args, **kwargs: calls.append("shown"),
    )

    window._sample_and_trace(Point(x=10.0, y=10.0))

    assert calls == ["shown"]
    assert window.project is not None
    assert len(window.project.curves) == 1
