"""
End-to-end test script for the FiftyOne time series SDK.

This is the source of truth for working with time series methods and
plotting locally. Run it to verify the full lifecycle:

    python scripts/test_timeseries.py

Covers:
  - Constructor (numpy, single + multi-channel)
  - from_csv
  - MongoDB round-trip (save/load)
  - Filtered load (channels, time range)
  - to_numpy export
  - query (in-memory subsetting)
  - to_plotly / plot
  - Many-to-many sample linking
  - Reverse lookup (samples for a time series)
  - Unlink / delete / cleanup
  - TimeSeries.list / exists
"""

import os
import tempfile

import numpy as np

import fiftyone as fo

TimeSeries = fo.TimeSeries


def separator(label: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}\n")


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Create from numpy — single channel
    # ------------------------------------------------------------------
    separator("1. Constructor — single channel")

    t = np.linspace(0, 10, 200)
    ts_single = TimeSeries("test_single", timestamps=t, values=np.sin(t))

    print(ts_single)
    print(f"  channels: {ts_single.channel_names}")
    print(f"  len:      {len(ts_single)}")
    assert ts_single.channel_names == ["channel_0"]
    assert len(ts_single) == 1
    print("  OK")

    # ------------------------------------------------------------------
    # 2. Create from numpy — multi-channel
    # ------------------------------------------------------------------
    separator("2. Constructor — multi-channel")

    values = np.column_stack([np.sin(t), np.cos(t), t * 0.5])
    ts_multi = TimeSeries(
        "test_multi",
        timestamps=t,
        values=values,
        channel_names=["sin", "cos", "linear"],
    )

    print(ts_multi)
    assert ts_multi.channel_names == ["sin", "cos", "linear"]
    assert len(ts_multi["sin"]) == 200
    print("  OK")

    # ------------------------------------------------------------------
    # 3. Create from CSV
    # ------------------------------------------------------------------
    separator("3. from_csv")

    csv_path = tempfile.mktemp(suffix=".csv")
    with open(csv_path, "w") as f:
        f.write("timestamp,speed,rpm,temp\n")
        for i in range(50):
            f.write(f"{i*0.1},{60+i},{3000+i*10},{90+i*0.05}\n")

    ts_csv = TimeSeries.from_csv("test_csv", csv_path)
    os.unlink(csv_path)

    print(ts_csv)
    assert set(ts_csv.channel_names) == {"speed", "rpm", "temp"}
    assert len(ts_csv["speed"]) == 50
    print("  OK")

    # ------------------------------------------------------------------
    # 4. list / exists
    # ------------------------------------------------------------------
    separator("4. TimeSeries.list / exists")

    names = TimeSeries.list()
    print(f"  registered: {names}")
    assert "test_single" in names
    assert "test_multi" in names
    assert "test_csv" in names
    assert TimeSeries.exists("test_multi")
    assert not TimeSeries.exists("nonexistent")
    print("  OK")

    # ------------------------------------------------------------------
    # 5. MongoDB round-trip (load)
    # ------------------------------------------------------------------
    separator("5. MongoDB round-trip")

    loaded = TimeSeries.load("test_multi")
    print(f"  loaded: {loaded}")
    assert set(loaded.channel_names) == {"sin", "cos", "linear"}
    assert np.allclose(loaded["sin"].values, np.sin(t))
    assert np.allclose(loaded["cos"].values, np.cos(t))
    assert np.allclose(loaded["linear"].values, t * 0.5)
    print("  values match!")

    # ------------------------------------------------------------------
    # 6. Filtered load (channels + time range)
    # ------------------------------------------------------------------
    separator("6. Filtered load")

    filtered = TimeSeries.load(
        "test_multi", channels=["sin"], start=2.0, end=4.0
    )
    print(f"  filtered: {filtered}")
    print(f"  points: {len(filtered['sin'])}")
    assert "sin" in filtered
    assert "cos" not in filtered
    assert all(ts >= 2.0 for ts in filtered["sin"].timestamps)
    assert all(ts <= 4.0 for ts in filtered["sin"].timestamps)
    print("  OK")

    # ------------------------------------------------------------------
    # 7. to_numpy export
    # ------------------------------------------------------------------
    separator("7. to_numpy")

    timestamps, vals, ch_names = loaded.to_numpy(channels=["sin", "cos"])
    print(f"  timestamps shape: {timestamps.shape}")
    print(f"  values shape:     {vals.shape}")
    print(f"  channel names:    {ch_names}")
    assert timestamps.shape == (200,)
    assert vals.shape == (200, 2)
    assert ch_names == ["sin", "cos"]
    print("  OK")

    # ------------------------------------------------------------------
    # 8. query (in-memory subsetting)
    # ------------------------------------------------------------------
    separator("8. query")

    sub = loaded.query(start=3.0, end=5.0, channels=["cos", "linear"])
    print(f"  query result: {sub}")
    print(f"  cos points:    {len(sub['cos'])}")
    print(f"  linear points: {len(sub['linear'])}")
    assert "cos" in sub
    assert "linear" in sub
    assert "sin" not in sub
    assert all(ts >= 3.0 for ts in sub["cos"].timestamps)
    assert all(ts <= 5.0 for ts in sub["cos"].timestamps)
    print("  OK")

    # ------------------------------------------------------------------
    # 9. to_plotly
    # ------------------------------------------------------------------
    separator("9. to_plotly")

    plotly_dict = loaded.to_plotly(channels=["sin", "cos"])
    print(f"  keys:   {list(plotly_dict.keys())}")
    print(f"  traces: {len(plotly_dict['data'])}")
    assert "data" in plotly_dict
    assert "layout" in plotly_dict
    assert len(plotly_dict["data"]) == 2
    assert plotly_dict["data"][0]["name"] == "sin"
    print("  OK")

    # ------------------------------------------------------------------
    # 10. plot (opens browser / inline)
    # ------------------------------------------------------------------
    separator("10. plot")

    loaded.plot(channels=["sin", "cos"], title="Test: sin & cos")
    print("  plot() called — check your browser/notebook")

    # ------------------------------------------------------------------
    # 11. Many-to-many sample linking
    # ------------------------------------------------------------------
    separator("11. Many-to-many linking")

    dataset = fo.Dataset("_ts_test_script")
    s1 = fo.Sample(filepath="/tmp/clip1.mp4")
    s2 = fo.Sample(filepath="/tmp/clip2.mp4")
    s3 = fo.Sample(filepath="/tmp/clip3.mp4")
    dataset.add_samples([s1, s2, s3])

    # Link: s1 -> multi, csv | s2 -> multi | s3 -> csv
    s1.link_timeseries("test_multi")
    s1.link_timeseries("test_csv")
    s2.link_timeseries("test_multi")
    s3.link_timeseries("test_csv")

    print(f"  s1 links: {s1.get_timeseries_names()}")
    print(f"  s2 links: {s2.get_timeseries_names()}")
    print(f"  s3 links: {s3.get_timeseries_names()}")
    assert "test_multi" in s1.get_timeseries_names()
    assert "test_csv" in s1.get_timeseries_names()
    assert s1.has_timeseries()
    assert s2.get_timeseries_names() == ["test_multi"]
    assert s3.get_timeseries_names() == ["test_csv"]
    print("  OK")

    # ------------------------------------------------------------------
    # 12. Reverse lookup
    # ------------------------------------------------------------------
    separator("12. Reverse lookup")

    multi_sample_ids = TimeSeries.get_sample_ids_for_timeseries("test_multi")
    csv_sample_ids = TimeSeries.get_sample_ids_for_timeseries("test_csv")
    print(f"  samples for test_multi: {multi_sample_ids}")
    print(f"  samples for test_csv:   {csv_sample_ids}")
    assert len(multi_sample_ids) == 2
    assert len(csv_sample_ids) == 2
    print("  OK")

    # ------------------------------------------------------------------
    # 13. Load through sample
    # ------------------------------------------------------------------
    separator("13. Load through sample")

    via_sample = s1.get_timeseries("test_multi")
    print(f"  loaded via s1: {via_sample}")
    assert np.allclose(via_sample["sin"].values, np.sin(t))
    print("  values match!")

    # ------------------------------------------------------------------
    # 14. Unlink
    # ------------------------------------------------------------------
    separator("14. Unlink")

    s1.unlink_timeseries("test_csv")
    print(f"  s1 after unlink csv: {s1.get_timeseries_names()}")
    assert "test_csv" not in s1.get_timeseries_names()
    assert "test_multi" in s1.get_timeseries_names()

    s3.unlink_all_timeseries()
    print(f"  s3 after unlink all: {s3.get_timeseries_names()}")
    assert s3.get_timeseries_names() == []
    assert not s3.has_timeseries()
    print("  OK")

    # ------------------------------------------------------------------
    # 15. Delete time series + cleanup
    # ------------------------------------------------------------------
    separator("15. Delete + cleanup")

    TimeSeries.delete("test_single")
    TimeSeries.delete("test_multi")
    TimeSeries.delete("test_csv")

    print(f"  registered after delete: {TimeSeries.list()}")
    assert TimeSeries.list() == []

    # Links should be cleaned up too
    assert s1.get_timeseries_names() == []
    assert s2.get_timeseries_names() == []
    print("  links cleaned up")

    fo.delete_dataset("_ts_test_script")
    print("  dataset deleted")

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------
    separator("ALL TESTS PASSED")


def demo() -> None:
    """Create a persistent dataset with time series and launch the App.

    Use this to visually test the Time Series panel plugin.
    Cleanup with: ``fo.delete_dataset("timeseries_demo")``
    """
    separator("DEMO — creating dataset + time series for the App")

    # Clean up previous run if any
    if fo.dataset_exists("timeseries_demo"):
        for name in TimeSeries.list():
            TimeSeries.delete(name)
        fo.delete_dataset("timeseries_demo")

    # Load real bed temperatures from CSV
    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "timeseries_demo",
        "temperatures.csv",
    )
    ts = TimeSeries.from_csv("bed_temperatures", csv_path)
    print(f"  Loaded: {ts}")
    for ch_name in ts.channel_names:
        ch = ts[ch_name]
        print(
            f"    {ch_name}: {len(ch)} pts, [{ch.values.min():.1f}, {ch.values.max():.1f}]°C"
        )

    print(f"  Registered: {TimeSeries.list()}")

    # Create dataset with the demo video
    dataset = fo.Dataset("timeseries_demo", persistent=True)

    video_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "timeseries_demo",
        "Artillery Sidewinder X2 - Bed Temperature Uniformity - FLIR Cam.mp4",
    )

    sample = fo.Sample(filepath=video_path)
    dataset.add_sample(sample)
    sample.compute_metadata()

    sample.link_timeseries("bed_temperatures")

    print(f"  Dataset: {dataset}")
    print(f"  Sample: {sample.filepath}")
    print(f"  Linked: {sample.get_timeseries_names()}")

    separator("Launching FiftyOne App — open the Time Series panel")
    session = fo.launch_app(dataset)
    input("Press Enter to shut down...")
    session.close()


if __name__ == "__main__":
    import sys

    if "--demo" in sys.argv:
        demo()
    else:
        main()
