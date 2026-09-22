# Example chart

## `nasa_hdbk_7005_shock_attenuation_srs.png`

Figure 5.7 from NASA-HDBK-7005, "Shock Response Spectrum Versus Distance from Pyroshock Source" —
a scanned chart, not a clean screenshot, so it's a good stand-in for the kind of real-world image
this app is meant to handle.

- **X axis** (linear): "Shock Path Distance from Shock Source, m", 0–2.5
- **Y axis** (linear): "Percentage of Source Value Remaining", 0–100
- **Two curves**: "Spectrum Ramp" and "Spectrum Peak", labeled by legend arrows rather than color
  — both strokes are dark/near-black, so they may not be reliably separable by
  `Points → Auto-Trace Curve by Color...`. Manual point-picking
  (`Points → Pick Points Mode`) is the more reliable way to digitize one of them if
  auto-tracing can't tell the two apart.

## Try it

```bash
uv run plot-digitizer
```

Then `File → Open Image...` and pick this file. Follow the "Example run" walkthrough in the
project [README](../README.md) using this chart's known axis ranges above as your calibration
reference values.

## Synthetic test plots (with answer keys)

The NASA chart above is good for practicing the workflow, but it has no recorded ground truth —
there's no way to check whether your digitized output is actually *correct*. These three
synthetic charts do: each curve was drawn from a fixed set of `(x, y)` data points, and those
exact points are saved alongside the image as an answer-key CSV (same `x,y` header format as
`File → Export Points to CSV...`), so you can diff your exported CSV directly against it.

Regenerate all of them (e.g. after tweaking `generate_test_plots.py`) with:

```bash
uv run python examples/generate_test_plots.py
```

### `test_plot_easy.png`

- **X axis** (linear): 0–10. **Y axis** (linear): 0–50.
- **2 curves**, well clear of each other (no overlap), thick lines, distinct colors and marker
  shapes: `test_plot_easy_curve1.csv` (blue, circles), `test_plot_easy_curve2.csv` (red, squares).
- Good first try for both manual point-picking and `Points → Auto-Trace Curve by Color...`.

### `test_plot_medium.png`

- **X axis** (linear): 0–20. **Y axis** (linear): 0–100.
- **3 curves** that cross each other at least once, moderately distinct colors, thinner lines,
  gridlines and a legend present: `test_plot_medium_curve1.csv` (blue, circles),
  `test_plot_medium_curve2.csv` (green, triangles), `test_plot_medium_curve3.csv` (orange,
  diamonds).
- Exercises picking the right curve at a crossing point, and auto-trace tolerance tuning near a
  gridline.

### `test_plot_hard.png`

- **X axis** (linear): 0–10. **Y axis** (**logarithmic**): 1–1000.
- **4 curves**, heavily overlapping, thin lines, light scan-style noise added to the image:
  - `test_plot_hard_curve1.csv` — dark blue, solid, circle markers.
  - `test_plot_hard_curve2.csv` — a very similar blue, dashed, **no markers** — deliberately close
    in color to curve 1 to stress-test `Points → Auto-Trace Curve by Color...`'s color tolerance;
    manual picking is the more reliable way to separate the two.
  - `test_plot_hard_curve3.csv` — red, solid, square markers.
  - `test_plot_hard_curve4.csv` — gray, dash-dot, no markers — thin enough, combined with this
    image's scan noise, that auto-trace's accuracy on it is unreliable; manual picking is the
    more reliable way to digitize it too.
- Also exercises **log-scale axis calibration** (`Calibration → Axes...` → Log scale for Y).

### `test_plot_scatter.png`

- **X axis** (linear): 0–10. **Y axis** (linear): 0–10.
- **2 series, markers only, no connecting line at all** — a genuine scatter plot:
  `test_plot_scatter_curve1.csv` (blue circles), `test_plot_scatter_curve2.csv` (red squares).
- Exercises marker-only auto-trace (`Points → Auto-Trace Curve by Color...` with no stroke to
  fall back on) rather than the marker-on-a-line case the other examples cover.
