# Time series

```python
import fiftyone as fo
import numpy as np
```

### Constructor (builds channels from stacked values, **saves immediately**)

```python
ts = fo.TimeSeries(
    "print_plane_temperatures",
    timestamps=t,
    values=np.column_stack([c1, c2]),
    channel_names=["c1", "c2"],
)
```

### CSV (loads file and **saves**)

```python
ts = fo.TimeSeries.from_csv(
    "bed", "temperatures.csv", timestamp_col="timestamp"
)
```

### Read back from DB

```python
ts = fo.TimeSeries.load("my_run")
ts = fo.TimeSeries.load("my_run", channels=["a"], start=0.0, end=60.0)
```

### Registry

```python
fo.TimeSeries.exists("my_run")
fo.TimeSeries.list()
fo.TimeSeries.delete("my_run")
```

### Slice / export

```python
window = ts.query(start=0, end=60, channels=["a"])
timestamps, values, names = ts.to_numpy()
fig_dict = ts.to_plotly()  # pass to Plotly, or use in notebooks
# ts.plot()  # opens browser, waits for Enter
```

### Add a channel on an existing object

```python
ts.add_channel("extra", t2, y2)
ts.save()
```

### Link a sample (by ObjectId)

```python
fo.TimeSeries.link_sample(sample._id, "my_run")
fo.TimeSeries.unlink_sample(sample._id, "my_run")
fo.TimeSeries.unlink_all_for_sample(sample._id)
fo.TimeSeries.get_timeseries_names_for_sample(sample._id)
fo.TimeSeries.get_sample_ids_for_timeseries("my_run")
```

---

Longer walkthroughs: `sdk_timeseries_demo.ipynb`,
`sdk_timeseries_sine_demo.ipynb`.
