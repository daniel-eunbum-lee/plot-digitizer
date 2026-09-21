from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt
from pytestqt.qtbot import QtBot

from plot_digitizer.gui.canvas import ImageCanvas
from plot_digitizer.gui.modes import InteractionMode

pytestmark = pytest.mark.gui


def _loaded_canvas(qtbot: QtBot) -> ImageCanvas:
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.show()
    canvas.resize(200, 200)
    canvas.load_image(np.zeros((100, 100, 3), dtype=np.uint8))
    return canvas


def test_default_mode_is_pan_with_scroll_hand_drag(qtbot: QtBot) -> None:
    canvas = _loaded_canvas(qtbot)
    assert canvas.mode is InteractionMode.PAN
    assert canvas.dragMode() == canvas.DragMode.ScrollHandDrag


def test_pan_mode_click_does_not_emit_image_clicked(qtbot: QtBot) -> None:
    canvas = _loaded_canvas(qtbot)
    clicks: list[tuple[float, float]] = []
    canvas.imageClicked.connect(lambda x, y: clicks.append((x, y)))

    qtbot.mouseClick(canvas.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(50, 50))

    assert clicks == []


def test_calibrate_mode_click_emits_image_clicked(qtbot: QtBot) -> None:
    canvas = _loaded_canvas(qtbot)
    canvas.mode = InteractionMode.CALIBRATE
    assert canvas.dragMode() == canvas.DragMode.NoDrag

    clicks: list[tuple[float, float]] = []
    canvas.imageClicked.connect(lambda x, y: clicks.append((x, y)))

    qtbot.mouseClick(canvas.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(50, 50))

    assert len(clicks) == 1
