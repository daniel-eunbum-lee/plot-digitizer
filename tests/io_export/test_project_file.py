from pathlib import Path

from plot_digitizer.calibration.axis import AxisCalibration, AxisScale
from plot_digitizer.imaging.perspective import PerspectiveTransform
from plot_digitizer.io_export.project_file import load_project, save_project
from plot_digitizer.model.curve import Curve
from plot_digitizer.model.point import Point
from plot_digitizer.model.project import Project


def _sample_project() -> Project:
    x_axis = AxisCalibration(scale=AxisScale.LINEAR)
    x_axis.add_reference(pixel=0.0, value=0.0)
    x_axis.add_reference(pixel=100.0, value=10.0)
    y_axis = AxisCalibration(scale=AxisScale.LOG)
    y_axis.add_reference(pixel=0.0, value=1.0)
    y_axis.add_reference(pixel=100.0, value=100.0)

    manual_curve = Curve(name="Manual", color_hex="#ff0000", source="manual")
    manual_curve.add_point(Point(x=1.0, y=2.0))
    manual_curve.add_point(Point(x=3.0, y=4.0))

    auto_curve = Curve(name="Auto", color_hex="#00ff00", source="auto")
    auto_curve.add_point(Point(x=5.0, y=6.0))

    perspective = PerspectiveTransform(
        src_points=(
            Point(x=0.0, y=0.0),
            Point(x=100.0, y=0.0),
            Point(x=100.0, y=80.0),
            Point(x=0.0, y=80.0),
        ),
        output_size=(100, 80),
    )

    return Project(
        image_path=Path("chart.png"),
        x_axis=x_axis,
        y_axis=y_axis,
        curves=[manual_curve, auto_curve],
        active_curve_index=1,
        perspective=perspective,
    )


def test_save_and_load_round_trips_full_project(tmp_path: Path) -> None:
    project = _sample_project()
    path = tmp_path / "project.json"

    save_project(project, path)
    loaded = load_project(path)

    assert loaded == project


def test_load_without_perspective_round_trips(tmp_path: Path) -> None:
    project = Project(image_path=Path("chart.png"))
    project.add_curve("Curve 1")
    path = tmp_path / "project.json"

    save_project(project, path)
    loaded = load_project(path)

    assert loaded.perspective is None
    assert loaded.curves[0].name == "Curve 1"
