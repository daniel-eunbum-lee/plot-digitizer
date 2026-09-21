from __future__ import annotations

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtWidgets import QGraphicsScene
from pytestqt.qtbot import QtBot

from plot_digitizer.calibration.axis import AxisScale
from plot_digitizer.gui.calibration_dialog import AxisCalibrationDialog
from plot_digitizer.imaging.axis_detection import LineCandidate

pytestmark = pytest.mark.gui


def _scene(width: float = 300.0, height: float = 200.0) -> QGraphicsScene:
    scene = QGraphicsScene()
    scene.setSceneRect(QRectF(0.0, 0.0, width, height))
    return scene


def test_add_point_appends_row_to_correct_axis_panel(qtbot: QtBot) -> None:
    dialog = AxisCalibrationDialog()
    qtbot.addWidget(dialog)

    dialog.add_point("x", 12.5)
    dialog.add_point("y", 34.0)

    assert dialog.x_panel.table.rowCount() == 1
    assert dialog.x_panel.table.item(0, 0).text() == "12.50"
    assert dialog.y_panel.table.rowCount() == 1
    assert dialog.y_panel.table.item(0, 0).text() == "34.00"


def test_accept_builds_calibrations_from_two_valid_reference_points(qtbot: QtBot) -> None:
    dialog = AxisCalibrationDialog()
    qtbot.addWidget(dialog)

    dialog.add_point("x", 0.0)
    dialog.add_point("x", 100.0)
    dialog.x_panel.table.item(0, 1).setText("0.0")
    dialog.x_panel.table.item(1, 1).setText("10.0")

    dialog.add_point("y", 0.0)
    dialog.add_point("y", 200.0)
    dialog.y_panel.table.item(0, 1).setText("0.0")
    dialog.y_panel.table.item(1, 1).setText("20.0")

    dialog._on_accept()

    assert dialog.x_calibration is not None
    assert dialog.y_calibration is not None
    assert dialog.x_calibration.scale is AxisScale.LINEAR
    assert dialog.x_calibration.pixel_to_value(50.0) == pytest.approx(5.0)
    assert dialog.result() == dialog.DialogCode.Accepted


def test_log_scale_selection_produces_log_calibration(qtbot: QtBot) -> None:
    dialog = AxisCalibrationDialog()
    qtbot.addWidget(dialog)

    log_index = dialog.y_panel.scale_combo.findData(AxisScale.LOG)
    dialog.y_panel.scale_combo.setCurrentIndex(log_index)

    dialog.add_point("x", 0.0)
    dialog.add_point("x", 100.0)
    dialog.x_panel.table.item(0, 1).setText("0.0")
    dialog.x_panel.table.item(1, 1).setText("10.0")

    dialog.add_point("y", 0.0)
    dialog.add_point("y", 200.0)
    dialog.y_panel.table.item(0, 1).setText("1.0")
    dialog.y_panel.table.item(1, 1).setText("10000.0")

    dialog._on_accept()

    assert dialog.y_calibration is not None
    assert dialog.y_calibration.scale is AxisScale.LOG
    # 4 decades (1 -> 10000) over 200px => 50px per decade.
    assert dialog.y_calibration.pixel_to_value(150.0) == pytest.approx(1000.0)


def test_auto_detect_populates_editable_removable_rows(qtbot: QtBot) -> None:
    image = np.full((200, 300, 3), 255, dtype=np.uint8)
    cv2.line(image, (60, 5), (60, 195), (0, 0, 0), 2)
    cv2.line(image, (5, 140), (295, 140), (0, 0, 0), 2)

    dialog = AxisCalibrationDialog(image=image)
    qtbot.addWidget(dialog)

    dialog.x_panel.auto_detect_button.click()
    dialog.y_panel.auto_detect_button.click()

    assert dialog.x_panel.table.rowCount() >= 1
    assert float(dialog.x_panel.table.item(0, 0).text()) == pytest.approx(60.0, abs=2.0)
    assert dialog.y_panel.table.rowCount() >= 1

    # Detected rows are ordinary rows: editable value, removable, and not
    # committed to anything until the user accepts the dialog.
    initial_row_count = dialog.x_panel.table.rowCount()
    dialog.x_panel.table.selectRow(0)
    dialog.x_panel._remove_selected()
    assert dialog.x_panel.table.rowCount() == initial_row_count - 1


def test_accept_with_too_few_points_shows_error_and_does_not_accept(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialog = AxisCalibrationDialog()
    qtbot.addWidget(dialog)
    dialog.add_point("x", 0.0)  # only one point: invalid

    calls: list[str] = []
    monkeypatch.setattr(
        "plot_digitizer.gui.calibration_dialog.QMessageBox.critical",
        lambda *args, **kwargs: calls.append("shown"),
    )

    dialog._on_accept()

    assert calls == ["shown"]
    assert dialog.x_calibration is None
    assert dialog.result() != dialog.DialogCode.Accepted


def test_add_reference_row_creates_live_scene_overlay(qtbot: QtBot) -> None:
    scene = _scene()
    baseline = len(scene.items())
    dialog = AxisCalibrationDialog(scene=scene)
    qtbot.addWidget(dialog)

    dialog.add_point("x", 60.0)
    dialog.add_point("y", 140.0)

    # One dashed line plus one label per row.
    assert len(scene.items()) == baseline + 4
    assert len(dialog.x_panel.overlay_rows) == 1
    assert len(dialog.y_panel.overlay_rows) == 1
    x_line, x_label = dialog.x_panel.overlay_rows[0]
    assert x_line in scene.items()
    assert x_label in scene.items()
    assert x_label.text() == "X1"
    assert x_line.line().x1() == pytest.approx(60.0)
    y_line, y_label = dialog.y_panel.overlay_rows[0]
    assert y_label.text() == "Y1"
    assert y_line.line().y1() == pytest.approx(140.0)


def test_remove_selected_removes_overlay_and_renumbers_labels(qtbot: QtBot) -> None:
    scene = _scene()
    dialog = AxisCalibrationDialog(scene=scene)
    qtbot.addWidget(dialog)
    dialog.add_point("x", 10.0)
    dialog.add_point("x", 20.0)
    dialog.add_point("x", 30.0)
    removed_line, removed_label = dialog.x_panel.overlay_rows[0]

    dialog.x_panel.table.selectRow(0)
    dialog.x_panel._remove_selected()

    assert dialog.x_panel.table.rowCount() == 2
    assert len(dialog.x_panel.overlay_rows) == 2
    assert removed_line not in scene.items()
    assert removed_label not in scene.items()
    # Surviving rows renumber so row N always maps to label X(N+1).
    assert [label.text() for _line, label in dialog.x_panel.overlay_rows] == ["X1", "X2"]
    assert dialog.x_panel.overlay_rows[0][0].line().x1() == pytest.approx(20.0)


def test_selecting_a_row_restyles_only_that_rows_overlay(qtbot: QtBot) -> None:
    scene = _scene()
    dialog = AxisCalibrationDialog(scene=scene)
    qtbot.addWidget(dialog)
    dialog.add_point("x", 10.0)
    dialog.add_point("x", 20.0)
    first_line = dialog.x_panel.overlay_rows[0][0]
    second_line = dialog.x_panel.overlay_rows[1][0]
    normal_width = first_line.pen().widthF()

    dialog.x_panel.table.selectRow(1)

    assert second_line.pen().widthF() > normal_width
    assert first_line.pen().widthF() == pytest.approx(normal_width)
    assert second_line.pen().color() != first_line.pen().color()

    dialog.x_panel.table.selectRow(0)

    assert first_line.pen().widthF() > normal_width
    assert second_line.pen().widthF() == pytest.approx(normal_width)


def test_reject_clears_all_temporary_overlays(qtbot: QtBot) -> None:
    scene = _scene()
    baseline = len(scene.items())
    dialog = AxisCalibrationDialog(scene=scene)
    qtbot.addWidget(dialog)
    dialog.add_point("x", 10.0)
    dialog.add_point("y", 20.0)
    assert len(scene.items()) > baseline

    dialog.reject()

    assert len(scene.items()) == baseline
    assert dialog.x_panel.overlay_rows == []
    assert dialog.y_panel.overlay_rows == []


def test_accept_clears_temporary_overlays_before_permanent_redraw(qtbot: QtBot) -> None:
    scene = _scene()
    baseline = len(scene.items())
    dialog = AxisCalibrationDialog(scene=scene)
    qtbot.addWidget(dialog)
    dialog.add_point("x", 0.0)
    dialog.add_point("x", 100.0)
    dialog.x_panel.table.item(0, 1).setText("0.0")
    dialog.x_panel.table.item(1, 1).setText("10.0")
    dialog.add_point("y", 0.0)
    dialog.add_point("y", 200.0)
    dialog.y_panel.table.item(0, 1).setText("0.0")
    dialog.y_panel.table.item(1, 1).setText("20.0")

    dialog._on_accept()

    assert dialog.result() == dialog.DialogCode.Accepted
    assert len(scene.items()) == baseline


def test_add_candidate_rows_marks_exactly_two_suggested_extremes(qtbot: QtBot) -> None:
    dialog = AxisCalibrationDialog(scene=_scene())
    qtbot.addWidget(dialog)
    candidates = [
        LineCandidate(position=120.0, length=190.0),
        LineCandidate(position=40.0, length=180.0),
        LineCandidate(position=260.0, length=170.0),
    ]

    dialog.x_panel.add_candidate_rows(candidates)

    table = dialog.x_panel.table
    assert table.rowCount() == 3
    bold_rows = [row for row in range(table.rowCount()) if table.item(row, 0).font().bold()]
    assert len(bold_rows) == 2
    marked_positions = {float(table.item(row, 0).text()) for row in bold_rows}
    assert marked_positions == {40.0, 260.0}
    # Highlighting is a proposal only: the rows stay editable and removable.
    assert table.item(bold_rows[0], 1).flags() & Qt.ItemFlag.ItemIsEditable
    table.selectRow(bold_rows[0])
    dialog.x_panel._remove_selected()
    assert table.rowCount() == 2


def _framed_chart(height: int = 400, width: int = 600) -> np.ndarray:
    """A chart with all four spines, so `detect_plot_area` can bound it."""
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (80, 40), (560, 340), (0, 0, 0), 2)
    return image


def test_add_candidate_rows_prefills_value_cell_from_ocr(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "plot_digitizer.gui.calibration_dialog.read_tick_label",
        lambda image, region: 12.5,
    )
    dialog = AxisCalibrationDialog(image=_framed_chart(), scene=_scene())
    qtbot.addWidget(dialog)

    dialog.x_panel.add_candidate_rows([LineCandidate(position=120.0, length=300.0)])

    value_item = dialog.x_panel.table.item(0, 1)
    assert value_item.text() == "12.5"
    # Still a proposal: the cell is editable like any hand-entered one.
    assert value_item.flags() & Qt.ItemFlag.ItemIsEditable


def test_add_candidate_rows_keeps_default_value_when_ocr_returns_none(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "plot_digitizer.gui.calibration_dialog.read_tick_label",
        lambda image, region: None,
    )
    dialog = AxisCalibrationDialog(image=_framed_chart(), scene=_scene())
    qtbot.addWidget(dialog)

    dialog.x_panel.add_candidate_rows([LineCandidate(position=120.0, length=300.0)])

    assert dialog.x_panel.table.item(0, 1).text() == "0.0"


def test_add_candidate_rows_without_image_skips_ocr(qtbot: QtBot) -> None:
    dialog = AxisCalibrationDialog(scene=_scene())
    qtbot.addWidget(dialog)

    dialog.x_panel.add_candidate_rows([LineCandidate(position=120.0, length=300.0)])

    assert dialog.x_panel.table.item(0, 1).text() == "0.0"


def test_add_candidate_rows_marks_nothing_when_no_suggestion(qtbot: QtBot) -> None:
    dialog = AxisCalibrationDialog(scene=_scene())
    qtbot.addWidget(dialog)

    dialog.x_panel.add_candidate_rows([LineCandidate(position=55.0, length=100.0)])

    table = dialog.x_panel.table
    assert table.rowCount() == 1
    assert not table.item(0, 0).font().bold()
