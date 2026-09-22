import csv
from pathlib import Path

from plot_digitizer.calibration.axis import AxisCalibration, AxisScale
from plot_digitizer.calibration.transform import CoordinateTransform
from plot_digitizer.io_export.csv_export import export_curve_csv, export_curves_csv
from plot_digitizer.model.curve import Curve
from plot_digitizer.model.point import Point


def test_export_curve_csv_writes_header_and_data_rows(tmp_path: Path) -> None:
    x_axis = AxisCalibration(scale=AxisScale.LINEAR)
    x_axis.add_reference(pixel=0.0, value=0.0)
    x_axis.add_reference(pixel=100.0, value=10.0)
    y_axis = AxisCalibration(scale=AxisScale.LINEAR)
    y_axis.add_reference(pixel=0.0, value=0.0)
    y_axis.add_reference(pixel=100.0, value=20.0)
    transform = CoordinateTransform(x_axis=x_axis, y_axis=y_axis)

    curve = Curve(name="c1")
    curve.add_point(Point(x=0.0, y=0.0))
    curve.add_point(Point(x=50.0, y=50.0))

    out_path = tmp_path / "points.csv"
    export_curve_csv(curve, transform, out_path)

    with out_path.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.reader(csv_file))

    assert rows[0] == ["x", "y"]
    assert rows[1] == ["0.0", "0.0"]
    assert rows[2] == ["5.0", "10.0"]


def _identity_transform() -> CoordinateTransform:
    x_axis = AxisCalibration(scale=AxisScale.LINEAR)
    x_axis.add_reference(pixel=0.0, value=0.0)
    x_axis.add_reference(pixel=100.0, value=100.0)
    y_axis = AxisCalibration(scale=AxisScale.LINEAR)
    y_axis.add_reference(pixel=0.0, value=0.0)
    y_axis.add_reference(pixel=100.0, value=100.0)
    return CoordinateTransform(x_axis=x_axis, y_axis=y_axis)


def test_export_curves_csv_writes_a_column_pair_per_curve(tmp_path: Path) -> None:
    transform = _identity_transform()
    curve_a = Curve(name="Alpha", points=[Point(x=0.0, y=0.0), Point(x=10.0, y=10.0)])
    curve_b = Curve(name="Beta", points=[Point(x=5.0, y=5.0)])

    out_path = tmp_path / "all_curves.csv"
    export_curves_csv([curve_a, curve_b], transform, out_path)

    with out_path.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.reader(csv_file))

    assert rows[0] == ["Alpha_x", "Alpha_y", "Beta_x", "Beta_y"]
    assert rows[1] == ["0.0", "0.0", "5.0", "5.0"]
    assert rows[2] == ["10.0", "10.0", "", ""]
