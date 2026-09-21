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
