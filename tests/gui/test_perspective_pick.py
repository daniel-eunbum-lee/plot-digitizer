from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from plot_digitizer.gui.main_window import MainWindow
from plot_digitizer.gui.modes import InteractionMode

pytestmark = pytest.mark.gui


def _window_with_image(
    qtbot: QtBot, tmp_path: Path, size: tuple[int, int] = (200, 300)
) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)
    height, width = size
    image_path = tmp_path / "chart.png"
    cv2.imwrite(str(image_path), np.full((height, width, 3), 255, dtype=np.uint8))
    window.open_image(image_path)
    return window


def test_start_perspective_pick_sets_mode(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window_with_image(qtbot, tmp_path)
    window.start_perspective_pick()
    assert window.canvas.mode is InteractionMode.PERSPECTIVE_PICK


def test_four_clicks_prompt_confirmation_and_replace_project(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window_with_image(qtbot, tmp_path, size=(200, 300))
    original_project = window.project
    window.start_perspective_pick()

    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    window._on_canvas_clicked(10.0, 10.0)
    window._on_canvas_clicked(290.0, 10.0)
    window._on_canvas_clicked(290.0, 190.0)
    window._on_canvas_clicked(10.0, 190.0)

    assert window.canvas.mode is InteractionMode.PAN
    assert window.project is not None
    assert window.project is not original_project
    assert window.project.perspective is not None
    assert not window.project.is_calibrated()
    assert window._perspective_pick_points == []
    assert window._perspective_overlay_items == []


def test_declining_confirmation_keeps_original_project(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window_with_image(qtbot, tmp_path, size=(200, 300))
    original_project = window.project
    window.start_perspective_pick()

    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.No,
    )

    window._on_canvas_clicked(10.0, 10.0)
    window._on_canvas_clicked(290.0, 10.0)
    window._on_canvas_clicked(290.0, 190.0)
    window._on_canvas_clicked(10.0, 190.0)

    assert window.project is original_project
