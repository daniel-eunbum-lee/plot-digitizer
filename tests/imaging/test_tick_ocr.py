from __future__ import annotations

import shutil

import cv2
import numpy as np
import pytest

from plot_digitizer.imaging.axis_detection import LineCandidate
from plot_digitizer.imaging.tick_ocr import read_tick_label, tick_label_region

requires_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None,
    reason="Tesseract OCR engine not installed",
)


def _text_image(text: str, *, width: int = 120, height: int = 40) -> np.ndarray:
    """Render black `text` on a white canvas at roughly chart tick-label size."""
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    cv2.putText(
        image,
        text,
        (6, height - 12),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    return image


@requires_tesseract
@pytest.mark.parametrize("text", ["42", "42.5", "-7", "1000", "0"])
def test_read_tick_label_recovers_rendered_number(text: str) -> None:
    image = _text_image(text)

    assert read_tick_label(image, (0, 0, image.shape[1], image.shape[0])) == pytest.approx(
        float(text)
    )


@requires_tesseract
def test_read_tick_label_returns_none_for_blank_region() -> None:
    blank = np.full((40, 120, 3), 255, dtype=np.uint8)

    assert read_tick_label(blank, (0, 0, 120, 40)) is None


@requires_tesseract
def test_read_tick_label_returns_none_for_non_numeric_text() -> None:
    image = _text_image("Curve", width=180)

    assert read_tick_label(image, (0, 0, 180, 40)) is None


def test_read_tick_label_returns_none_for_degenerate_region() -> None:
    image = _text_image("42")

    assert read_tick_label(image, (10, 10, 10, 10)) is None
    assert read_tick_label(image, (500, 500, 600, 600)) is None


def test_read_tick_label_returns_none_when_tesseract_binary_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pytesseract

    def _raise(*args: object, **kwargs: object) -> str:
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "image_to_string", _raise)

    assert read_tick_label(_text_image("42"), (0, 0, 120, 40)) is None


def test_read_tick_label_returns_none_on_unexpected_ocr_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(*args: object, **kwargs: object) -> str:
        raise RuntimeError("tesseract exploded")

    monkeypatch.setattr("pytesseract.image_to_string", _raise)

    assert read_tick_label(_text_image("42"), (0, 0, 120, 40)) is None


def test_tick_label_region_for_x_axis_sits_below_the_plot_area() -> None:
    region = tick_label_region(
        LineCandidate(position=300.0, length=300.0),
        axis="x",
        plot_area=(80.0, 40.0, 560.0, 340.0),
        image_shape=(400, 600),
    )

    x0, y0, x1, y1 = region
    assert x0 < 300 < x1
    assert y0 >= 340
    assert y1 > y0


def test_tick_label_region_for_y_axis_sits_left_of_the_plot_area() -> None:
    region = tick_label_region(
        LineCandidate(position=200.0, length=480.0),
        axis="y",
        plot_area=(80.0, 40.0, 560.0, 340.0),
        image_shape=(400, 600),
    )

    x0, y0, x1, y1 = region
    assert x1 <= 80
    assert x0 < x1
    assert y0 < 200 < y1


def test_tick_label_region_is_clamped_to_image_bounds() -> None:
    region = tick_label_region(
        LineCandidate(position=5.0, length=300.0),
        axis="y",
        plot_area=(10.0, 5.0, 560.0, 395.0),
        image_shape=(400, 600),
    )

    x0, y0, x1, y1 = region
    assert 0 <= x0 <= x1 <= 600
    assert 0 <= y0 <= y1 <= 400
