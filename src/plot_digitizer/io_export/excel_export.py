"""Export every digitized curve to an Excel workbook, one sheet per curve."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from plot_digitizer.calibration.transform import CoordinateTransform
from plot_digitizer.model.curve import Curve

# Excel's own hard limit on a sheet name's length.
_MAX_SHEET_NAME_LENGTH = 31
# Characters Excel forbids in a sheet name.
_INVALID_SHEET_CHARS = frozenset("[]:*?/\\")


def export_curves_excel(curves: list[Curve], transform: CoordinateTransform, path: Path) -> None:
    workbook = Workbook()
    used_names: set[str] = set()
    for index, curve in enumerate(curves):
        sheet_name = _unique_sheet_name(curve.name, used_names)
        used_names.add(sheet_name)
        # The workbook starts with one default sheet ("Sheet"); reuse it for
        # the first curve instead of creating-then-removing it, since a
        # workbook can never be saved with zero sheets.
        sheet = workbook.active if index == 0 else workbook.create_sheet()
        assert sheet is not None
        sheet.title = sheet_name
        sheet.append(["x", "y"])
        for point in curve.to_data_points(transform):
            sheet.append([point.x, point.y])
    workbook.save(path)


def _unique_sheet_name(name: str, used: set[str]) -> str:
    sanitized = _sanitize_sheet_name(name)
    candidate = sanitized[:_MAX_SHEET_NAME_LENGTH]
    suffix = 1
    while candidate in used:
        suffix += 1
        marker = f"_{suffix}"
        candidate = sanitized[: _MAX_SHEET_NAME_LENGTH - len(marker)] + marker
    return candidate


def _sanitize_sheet_name(name: str) -> str:
    cleaned = "".join(ch for ch in name if ch not in _INVALID_SHEET_CHARS).strip()
    return cleaned or "Sheet"
