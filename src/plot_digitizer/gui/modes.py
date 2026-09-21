"""Canvas interaction modes: what a left-click on the canvas means."""

from __future__ import annotations

from enum import Enum, auto


class InteractionMode(Enum):
    PAN = auto()
    CALIBRATE = auto()
    PICK_POINT = auto()
    PERSPECTIVE_PICK = auto()
    AUTO_TRACE_SAMPLE = auto()
