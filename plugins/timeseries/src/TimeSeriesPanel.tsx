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
  const separateAxes: boolean = state.separate_axes || false;

  const currentTime = frameNumber > 0 ? (frameNumber - 1) / fps : null;

  const plotData = useMemo(() => {
    if (!separateAxes) {
      return traces.map((t: any) => ({
        x: t.x,
        y: t.y,
        type: "scatter" as const,
        mode: "lines" as const,
        name: t.name,
      }));
    }
    // Subplots: each trace gets its own xaxis/yaxis pair
    return traces.map((t: any, i: number) => ({
      x: t.x,
      y: t.y,
      type: "scatter" as const,
      mode: "lines" as const,
      name: t.name,
      xaxis: i === 0 ? "x" : `x${i + 1}`,
      yaxis: i === 0 ? "y" : `y${i + 1}`,
    }));
  }, [traces, separateAxes]);

  const layout = useMemo(() => {
    const axisBase = {
      showgrid: true,
      color: theme?.text?.secondary,
      gridcolor: theme?.primary?.softBorder,
    };

    const playheadLine = {
      color: "#ccff00",
      width: 2,
      dash: "dot",
    };

    // --- Shared axis mode (FLIR-style) ---
    if (!separateAxes) {
      const shapes: any[] = [];
      if (currentTime !== null && traces.length > 0) {
        shapes.push({
          type: "line",
          x0: currentTime,
          x1: currentTime,
          y0: 0,
          y1: 1,
          yref: "paper",
          line: playheadLine,
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
        xaxis: { ...axisBase, title: "Time (s)" },
        yaxis: { ...axisBase, title: "" },
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
    }

    // --- Subplot mode (Artemis-style) ---
    const n = traces.length;
    const gap = 0.08;
    const totalGap = gap * (n - 1);
    const plotHeight = (1 - totalGap) / n;

    const shapes: any[] = [];
    const annotations: any[] = [];
    const layoutObj: any = {
      title: tsName,
      font: {
        family: "var(--fo-fontFamily-body)",
        size: 14,
        color: theme?.text?.secondary,
      },
      showlegend: false,
      autosize: true,
      margin: { l: 60, r: 20, t: 40, b: 50 },
      paper_bgcolor: theme?.background?.mediaSpace,
      plot_bgcolor: theme?.background?.mediaSpace,
    };

    for (let i = 0; i < n; i++) {
      const bottom = 1 - (i + 1) * plotHeight - i * gap;
      const top = 1 - i * plotHeight - i * gap;
      const xKey = i === 0 ? "xaxis" : `xaxis${i + 1}`;
      const yKey = i === 0 ? "yaxis" : `yaxis${i + 1}`;

      layoutObj[xKey] = {
        ...axisBase,
        anchor: i === 0 ? "y" : `y${i + 1}`,
        title: i === n - 1 ? "Time (s)" : "",
        showticklabels: i === n - 1,
      };

      layoutObj[yKey] = {
        ...axisBase,
        domain: [bottom, top],
        title: "",
      };

      // Title annotation above each subplot
      annotations.push({
        text: traces[i]?.name || "",
        xref: "paper",
        yref: "paper",
        x: 0,
        y: top,
        xanchor: "left",
        yanchor: "bottom",
        showarrow: false,
        font: {
          size: 12,
          color: theme?.text?.secondary,
        },
      });

      // Playhead line per subplot
      if (currentTime !== null) {
        shapes.push({
          type: "line",
          x0: currentTime,
          x1: currentTime,
          y0: bottom,
          y1: top,
          yref: "paper",
          xref: i === 0 ? "x" : `x${i + 1}`,
          line: playheadLine,
        });
      }
    }

    layoutObj.shapes = shapes;
    layoutObj.annotations = annotations;
    return layoutObj;
  }, [currentTime, traces, tsName, theme, separateAxes]);

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
