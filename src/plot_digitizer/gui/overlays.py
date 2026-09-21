"""Overlay graphics items drawn on top of the canvas image."""

from __future__ import annotations

from PySide6.QtCore import QLineF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsSimpleTextItem,
)

_PEN_WIDTH = 2.0
_HIGHLIGHT_PEN_WIDTH = 4.0
_HIGHLIGHT_COLOR = QColor("#ff8c00")
_OVERLAY_Z = 10.0
_POINT_RADIUS = 4.0
_LABEL_OFFSET = 4.0
_LABEL_POINT_SIZE = 9


def make_vertical_reference_line(x: float, height: float, color: QColor) -> QGraphicsLineItem:
    """Dashed vertical line marking an x-axis reference point's pixel position."""
    item = QGraphicsLineItem(QLineF(x, 0.0, x, height))
    pen = QPen(color, _PEN_WIDTH)
    pen.setStyle(Qt.PenStyle.DashLine)
    item.setPen(pen)
    item.setZValue(_OVERLAY_Z)
    return item


def make_data_point_marker(x: float, y: float, color: QColor) -> QGraphicsEllipseItem:
    """Filled circle marking one picked/traced data point at its pixel position."""
    item = QGraphicsEllipseItem(
        QRectF(x - _POINT_RADIUS, y - _POINT_RADIUS, _POINT_RADIUS * 2, _POINT_RADIUS * 2)
    )
    item.setBrush(QBrush(color))
    item.setPen(QPen(QColor("black"), 1))
    item.setZValue(_OVERLAY_Z + 1)
    return item


def make_horizontal_reference_line(y: float, width: float, color: QColor) -> QGraphicsLineItem:
    """Dashed horizontal line marking a y-axis reference point's pixel position."""
    item = QGraphicsLineItem(QLineF(0.0, y, width, y))
    pen = QPen(color, _PEN_WIDTH)
    pen.setStyle(Qt.PenStyle.DashLine)
    item.setPen(pen)
    item.setZValue(_OVERLAY_Z)
    return item


def make_reference_label(text: str, x: float, y: float, color: QColor) -> QGraphicsSimpleTextItem:
    """Small text tag naming a reference line, so a table row maps to a visible line."""
    item = QGraphicsSimpleTextItem(text)
    font = QFont()
    font.setPointSize(_LABEL_POINT_SIZE)
    font.setBold(True)
    item.setFont(font)
    item.setBrush(QBrush(color))
    item.setPos(x + _LABEL_OFFSET, y + _LABEL_OFFSET)
    item.setZValue(_OVERLAY_Z + 2)
    # Scene units are image pixels, so without this the tag would scale with
    # wheel zoom and become unreadable (or enormous) instead of staying a
    # fixed-size screen annotation.
    item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
    return item


def set_reference_line_highlighted(
    item: QGraphicsLineItem, *, highlighted: bool, base_color: QColor
) -> None:
    """Toggle a reference line between its normal and selected-row appearance."""
    pen = item.pen()
    pen.setWidthF(_HIGHLIGHT_PEN_WIDTH if highlighted else _PEN_WIDTH)
    pen.setColor(_HIGHLIGHT_COLOR if highlighted else base_color)
    pen.setStyle(Qt.PenStyle.SolidLine if highlighted else Qt.PenStyle.DashLine)
    item.setPen(pen)
