import pytest

from plot_digitizer.calibration.axis import AxisCalibration, AxisScale
from plot_digitizer.calibration.transform import CoordinateTransform
from plot_digitizer.model.curve import Curve
from plot_digitizer.model.point import Point


def _linear_transform() -> CoordinateTransform:
    x_axis = AxisCalibration(scale=AxisScale.LINEAR)
    x_axis.add_reference(pixel=0.0, value=0.0)
    x_axis.add_reference(pixel=100.0, value=10.0)
    y_axis = AxisCalibration(scale=AxisScale.LINEAR)
    y_axis.add_reference(pixel=0.0, value=100.0)
    y_axis.add_reference(pixel=100.0, value=0.0)
    return CoordinateTransform(x_axis=x_axis, y_axis=y_axis)


def test_add_and_remove_point() -> None:
    curve = Curve(name="c1")
    curve.add_point(Point(x=1.0, y=2.0))
    curve.add_point(Point(x=3.0, y=4.0))

    assert len(curve.points) == 2
    curve.remove_point(0)
    assert curve.points == [Point(x=3.0, y=4.0)]


def test_move_point_replaces_in_place() -> None:
    curve = Curve(name="c1")
    curve.add_point(Point(x=1.0, y=2.0))

    curve.move_point(0, Point(x=9.0, y=9.0))

    assert curve.points == [Point(x=9.0, y=9.0)]


def test_to_data_points_applies_transform_in_order() -> None:
    curve = Curve(name="c1")
    curve.add_point(Point(x=0.0, y=0.0))
    curve.add_point(Point(x=50.0, y=50.0))

    data_points = curve.to_data_points(_linear_transform())

    assert [p.x for p in data_points] == pytest.approx([0.0, 5.0])
    assert [p.y for p in data_points] == pytest.approx([100.0, 50.0])
