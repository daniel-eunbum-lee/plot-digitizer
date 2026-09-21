import pytest

from plot_digitizer.calibration.axis import AxisCalibration, AxisScale
from plot_digitizer.calibration.transform import CoordinateTransform
from plot_digitizer.model.point import Point


def test_independent_linear_x_and_log_y_axes() -> None:
    x_axis = AxisCalibration(scale=AxisScale.LINEAR)
    x_axis.add_reference(pixel=0.0, value=0.0)
    x_axis.add_reference(pixel=100.0, value=10.0)

    y_axis = AxisCalibration(scale=AxisScale.LOG)
    y_axis.add_reference(pixel=200.0, value=1.0)
    y_axis.add_reference(pixel=0.0, value=100.0)

    transform = CoordinateTransform(x_axis=x_axis, y_axis=y_axis)

    data_point = transform.pixel_to_data(Point(x=50.0, y=100.0))
    assert data_point.x == pytest.approx(5.0)
    assert data_point.y == pytest.approx(10.0)


def test_pixel_to_data_to_pixel_round_trip() -> None:
    x_axis = AxisCalibration(scale=AxisScale.LINEAR)
    x_axis.add_reference(pixel=10.0, value=0.0)
    x_axis.add_reference(pixel=210.0, value=20.0)

    y_axis = AxisCalibration(scale=AxisScale.LINEAR)
    y_axis.add_reference(pixel=300.0, value=0.0)
    y_axis.add_reference(pixel=100.0, value=50.0)

    transform = CoordinateTransform(x_axis=x_axis, y_axis=y_axis)

    original = Point(x=123.0, y=210.0)
    data_point = transform.pixel_to_data(original)
    round_tripped = transform.data_to_pixel(data_point.x, data_point.y)

    assert round_tripped.x == pytest.approx(original.x)
    assert round_tripped.y == pytest.approx(original.y)
