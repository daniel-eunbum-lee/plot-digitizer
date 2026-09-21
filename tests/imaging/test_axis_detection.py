import cv2
import numpy as np
import pytest

from plot_digitizer.imaging.axis_detection import detect_horizontal_lines, detect_vertical_lines


def _blank_chart(height: int = 200, width: int = 300) -> np.ndarray:
    return np.full((height, width, 3), 255, dtype=np.uint8)


def test_detect_vertical_lines_finds_known_axis_position() -> None:
    image = _blank_chart()
    cv2.line(image, (50, 5), (50, 195), (0, 0, 0), 2)

    candidates = detect_vertical_lines(image)

    assert candidates
    assert candidates[0].position == pytest.approx(50.0, abs=2.0)


def test_detect_horizontal_lines_finds_known_axis_position() -> None:
    image = _blank_chart()
    cv2.line(image, (5, 150), (295, 150), (0, 0, 0), 2)

    candidates = detect_horizontal_lines(image)

    assert candidates
    assert candidates[0].position == pytest.approx(150.0, abs=2.0)


def test_detect_vertical_lines_ignores_horizontal_lines() -> None:
    image = _blank_chart()
    cv2.line(image, (5, 100), (295, 100), (0, 0, 0), 2)

    candidates = detect_vertical_lines(image)

    assert candidates == []


def test_no_lines_returns_empty_list() -> None:
    image = _blank_chart()

    assert detect_vertical_lines(image) == []
    assert detect_horizontal_lines(image) == []


def test_longest_candidate_ranked_first() -> None:
    image = _blank_chart()
    cv2.line(image, (50, 80), (50, 120), (0, 0, 0), 2)  # short
    cv2.line(image, (200, 5), (200, 195), (0, 0, 0), 2)  # long, full-height

    candidates = detect_vertical_lines(image, min_length_fraction=0.1)

    assert candidates[0].position == pytest.approx(200.0, abs=2.0)
