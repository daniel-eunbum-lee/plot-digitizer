from __future__ import annotations

import cv2
import numpy as np
import pytest
from pytestqt.qtbot import QtBot

from plot_digitizer.calibration.axis import AxisScale
from plot_digitizer.gui.calibration_dialog import AxisCalibrationDialog

pytestmark = pytest.mark.gui


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
