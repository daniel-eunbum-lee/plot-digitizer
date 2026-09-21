from __future__ import annotations

import cv2
import numpy as np
import pytest

from plot_digitizer.imaging.axis_detection import detect_plot_area
from plot_digitizer.imaging.legend_detect import detect_legend_box


def _chart_with_legend(
    *,
    legend_box: tuple[int, int, int, int] = (250, 30, 370, 70),
    plot_box: tuple[int, int, int, int] = (40, 20, 380, 260),
) -> np.ndarray:
    """A framed plot with a small, inset, dark-bordered legend-like box."""
    image = np.full((300, 400, 3), 255, dtype=np.uint8)
    left, top, right, bottom = plot_box
    cv2.rectangle(image, (left, top), (right, bottom), (0, 0, 0), 2)
    lx0, ly0, lx1, ly1 = legend_box
    cv2.rectangle(image, (lx0, ly0), (lx1, ly1), (60, 60, 60), 1)
    return image


def test_detects_a_legend_inset_from_the_plot_spines() -> None:
    image = _chart_with_legend()
    plot_area = detect_plot_area(image)

    box = detect_legend_box(image, plot_area=plot_area)

    assert box is not None
    x0, y0, x1, y1 = box
    assert x0 == pytest.approx(250, abs=3)
    assert y0 == pytest.approx(30, abs=3)
    assert x1 == pytest.approx(370, abs=3)
    assert y1 == pytest.approx(70, abs=3)


def test_returns_none_without_a_plot_area() -> None:
    image = _chart_with_legend()

    assert detect_legend_box(image, plot_area=None) is None


def test_returns_none_when_no_box_clears_the_spines() -> None:
    # Only the plot's own frame exists -- no separate inset box to find.
    image = np.full((300, 400, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (40, 20), (380, 260), (0, 0, 0), 2)
    plot_area = detect_plot_area(image)

    assert detect_legend_box(image, plot_area=plot_area) is None


def test_ignores_a_light_gridline_bounded_region() -> None:
    # A grid cell bounded by thin, light gridlines must not be mistaken for a
    # legend: its "border" is far lighter than a legend's deliberate dark frame.
    image = _chart_with_legend()
    cv2.rectangle(image, (100, 100), (200, 180), (210, 210, 210), 1)
    plot_area = detect_plot_area(image)

    box = detect_legend_box(image, plot_area=plot_area)

    assert box is not None
    assert box != (100, 100, 200, 180)
