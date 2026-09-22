from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from PySide6.QtWidgets import QDialog
from pytestqt.qtbot import QtBot

from plot_digitizer.calibration.axis import AxisCalibration, AxisScale
from plot_digitizer.gui.main_window import MainWindow
from plot_digitizer.gui.resample_dialog import ResampleDialog
from plot_digitizer.model.point import Point

pytestmark = pytest.mark.gui


def _window_with_image(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)
    image_path = tmp_path / "chart.png"
    cv2.imwrite(str(image_path), np.full((100, 200, 3), 255, dtype=np.uint8))
    window.open_image(image_path)
    return window


def _calibrate(window: MainWindow) -> None:
    """Pixel x == data x; data y == 100 - pixel y."""
    assert window.project is not None
    x_axis = AxisCalibration(scale=AxisScale.LINEAR)
    x_axis.add_reference(pixel=0.0, value=0.0)
    x_axis.add_reference(pixel=100.0, value=100.0)
    y_axis = AxisCalibration(scale=AxisScale.LINEAR)
    y_axis.add_reference(pixel=100.0, value=0.0)
    y_axis.add_reference(pixel=0.0, value=100.0)
    window.project.x_axis = x_axis
    window.project.y_axis = y_axis


def _accept_resample_dialog_with(monkeypatch: pytest.MonkeyPatch, step: float) -> None:
    def fake_exec(dialog: ResampleDialog) -> int:
        dialog.step_spinbox.setValue(step)
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(ResampleDialog, "exec", fake_exec)


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


def test_rename_curve_updates_name_and_panel(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window_with_image(qtbot, tmp_path)
    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QInputDialog.getText",
        lambda *args, **kwargs: ("Temperature", True),
    )

    window._on_rename_curve_requested()

    assert window.project is not None
    assert window.project.active_curve is not None
    assert window.project.active_curve.name == "Temperature"
    assert window._curve_panel.list_widget.item(0).text() == "Temperature"


def test_rename_curve_cancelled_leaves_name_unchanged(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window_with_image(qtbot, tmp_path)
    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QInputDialog.getText",
        lambda *args, **kwargs: ("Ignored", False),
    )

    window._on_rename_curve_requested()

    assert window.project is not None
    assert window.project.active_curve is not None
    assert window.project.active_curve.name == "Curve 1"


def test_rename_curve_blank_name_is_rejected(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window_with_image(qtbot, tmp_path)
    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QInputDialog.getText",
        lambda *args, **kwargs: ("   ", True),
    )

    window._on_rename_curve_requested()

    assert window.project is not None
    assert window.project.active_curve is not None
    assert window.project.active_curve.name == "Curve 1"


def test_resample_replaces_points_and_undo_restores_them(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window_with_image(qtbot, tmp_path)
    _calibrate(window)
    assert window.project is not None
    curve = window.project.active_curve
    assert curve is not None
    original = [Point(x=0.0, y=100.0), Point(x=3.0, y=97.0), Point(x=10.0, y=90.0)]
    curve.points = list(original)
    _accept_resample_dialog_with(monkeypatch, step=5.0)

    window._on_resample_requested()

    # data x grid 0, 5, 10 -> pixel x 0, 5, 10 with this calibration
    assert [point.x for point in curve.points] == pytest.approx([0.0, 5.0, 10.0])
    assert window._point_table_model.rowCount() == 3

    window._undo_stack.undo()

    assert curve.points == original
    assert window._point_table_model.rowCount() == 3

    window._undo_stack.redo()

    assert [point.x for point in curve.points] == pytest.approx([0.0, 5.0, 10.0])


def test_resample_requires_calibrated_axes(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window_with_image(qtbot, tmp_path)
    assert window.project is not None
    curve = window.project.active_curve
    assert curve is not None
    curve.points = [Point(x=0.0, y=0.0), Point(x=5.0, y=5.0)]
    warnings: list[str] = []
    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QMessageBox.warning",
        lambda *args, **kwargs: warnings.append("shown"),
    )

    window._on_resample_requested()

    assert warnings == ["shown"]
    assert len(curve.points) == 2


def test_resample_requires_at_least_two_points(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window_with_image(qtbot, tmp_path)
    _calibrate(window)
    assert window.project is not None
    curve = window.project.active_curve
    assert curve is not None
    curve.points = [Point(x=1.0, y=1.0)]
    messages: list[str] = []
    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QMessageBox.information",
        lambda *args, **kwargs: messages.append("shown"),
    )

    window._on_resample_requested()

    assert messages == ["shown"]
    assert len(curve.points) == 1


def test_resample_dialog_exposes_chosen_step(qtbot: QtBot) -> None:
    dialog = ResampleDialog()
    qtbot.addWidget(dialog)

    dialog.step_spinbox.setValue(0.25)

    assert dialog.step == pytest.approx(0.25)
