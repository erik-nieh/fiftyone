"""Create real time series from OCR-extracted temperature data."""
import json
import numpy as np
import fiftyone as fo
from fiftyone.core.timeseries import TimeSeries

with open(
    "/home/erik-work/code/fiftyone/data/timeseries_demo/extracted_temps.json"
) as f:
    raw = json.load(f)

timestamps = np.array(raw["timestamps"], dtype=np.float64)
channels = raw["channels"]

# Delete old mock data
for name in ["demo_imu", "demo_gps", "demo_temperature"]:
    if TimeSeries.exists(name):
        TimeSeries.delete(name)
        print(f"Deleted {name}")

# Create 4-corner temperature time series
values = np.column_stack(
    [
        np.array(channels["top_left"]),
        np.array(channels["top_right"]),
        np.array(channels["bottom_left"]),
        np.array(channels["bottom_right"]),
    ]
)
ts = TimeSeries(
    "bed_temperatures",
    timestamps=timestamps,
    values=values,
    channel_names=["top_left", "top_right", "bottom_left", "bottom_right"],
)
print(f"Created: {ts}")

# Create computed average
avg_ts = TimeSeries(
    "bed_avg_temperature",
    timestamps=timestamps,
    values=values.mean(axis=1),
    channel_names=["avg_celsius"],
)
print(f"Created: {avg_ts}")

# Update sample links
dataset = fo.load_dataset("timeseries_demo")
sample = dataset.first()
sample.unlink_all_timeseries()
sample.link_timeseries("bed_temperatures")
sample.link_timeseries("bed_avg_temperature")
print(f"Linked: {sample.get_timeseries_names()}")
print("Done!")
