from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from pytestqt.qtbot import QtBot

from plot_digitizer.gui.main_window import MainWindow

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
