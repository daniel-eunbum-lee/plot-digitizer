import math

import pytest

from plot_digitizer.calibration.axis import AxisCalibration, AxisScale, CalibrationError


def test_linear_two_point_exact_recovery() -> None:
    axis = AxisCalibration(scale=AxisScale.LINEAR)
    axis.add_reference(pixel=100.0, value=0.0)
    axis.add_reference(pixel=300.0, value=20.0)

    assert axis.pixel_to_value(200.0) == pytest.approx(10.0)
    assert axis.value_to_pixel(10.0) == pytest.approx(200.0)


def test_log_two_point_exact_recovery_across_decades() -> None:
    axis = AxisCalibration(scale=AxisScale.LOG)
    axis.add_reference(pixel=0.0, value=1.0)
    axis.add_reference(pixel=100.0, value=100.0)

    assert axis.pixel_to_value(50.0) == pytest.approx(10.0)
    assert axis.value_to_pixel(10.0) == pytest.approx(50.0)


def test_linear_least_squares_with_more_than_two_points() -> None:
    axis = AxisCalibration(scale=AxisScale.LINEAR)
    # Noisy but linear-ish: true line is value = pixel / 10, with a nudge on one point.
    axis.add_reference(pixel=0.0, value=0.0)
    axis.add_reference(pixel=100.0, value=9.5)
    axis.add_reference(pixel=200.0, value=20.5)

    assert axis.pixel_to_value(100.0) == pytest.approx(10.0, abs=1.0)


def test_pixel_to_value_to_pixel_round_trip() -> None:
    axis = AxisCalibration(scale=AxisScale.LINEAR)
    axis.add_reference(pixel=50.0, value=5.0)
    axis.add_reference(pixel=150.0, value=25.0)

    for pixel in (50.0, 87.0, 150.0, 200.0):
        value = axis.pixel_to_value(pixel)
        assert axis.value_to_pixel(value) == pytest.approx(pixel)


def test_too_few_reference_points_raises() -> None:
    axis = AxisCalibration(scale=AxisScale.LINEAR)
    axis.add_reference(pixel=0.0, value=0.0)

    assert not axis.is_valid()
    with pytest.raises(CalibrationError, match="at least 2"):
        axis.pixel_to_value(10.0)


def test_duplicate_pixel_positions_raises() -> None:
    axis = AxisCalibration(scale=AxisScale.LINEAR)
    axis.add_reference(pixel=42.0, value=0.0)
    axis.add_reference(pixel=42.0, value=100.0)

    with pytest.raises(CalibrationError, match="same pixel position"):
        axis.pixel_to_value(10.0)


@pytest.mark.parametrize("bad_value", [0.0, -5.0])
def test_log_axis_rejects_non_positive_reference_value(bad_value: float) -> None:
    axis = AxisCalibration(scale=AxisScale.LOG)
    axis.add_reference(pixel=0.0, value=1.0)

    with pytest.raises(CalibrationError, match="positive"):
        axis.add_reference(pixel=100.0, value=bad_value)
        axis.pixel_to_value(50.0)


def test_log_axis_rejects_non_positive_value_to_pixel() -> None:
    axis = AxisCalibration(scale=AxisScale.LOG)
    axis.add_reference(pixel=0.0, value=1.0)
    axis.add_reference(pixel=100.0, value=100.0)

    with pytest.raises(CalibrationError, match="positive"):
        axis.value_to_pixel(0.0)


def test_log_scale_matches_manual_log10_math() -> None:
    axis = AxisCalibration(scale=AxisScale.LOG)
    axis.add_reference(pixel=0.0, value=1.0)
    axis.add_reference(pixel=200.0, value=10000.0)

    # 4 decades over 200px => 50px per decade.
    assert axis.value_to_pixel(1000.0) == pytest.approx(150.0)
    assert math.log10(axis.pixel_to_value(150.0)) == pytest.approx(3.0)
