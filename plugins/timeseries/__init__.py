"""
Time series visualization panel for FiftyOne.

| Copyright 2017-2026, Voxel51, Inc.
| `voxel51.com <https://voxel51.com/>`_
|
"""

import logging

import fiftyone.operators.types as types
from fiftyone.operators.categories import Categories
from fiftyone.operators.panel import Panel, PanelConfig

import fiftyone.core.timeseries as fots

logger = logging.getLogger(__name__)

# Max points per trace sent to the frontend
_MAX_PLOT_POINTS = 500


def _downsample(trace: dict) -> dict:
    """Downsample a single Plotly trace if needed."""
    x = trace.get("x", [])
    y = trace.get("y", [])
    if len(x) > _MAX_PLOT_POINTS:
        step = max(1, len(x) // _MAX_PLOT_POINTS)
        x = x[::step]
        y = y[::step]
    return {**trace, "x": x, "y": y}


class TimeSeriesPanel(Panel):
    @property
    def config(self):
        return PanelConfig(
            name="timeseries_panel",
            label="Time Series",
            icon="timeline",
            category=Categories.ANALYZE,
            surfaces="grid modal",
        )

    def render(self, ctx):
        panel = types.Object()

        data = []
        layout = {}

        sample_id = ctx.current_sample
        if sample_id:
            try:
                from bson import ObjectId

                sid = ObjectId(sample_id)
                ts_names = fots.TimeSeries.get_timeseries_names_for_sample(sid)

                if ts_names:
                    ts = fots.TimeSeries.load(ts_names[0])
                    plotly = ts.to_plotly()
                    data = [_downsample(t) for t in plotly["data"]]
                    layout = plotly["layout"]
                    layout["title"] = ts_names[0]
            except Exception as e:
                logger.error("[TS] render error: %s", e, exc_info=True)
                layout = {"title": f"Error: {e}"}

        panel.plot("plot", data=data, layout=layout)

        return types.Property(panel)


def register(p):
    p.register(TimeSeriesPanel)
