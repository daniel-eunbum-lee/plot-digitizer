"""QGraphicsView-based canvas: displays the loaded image with zoom/pan."""

from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPainter, QPixmap, QWheelEvent
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from plot_digitizer.gui.modes import InteractionMode


def bgr_to_pixmap(image: np.ndarray) -> QPixmap:
    """Convert an OpenCV BGR array to a QPixmap for display."""
    rgb = np.ascontiguousarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    height, width, channels = rgb.shape
    qimage = QImage(rgb.data, width, height, channels * width, QImage.Format.Format_RGB888)
    # .copy() detaches from the numpy buffer, which QImage would otherwise
    # reference without owning -- `rgb` going out of scope would leave the
    # pixmap pointing at freed memory.
    return QPixmap.fromImage(qimage.copy())


class ImageCanvas(QGraphicsView):
    """Displays a raster image with mouse-wheel zoom, drag-to-pan, and mode-gated click-picking.

    Scene coordinates are set up to equal source-image pixel coordinates
    (the pixmap is added at the scene origin with sceneRect matching its
    pixel size), so `imageClicked` coordinates can be used directly as
    `Point` pixel coordinates with no further conversion.
    """

    _ZOOM_STEP = 1.15
    _MIN_SCALE = 0.05
    _MAX_SCALE = 40.0

    imageClicked = Signal(float, float)

    def __init__(self) -> None:
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._scale_factor = 1.0
        self._mode = InteractionMode.PAN

        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._apply_drag_mode()

    @property
    def mode(self) -> InteractionMode:
        return self._mode

    @mode.setter
    def mode(self, value: InteractionMode) -> None:
        self._mode = value
        self._apply_drag_mode()

    def _apply_drag_mode(self) -> None:
        drag_mode = (
            QGraphicsView.DragMode.ScrollHandDrag
            if self._mode is InteractionMode.PAN
            else QGraphicsView.DragMode.NoDrag
        )
        self.setDragMode(drag_mode)

    def load_image(self, image: np.ndarray) -> None:
        pixmap = bgr_to_pixmap(image)
        self._scene.clear()
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(pixmap.rect())
        self._scale_factor = 1.0
        self.resetTransform()
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._pixmap_item is None:
            return
        zoom_in = event.angleDelta().y() > 0
        factor = self._ZOOM_STEP if zoom_in else 1 / self._ZOOM_STEP
        new_scale = self._scale_factor * factor
        if not (self._MIN_SCALE <= new_scale <= self._MAX_SCALE):
            return
        self._scale_factor = new_scale
        self.scale(factor, factor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._pixmap_item is not None and self._mode is not InteractionMode.PAN:
            scene_pos = self.mapToScene(event.position().toPoint())
            self.imageClicked.emit(scene_pos.x(), scene_pos.y())
            return
        super().mousePressEvent(event)
