"""Load the time series demo dataset and launch the FiftyOne app."""

import subprocess
import time

import fiftyone as fo
import fiftyone.core.timeseries as fo

DATA_DIR = "/home/erik-work/code/fiftyone/data/timeseries_demo"
VIDEO_PATH = f"{DATA_DIR}/Artillery Sidewinder X2 - Bed Temperature Uniformity - FLIR Cam.mp4"
TRIM_VIDEO_PATH = f"{DATA_DIR}/bed_temp_first_180s.mp4"
CSV_PATH = f"{DATA_DIR}/temperatures.csv"
DATASET_NAME = "timeseries-demo"
TS_FULL = "bed_temperatures"
TS_180 = "bed_temperatures_180s"

# Clean up any previous run
for name in fo.list_datasets():
    if "timeseries" in name.lower():
        fo.delete_dataset(name)
for ts_name in [TS_FULL, TS_180]:
    if fo.TimeSeries.exists(ts_name):
        fo.TimeSeries.delete(ts_name)

# Create dataset
dataset = fo.Dataset(DATASET_NAME, persistent=True)

# --- Full video sample ---
sample_full = fo.Sample(filepath=VIDEO_PATH)
sample_full.compute_metadata()
dataset.add_sample(sample_full)

ts_full = fo.TimeSeries.from_csv(
    name=TS_FULL,
    filepath=CSV_PATH,
    timestamp_col="timestamp",
)
fo.TimeSeries.link_sample(sample_full._id, TS_FULL)

print(f"Full sample: {sample_full.id} ({sample_full.metadata.duration:.0f}s)")
print(f"  Time series: {ts_full}")

# --- Trimmed 180s sample ---
print("Trimming video to 180s...")
subprocess.run(
    [
        "ffmpeg",
        "-y",
        "-i",
        VIDEO_PATH,
        "-t",
        "180",
        "-c",
        "copy",
        TRIM_VIDEO_PATH,
    ],
    capture_output=True,
    check=True,
)

sample_180 = fo.Sample(filepath=TRIM_VIDEO_PATH)
sample_180.compute_metadata()
dataset.add_sample(sample_180)

ts_180 = ts_full.query(start=0, end=180)
ts_180._name = TS_180
ts_180.save()
fo.TimeSeries.link_sample(sample_180._id, TS_180)

print(f"180s sample: {sample_180.id} ({sample_180.metadata.duration:.0f}s)")
print(f"  Time series: {ts_180}")

# --- Launch ---
print(f"\nDataset: {len(dataset)} samples")
session = fo.launch_app(dataset)
print(f"App running at {session.url}")
try:
    while True:
        time.sleep(60)
except KeyboardInterrupt:
    pass
