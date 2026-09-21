import cv2
import numpy as np
import pytest

from plot_digitizer.imaging.axis_detection import (
    LineCandidate,
    detect_horizontal_lines,
    detect_vertical_lines,
    suggest_extremes,
)


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


def test_suggest_extremes_picks_min_and_max_position() -> None:
    candidates = [
        LineCandidate(position=120.0, length=190.0),
        LineCandidate(position=40.0, length=180.0),
        LineCandidate(position=260.0, length=170.0),
        LineCandidate(position=80.0, length=160.0),
    ]

    suggestion = suggest_extremes(candidates)

    assert suggestion is not None
    low, high = suggestion
    assert low.position == 40.0
    assert high.position == 260.0


def test_suggest_extremes_only_considers_top_k_longest() -> None:
    # The list arrives sorted by length descending; the far-out short line
    # past top_k must not be allowed to win the "extreme" slot.
    candidates = [
        LineCandidate(position=100.0, length=190.0),
        LineCandidate(position=200.0, length=180.0),
        LineCandidate(position=900.0, length=20.0),
    ]

    suggestion = suggest_extremes(candidates, top_k=2)

    assert suggestion is not None
    low, high = suggestion
    assert (low.position, high.position) == (100.0, 200.0)


def test_suggest_extremes_returns_none_for_too_few_candidates() -> None:
    assert suggest_extremes([]) is None
    assert suggest_extremes([LineCandidate(position=10.0, length=100.0)]) is None
    # Two candidates exist, but top_k trims the list below the pair minimum.
    candidates = [
        LineCandidate(position=10.0, length=100.0),
        LineCandidate(position=50.0, length=90.0),
    ]
    assert suggest_extremes(candidates, top_k=1) is None


def test_suggest_extremes_returns_none_when_all_positions_identical() -> None:
    candidates = [
        LineCandidate(position=70.0, length=100.0),
        LineCandidate(position=70.0, length=90.0),
    ]

    assert suggest_extremes(candidates) is None


def test_suggest_extremes_with_duplicate_positions_still_spans_the_range() -> None:
    candidates = [
        LineCandidate(position=50.0, length=100.0),
        LineCandidate(position=50.0, length=95.0),
        LineCandidate(position=250.0, length=90.0),
    ]

    suggestion = suggest_extremes(candidates)

    assert suggestion is not None
    low, high = suggestion
    assert (low.position, high.position) == (50.0, 250.0)
