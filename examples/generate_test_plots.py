"""Generate synthetic easy/medium/hard test-plot chart images and answer-key CSVs.

Not part of the plot_digitizer package (matplotlib is a dev-only dependency, never
imported from src/). Run with:

    uv run python examples/generate_test_plots.py

Each chart is a small set of discrete (x, y) data points connected by a styled line,
mirroring how a real chart encodes discrete data. The exact points used to draw each
curve are written out as answer-key CSVs in the same two-column x,y format the app's
own "Export Points to CSV..." produces, so exported output can be diffed directly
against a known-correct answer.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import NamedTuple

import cv2
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

_EXAMPLES_DIR = Path(__file__).parent
_DPI = 150
_RNG_SEED = 0


class CurveSpec(NamedTuple):
    label: str
    x: np.ndarray
    y: np.ndarray
    color: str
    marker: str | None
    linestyle: str
    linewidth: float


def _write_answer_key(curve: CurveSpec, path: Path) -> None:
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["x", "y"])
        for x, y in zip(curve.x, curve.y, strict=True):
            writer.writerow([float(x), float(y)])


def _render(
    curves: list[CurveSpec],
    *,
    png_path: Path,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
    yscale: str,
    title: str,
    grid: bool,
    legend: bool,
) -> None:
    fig, ax = plt.subplots(figsize=(8, 6), dpi=_DPI)
    for curve in curves:
        ax.plot(
            curve.x,
            curve.y,
            color=curve.color,
            marker=curve.marker,
            linestyle=curve.linestyle,
            linewidth=curve.linewidth,
            markersize=7,
            label=curve.label,
        )
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_yscale(yscale)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_title(title)
    if grid:
        ax.grid(True, which="both", linestyle=":", alpha=0.5)
    if legend:
        ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(png_path)
    plt.close(fig)


def _add_scan_noise(png_path: Path, *, sigma: float) -> None:
    """Add light Gaussian noise to mimic a scanned (not screenshotted) chart.

    Applied post-render with cv2 rather than matplotlib, since matplotlib has no
    built-in noise/scan-artifact primitive.
    """
    image = cv2.imread(str(png_path))
    assert image is not None, f"failed to read back {png_path}"
    rng = np.random.default_rng(_RNG_SEED)
    noise = rng.normal(0, sigma, image.shape)
    noisy = np.clip(image.astype(np.float64) + noise, 0, 255).astype(np.uint8)
    cv2.imwrite(str(png_path), noisy)


def _build_easy() -> list[CurveSpec]:
    x = np.linspace(0, 10, 10)
    return [
        CurveSpec("Curve A", x, 2 * x + 5, "tab:blue", "o", "-", 2.5),
        CurveSpec("Curve B", x, 40 - x, "tab:red", "s", "-", 2.5),
    ]


def _build_medium() -> list[CurveSpec]:
    x = np.linspace(0, 20, 13)
    return [
        CurveSpec("Curve A", x, 5 + 3 * x, "tab:blue", "o", "-", 1.5),
        CurveSpec("Curve B", x, 80 - 2.5 * x, "tab:green", "^", "-", 1.5),
        CurveSpec("Curve C", x, 10 + 0.25 * (x - 10) ** 2, "tab:orange", "D", "-", 1.5),
    ]


def _build_hard() -> list[CurveSpec]:
    x = np.linspace(0.5, 10, 15)
    return [
        CurveSpec("Curve A", x, 5 * np.exp(0.35 * x), "#1a3fa8", "o", "-", 1.0),
        CurveSpec("Curve B", x, 4 * np.exp(0.33 * x), "#2a4fb8", None, "--", 1.0),
        CurveSpec("Curve C", x, 400 / x, "tab:red", "s", "-", 1.0),
        CurveSpec("Curve D", x, 2 + 8 * x, "tab:gray", None, "-.", 1.0),
    ]


def _generate(name: str, curves: list[CurveSpec], **render_kwargs: object) -> None:
    png_path = _EXAMPLES_DIR / f"test_plot_{name}.png"
    _render(curves, png_path=png_path, **render_kwargs)  # type: ignore[arg-type]
    for i, curve in enumerate(curves, start=1):
        _write_answer_key(curve, _EXAMPLES_DIR / f"test_plot_{name}_curve{i}.csv")
    print(f"wrote {png_path.name} + {len(curves)} answer-key CSV(s)")


def main() -> None:
    _generate(
        "easy",
        _build_easy(),
        xlim=(0, 10),
        ylim=(0, 50),
        yscale="linear",
        title="Test Plot - Easy",
        grid=False,
        legend=True,
    )
    _generate(
        "medium",
        _build_medium(),
        xlim=(0, 20),
        ylim=(0, 100),
        yscale="linear",
        title="Test Plot - Medium",
        grid=True,
        legend=True,
    )
    hard_png = _EXAMPLES_DIR / "test_plot_hard.png"
    _generate(
        "hard",
        _build_hard(),
        xlim=(0, 10),
        ylim=(1, 1000),
        yscale="log",
        title="Test Plot - Hard",
        grid=True,
        legend=True,
    )
    _add_scan_noise(hard_png, sigma=4.0)


if __name__ == "__main__":
    main()
