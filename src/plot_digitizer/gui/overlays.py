"""Overlay graphics items drawn on top of the canvas image."""

from __future__ import annotations

from PySide6.QtCore import QLineF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsLineItem

_PEN_WIDTH = 2.0
_OVERLAY_Z = 10.0
_POINT_RADIUS = 4.0


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
