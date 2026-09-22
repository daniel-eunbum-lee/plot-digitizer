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


def test_thin_1px_line_is_not_erased_by_mask_cleanup() -> None:
    # Regression test: the mask-cleanup step used to run a 3x3 morphological
    # "open" unconditionally to despeckle noise, but that requires a full 3x3
    # same-color neighborhood to survive -- which erases *any* stroke thinner
    # than that, including a perfectly real 1px hairline (common on
    # screenshots/vector-rendered charts), not just noise.
    image = np.full((200, 300, 3), 255, dtype=np.uint8)
    cv2.line(image, (10, 100), (290, 50), (0, 0, 255), 1)

    traced = trace_curve_by_color(image, target_bgr=(0, 0, 255), tolerance=30.0)

    assert len(traced) > 250


def test_legend_swatch_is_not_traced_as_curve_data() -> None:
    # A framed plot with a small inset legend box holding a sample line in
    # the exact curve color, well clear of the real curve -- if it leaked
    # into the trace it would show up as spurious points at the legend's row.
    image = np.full((200, 300, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (20, 10), (280, 190), (0, 0, 0), 2)  # plot spines
    curve_points = np.array([(30, 150), (150, 100), (270, 60)], dtype=np.int32)
    cv2.polylines(image, [curve_points], False, (0, 0, 255), 2)
    cv2.rectangle(image, (200, 20), (260, 40), (80, 80, 80), 1)  # legend frame
    cv2.line(image, (205, 30), (225, 30), (0, 0, 255), 2)  # legend swatch line

    traced = trace_curve_by_color(image, target_bgr=(0, 0, 255), tolerance=30.0)

    assert traced
    assert all(p.y > 40 for p in traced)


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


def test_marker_clipped_by_the_image_border_traces_to_one_point_not_many() -> None:
    # A scatter-plot marker sitting at (or near) a plot's edge is often
    # partly cut off by the image border. detect_marker_blobs deliberately
    # doesn't report a clipped glyph as a full blob (only part of it was
    # drawn), so without special handling it used to fall through to the
    # column-wise line tracer and produce one spurious point per column
    # instead of the single real data point it represents.
    image = _draw_curve_with_markers(with_line=False)
    clipped_center = (0, 170)
    cv2.circle(image, clipped_center, _MARKER_RADIUS, (0, 0, 255), -1)

    traced = trace_curve_by_color(image, target_bgr=(0, 0, 255), tolerance=30.0)

    assert len(traced) == len(_MARKER_CENTERS) + 1
    near_edge = [p for p in traced if p.x < _MARKER_RADIUS * 2]
    assert len(near_edge) == 1
    assert abs(near_edge[0].y - clipped_center[1]) < 2.0


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


def _load_answer_key(path: Path) -> list[tuple[float, float]]:
    with path.open(newline="") as handle:
        return [(float(row["x"]), float(row["y"])) for row in csv.DictReader(handle)]


def _nearest_y_errors(traced: list, answer_key: list[tuple[float, float]]) -> list[float]:
    """Absolute y-error at each answer-key x, matched to the nearest traced point."""
    errors = []
    for key_x, key_y in answer_key:
        nearest = min(traced, key=lambda point: abs(point.x - key_x))
        assert abs(nearest.x - key_x) < 0.1
        errors.append(nearest.y - key_y)
    return errors


def _nearest_y_relative_errors_allowing_gaps(
    traced: list, answer_key: list[tuple[float, float]], *, x_tolerance: float = 0.15
) -> list[float]:
    """Like `_nearest_y_errors`, but relative (see below) and gap-tolerant.

    Relative to the answer's value, since a fixed absolute tolerance means
    wildly different things at y=1 and y=1000 on a log-scale axis. Gap
    tolerant: on a chart with heavily overlapping curves, one curve is
    occasionally fully hidden behind another at a given x, leaving no
    traced point anywhere near it -- an answer-key x with no sufficiently
    close traced match is skipped rather than forced into a bogus error
    against whatever unrelated point happens to be nearest. The caller
    should still assert most points *did* find a close match, so this
    can't silently paper over a genuinely broken trace.
    """
    errors = []
    matched = 0
    for key_x, key_y in answer_key:
        nearest = min(traced, key=lambda point: abs(point.x - key_x))
        if abs(nearest.x - key_x) > x_tolerance:
            continue
        matched += 1
        errors.append((nearest.y - key_y) / key_y)
    assert matched >= 0.9 * len(answer_key), (
        f"only {matched}/{len(answer_key)} answer-key points had a close traced match"
    )
    return errors


def test_easy_example_curve_matches_its_answer_key() -> None:
    image = cv2.imread(str(_EXAMPLES_DIR / "test_plot_easy.png"))
    assert image is not None
    # The legend's sample line and glyph are drawn in the identical curve
    # color as curve 1; trace_curve_by_color's automatic legend exclusion
    # (legend_detect.detect_legend_box) is what keeps them out, not a manual
    # crop -- this test would fail if that exclusion silently broke.

    left, right, bottom, top = _axes_spines(image)
    transform = CoordinateTransform(
        x_axis=AxisCalibration(AxisScale.LINEAR, [(left, 0.0), (right, 10.0)]),
        y_axis=AxisCalibration(AxisScale.LINEAR, [(bottom, 0.0), (top, 50.0)]),
    )
    traced = [
        transform.pixel_to_data(point)
        for point in trace_curve_by_color(image, target_bgr=(180, 119, 31), tolerance=30.0)
    ]

    answer_key = _load_answer_key(_EXAMPLES_DIR / "test_plot_easy_curve1.csv")
    errors = _nearest_y_errors(traced, answer_key)
    rms_error = math.sqrt(sum(error**2 for error in errors) / len(errors))
    # 1% of the chart's 50-unit y-range. The measured error is ~0.03 (0.06%),
    # so this leaves an order of magnitude of headroom for rasterization
    # differences between OpenCV builds.
    assert rms_error < 0.5
    assert max(abs(error) for error in errors) < 1.0


def test_medium_example_curves_match_their_answer_keys() -> None:
    image = cv2.imread(str(_EXAMPLES_DIR / "test_plot_medium.png"))
    assert image is not None
    left, right, bottom, top = _axes_spines(image)
    transform = CoordinateTransform(
        x_axis=AxisCalibration(AxisScale.LINEAR, [(left, 0.0), (right, 20.0)]),
        y_axis=AxisCalibration(AxisScale.LINEAR, [(bottom, 0.0), (top, 100.0)]),
    )
    # (curve number, color, rms tolerance, max tolerance), all well under 1%
    # of the chart's 100-unit y-range; measured errors are ~0.08/0.44/0.04
    # rms and ~0.18/0.50/0.07 max, respectively.
    cases = [
        (1, (180, 119, 31), 0.5, 1.0),
        (2, (44, 160, 44), 1.0, 1.5),
        (3, (14, 127, 255), 0.5, 1.0),
    ]
    for curve_number, bgr, rms_tolerance, max_tolerance in cases:
        traced = [
            transform.pixel_to_data(point)
            for point in trace_curve_by_color(image, target_bgr=bgr, tolerance=30.0)
        ]
        answer_key = _load_answer_key(_EXAMPLES_DIR / f"test_plot_medium_curve{curve_number}.csv")
        errors = _nearest_y_errors(traced, answer_key)
        rms_error = math.sqrt(sum(error**2 for error in errors) / len(errors))
        assert rms_error < rms_tolerance, f"curve {curve_number}: rms error {rms_error}"
        assert max(abs(error) for error in errors) < max_tolerance, f"curve {curve_number}"


def test_hard_example_solid_curves_match_their_answer_keys() -> None:
    """Curves 1 and 3: solid strokes, distinct colors -- the "normal" cases here.

    Curves 2 and 4 are deliberately excluded from this accuracy assertion and
    documented instead (examples/README.md) as known-hard cases for
    color-based auto-trace: curve 2 is intentionally near-identical in color
    to curve 1 (a stress test), and curve 4 is a thin, marker-less,
    dash-dot line under this image's scan noise -- manual point-picking is
    the recommended path for both, not a tolerance this test should pretend
    to guarantee.
    """
    image = cv2.imread(str(_EXAMPLES_DIR / "test_plot_hard.png"))
    assert image is not None
    left, right, bottom, top = _axes_spines(image)
    transform = CoordinateTransform(
        x_axis=AxisCalibration(AxisScale.LINEAR, [(left, 0.0), (right, 10.0)]),
        y_axis=AxisCalibration(AxisScale.LOG, [(bottom, 1.0), (top, 1000.0)]),
    )
    # (curve number, color, rms relative-error tolerance, max relative-error
    # tolerance) -- relative, since the y-axis is logarithmic and a fixed
    # absolute tolerance means very different things at y=1 vs y=1000.
    # Measured: curve 1 ~3.7%/16% (rms/max), curve 3 ~0.3%/0.7%.
    cases = [
        (1, (168, 63, 26), 0.10, 0.25),
        (3, (40, 39, 214), 0.05, 0.10),
    ]
    for curve_number, bgr, rms_tolerance, max_tolerance in cases:
        traced = [
            transform.pixel_to_data(point)
            for point in trace_curve_by_color(image, target_bgr=bgr, tolerance=30.0)
        ]
        answer_key = _load_answer_key(_EXAMPLES_DIR / f"test_plot_hard_curve{curve_number}.csv")
        errors = _nearest_y_relative_errors_allowing_gaps(traced, answer_key)
        rms_error = math.sqrt(sum(error**2 for error in errors) / len(errors))
        assert rms_error < rms_tolerance, f"curve {curve_number}: rms relative error {rms_error}"
        assert max(abs(error) for error in errors) < max_tolerance, f"curve {curve_number}"


def test_hard_example_curve4_no_longer_traces_to_nothing() -> None:
    # curve 4 (gray, dash-dot, no markers) is thin enough that mask cleanup
    # used to erase it completely under this image's scan noise (see the
    # _clean_mask fallback path). It remains a documented hard case for
    # accuracy (see examples/README.md) -- this only guards the regression
    # of silently tracing zero points instead of an imperfect-but-real curve.
    image = cv2.imread(str(_EXAMPLES_DIR / "test_plot_hard.png"))
    assert image is not None

    traced = trace_curve_by_color(image, target_bgr=(127, 127, 127), tolerance=30.0)

    assert traced


def test_scatter_example_series_match_their_answer_keys() -> None:
    """Marker-only digitizing (no connecting line at all) against a real scatter chart."""
    image = cv2.imread(str(_EXAMPLES_DIR / "test_plot_scatter.png"))
    assert image is not None
    left, right, bottom, top = _axes_spines(image)
    transform = CoordinateTransform(
        x_axis=AxisCalibration(AxisScale.LINEAR, [(left, 0.0), (right, 10.0)]),
        y_axis=AxisCalibration(AxisScale.LINEAR, [(bottom, 0.0), (top, 10.0)]),
    )
    # (series number, color, expected point count) -- exact count, not just an
    # accuracy tolerance: a marker-only chart has no notion of "the curve
    # crosses this x", so a missed or spurious point is a distinct failure
    # mode from a slightly-off one.
    cases = [(1, (180, 119, 31), 15), (2, (40, 39, 214), 12)]
    for series_number, bgr, expected_count in cases:
        traced = [
            transform.pixel_to_data(point)
            for point in trace_curve_by_color(image, target_bgr=bgr, tolerance=30.0)
        ]
        answer_key = _load_answer_key(_EXAMPLES_DIR / f"test_plot_scatter_curve{series_number}.csv")
        assert len(traced) == expected_count == len(answer_key), f"series {series_number}"
        for key_x, key_y in answer_key:
            nearest = min(traced, key=lambda point: abs(point.x - key_x))
            assert abs(nearest.x - key_x) < 0.05, f"series {series_number}"
            assert abs(nearest.y - key_y) < 0.05, f"series {series_number}"


def test_sample_color_bgr_reads_exact_pixel() -> None:
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    image[5, 5] = (10, 20, 30)

    assert sample_color_bgr(image, Point(x=5.0, y=5.0)) == (10, 20, 30)


def test_sample_color_bgr_clamps_out_of_bounds() -> None:
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    image[9, 9] = (1, 2, 3)

    assert sample_color_bgr(image, Point(x=100.0, y=100.0)) == (1, 2, 3)
    assert sample_color_bgr(image, Point(x=-5.0, y=-5.0)) == tuple(image[0, 0].tolist())
