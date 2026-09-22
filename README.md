# plot-digitizer

A desktop GUI app for extracting numeric data points out of an image of a chart or plot — a scan,
photo, or screenshot that has no underlying data attached to it. Calibrate the axes, click (or
auto-trace) the points you care about, and export them as CSV.

## Features

- **Perspective correction** — straighten a photographed/skewed chart via a 4-point homography
  before doing anything else.
- **Axis calibration** — click two or more known reference points per axis; each axis is
  independently **linear or logarithmic**.
- **Automatic axis/gridline detection** — proposes candidate axis and gridline positions (Hough
  line detection) as editable, removable rows you review and confirm; nothing is ever silently
  auto-applied.
- **Manual point picking** — click directly on a curve; pixel coordinates are converted to
  real-world data coordinates live.
- **Automatic color-based curve tracing** — sample a curve's color and auto-trace it into a dense,
  fully editable set of points.
- **Multiple curves/series** per project, with add/switch/delete/rename.
- **Undo/redo** for point edits.
- **Reset Project** — discard calibration, perspective correction, and all points, and start
  over on the current image without re-browsing for the file.
- **CSV export** (single active curve, or all curves at once in one file), **Excel export** (all
  curves, one workbook sheet each), and **project save/load** (JSON) so a session can be resumed
  later.

## Requirements

- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/) for dependency management
- A display (or `QT_QPA_PLATFORM=offscreen` for headless environments — see below)

## Installation

```bash
git clone https://github.com/daniel-eunbum-lee/plot-digitizer.git
cd plot-digitizer
uv sync
```

This creates a `.venv` and installs everything from `pyproject.toml`/`uv.lock`, including
PySide6, NumPy, and OpenCV.

## Running the app

```bash
uv run plot-digitizer
# or, equivalently:
uv run python -m plot_digitizer
```

On a headless machine (a container or CI with no display), export `QT_QPA_PLATFORM=offscreen`
first — the window will run without a visible display server.

### Optional: Tesseract OCR for axis-value suggestions

"Auto-Detect Lines" in the calibration dialog can also try to *read* each detected tick's label
off the image and pre-fill the Value cell with it. That uses the [Tesseract OCR
engine](https://github.com/tesseract-ocr/tesseract), a **system binary that `uv sync` does not
install** — the `pytesseract` Python package it ships with is only a thin wrapper around it.

On Windows, install it via the [UB-Mannheim
installer](https://github.com/UB-Mannheim/tesseract/wiki) or `choco install tesseract`, then
either make sure `tesseract.exe` is on your `PATH` or point `pytesseract` at it explicitly:

```python
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

On Linux/macOS: `apt install tesseract-ocr` or `brew install tesseract`.

This is entirely optional and fully local — no network calls. **If Tesseract is absent the app
works exactly as before**: the Value cells just start at `0.0` and you type the real values in
yourself. Even when it is installed, OCR'd values are only a pre-filled *suggestion* in an
editable cell — nothing is auto-applied to the calibration, so always check them.

## Example run

A typical digitizing session:

1. **Open an image** — `File → Open Image...` and pick a PNG/JPG/BMP/TIFF of a chart.
2. **(Optional) Correct perspective** — if the image is a skewed photo rather than a flat
   screenshot, use `Perspective → Correct Perspective...` and click the chart's 4 corners in
   order (top-left, top-right, bottom-right, bottom-left). Confirm the prompt to apply it — this
   replaces the working image with a straightened version.
3. **Calibrate the axes** — `Calibration → Axes...` opens a dialog with one panel per axis:
   - Choose **Linear** or **Log** scale for each axis independently.
   - Click "Add X/Y Reference Point", then click the corresponding tick mark on the image; type
     in its real value. Repeat for at least 2 points per axis (more improves accuracy via a
     least-squares fit).
   - Or click "Auto-Detect Lines" to propose candidate tick/gridline pixel positions — review,
     delete any wrong ones, and fill in the real values yourself.
   - Click OK once both axes have ≥2 valid reference points.
4. **Digitize the curve**, either or both:
   - **Manually**: enable `Points → Pick Points Mode`, then click along the curve. Each click adds
     a row to the "Digitized Points" table (pixel and data coordinates shown side by side).
   - **Automatically**: `Points → Auto-Trace Curve by Color...`, click on the curve to sample its
     color, adjust the match tolerance if needed, and accept — a new curve is traced and added,
     fully editable afterward like any manual one.
5. **Manage curves** — the "Curves" panel lists all curves in the project; add, switch, delete, or
   rename them (double-click a curve's name, or the "Rename Curve..." button) as needed.
   `Edit → Undo/Redo` reverts/reapplies point picks.
6. **Export** — `File → Export Points to CSV...` writes the active curve's data coordinates to a
   CSV file (`x,y` header). To export every curve at once, use `File → Export All Curves to
   CSV...` (one file, an `{name}_x`/`{name}_y` column pair per curve) or `File → Export All Curves
   to Excel...` (one workbook, one sheet per curve). `File → Save Project As...` saves the whole
   session (image path, calibration, all curves, perspective correction) as JSON, reopenable via
   `File → Open Project...`.

Made a mess of calibration or points and want to start over on the same image? `File → Reset
Project...` discards calibration, perspective correction, and all points, and reloads the
original image — no need to re-browse for the file.

A ready-made chart to practice this on is included at
[`examples/nasa_hdbk_7005_shock_attenuation_srs.png`](examples/nasa_hdbk_7005_shock_attenuation_srs.png)
— a real scanned figure with linear axes and two similarly-colored curves. See
[`examples/README.md`](examples/README.md) for its axis ranges and a note on why it's a good
edge case for auto-tracing.

For checking your own digitizing *accuracy* against a known-correct answer (the NASA chart above
has no recorded ground truth), `examples/` also has three synthetic test plots — easy, medium,
and hard — each with an answer-key CSV per curve giving the exact data points used to draw it.
See [`examples/README.md`](examples/README.md) for details.

## Development

```bash
uv run pytest                    # full test suite
uv run pytest -m "not gui"       # headless-only subset (no Qt display needed)
uv run ruff check .              # lint
uv run ruff format .             # format
uv run mypy src                  # type check
uv run --group docs mkdocs serve # docs site, live-reloading, at http://127.0.0.1:8000
```

CI (`.github/workflows/ci.yml`) runs lint, format-check, mypy, and the full test suite on every
push/PR to `main`, plus a separate job that builds the docs site.

See `CLAUDE.md` for the architecture overview and repo conventions, and `PLAN.md` for the
milestone-by-milestone implementation history and known limitations.

## Non-goals (v1)

- Lens (barrel/pincushion) undistortion — only 4-point perspective correction is supported.
- Tracing looping or parametric curves (more than one y per x) — automatic tracing only handles
  function-like curves.

## License

MIT — see [LICENSE](LICENSE).
