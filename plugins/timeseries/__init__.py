"""
Time series visualization plugin for FiftyOne.

Provides a GetTimeSeriesData operator that the JS panel component calls
to fetch plotly traces for the current sample.

| Copyright 2017-2026, Voxel51, Inc.
| `voxel51.com <https://voxel51.com/>`_
|
"""

import logging
from typing import Any

import fiftyone as fo
import fiftyone.operators as foo
import fiftyone.operators.types as types

import fiftyone.core.timeseries as fots

logger = logging.getLogger(__name__)

_MAX_PLOT_POINTS = 2000


def _downsample(
    timestamps: list[Any],
    values: list[Any],
    max_points: int = _MAX_PLOT_POINTS,
) -> tuple[list[Any], list[Any]]:
    """Downsample parallel lists if they exceed max_points."""
    if len(timestamps) <= max_points:
        return timestamps, values
    step = max(1, len(timestamps) // max_points)
    return timestamps[::step], values[::step]


class GetTimeSeriesData(foo.Operator):
    @property
    def config(self):
        return foo.OperatorConfig(
            name="get_timeseries_data",
            label="Get Time Series Data",
            unlisted=True,
        )

    def resolve_input(self, ctx):
        inputs = types.Object()
        inputs.str("sample_id", required=True)
        return types.Property(inputs)

    def execute(self, ctx):
        sample_id = ctx.params.get("sample_id")
        if not sample_id:
            return {"traces": [], "ts_name": "", "fps": 0}

        try:
            from bson import ObjectId

            sid = ObjectId(sample_id)
            ts_names = fots.TimeSeries.get_timeseries_names_for_sample(sid)

            if not ts_names:
                return {"traces": [], "ts_name": "No time series", "fps": 0}

            ts = fots.TimeSeries.load(ts_names[0])
            plotly_fig = ts.to_plotly()

            traces: list[dict[str, Any]] = []
            for t in plotly_fig["data"]:
                x, y = _downsample(t.get("x", []), t.get("y", []))
                traces.append({"x": x, "y": y, "name": t.get("name", "")})

            # Get FPS from sample metadata
            fps: float = 0
            try:
                dataset = ctx.dataset
                if dataset:
                    sample = dataset[sid]
                    if (
                        sample.metadata
                        and hasattr(sample.metadata, "frame_rate")
                        and sample.metadata.frame_rate
                    ):
                        fps = sample.metadata.frame_rate
            except Exception:
                pass

            # Detect if traces need separate y-axes (ranges differ by >10x)
            separate_axes = False
            if len(traces) > 1:
                ranges = []
                for t in traces:
                    ys = [v for v in t["y"] if v is not None]
                    if ys:
                        ranges.append(max(ys) - min(ys))
                if ranges and min(ranges) > 0:
                    separate_axes = max(ranges) / min(ranges) > 10

            # Push data into panel state so JS can read it
            if ctx.panel:
                ctx.panel.state.traces = traces
                ctx.panel.state.ts_name = ts_names[0]
                ctx.panel.state.fps = fps
                ctx.panel.state.separate_axes = separate_axes

            return {
                "traces": traces,
                "ts_name": ts_names[0],
                "fps": fps,
                "separate_axes": separate_axes,
            }

        except Exception as e:
            logger.error("[TS] error: %s", e, exc_info=True)
            return {"traces": [], "ts_name": f"Error: {e}", "fps": 0}


def register(p):
    p.register(GetTimeSeriesData)
