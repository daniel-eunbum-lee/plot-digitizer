import cv2
import numpy as np

from plot_digitizer.imaging.marker_detect import detect_marker_blobs, estimate_stroke_thickness

_STROKE_ROW = 100
_STROKE_THICKNESS = 3
_MARKER_RADIUS = 8  # 17px diameter, comfortably above the stroke thickness
_CIRCLE_CENTERS = [(60, _STROKE_ROW), (180, _STROKE_ROW)]
_SQUARE_CENTER = (240, _STROKE_ROW)
_SQUARE_HALF = 8  # 17px square
_MIN_DIAMETER = 6.0
_MAX_DIAMETER = 40.0


def _blank_mask(height: int = 200, width: int = 300) -> np.ndarray:
    return np.zeros((height, width), dtype=np.uint8)


def _draw_thin_line(mask: np.ndarray) -> None:
    # Set the rows directly: cv2.line rasterizes a "thickness" of 3 as 5 rows,
    # which would make the expected thickness in these tests ambiguous.
    half = _STROKE_THICKNESS // 2
    mask[_STROKE_ROW - half : _STROKE_ROW + half + 1, :] = 1


def _mask_with_markers_on_a_line() -> np.ndarray:
    """A thin stroke with glyphs drawn on top of it, as a real chart draws them."""
    mask = _blank_mask()
    _draw_thin_line(mask)
    for center in _CIRCLE_CENTERS:
        cv2.circle(mask, center, _MARKER_RADIUS, 1, -1)
    cv2.rectangle(
        mask,
        (_SQUARE_CENTER[0] - _SQUARE_HALF, _SQUARE_CENTER[1] - _SQUARE_HALF),
        (_SQUARE_CENTER[0] + _SQUARE_HALF, _SQUARE_CENTER[1] + _SQUARE_HALF),
        1,
        -1,
    )
    return mask


def test_detect_marker_blobs_finds_every_glyph_at_its_true_center() -> None:
    mask = _mask_with_markers_on_a_line()

    blobs = detect_marker_blobs(mask, min_diameter=_MIN_DIAMETER, max_diameter=_MAX_DIAMETER)

    expected_centers = [*_CIRCLE_CENTERS, _SQUARE_CENTER]
    assert len(blobs) == len(expected_centers)
    # blobs come back sorted by x, matching the order the shapes were drawn in
    for blob, (x, y) in zip(blobs, expected_centers, strict=True):
        assert abs(blob.center_x - x) < 1.0
        assert abs(blob.center_y - y) < 1.0
        # Reported size is the eroded core grown back by the kernel width, which
        # is exact for a flat-sided glyph and a shade small for a round one.
        assert abs(blob.width - (2 * _MARKER_RADIUS + 1)) <= 2.0
        assert abs(blob.height - (2 * _MARKER_RADIUS + 1)) <= 2.0


def test_thin_line_alone_yields_no_blobs() -> None:
    mask = _blank_mask()
    _draw_thin_line(mask)

    assert detect_marker_blobs(mask, min_diameter=_MIN_DIAMETER, max_diameter=_MAX_DIAMETER) == []


def test_empty_mask_yields_no_blobs() -> None:
    assert (
        detect_marker_blobs(_blank_mask(), min_diameter=_MIN_DIAMETER, max_diameter=_MAX_DIAMETER)
        == []
    )


def test_short_thick_diagonal_stroke_is_not_mistaken_for_a_glyph() -> None:
    # Square-ish bounding box, but it only fills a fraction of it -- the case
    # the extent test exists for.
    mask = _blank_mask()
    cv2.line(mask, (40, 40), (70, 70), 1, 8)

    assert detect_marker_blobs(mask, min_diameter=_MIN_DIAMETER, max_diameter=_MAX_DIAMETER) == []


def test_glyph_larger_than_max_diameter_is_rejected() -> None:
    mask = _blank_mask()
    cv2.circle(mask, (150, 100), 40, 1, -1)

    assert detect_marker_blobs(mask, min_diameter=_MIN_DIAMETER, max_diameter=_MAX_DIAMETER) == []


def test_estimate_stroke_thickness_measures_a_horizontal_stroke() -> None:
    mask = _blank_mask()
    _draw_thin_line(mask)

    assert estimate_stroke_thickness(mask) == float(_STROKE_THICKNESS)


def test_estimate_stroke_thickness_measures_a_vertical_stroke() -> None:
    mask = _blank_mask()
    mask[:, 149:152] = 1

    # Column runs span the whole image height here; the row runs are the ones
    # that cross the stroke.
    assert estimate_stroke_thickness(mask) == float(_STROKE_THICKNESS)


def test_estimate_stroke_thickness_ignores_glyphs_drawn_on_the_stroke() -> None:
    assert estimate_stroke_thickness(_mask_with_markers_on_a_line()) == float(_STROKE_THICKNESS)


def test_estimate_stroke_thickness_ignores_isolated_glyphs() -> None:
    # A scatter chart has no stroke at all: reporting the glyph diameter here
    # would push every derived threshold past the glyphs themselves.
    mask = _blank_mask()
    for center in _CIRCLE_CENTERS:
        cv2.circle(mask, center, _MARKER_RADIUS, 1, -1)

    assert estimate_stroke_thickness(mask) == 0.0


def test_estimate_stroke_thickness_of_empty_mask_is_zero() -> None:
    assert estimate_stroke_thickness(_blank_mask()) == 0.0
