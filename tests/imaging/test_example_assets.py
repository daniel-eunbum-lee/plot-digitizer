"""Regression guard: the bundled example chart stays loadable (not a digitizing-accuracy test)."""

from pathlib import Path

from plot_digitizer.imaging.io import load_image

_EXAMPLE_PATH = (
    Path(__file__).resolve().parents[2] / "examples" / "nasa_hdbk_7005_shock_attenuation_srs.png"
)


def test_example_chart_loads_with_expected_shape() -> None:
    image = load_image(_EXAMPLE_PATH)

    assert image.shape == (389, 514, 3)
    assert image.dtype.name == "uint8"
