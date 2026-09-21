from pathlib import Path

import pytest

from plot_digitizer.calibration.axis import AxisScale
from plot_digitizer.model.point import Point
from plot_digitizer.model.project import Project


def test_new_project_defaults_to_linear_uncalibrated_axes() -> None:
    project = Project(image_path=Path("chart.png"))

    assert project.x_axis.scale is AxisScale.LINEAR
    assert project.y_axis.scale is AxisScale.LINEAR
    assert not project.is_calibrated()


def test_is_calibrated_true_once_both_axes_have_two_references() -> None:
    project = Project(image_path=Path("chart.png"))
    project.x_axis.add_reference(pixel=0.0, value=0.0)
    project.x_axis.add_reference(pixel=100.0, value=10.0)
    project.y_axis.add_reference(pixel=0.0, value=0.0)
    project.y_axis.add_reference(pixel=100.0, value=10.0)

    assert project.is_calibrated()


def test_transform_composes_both_axes() -> None:
    project = Project(image_path=Path("chart.png"))
    project.x_axis.add_reference(pixel=0.0, value=0.0)
    project.x_axis.add_reference(pixel=100.0, value=10.0)
    project.y_axis.add_reference(pixel=0.0, value=0.0)
    project.y_axis.add_reference(pixel=200.0, value=20.0)

    data_point = project.transform().pixel_to_data(Point(x=50.0, y=100.0))
    assert data_point.x == pytest.approx(5.0)
    assert data_point.y == pytest.approx(10.0)
