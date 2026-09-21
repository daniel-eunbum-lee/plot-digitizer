# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`plot-digitizer` is a desktop GUI app (PySide6/Qt6) for extracting data points from an image of
a chart or plot (scan, photo, or screenshot with no underlying data). Workflow: load image →
optionally correct perspective distortion → calibrate axes (linear or log, independently per
axis) → pick data points (manually or via automatic color-based curve tracing) → export to CSV.

See `PLAN.md` for the milestone roadmap and current status — update it as milestones complete.

## Commands

```
uv sync                      # install/update the environment from pyproject.toml + uv.lock
uv run python -m plot_digitizer   # launch the app
uv run pytest                 # run the full test suite
uv run pytest -m "not gui"    # run only the headless (non-Qt-display) subset
uv run pytest tests/calibration/test_transform.py   # run a single test file
uv run ruff check .            # lint
uv run ruff format .            # format
uv run mypy src                  # type check
```

QT_QPA_PLATFORM=offscreen is required for any GUI test/run in a headless environment (CI,
containers without a display) — pytest-qt tests marked `gui` should set this automatically via
fixture, but a manual `uv run python -m plot_digitizer` in a headless shell needs it exported.

## Architecture

Source lives under `src/plot_digitizer/` (src-layout). Dependency direction is one-way and
matters more than usual here because it's what keeps the CV/math logic unit-testable without a
display:

- `calibration/` and `model/` — pure Python, **no PySide6 or OpenCV imports**. Coordinate-transform
  math and the `Project`/`Curve`/`Point` data model. Fully testable with plain pytest, no display.
- `imaging/` — depends on NumPy/OpenCV, but not Qt. Perspective correction, axis/gridline
  detection, color-based curve tracing. Testable headlessly against synthetic image arrays.
- `io_export/` — CSV and project-file (JSON) serialization. Depends only on `model/`.
- `gui/` — the only layer importing PySide6. Thin wiring: widgets call into `calibration/`,
  `model/`, `imaging/`, `io_export/` rather than reimplementing logic inline.

**Fixed pipeline order**: perspective correction always runs before axis calibration, which
always runs before point picking/tracing. Calibration and picking operate on the corrected
working image, so no point ever needs remapping through two transforms — don't build features
that assume the order can vary.

**Point storage invariant**: a picked/traced point's pixel coordinates (`Point`) are the
persisted source of truth; its real-world data coordinates (`DataPoint`) are always *derived* on
demand via the current `CoordinateTransform`, never persisted as the primary value. This means
re-calibrating an axis after points are placed rescales their data values instead of corrupting
them — don't invert this by persisting data coordinates as ground truth.

## Conventions specific to this repo

- Type hints on every non-trivial function (already required globally, called out here because
  this codebase leans numeric/array-heavy where it's easy to skip).
- Why-comments are expected — not restating-the-code comments — around: the log-scale coordinate
  fit in `calibration/`, the homography math in `imaging/perspective.py`, and the curve-tracing
  heuristics in `imaging/curve_trace.py`. These are the spots where the *reason* for a
  non-obvious step (e.g. why log-transform before fitting, why cluster in HSV not RGB) isn't
  visible from the code alone.
- Model types (`Point`, `DataPoint`, `Curve`, `Project`, `AxisCalibration`) are plain dataclasses,
  framework-agnostic — no Qt types inside them.
- Automatic detection features (axis/gridline detection, curve tracing) always **propose,
  never auto-apply**: results land as editable overlays/candidates the user confirms, never as a
  silent mutation of calibration or committed points.
- Use `opencv-python-headless`, not `opencv-python` — avoids bundling a second GUI toolkit
  alongside PySide6.
