from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from plot_digitizer.gui.canvas import ImageCanvas, bgr_to_pixmap

pytestmark = pytest.mark.gui


def test_bgr_to_pixmap_preserves_size(qapp: QApplication) -> None:
    # QPixmap requires a live QApplication; the unused `qapp` argument pulls
    # in pytest-qt's fixture that creates one before this test body runs.
    image = np.zeros((40, 60, 3), dtype=np.uint8)
    pixmap = bgr_to_pixmap(image)
    assert pixmap.width() == 60
    assert pixmap.height() == 40


def test_load_image_sets_scene_rect(qtbot: QtBot) -> None:
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    image = np.zeros((40, 60, 3), dtype=np.uint8)

    canvas.load_image(image)

    scene_rect = canvas.scene().sceneRect()
    assert scene_rect.width() == 60
    assert scene_rect.height() == 40
