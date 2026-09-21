import csv
import math
from pathlib import Path

import cv2
import numpy as np

from plot_digitizer.calibration.axis import AxisCalibration, AxisScale
from plot_digitizer.calibration.transform import CoordinateTransform
from plot_digitizer.imaging.color import sample_color_bgr
from plot_digitizer.imaging.curve_trace import trace_curve_by_color
from plot_digitizer.model.point import Point

_EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
_MARKER_CENTERS = [(50, 140), (150, 90), (250, 120)]
_MARKER_RADIUS = 8  # 17px glyph over a ~5px stroke, as on a real chart


def _draw_sine_curve(width: int = 300, height: int = 200) -> tuple[np.ndarray, list[int]]:
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    expected_y = []
    for x in range(width):
        y = int(100 - 60 * math.sin(x / 40))
        expected_y.append(y)
    points = np.array(list(zip(range(width), expected_y, strict=True)), dtype=np.int32)
    cv2.polylines(image, [points], False, (0, 0, 255), 2)
    return image, expected_y


def test_trace_curve_by_color_matches_known_sine_within_tolerance() -> None:
    image, expected_y = _draw_sine_curve()

    traced = trace_curve_by_color(image, target_bgr=(0, 0, 255), tolerance=30.0)

    assert len(traced) > 250
    traced_by_x = {int(p.x): p.y for p in traced}
    errors = [abs(traced_by_x[x] - expected_y[x]) for x in traced_by_x if 5 < x < 295]
    rms_error = math.sqrt(sum(e**2 for e in errors) / len(errors))
    assert rms_error < 3.0


def test_trace_curve_ignores_unrelated_colors() -> None:
    image, _ = _draw_sine_curve()
    cv2.line(image, (0, 190), (299, 190), (0, 0, 0), 1)  # unrelated black axis line

    traced = trace_curve_by_color(image, target_bgr=(0, 0, 255), tolerance=30.0)

    assert all(p.y < 180 for p in traced)


def test_no_matching_color_returns_empty_list() -> None:
    image = np.full((100, 100, 3), 255, dtype=np.uint8)

    traced = trace_curve_by_color(image, target_bgr=(0, 255, 0), tolerance=10.0)

    assert traced == []


def _draw_curve_with_markers(*, with_line: bool) -> np.ndarray:
    image = np.full((200, 300, 3), 255, dtype=np.uint8)
    if with_line:
        cv2.polylines(image, [np.array(_MARKER_CENTERS, dtype=np.int32)], False, (0, 0, 255), 3)
    for center in _MARKER_CENTERS:
        cv2.circle(image, center, _MARKER_RADIUS, (0, 0, 255), -1)
    return image


def test_marker_on_a_line_traces_to_exactly_one_point_at_its_center() -> None:
    image = _draw_curve_with_markers(with_line=True)

    traced = trace_curve_by_color(image, target_bgr=(0, 0, 255), tolerance=30.0)

    for center_x, center_y in _MARKER_CENTERS:
        inside_marker = [p for p in traced if abs(p.x - center_x) <= _MARKER_RADIUS]
        # One point for the glyph, not one per column of its silhouette.
        assert len(inside_marker) == 1
        assert abs(inside_marker[0].x - center_x) < 1.0
        assert abs(inside_marker[0].y - center_y) < 1.0


def test_markers_without_a_connecting_line_trace_to_their_centers_only() -> None:
    image = _draw_curve_with_markers(with_line=False)

    traced = trace_curve_by_color(image, target_bgr=(0, 0, 255), tolerance=30.0)

    # Nothing is drawn between the glyphs, so nothing may be invented there.
    assert len(traced) == len(_MARKER_CENTERS)
    for point, (center_x, center_y) in zip(traced, _MARKER_CENTERS, strict=True):
        assert abs(point.x - center_x) < 1.0
        assert abs(point.y - center_y) < 1.0


def test_marker_free_curve_traces_identically_with_and_without_marker_detection() -> None:
    image, _ = _draw_sine_curve()

    with_detection = trace_curve_by_color(image, target_bgr=(0, 0, 255), tolerance=30.0)
    without_detection = trace_curve_by_color(
        image, target_bgr=(0, 0, 255), tolerance=30.0, detect_markers=False
    )

    assert with_detection == without_detection


def test_dashed_example_curve_traces_identically_with_and_without_marker_detection() -> None:
    # test_plot_hard's curve B is dashed with no markers at all: its dash
    # fragments must not be mistaken for glyphs, so enabling detection may not
    # change a single traced point.
    image = cv2.imread(str(_EXAMPLES_DIR / "test_plot_hard.png"))
    assert image is not None
    dashed_blue = (184, 79, 42)  # "#2a4fb8" as BGR

    with_detection = trace_curve_by_color(image, target_bgr=dashed_blue, tolerance=30.0)
    without_detection = trace_curve_by_color(
        image, target_bgr=dashed_blue, tolerance=30.0, detect_markers=False
    )

    assert with_detection
    assert with_detection == without_detection


def _axes_spines(image: np.ndarray) -> tuple[float, float, float, float]:
    """(left, right, bottom, top) pixel positions of the plot box.

    The axes spines are the only near-black lines spanning most of the image,
    so the columns/rows where dark pixels dominate locate them. Each spine sits
    exactly at an axis limit, which is what makes them usable as calibration
    reference points.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    dark = gray < 100
    height, width = gray.shape
    columns = np.flatnonzero(dark.sum(axis=0) > 0.5 * height)
    rows = np.flatnonzero(dark.sum(axis=1) > 0.5 * width)
    return (
        float(columns[columns < width / 2].mean()),
        float(columns[columns > width / 2].mean()),
        float(rows[rows > height / 2].mean()),
        float(rows[rows < height / 2].mean()),
    )


def test_easy_example_curve_matches_its_answer_key() -> None:
    image = cv2.imread(str(_EXAMPLES_DIR / "test_plot_easy.png"))
    assert image is not None
    # The legend's sample line and glyph are drawn in the identical curve color;
    # restricting tracing to a region of interest is a separate concern, so
    # blank the legend box (well clear of both curves) out of the way here.
    image[55:145, 985:1165] = 255

    left, right, bottom, top = _axes_spines(image)
    transform = CoordinateTransform(
        x_axis=AxisCalibration(AxisScale.LINEAR, [(left, 0.0), (right, 10.0)]),
        y_axis=AxisCalibration(AxisScale.LINEAR, [(bottom, 0.0), (top, 50.0)]),
    )
    traced = [
        transform.pixel_to_data(point)
        for point in trace_curve_by_color(image, target_bgr=(180, 119, 31), tolerance=30.0)
    ]

    with (_EXAMPLES_DIR / "test_plot_easy_curve1.csv").open(newline="") as handle:
        answer_key = [(float(row["x"]), float(row["y"])) for row in csv.DictReader(handle)]

    errors = []
    for key_x, key_y in answer_key:
        nearest = min(traced, key=lambda point: abs(point.x - key_x))
        assert abs(nearest.x - key_x) < 0.1
        errors.append(nearest.y - key_y)
    rms_error = math.sqrt(sum(error**2 for error in errors) / len(errors))
    # 1% of the chart's 50-unit y-range. The measured error is ~0.03 (0.06%),
    # so this leaves an order of magnitude of headroom for rasterization
    # differences between OpenCV builds.
    assert rms_error < 0.5
    assert max(abs(error) for error in errors) < 1.0


def test_sample_color_bgr_reads_exact_pixel() -> None:
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    image[5, 5] = (10, 20, 30)

    assert sample_color_bgr(image, Point(x=5.0, y=5.0)) == (10, 20, 30)


def test_sample_color_bgr_clamps_out_of_bounds() -> None:
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    image[9, 9] = (1, 2, 3)

    assert sample_color_bgr(image, Point(x=100.0, y=100.0)) == (1, 2, 3)
    assert sample_color_bgr(image, Point(x=-5.0, y=-5.0)) == tuple(image[0, 0].tolist())
