"""Pixel-space and data-space point types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    """A position in source-image pixel space. The persisted source of truth for a picked point."""

    x: float
    y: float


@dataclass(frozen=True)
class DataPoint:
    """A position in real-world data space.

    Always derived from a Point via the current CoordinateTransform, never
    persisted as the primary value -- re-calibrating an axis should rescale
    a curve's data values, not corrupt already-picked points.
    """

    x: float
    y: float
