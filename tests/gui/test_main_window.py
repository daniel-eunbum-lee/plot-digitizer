from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from plot_digitizer.gui.main_window import MainWindow
from plot_digitizer.model.point import Point

pytestmark = pytest.mark.gui


def test_open_image_loads_into_canvas(qtbot: QtBot, tmp_path: Path) -> None:
    image_path = tmp_path / "chart.png"
    cv2.imwrite(str(image_path), np.full((50, 80, 3), 255, dtype=np.uint8))

    window = MainWindow()
    qtbot.addWidget(window)
    window.open_image(image_path)

    scene_rect = window.canvas.scene().sceneRect()
    assert scene_rect.width() == 80
    assert scene_rect.height() == 50


def test_open_missing_image_shows_error_without_crashing(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    calls: list[str] = []
    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QMessageBox.critical",
        lambda *args, **kwargs: calls.append("shown"),
    )

    window.open_image(tmp_path / "missing.png")

    assert calls == ["shown"]


def test_reset_project_with_no_image_shows_info_dialog(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    calls: list[str] = []
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "plot_digitizer.gui.main_window.QMessageBox.information",
            lambda *args, **kwargs: calls.append("shown"),
        )
        window.reset_project()

    assert calls == ["shown"]
    assert window.project is None


def test_reset_project_confirmed_reloads_image_and_clears_state(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image_path = tmp_path / "chart.png"
    cv2.imwrite(str(image_path), np.full((50, 80, 3), 255, dtype=np.uint8))

    window = MainWindow()
    qtbot.addWidget(window)
    window.open_image(image_path)
    assert window.project is not None
    window.project.active_curve.add_point(Point(x=1.0, y=2.0))  # type: ignore[union-attr]
    assert window.project.active_curve.points  # type: ignore[union-attr]

    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    window.reset_project()

    assert window.project is not None
    assert window.project.image_path == image_path
    assert not window.project.active_curve.points  # type: ignore[union-attr]
    assert not window.project.is_calibrated()
    assert window.project.perspective is None


def test_reset_project_declined_leaves_state_untouched(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image_path = tmp_path / "chart.png"
    cv2.imwrite(str(image_path), np.full((50, 80, 3), 255, dtype=np.uint8))

    window = MainWindow()
    qtbot.addWidget(window)
    window.open_image(image_path)
    assert window.project is not None
    window.project.active_curve.add_point(Point(x=1.0, y=2.0))  # type: ignore[union-attr]
    original_project = window.project

    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.No,
    )

    window.reset_project()

    assert window.project is original_project
    assert window.project.active_curve.points  # type: ignore[union-attr]
