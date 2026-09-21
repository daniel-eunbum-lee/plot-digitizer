import math

import cv2
import numpy as np

from plot_digitizer.imaging.color import sample_color_bgr
from plot_digitizer.imaging.curve_trace import trace_curve_by_color
from plot_digitizer.model.point import Point


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


def test_sample_color_bgr_reads_exact_pixel() -> None:
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    image[5, 5] = (10, 20, 30)

    assert sample_color_bgr(image, Point(x=5.0, y=5.0)) == (10, 20, 30)


def test_sample_color_bgr_clamps_out_of_bounds() -> None:
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    image[9, 9] = (1, 2, 3)

    assert sample_color_bgr(image, Point(x=100.0, y=100.0)) == (1, 2, 3)
    assert sample_color_bgr(image, Point(x=-5.0, y=-5.0)) == tuple(image[0, 0].tolist())
