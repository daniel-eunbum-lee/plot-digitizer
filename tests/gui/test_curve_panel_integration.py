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


def test_opening_image_populates_curve_panel_with_default_curve(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window = _window_with_image(qtbot, tmp_path)
    assert window._curve_panel.list_widget.count() == 1
    assert window._curve_panel.list_widget.item(0).text() == "Curve 1"


def test_add_curve_appends_and_switches_active_curve(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window_with_image(qtbot, tmp_path)
    window._on_add_curve_requested()

    assert window.project is not None
    assert len(window.project.curves) == 2
    assert window.project.active_curve_index == 1
    assert window._curve_panel.list_widget.count() == 2


def test_curve_selected_switches_active_curve_and_table(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window_with_image(qtbot, tmp_path)
    window._pick_points_action.setChecked(True)
    window._on_canvas_clicked(5.0, 5.0)
    window._on_add_curve_requested()
    window._on_canvas_clicked(50.0, 50.0)

    window._on_curve_selected(0)

    assert window.project is not None
    assert window.project.active_curve_index == 0
    assert window._point_table_model.rowCount() == 1


def test_delete_curve_removes_active_curve(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window_with_image(qtbot, tmp_path)
    window._on_add_curve_requested()

    window._on_delete_curve_requested()

    assert window.project is not None
    assert len(window.project.curves) == 1


def test_cannot_delete_last_remaining_curve(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window_with_image(qtbot, tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QMessageBox.information",
        lambda *args, **kwargs: calls.append("shown"),
    )

    window._on_delete_curve_requested()

    assert calls == ["shown"]
    assert window.project is not None
    assert len(window.project.curves) == 1
