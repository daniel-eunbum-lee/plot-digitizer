from __future__ import annotations

import pytest
from PySide6.QtGui import QColor

from plot_digitizer.gui.overlays import make_data_point_marker, set_data_point_marker_highlighted

pytestmark = pytest.mark.gui

_BASE_COLOR = QColor("#1f77b4")


def test_highlighting_a_marker_changes_its_color_and_size() -> None:
    marker = make_data_point_marker(10.0, 20.0, _BASE_COLOR)
    original_rect = marker.rect()

    set_data_point_marker_highlighted(marker, highlighted=True, base_color=_BASE_COLOR)

    assert marker.brush().color() != _BASE_COLOR
    assert marker.rect().width() > original_rect.width()


def test_unhighlighting_a_marker_restores_its_original_appearance() -> None:
    marker = make_data_point_marker(10.0, 20.0, _BASE_COLOR)
    original_rect = marker.rect()

    set_data_point_marker_highlighted(marker, highlighted=True, base_color=_BASE_COLOR)
    set_data_point_marker_highlighted(marker, highlighted=False, base_color=_BASE_COLOR)

    assert marker.brush().color() == _BASE_COLOR
    assert marker.rect().width() == pytest.approx(original_rect.width())
    assert marker.rect().center() == original_rect.center()
