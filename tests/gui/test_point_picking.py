from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from pytestqt.qtbot import QtBot

from plot_digitizer.gui.main_window import MainWindow
from plot_digitizer.gui.modes import InteractionMode
from plot_digitizer.model.point import Point

pytestmark = pytest.mark.gui


def _window_with_image(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)
    image_path = tmp_path / "chart.png"
    cv2.imwrite(str(image_path), np.full((100, 200, 3), 255, dtype=np.uint8))
    window.open_image(image_path)
    return window


def test_pick_points_mode_adds_point_to_active_curve_and_table(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window = _window_with_image(qtbot, tmp_path)
    window._pick_points_action.setChecked(True)
    assert window.canvas.mode is InteractionMode.PICK_POINT

    window._on_canvas_clicked(42.0, 24.0)

    assert window.project is not None
    active = window.project.active_curve
    assert active is not None
    assert active.points[-1].x == pytest.approx(42.0)
    assert active.points[-1].y == pytest.approx(24.0)
    assert window._point_table_model.rowCount() == 1
    assert len(window._data_point_overlay_items) == 1


def test_pan_mode_click_does_not_add_point(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window_with_image(qtbot, tmp_path)
    assert window.canvas.mode is InteractionMode.PAN

    window._on_canvas_clicked(42.0, 24.0)

    assert window.project is not None
    assert window.project.active_curve is not None
    assert window.project.active_curve.points == []


def test_export_csv_without_calibration_warns_and_does_not_write(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window_with_image(qtbot, tmp_path)
    window._add_data_point(Point(x=1.0, y=1.0))

    calls: list[str] = []
    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QMessageBox.warning",
        lambda *args, **kwargs: calls.append("shown"),
    )

    window.export_csv_dialog()

    assert calls == ["shown"]


def test_export_csv_with_calibration_writes_file(
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

    out_path = tmp_path / "export.csv"
    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(out_path), "CSV (*.csv)"),
    )

    window.export_csv_dialog()

    assert out_path.exists()
    content = out_path.read_text()
    assert "x,y" in content
    assert "10.0,5.0" in content


def test_export_all_curves_csv_writes_a_column_per_curve(
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
    window._on_add_curve_requested()
    window._on_canvas_clicked(50.0, 25.0)

    out_path = tmp_path / "all_curves.csv"
    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(out_path), "CSV (*.csv)"),
    )

    window.export_all_curves_csv_dialog()

    assert out_path.exists()
    content = out_path.read_text()
    assert "Curve 1_x,Curve 1_y,Curve 2_x,Curve 2_y" in content


def test_export_all_curves_excel_writes_one_sheet_per_curve(
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

    out_path = tmp_path / "all_curves.xlsx"
    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(out_path), "Excel Workbook (*.xlsx)"),
    )

    window.export_all_curves_excel_dialog()

    assert out_path.exists()
    import openpyxl

    workbook = openpyxl.load_workbook(out_path)
    assert workbook.sheetnames == ["Curve 1"]


def test_export_all_curves_warns_when_uncalibrated(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window_with_image(qtbot, tmp_path)
    window._add_data_point(Point(x=1.0, y=1.0))

    calls: list[str] = []
    monkeypatch.setattr(
        "plot_digitizer.gui.main_window.QMessageBox.warning",
        lambda *args, **kwargs: calls.append("shown"),
    )

    window.export_all_curves_csv_dialog()

    assert calls == ["shown"]


def test_selecting_a_table_row_highlights_only_its_canvas_marker(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window = _window_with_image(qtbot, tmp_path)
    window._pick_points_action.setChecked(True)
    window._on_canvas_clicked(10.0, 10.0)
    window._on_canvas_clicked(20.0, 20.0)
    base_colors = [marker.brush().color() for marker in window._data_point_overlay_items]

    window._point_table_view.selectRow(1)

    colors = [marker.brush().color() for marker in window._data_point_overlay_items]
    assert colors[0] == base_colors[0]
    assert colors[1] != base_colors[1]

    window._point_table_view.clearSelection()

    colors_after_clear = [marker.brush().color() for marker in window._data_point_overlay_items]
    assert colors_after_clear == base_colors
