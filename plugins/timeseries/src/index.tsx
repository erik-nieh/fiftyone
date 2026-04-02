import {
  Categories,
  PluginComponentType,
  registerComponent,
} from "@fiftyone/plugins";
import TimeSeriesPanel from "./TimeSeriesPanel";

registerComponent({
  name: "timeseries_panel",
  label: "Time Series",
  component: TimeSeriesPanel,
  type: PluginComponentType.Panel,
  activator: () => true,
  panelOptions: {
    surfaces: "grid modal",
    category: Categories.Analyze,
    isNew: false,
  },
});
