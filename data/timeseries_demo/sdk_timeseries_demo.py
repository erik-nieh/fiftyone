# pylint: disable=import-error,no-name-in-module
"""SDK demo: load a persisted time series, analyze with NumPy, open Plotly.

Run ``load_demo.py`` first (or otherwise ensure ``bed_temperatures`` exists).

Usage:
    python sdk_timeseries_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_demo = Path(__file__).resolve().parent
if str(_demo) not in sys.path:
    sys.path.insert(0, str(_demo))
from setup_fiftyone_dev_env import setup

setup(verbose=False)

import fiftyone.core.timeseries as fots

TS_NAME = "bed_temperatures"


def main() -> None:
    if not fots.TimeSeries.exists(TS_NAME):
        raise SystemExit(
            f"Time series {TS_NAME!r} not found. Run load_demo.py first "
            "(or create the series another way)."
        )

    ts = fots.TimeSeries.load(TS_NAME)
    timestamps, values, channel_names = ts.to_numpy()

    print(
        f"Loaded {TS_NAME!r}: {len(timestamps)} points × {len(channel_names)} channels"
    )
    print(f"  Channels: {channel_names}")
    print(f"  Time span: {timestamps[0]:.1f}s → {timestamps[-1]:.1f}s\n")

    # --- NumPy interactions ------------------------------------------------
    means = values.mean(axis=0)
    stds = values.std(axis=0)
    print("Per-channel mean (°C) and std:")
    for name, m, s in zip(channel_names, means, stds):
        print(f"  {name:14s}  mean={m:.2f}  std={s:.3f}")

    # Bed uniformity proxy: spread across corners at each instant
    spread = values.max(axis=1) - values.min(axis=1)
    print(
        f"\nCorner temperature spread (max−min per timestep): "
        f"mean={spread.mean():.3f}°C  max={spread.max():.3f}°C"
    )

    # How correlated are the four corners?
    corr = np.corrcoef(values.T)
    print(
        "\nChannel correlation matrix (rows/cols = "
        + ", ".join(channel_names)
        + "):"
    )
    with np.printoptions(precision=3, suppress=True):
        print(corr)

    # Simple smoothed view of one channel (moving average, NumPy only)
    win = 11
    kernel = np.ones(win) / win
    tl_idx = channel_names.index("top_left")
    smoothed = np.convolve(values[:, tl_idx], kernel, mode="same")
    print(
        f"\nSmoothed top_left ({win}-sample boxcar): "
        f"first raw={values[0, tl_idx]:.2f}, first smooth={smoothed[0]:.2f}"
    )

    # --- Plot ---------------------------------------------------------------
    # First minute only keeps the demo snappy; all channels on one figure
    window = ts.query(start=0.0, end=60.0)
    print(
        f"\nOpening Plotly for 0–60s window ({len(window[channel_names[0]])} samples per channel)..."
    )
    window.plot(title=f"{TS_NAME} (0–60s) — SDK demo")


if __name__ == "__main__":
    main()
