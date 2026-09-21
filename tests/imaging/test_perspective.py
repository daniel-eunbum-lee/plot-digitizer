import cv2
import numpy as np
import pytest

from plot_digitizer.imaging.perspective import PerspectiveTransform, estimate_output_size
from plot_digitizer.model.point import Point


def test_warp_point_maps_corners_to_output_rectangle() -> None:
    corners = (
        Point(x=10.0, y=20.0),
        Point(x=110.0, y=30.0),
        Point(x=100.0, y=180.0),
        Point(x=0.0, y=170.0),
    )
    transform = PerspectiveTransform(src_points=corners, output_size=(100, 150))

    assert transform.warp_point(corners[0]).x == pytest.approx(0.0, abs=1e-3)
    assert transform.warp_point(corners[0]).y == pytest.approx(0.0, abs=1e-3)
    assert transform.warp_point(corners[2]).x == pytest.approx(99.0, abs=1e-3)
    assert transform.warp_point(corners[2]).y == pytest.approx(149.0, abs=1e-3)


def test_warp_image_produces_requested_output_size() -> None:
    image = np.zeros((200, 200, 3), dtype=np.uint8)
    corners = (
        Point(x=20.0, y=10.0),
        Point(x=180.0, y=30.0),
        Point(x=170.0, y=190.0),
        Point(x=10.0, y=170.0),
    )
    transform = PerspectiveTransform(src_points=corners, output_size=(120, 160))

    warped = transform.warp_image(image)

    assert warped.shape[:2] == (160, 120)


def test_warp_image_straightens_a_known_skew() -> None:
    # A skewed white quadrilateral on a black background; after correction
    # the interior should be (almost) entirely white, since the corners are
    # mapped exactly onto the output rectangle's corners.
    image = np.zeros((200, 200, 3), dtype=np.uint8)
    corners_px = np.array([[20, 40], [190, 10], [180, 195], [5, 160]], dtype=np.int32)
    cv2.fillConvexPoly(image, corners_px, (255, 255, 255))

    corners = tuple(Point(x=float(x), y=float(y)) for x, y in corners_px)
    transform = PerspectiveTransform(src_points=corners, output_size=(100, 100))

    warped = transform.warp_image(image)
    interior = warped[10:-10, 10:-10]

    assert interior.mean() > 250


def test_estimate_output_size_averages_opposite_edges() -> None:
    corners = (
        Point(x=0.0, y=0.0),
        Point(x=100.0, y=0.0),
        Point(x=100.0, y=50.0),
        Point(x=0.0, y=50.0),
    )
    width, height = estimate_output_size(corners)
    assert width == 100
    assert height == 50
