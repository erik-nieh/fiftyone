import React, { useEffect, useMemo } from "react";
import { useRecoilValueLoadable } from "recoil";
import { usePanelState } from "@fiftyone/spaces";
import { useTheme } from "@fiftyone/components/src/components/ThemeProvider";
import { usePanelEvent } from "@fiftyone/operators";
import { useFrameNumber } from "@fiftyone/playback";
import { nullableModalSampleId } from "@fiftyone/state";
import Plot from "react-plotly.js";

const GET_DATA_OP = "@voxel51/timeseries/get_timeseries_data";

export default function TimeSeriesPanel({ panelNode }) {
  const panelId = panelNode?.id;
  const theme = useTheme();
  const triggerEvent = usePanelEvent();

  const [panelState] = usePanelState(null, panelId);

  const sampleLoadable = useRecoilValueLoadable(nullableModalSampleId);
  const sampleId =
    sampleLoadable.state === "hasValue" ? sampleLoadable.contents : null;

  let frameNumber = -1;
  try {
    frameNumber = useFrameNumber();
  } catch {
    // Not in a timeline context
  }

  // Fetch data when sample changes
  useEffect(() => {
    if (!panelId || !sampleId) return;
    triggerEvent(panelId, {
      panelId,
      operator: GET_DATA_OP,
      params: { sample_id: sampleId },
    });
  }, [panelId, sampleId]);

  const state = panelState?.state || panelState || {};
  const traces: any[] = state.traces || [];
  const fps: number = state.fps || 7.74;
  const tsName: string = state.ts_name || "Time Series";

  const currentTime = frameNumber > 0 ? (frameNumber - 1) / fps : null;

  const plotData = useMemo(() => {
    return traces.map((t: any) => ({
      x: t.x,
      y: t.y,
      type: "scatter" as const,
      mode: "lines" as const,
      name: t.name,
    }));
  }, [traces]);

  const layout = useMemo(() => {
    const shapes: any[] = [];
    if (currentTime !== null && traces.length > 0) {
      shapes.push({
        type: "line",
        x0: currentTime,
        x1: currentTime,
        y0: 0,
        y1: 1,
        yref: "paper",
        line: {
          color: "#ccff00",
          width: 2,
          dash: "dot",
        },
      });
    }

    return {
      shapes,
      title: tsName,
      font: {
        family: "var(--fo-fontFamily-body)",
        size: 14,
        color: theme?.text?.secondary,
      },
      xaxis: {
        title: "Time (s)",
        showgrid: true,
        color: theme?.text?.secondary,
        gridcolor: theme?.primary?.softBorder,
      },
      yaxis: {
        title: "°C",
        showgrid: true,
        color: theme?.text?.secondary,
        gridcolor: theme?.primary?.softBorder,
      },
      showlegend: traces.length > 1,
      legend: {
        x: 1,
        y: 1,
        bgcolor: "rgba(0,0,0,0)",
        font: { color: theme?.text?.secondary },
      },
      autosize: true,
      margin: { l: 50, r: 20, t: 40, b: 50 },
      paper_bgcolor: theme?.background?.mediaSpace,
      plot_bgcolor: theme?.background?.mediaSpace,
    };
  }, [currentTime, traces, tsName, theme]);

  if (traces.length === 0) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          color: theme?.text?.secondary,
        }}
      >
        {sampleId
          ? "Loading time series..."
          : "Open a sample to see time series"}
      </div>
    );
  }

  return (
    <Plot
      data={plotData}
      layout={layout}
      config={{ displaylogo: false, scrollZoom: true }}
      style={{ height: "100%", width: "100%" }}
      useResizeHandler
    />
  );
}
