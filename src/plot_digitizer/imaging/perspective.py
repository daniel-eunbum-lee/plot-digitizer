"""4-point perspective correction: straightens a skewed photo/scan of a chart."""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from plot_digitizer.model.point import Point


@dataclass
class PerspectiveTransform:
    """Homography mapping 4 clicked source corners onto an axis-aligned rectangle.

    Corner order matters and must be consistent: top-left, top-right,
    bottom-right, bottom-left (clockwise from top-left). getPerspectiveTransform
    just solves for whatever correspondence it's given, so a mismatched
    corner order would silently produce a mirrored/rotated warp rather than
    raise an error -- there's nothing in the math itself that can catch that.
    """

    src_points: tuple[Point, Point, Point, Point]
    output_size: tuple[int, int]

    def _matrix(self) -> np.ndarray:
        width, height = self.output_size
        dst = np.array(
            [(0, 0), (width - 1, 0), (width - 1, height - 1), (0, height - 1)],
            dtype=np.float32,
        )
        src = np.array([(p.x, p.y) for p in self.src_points], dtype=np.float32)
        return cv2.getPerspectiveTransform(src, dst)

    def warp_image(self, image: np.ndarray) -> np.ndarray:
        width, height = self.output_size
        return cv2.warpPerspective(image, self._matrix(), (width, height))

    def warp_point(self, point: Point) -> Point:
        matrix = self._matrix()
        vector = matrix @ np.array([point.x, point.y, 1.0])
        return Point(x=vector[0] / vector[2], y=vector[1] / vector[2])


def estimate_output_size(corners: tuple[Point, Point, Point, Point]) -> tuple[int, int]:
    """Pick an output rectangle size from 4 clicked corners (TL, TR, BR, BL).

    Averages opposite edge lengths so a slightly skewed quadrilateral still
    produces a sensible width/height instead of a fixed, arbitrary size.
    """
    top_left, top_right, bottom_right, bottom_left = corners

    def distance(a: Point, b: Point) -> float:
        return math.hypot(a.x - b.x, a.y - b.y)

    width = (distance(top_left, top_right) + distance(bottom_left, bottom_right)) / 2
    height = (distance(top_left, bottom_left) + distance(top_right, bottom_right)) / 2
    return max(1, round(width)), max(1, round(height))
