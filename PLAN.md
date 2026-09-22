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

## M10 — Marker-aware curve tracing
- [x] `imaging/marker_detect.py` (`MarkerBlob`, `estimate_stroke_thickness`, `detect_marker_blobs`
      via eroded `cv2.findContours` + `cv2.moments`, sized relative to the estimated stroke
      thickness so thresholds scale with image resolution rather than hardcoded pixel constants)
- [x] `trace_curve_by_color(..., detect_markers=True)`: detects marker blobs, cuts their (dilated)
      bounding boxes out of the mask before the existing column-median line scan, then inserts one
      point per blob centroid — markers no longer skew the traced line, and marker-only (no
      connecting line) curves now trace correctly too. Zero-blob input (pure-line curves, e.g. the
      hard plot's dashed/dash-dot curves) is byte-identical to the pre-M10 algorithm.
- [x] Verified: 15 new/extended tests; RMS error on `examples/test_plot_easy.png` (answer-key
      checked) is 0.0298 data units = 0.06% of the 50-unit y-range — the first test to actually use
      the example-plot answer-key CSVs for accuracy checking. Lint/format/mypy clean.
      Scope note: no `kind`/`source` field added to `Point`/`DataPoint`/`Curve` — marker-vs-line
      distinction stays internal to tracing, no save-format change.

## M11 — Calibration UX: live overlays + auto-suggested extremes
- [x] `AxisCalibrationDialog`/`_AxisPanel` now take a `scene` and draw a live, labeled ("X1", "Y1",
      ...) overlay for every reference/candidate row as it's added — previously nothing was drawn
      on the canvas until the dialog was accepted. Selecting a table row highlights its overlay
      line; removing a row removes its overlay; reject/close clears all temporary overlays.
- [x] `imaging/axis_detection.suggest_extremes()`: picks the min/max-position candidates among the
      longest detected lines and visually flags those two rows (bold + highlight) as likely axis
      extremes — still ordinary editable/removable rows, never auto-applied, per M7's rule.
- [x] Verified: extended `test_calibration_dialog.py`/`test_axis_detection.py`; lint/format/mypy
      clean.

## M12 — OCR-based tick-value auto-fill
- [x] `imaging/tick_ocr.py` (`detect_plot_area`, `tick_label_region`, `read_tick_label` via
      `pytesseract`, grayscale -> 3x upscale -> Otsu threshold preprocessing) pre-fills a candidate
      row's Value cell with an OCR-read number instead of the previous hardcoded `"0.0"` — still a
      normal editable cell, same propose-never-auto-apply rule as line detection.
- [x] New dependency: `pytesseract` (pinned in `pyproject.toml`). **Requires the Tesseract OCR
      engine installed separately as a system binary** (not installed by `uv sync`) — documented in
      README. Every OCR call site catches failures (including `TesseractNotFoundError`) and
      degrades to no pre-fill; the app never crashes without the binary present.
- [x] Verified geometrically against all three example plots (plot-area detection + crop regions
      visually confirmed correct); recovers both axis endpoints on the easy/medium plots. Known
      limitation, documented in the module docstring: matplotlib's log-axis superscript tick labels
      (e.g. "10³") OCR as "103", not 1000 — expected to be corrected by hand in the editable cell.
      Tesseract wasn't installed in the dev environment this was built in, so the 7 OCR-dependent
      tests are `skipif`-guarded on `shutil.which("tesseract")`; non-OCR code paths (graceful
      degradation) are tested unconditionally. Lint/format/mypy clean.

## M13 — Fixed X-step (abscissa increment) resample
- [x] `calibration/resample.py` (pure, no Qt/OpenCV): `resample_curve_to_step(points, transform,
      step)` sorts to data space, builds a fixed-step grid from the data-x range, linearly
      interpolates via `numpy.interp`, converts back to pixel space. Log-x axes step additively in
      data space (matching how a user reads increments off the axis), not exponentially — documented
      inline since it sits next to the log-fit math in `calibration/axis.py`.
- [x] `gui/resample_dialog.py` + a "Resample to Fixed X Step..." button in `curve_panel.py`,
      wired through a new `ResampleCurveCommand` (`gui/undo_commands.py`) so applying it replaces
      the selected curve's points in place and is fully undoable via the existing `QUndoStack` —
      confirmed with a round-trip test (resample, then undo restores the exact original point list).
- [x] Verified: 12 new/extended tests covering grid boundaries, interpolation correctness, the
      log-x case, validation errors (`step <= 0`, <2 points), and the undo/redo round-trip.
      Lint/format/mypy clean.

## M14 — GitHub issue backlog (#1-#5)
- [x] #5 bug: `axis_detection._detect_lines` clustered a thick line's two Canny
      edges into one candidate at their midpoint (`_EDGE_MERGE_DISTANCE = 14px`,
      empirically covers strokes up to ~12px). Regression tests added for
      thick-line centering and for distinct nearby gridlines *not* merging.
      63 tests -> 65, all passing; lint/format/mypy clean.
- [x] #1 bug: added `imaging/legend_detect.py` (`detect_legend_box`): a
      rectangle inset from the plot spines with a dark solid border (vs. a
      light/dashed gridline-bounded region) and a plausible size. Wired into
      `curve_trace.trace_curve_by_color` as a mask-clearing step before
      thresholding/marker detection (`exclude_legend=True` by default).
      Refactored `detect_plot_area` out of `tick_ocr.py` into
      `axis_detection.py` (pure geometry, no OCR dependency) so curve tracing
      doesn't have to import `pytesseract` to use it. Verified against all
      three real example charts' actual legends plus synthetic tests
      (framed-box detection, no-plot-area no-op, gridline-cell rejection, and
      an end-to-end trace where a same-colored legend swatch is correctly
      excluded). The easy-example test's manual legend pixel-blank hack was
      removed since detection now handles it live. 131 tests passing,
      lint/format/mypy clean.
- [x] #2 enhancement ("trace by marker"): confirmed already implemented in
      `marker_detect.py` / wired into `curve_trace.trace_curve_by_color`
      (`detect_markers=True` by default, commit 99a4c9d, merged ~30min before
      the issue was filed) -- glyph center is reported as the point, matching
      the issue's ask exactly. No new code; close with an explanation.
- [x] #3 enhancement: added `overlays.set_data_point_marker_highlighted`
      (mirrors the existing `set_reference_line_highlighted`) and wired the
      "Digitized Points" `QTableView`'s row selection to it in
      `main_window.py` (`_on_point_table_selection_changed`), same
      select-a-row -> highlight-the-canvas-marker behavior the calibration
      dialog already had. 134 tests passing (new: overlay unit tests +
      integration test asserting only the selected row's marker changes color
      and clearing selection restores all of them); lint/format/mypy clean.
- [x] #4 enhancement: switched all three x-grids in
      `examples/generate_test_plots.py` to exact steps (easy 1.0, medium 2.0,
      hard 0.5, all via `np.linspace` endpoints chosen so the step divides
      evenly) instead of arbitrary point counts over a fixed range; regenerated
      all three PNGs and their answer-key CSVs. 134 tests still passing against
      the regenerated fixtures; lint/format/mypy clean.

## M15 — GitHub issue backlog (#6-#8)
- [x] #8 bug: `AxisCalibrationDialog` was opened via blocking `dialog.exec()`
      (application-modal), which blocks all input to the canvas underneath --
      so a real user could never click a calibration point on the image at
      all, and mouse-wheel zoom on the canvas was blocked the same way. Fixed
      by switching to non-modal `show()` + a `finished` signal handler in
      `main_window.py` (`_on_calibration_dialog_finished`), with a guard
      against opening a second dialog while one is already open. Wheel-zoom
      was never mode-gated in `canvas.py`, so it now works during calibration
      "for free" once the canvas can receive events at all -- satisfies the
      "zoom in/out to pick precisely" part of the ask too, no separate change
      needed. This is almost certainly also the root cause of #6's "can't get
      correct data values" complaint (unrelated to tracing accuracy, which
      checks out fine independently -- see #6 below). 137 tests passing
      (3 new regression tests), lint/format/mypy clean.
- [x] #7 enhancement: curve renaming (`CurvePanel`'s new "Rename Curve..."
      button / double-click a curve in the list, both routed through
      `QInputDialog.getText`) and multi-curve export: `io_export/csv_export.py`
      gained `export_curves_csv` (one CSV, `{name}_x`/`{name}_y` column pair
      per curve, ragged curves padded with blank cells rather than truncated),
      and a new `io_export/excel_export.py` (`export_curves_excel`, one sheet
      per curve, with sheet-name sanitization/truncation/dedup for Excel's
      naming rules) via a new `openpyxl` runtime dependency (+ `types-openpyxl`
      dev dependency for mypy). Two new File-menu actions wire these in.
      148 tests passing, lint/format/mypy clean.
- [x] #6 enhancement/docs:
      - `.github/workflows/ci.yml`: a `test` job (system Qt libs, `uv sync
        --locked`, ruff check/format, mypy, pytest under offscreen Qt) and a
        `docs` job (`mkdocs build`), both on push/PR to `main`.
      - Extended accuracy-tolerance tests to the medium and hard examples
        (previously only easy had one): medium's 3 curves within 1% of its
        100-unit y-range; hard's 2 "normal" curves within a log-scale-relative
        tolerance, gap-tolerant for heavy curve overlap. Curves 2 and 4 in the
        hard example are documented (examples/README.md) as known-hard
        auto-trace cases rather than given a tolerance they can't meet.
      - **Found and fixed a real accuracy bug in the process**: `curve_trace.
        _clean_mask`'s despeckling was an unconditional 3x3 morphological
        "open", which erases *any* stroke thinner than a full 3x3
        neighborhood -- including a perfectly ordinary 1px hairline, not just
        noise (confirmed on a clean, noise-free synthetic 1px line: 281/281
        pixels traced to zero). Now falls back to a connected-component area
        filter (only when plain opening would erase the mask entirely, so
        every previously-working case is unaffected) that keys on a
        component's pixel count rather than its 2D thickness.
      - MkDocs website (`mkdocs.yml` + `docs/`, Material theme): `docs/index.md`
        and `docs/examples.md` pull in the existing root `README.md` and
        `examples/README.md` via `pymdownx.snippets` rather than duplicating
        content -- single source of truth, at the cost of a few internal
        relative links not resolving inside the built site (harmless
        warnings, not build failures; a known, accepted limitation). PDF
        export deliberately deferred (see discussion) -- heavy native
        toolchains (weasyprint/pandoc+LaTeX) for uncertain payoff.
      - New `docs` dependency group (`mkdocs`, `mkdocs-material`).
      - 152 tests passing, lint/format/mypy clean.

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

## M16 — GitHub issue backlog (#9-#10)
- [x] #9 enhancement ("marker only digitize"): marker-only auto-trace already
      worked for a well-separated scatter chart, but a marker sitting at (or
      near) the plot's edge is often partly cut off by the image border --
      `detect_marker_blobs` deliberately doesn't report a clipped glyph as a
      full blob (only part of it was drawn), so it used to fall through to
      the column-wise line tracer and produce one spurious point per column
      instead of the single real data point it represents. Fixed in
      `curve_trace.py` with `_extract_clipped_marker_fragments`: any leftover
      component shaped like a partial marker (plausible size relative to the
      already-detected full blobs, not too elongated) is pulled out as one
      point at its centroid before the line tracer ever sees it -- gated on
      at least one full blob having been found, so a genuine line-only chart
      (no blobs at all) behaves exactly as before.
- [x] #10 enhancement ("make test cases"): added `test_plot_scatter.png` (2
      series, markers only, no connecting line, generated by
      `generate_test_plots.py`) with its own answer-key CSVs, alongside a
      synthetic regression test for the edge-clipped-marker fix above.
      Verified exact point-count + sub-0.01-unit accuracy against the new
      example. 154 tests passing, lint/format/mypy clean.
