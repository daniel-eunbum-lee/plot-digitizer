from __future__ import annotations

import pytest

from plot_digitizer.calibration.axis import AxisCalibration, AxisScale
from plot_digitizer.calibration.resample import resample_curve_to_step
from plot_digitizer.calibration.transform import CoordinateTransform
from plot_digitizer.model.point import Point


def _linear_transform() -> CoordinateTransform:
    """Pixel x == data x, and data y == 100 - pixel y (y grows upward)."""
    x_axis = AxisCalibration(scale=AxisScale.LINEAR)
    x_axis.add_reference(pixel=0.0, value=0.0)
    x_axis.add_reference(pixel=100.0, value=100.0)

    y_axis = AxisCalibration(scale=AxisScale.LINEAR)
    y_axis.add_reference(pixel=100.0, value=0.0)
    y_axis.add_reference(pixel=0.0, value=100.0)

    return CoordinateTransform(x_axis=x_axis, y_axis=y_axis)


def _log_x_transform() -> CoordinateTransform:
    """Log x over 2 decades (1 at pixel 0, 100 at pixel 200), linear y."""
    x_axis = AxisCalibration(scale=AxisScale.LOG)
    x_axis.add_reference(pixel=0.0, value=1.0)
    x_axis.add_reference(pixel=200.0, value=100.0)

    y_axis = AxisCalibration(scale=AxisScale.LINEAR)
    y_axis.add_reference(pixel=100.0, value=0.0)
    y_axis.add_reference(pixel=0.0, value=100.0)

    return CoordinateTransform(x_axis=x_axis, y_axis=y_axis)


def test_resamples_linear_curve_onto_exact_grid() -> None:
    transform = _linear_transform()
    # y = 2x + 1 in data space, sampled at irregular x.
    data_x = [0.0, 1.0, 7.0, 10.0]
    points = [transform.data_to_pixel(x, 2 * x + 1) for x in data_x]

    resampled = resample_curve_to_step(points, transform, step=2.5)

    results = [transform.pixel_to_data(point) for point in resampled]
    assert [result.x for result in results] == pytest.approx([0.0, 2.5, 5.0, 7.5, 10.0])
    # Linear interpolation of a linear function is exact.
    assert [result.y for result in results] == pytest.approx([1.0, 6.0, 11.0, 16.0, 21.0])


def test_nonlinear_curve_matches_manual_linear_interpolation() -> None:
    transform = _linear_transform()
    # y = x**2 sampled at integer x; interpolation is piecewise-linear, not exact.
    data_x = [0.0, 1.0, 2.0, 3.0, 4.0]
    points = [transform.data_to_pixel(x, x**2) for x in data_x]

    resampled = resample_curve_to_step(points, transform, step=0.5)

    results = [transform.pixel_to_data(point) for point in resampled]
    assert [result.x for result in results] == pytest.approx(
        [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    )
    # Midpoints are the mean of the bracketing samples (e.g. x=1.5 -> (1 + 4) / 2).
    assert [result.y for result in results] == pytest.approx(
        [0.0, 0.5, 1.0, 2.5, 4.0, 6.5, 9.0, 12.5, 16.0]
    )
    # Not the true curve value: 1.5**2 == 2.25, but linear interpolation gives 2.5.
    assert results[3].y != pytest.approx(2.25)


def test_grid_stops_at_or_before_the_last_data_x() -> None:
    transform = _linear_transform()
    points = [transform.data_to_pixel(x, x) for x in (0.0, 7.0)]

    resampled = resample_curve_to_step(points, transform, step=2.0)

    grid_x = [transform.pixel_to_data(point).x for point in resampled]
    assert grid_x == pytest.approx([0.0, 2.0, 4.0, 6.0])


def test_grid_starts_at_the_first_data_x_without_snapping() -> None:
    transform = _linear_transform()
    points = [transform.data_to_pixel(x, x) for x in (1.3, 5.3)]

    resampled = resample_curve_to_step(points, transform, step=2.0)

    grid_x = [transform.pixel_to_data(point).x for point in resampled]
    assert grid_x == pytest.approx([1.3, 3.3, 5.3])


def test_unsorted_input_points_are_sorted_by_data_x() -> None:
    transform = _linear_transform()
    points = [transform.data_to_pixel(x, 2 * x + 1) for x in (10.0, 0.0, 4.0)]

    resampled = resample_curve_to_step(points, transform, step=5.0)

    results = [transform.pixel_to_data(point) for point in resampled]
    assert [result.x for result in results] == pytest.approx([0.0, 5.0, 10.0])
    assert [result.y for result in results] == pytest.approx([1.0, 11.0, 21.0])


def test_log_x_axis_uses_additive_steps_in_data_space() -> None:
    transform = _log_x_transform()
    points = [transform.data_to_pixel(x, 10.0) for x in (1.0, 100.0)]

    resampled = resample_curve_to_step(points, transform, step=1.0)

    grid_x = [transform.pixel_to_data(point).x for point in resampled]
    assert len(grid_x) == 100
    # Additive (1, 2, 3, ...), not multiplicative (1, 10, 100).
    assert grid_x[:4] == pytest.approx([1.0, 2.0, 3.0, 4.0])
    assert grid_x[-1] == pytest.approx(100.0)


def test_rejects_non_positive_step() -> None:
    transform = _linear_transform()
    points = [transform.data_to_pixel(x, x) for x in (0.0, 10.0)]

    with pytest.raises(ValueError, match="step must be positive"):
        resample_curve_to_step(points, transform, step=0.0)
    with pytest.raises(ValueError, match="step must be positive"):
        resample_curve_to_step(points, transform, step=-1.0)


def test_rejects_fewer_than_two_points() -> None:
    transform = _linear_transform()

    with pytest.raises(ValueError, match="at least 2 points"):
        resample_curve_to_step([], transform, step=1.0)
    with pytest.raises(ValueError, match="at least 2 points"):
        resample_curve_to_step([Point(x=0.0, y=0.0)], transform, step=1.0)
