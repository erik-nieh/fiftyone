"""Load temperature CSV into TimeSeries and link to the demo video sample."""

import os

import fiftyone as fo
from fiftyone.core.timeseries import TimeSeries

CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "timeseries_demo",
    "temperatures.csv",
)

VIDEO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "timeseries_demo",
    "Artillery Sidewinder X2 - Bed Temperature Uniformity - FLIR Cam.mp4",
)

TS_NAME = "bed_temperatures"


def main() -> None:
    # Clean up previous runs
    for name in TimeSeries.list():
        TimeSeries.delete(name)
        print(f"Deleted old time series: {name}")

    # Load from CSV
    ts = TimeSeries.from_csv(TS_NAME, CSV_PATH)
    print(f"Loaded: {ts}")
    print(f"  Channels: {ts.channel_names}")
    for ch_name in ts.channel_names:
        ch = ts[ch_name]
        print(
            f"  {ch_name}: {len(ch)} points, range [{ch.values.min():.1f}, {ch.values.max():.1f}]°C"
        )

    # Verify round-trip through MongoDB
    loaded = TimeSeries.load(TS_NAME)
    print(f"\nRound-trip from MongoDB: {loaded}")
    for ch_name in loaded.channel_names:
        orig = ts[ch_name]
        rt = loaded[ch_name]
        assert len(orig) == len(rt), f"{ch_name} length mismatch"
        max_diff = abs(orig.values - rt.values).max()
        print(f"  {ch_name}: max diff = {max_diff:.6f}")

    # Create or load the demo dataset
    if fo.dataset_exists("timeseries_demo"):
        dataset = fo.load_dataset("timeseries_demo")
        print(f"\nLoaded dataset: {dataset}")
    else:
        dataset = fo.Dataset("timeseries_demo", persistent=True)
        sample = fo.Sample(filepath=VIDEO_PATH)
        dataset.add_sample(sample)
        sample.compute_metadata()
        print(f"\nCreated dataset: {dataset}")

    # Link time series to the sample
    sample = dataset.first()
    sample.unlink_all_timeseries()
    sample.link_timeseries(TS_NAME)
    print(f"Linked '{TS_NAME}' to sample")
    print(f"  Sample timeseries: {sample.get_timeseries_names()}")

    # Verify load through sample
    via_sample = sample.get_timeseries(TS_NAME)
    print(f"  Loaded via sample: {via_sample}")

    print("\nDone!")


if __name__ == "__main__":
    main()
