# Plot Digitizer — Implementation Plan

Status legend: `[ ]` pending, `[~]` in progress, `[x]` done

## M0 — Guidelines & repo setup
- [x] `pyproject.toml` with dependencies + ruff/mypy/pytest config
- [x] `CLAUDE.md`
- [x] `PLAN.md` (this file)
- [x] Minimal package skeleton (`src/plot_digitizer/__init__.py`, `__main__.py`) + placeholder test
- [x] `uv sync`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
      `uv run mypy src` all verified clean

**Environment gap (resolved 2026-09-21):** this container's base image was missing system libs
`PySide6.QtGui`/`QtWidgets` need — `libGL.so.1`, then `libdbus-1.so.3`. Fixed for this running
container via `sudo apt-get install -y libgl1 libegl1 libxkbcommon0 libdbus-1-3`; verified
`QApplication` launches under `QT_QPA_PLATFORM=offscreen`. **Not yet persisted**: these packages
aren't in `.devcontainer/claude/devcontainer.json`'s `postCreateCommand`, so a fresh container
rebuild will hit this again — add them there if that's wanted. `pytest-qt` was deliberately left
out of the dev dependency group in M0; add it back (`uv add --group dev pytest-qt`) when M2 needs
actual GUI tests — the libs above are now confirmed present so it will work.

## M1 — Pure calibration/coordinate-transform math
- [x] `AxisScale` enum, `AxisCalibration` (linear + log, 2-point and least-squares fit)
- [x] `CoordinateTransform` (composes independent x/y `AxisCalibration`)
- [x] `Point` / `DataPoint` dataclasses
- [x] Tests: round-trips, error cases (duplicate pixels, non-positive log values) — 12 passing,
      `ruff check`/`ruff format --check`/`mypy src` all clean

## M2 — Minimal GUI shell (load image, zoom/pan)
- [x] `app.py` / `__main__.py` QApplication bootstrap
- [x] `gui/main_window.py`, `gui/canvas.py` (QGraphicsView zoom/pan)
- [x] `imaging/io.py` image load
- [x] Manual verify: launched offscreen, opened a synthetic image, scene rect matches image size;
      16 tests passing (`QT_QPA_PLATFORM=offscreen uv run pytest`), lint/format/mypy clean.
      **Not yet verified**: real on-screen wheel-zoom/drag-pan interaction (no display in this
      environment) — worth a manual check on a machine with a display before calling M2 fully done.

## M3 — Manual axis calibration workflow
- [x] `CALIBRATE` interaction mode (`gui/modes.py`), `gui/calibration_dialog.py`, `gui/overlays.py`
- [x] `model/project.py` (Project holds x/y `AxisCalibration` + `transform()`)
- [x] `ImageCanvas.imageClicked` signal, mode-gated (pan clicks don't emit, calibrate/pick do)
- [x] Verified: 28 tests passing incl. mode-gating and dialog accept/reject; manual scripted
      end-to-end run (add 2 x-refs + 2 y-refs, accept, `pixel_to_data`) matched hand-calculated
      values exactly. Lint/format/mypy clean.
      **Not yet verified**: real mouse-driven dialog interaction on a physical display.

## M4 — Manual point picking + CSV export
- [x] `PICK_POINT` mode (toggle menu action), `model/curve.py`, `gui/point_table.py` (dock widget)
- [x] `io_export/csv_export.py`, data-point canvas overlays (`gui/overlays.make_data_point_marker`)
- [x] Verified: 36 tests passing (curve model, CSV export format, pick-mode gating, table sync,
      export warns when uncalibrated / writes correct values when calibrated). Lint/format/mypy
      clean. v1 scope is a single default curve ("Curve 1") — multi-curve UI is M9.

## M5 — Log-scale axis support
- [x] Scale selector was already wired into `calibration_dialog.py`'s per-axis combo box in M3
      (each axis picks Linear/Log independently); math from M1. Added an explicit test exercising
      the full dialog -> `AxisCalibration(scale=LOG)` -> `pixel_to_value` path (4 decades over
      200px), confirming it end-to-end. 37 tests passing, lint/format/mypy clean.

## M6 — Perspective/distortion correction
- [x] `imaging/perspective.py` (`PerspectiveTransform`, `estimate_output_size`, homography via
      `cv2.getPerspectiveTransform`/`warpPerspective`)
- [x] `PERSPECTIVE_PICK` mode: click 4 corners (TL/TR/BR/BL) -> confirm -> replaces working image
      + resets calibration/points (pixel space changes entirely, so stale calibration would be
      silently wrong otherwise)
- [x] Verified: 44 tests passing (homography math, corner-order handling, confirm/decline flow);
      **visually confirmed** by rendering a synthetic skewed quadrilateral and its corrected
      output as PNGs and inspecting them — the skewed rectangle became axis-aligned with the
      interior marker preserved in the right relative position. Lint/format/mypy clean.
      Non-goal reminder: no lens undistortion, perspective only.

## M7 — Automatic axis/gridline detection
- [x] `imaging/axis_detection.py` (Canny + `cv2.HoughLinesP`, angle-filtered, merged by position,
      ranked by length) — caught a real OpenCV cross-version shape bug (`HoughLinesP` returns
      `(N,4)` on this installed version, not the commonly-documented `(N,1,4)`) via the pytest
      suite before it ever reached the GUI
- [x] "Auto-Detect Lines" button per axis in `calibration_dialog.py`: candidates land as ordinary
      editable/removable table rows (not auto-applied) — user still deletes wrong ones and always
      types the real value
- [x] Verified: 50 tests passing; **visually/numerically confirmed** on a synthetic chart with a
      real axis, 3 gridlines per axis, and a sine-wave curve — detected positions matched the
      known pixel positions within ~1px, and the curved line was correctly *not* picked up as a
      false-positive gridline. Lint/format/mypy clean.

## M8 — Automatic color-based curve tracing
- [x] `imaging/color.py` (`sample_color_bgr`), `imaging/curve_trace.py` (column-wise median
      tracing + open/close morphology cleanup), `gui/color_picker_dialog.py`
- [x] `AUTO_TRACE_SAMPLE` mode: click curve -> sample color -> review swatch/tolerance dialog ->
      traced points land as a new `source="auto"` `Curve`, editable like any manual one
- [x] Verified: 59 tests passing, incl. an RMS-error check against a known sine curve (< 3px RMS)
      and confirmation that an unrelated black axis line isn't picked up as the traced color.
      Lint/format/mypy clean. Non-goal reminder: function-like curves only (single y per x); no
      skeleton/graph-walk tracing for loops or parametric curves.

## M9 — Polish
- [x] Multi-curve/series support: `gui/curve_panel.py` dock (switch/add/delete curves), wired
      into `MainWindow` alongside the point table dock
- [x] Project save/load: `io_export/project_file.py` (JSON: calibration, curves, perspective);
      round-trips via dataclass equality in tests
- [x] Undo/redo: `gui/undo_commands.py` + `QUndoStack`, scoped to point add/remove only (the
      highest-value case) — calibration/curve-management edits are not undoable yet, noted below
- [x] Packaging: `uv run which plot-digitizer` resolves the console script; launched it under
      `QT_QPA_PLATFORM=offscreen`, confirmed it stayed running (didn't crash on startup), then
      terminated it cleanly
- [x] Full end-to-end run-through on a synthetic chart (axes + gridlines + a linear curve with a
      known equation): open image -> calibrate both axes -> manual pick -> undo -> redo ->
      auto-trace by color -> multi-curve -> save project -> reload project -> export CSV. The
      auto-traced curve's exported data values matched the chart's known equation exactly (e.g.
      y=62.4 at the curve's far end, computed by hand from the drawn pixel coordinates).
      69 tests passing; lint/format/mypy clean.

**Scope note**: undo/redo covers point add/remove only, not calibration or curve add/delete/
rename — acceptable for v1 since those are less frequent, deliberate actions rather than
misclicks, but worth expanding if real usage shows otherwise.

## Non-goals for v1
- Lens (barrel/pincushion) undistortion — only 4-point perspective correction is in scope.
- Skeleton/graph-walk tracing for looping or parametric (non-function) curves — column-wise
  centroid tracing only; revisit if real usage needs it.

## Post-v1 additions
- **Reset Project** (`File → Reset Project...`): confirms, then reloads the current image via the
  existing `open_image()` reset path — discards calibration, perspective, and all points without
  needing to re-browse for the file. Added because there was previously no way to discard bad
  calibration/points on the *same* image short of re-opening it via the file dialog.
- **Synthetic test plots with answer keys** (`examples/test_plot_{easy,medium,hard}.png` +
  per-curve `*_curveN.csv`, generated by `examples/generate_test_plots.py`): unlike the NASA
  example, each curve's exact data points are known and saved, so digitizing accuracy can be
  checked directly (diff the exported CSV against the answer key) rather than eyeballed. Adds
  `matplotlib` as a **dev-only** dependency (not imported anywhere under `src/`) for chart
  rendering. See `examples/README.md` for per-difficulty details.
