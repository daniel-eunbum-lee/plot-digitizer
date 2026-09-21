"""Best-effort OCR of axis tick labels, used only to pre-fill editable cells.

Like `axis_detection`, this module only ever *proposes*: a recovered number is
written into a calibration dialog cell the user still reviews and edits. OCR on
a 10-pixel-tall tick label is unreliable enough that anything auto-applied here
would silently corrupt a calibration, so every failure path -- an unreadable
crop, unparseable text, or a missing Tesseract binary entirely -- degrades to
`None` and the caller falls back to its ordinary default.

Known limitation: a log axis whose ticks are typeset as powers ("10^3") has no
plain-text number to read -- OCR sees the mantissa and exponent as one run of
digits and proposes 103 rather than 1000. That is precisely why the result
lands in an editable cell rather than in the calibration.

`pytesseract` is a thin wrapper around the separately-installed Tesseract
system binary. That binary is *not* installed by `uv sync`, so it is routinely
absent; `read_tick_label` therefore catches broadly rather than enumerating
exception types, and must never raise into the GUI layer.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytesseract

from plot_digitizer.imaging.axis_detection import (
    LineCandidate,
    detect_horizontal_lines,
    detect_vertical_lines,
)

# psm 7 == "treat the image as a single text line", which is exactly what a
# cropped tick label is. Whitelisting digits/./- keeps Tesseract from
# "helpfully" reading a 0 as an O or a 1 as an l, which float() would reject.
_TESSERACT_CONFIG = "--psm 7 -c tessedit_char_whitelist=0123456789.-"

# Tick-label text at a typical chart DPI (~150) is only ~10-14px tall, well
# below the ~30px Tesseract is tuned for, so upscale before OCR.
_UPSCALE_FACTOR = 3

# Crop geometry, as fractions of the plot area's own size, with pixel floors
# for very small charts. Fractions rather than fixed pixels because the same
# chart scanned at 2x resolution has 2x-taller labels sitting 2x further out,
# and the plot area scales with it.
#
# The numbers are tuned against matplotlib's default layout, measured on
# examples/test_plot_{easy,medium,hard}.png. The band has to thread a needle:
# wide enough for a 4-character label ("1000", "-2.5"), but tight enough to
# exclude the tick marks and the *axis title* on either side of it, since a
# stray glyph from either would make the whole line unparseable.
_X_LABEL_GAP_FRACTION = 0.017  # below the bottom spine, clearing the tick marks
_X_LABEL_HEIGHT_FRACTION = 0.032  # ...and stopping short of the x-axis title
_X_LABEL_HALF_WIDTH_FRACTION = 0.028
_Y_LABEL_GAP_FRACTION = 0.010  # left of the left spine
_Y_LABEL_WIDTH_FRACTION = 0.038  # ...and stopping short of the y-axis title
_Y_LABEL_HALF_HEIGHT_FRACTION = 0.020

_MIN_LABEL_GAP = 4
_MIN_X_LABEL_HEIGHT = 14
_MIN_X_LABEL_HALF_WIDTH = 14
_MIN_Y_LABEL_WIDTH = 30
_MIN_Y_LABEL_HALF_HEIGHT = 9

# How many of the longest detected lines are trusted as plot-area edge
# candidates. Beyond this, short strays (legend borders, the curve itself)
# start to dominate and would blow the bounding box out.
_PLOT_AREA_TOP_K = 6


def read_tick_label(image: np.ndarray, region: tuple[int, int, int, int]) -> float | None:
    """Read `region` of `image` as a single number, or return None if it can't be.

    `region` is `(x0, y0, x1, y1)` in pixel coordinates and is clamped to the
    image bounds. Returns None -- never raises -- for a degenerate region,
    empty or non-numeric OCR output, a missing Tesseract binary
    (`pytesseract.TesseractNotFoundError`), or any other failure.
    """
    crop = _crop(image, region)
    if crop is None:
        return None
    try:
        text = pytesseract.image_to_string(_prepare_for_ocr(crop), config=_TESSERACT_CONFIG)
    except Exception:
        # Includes TesseractNotFoundError (binary not installed) and any
        # subprocess/decoding failure. OCR is a convenience, not a feature the
        # app depends on, so no failure here is worth surfacing.
        return None
    return _parse_number(text)


def tick_label_region(
    candidate: LineCandidate,
    *,
    axis: str,
    plot_area: tuple[float, float, float, float],
    image_shape: tuple[int, int],
) -> tuple[int, int, int, int]:
    """Guess where `candidate`'s tick label sits, as an `(x0, y0, x1, y1)` crop.

    `plot_area` is `(left, top, right, bottom)` in pixel coordinates. Charts
    put x tick labels in a band just *below* the plot's bottom edge, centred on
    the tick's column, and y tick labels just *left* of the left edge, centred
    on the tick's row -- so the plot area is what anchors the offsets. The
    returned box is clamped to `image_shape` (height, width).
    """
    left, top, right, bottom = plot_area
    height, width = image_shape
    plot_width = right - left
    plot_height = bottom - top
    if axis == "x":
        half_width = max(_MIN_X_LABEL_HALF_WIDTH, _X_LABEL_HALF_WIDTH_FRACTION * plot_width)
        gap = max(_MIN_LABEL_GAP, _X_LABEL_GAP_FRACTION * plot_height)
        band = max(_MIN_X_LABEL_HEIGHT, _X_LABEL_HEIGHT_FRACTION * plot_height)
        x0 = candidate.position - half_width
        x1 = candidate.position + half_width
        y0 = bottom + gap
        y1 = y0 + band
    else:
        half_height = max(_MIN_Y_LABEL_HALF_HEIGHT, _Y_LABEL_HALF_HEIGHT_FRACTION * plot_height)
        gap = max(_MIN_LABEL_GAP, _Y_LABEL_GAP_FRACTION * plot_width)
        band = max(_MIN_Y_LABEL_WIDTH, _Y_LABEL_WIDTH_FRACTION * plot_width)
        x1 = left - gap
        x0 = x1 - band
        y0 = candidate.position - half_height
        y1 = candidate.position + half_height
    return (
        _clamp(x0, width),
        _clamp(y0, height),
        _clamp(x1, width),
        _clamp(y1, height),
    )


def detect_plot_area(image: np.ndarray) -> tuple[float, float, float, float] | None:
    """Infer the plot's bounding box from its detected axis spines.

    The two outermost long vertical lines are taken as the left/right edges and
    the two outermost long horizontal lines as the top/bottom edges -- on a
    framed chart these are the spines, and on an unframed one the outermost
    gridlines, which are close enough to anchor a label crop.

    Returns None when the image yields too few lines to bound a box, or when
    the resulting box is degenerate.
    """
    verticals = detect_vertical_lines(image)[:_PLOT_AREA_TOP_K]
    horizontals = detect_horizontal_lines(image)[:_PLOT_AREA_TOP_K]
    if len(verticals) < 2 or len(horizontals) < 2:
        return None
    left = min(candidate.position for candidate in verticals)
    right = max(candidate.position for candidate in verticals)
    top = min(candidate.position for candidate in horizontals)
    bottom = max(candidate.position for candidate in horizontals)
    if left >= right or top >= bottom:
        return None
    return left, top, right, bottom


def _crop(image: np.ndarray, region: tuple[int, int, int, int]) -> np.ndarray | None:
    height, width = image.shape[:2]
    x0, y0, x1, y1 = region
    x0, x1 = sorted((_clamp(x0, width), _clamp(x1, width)))
    y0, y1 = sorted((_clamp(y0, height), _clamp(y1, height)))
    if x1 - x0 < 1 or y1 - y0 < 1:
        return None
    return image[y0:y1, x0:x1]


def _prepare_for_ocr(crop: np.ndarray) -> np.ndarray:
    """Grayscale, upscale, then binarize -- in that order.

    Upscaling before thresholding lets the cubic interpolation work on the
    original anti-aliased grays; thresholding first would throw that detail
    away and leave blocky, jagged glyph edges for Tesseract. Otsu picks the
    black/white split per crop, which handles both crisp screenshots and the
    washed-out grays of a scan without a hand-tuned constant.
    """
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    upscaled = cv2.resize(
        gray,
        None,
        fx=_UPSCALE_FACTOR,
        fy=_UPSCALE_FACTOR,
        interpolation=cv2.INTER_CUBIC,
    )
    _threshold, binary = cv2.threshold(upscaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return np.asarray(binary)


def _parse_number(text: str) -> float | None:
    # The character whitelist can still emit stray separators at either end
    # (a tick mark clipped into the crop reads as a '-' or '.'), so trim those
    # before parsing rather than discarding an otherwise-good read. A leading
    # '-' is meaningful, so only trailing signs are stripped.
    cleaned = text.strip().strip(".").rstrip("-")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _clamp(value: float, limit: int) -> int:
    return max(0, min(int(round(value)), limit))
