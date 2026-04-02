"""
Time series data support for FiftyOne.

Time series are standalone entities stored in their own MongoDB time series
collections.  Samples have a many-to-many relationship with time series
via a lightweight links collection.

| Copyright 2017-2026, Voxel51, Inc.
| `voxel51.com <https://voxel51.com/>`_
|
"""

from __future__ import annotations

import csv
import datetime
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
from bson import ObjectId
import pymongo

from fiftyone.core.odm.database import get_db_conn

# Epoch used to convert float seconds → BSON datetime for MongoDB timeField
_EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)

# Mongo collection that tracks registered time series
_REGISTRY_COLLECTION = "_timeseries_registry"

# Mongo collection that tracks sample <-> time series links
_LINKS_COLLECTION = "_timeseries_links"

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _seconds_to_datetime(seconds: float) -> datetime.datetime:
    """Convert float seconds to BSON-compatible UTC datetime."""
    return _EPOCH + datetime.timedelta(seconds=seconds)


def _datetime_to_seconds(dt: datetime.datetime) -> float:
    """Convert UTC datetime back to float seconds."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return (dt - _EPOCH).total_seconds()


def _data_collection_name(name: str) -> str:
    """MongoDB collection name for a time series' data."""
    return f"ts.{name}"


def _ensure_registry(
    db: pymongo.database.Database,
) -> pymongo.collection.Collection:
    """Get or create the time series registry collection."""
    coll = db[_REGISTRY_COLLECTION]
    coll.create_index("name", unique=True)
    return coll


def _ensure_links(
    db: pymongo.database.Database,
) -> pymongo.collection.Collection:
    """Get or create the time series links (junction) collection."""
    coll = db[_LINKS_COLLECTION]
    coll.create_index([("sample_id", 1), ("timeseries_name", 1)], unique=True)
    coll.create_index("timeseries_name")
    return coll


def _ensure_data_collection(
    db: pymongo.database.Database,
    collection_name: str,
) -> pymongo.collection.Collection:
    """Get or create a native MongoDB time series data collection."""
    if collection_name not in db.list_collection_names():
        db.create_collection(
            collection_name,
            timeseries={
                "timeField": "timestamp",
                "metaField": "meta",
                "granularity": "seconds",
            },
        )
        logger.info("Created time series collection %s", collection_name)
    return db[collection_name]


# ------------------------------------------------------------------
# Channel
# ------------------------------------------------------------------


class TimeSeriesChannel:
    """A single channel of time series data.

    Args:
        name: the channel name
        timestamps: 1D numpy array of timestamps (float seconds)
        values: 1D numpy array of values
    """

    def __init__(
        self,
        name: str,
        timestamps: np.ndarray,
        values: np.ndarray,
    ):
        self.name = name
        self.timestamps = np.asarray(timestamps, dtype=np.float64)
        self.values = np.asarray(values, dtype=np.float64)

        if self.timestamps.shape != self.values.shape:
            raise ValueError(
                f"timestamps and values must have same shape, "
                f"got {self.timestamps.shape} vs {self.values.shape}"
            )

    def __len__(self) -> int:
        return len(self.timestamps)

    def __repr__(self) -> str:
        if len(self) == 0:
            return f"<TimeSeriesChannel: name={self.name!r}, points=0>"
        return (
            f"<TimeSeriesChannel: name={self.name!r}, "
            f"points={len(self)}, "
            f"range=[{self.timestamps[0]:.3f}, {self.timestamps[-1]:.3f}]>"
        )

    def query(
        self,
        start: Optional[float] = None,
        end: Optional[float] = None,
    ) -> "TimeSeriesChannel":
        """Return a subset of this channel within [start, end].

        Args:
            start: start timestamp (inclusive), or None for beginning
            end: end timestamp (inclusive), or None for end

        Returns:
            a new :class:`TimeSeriesChannel`
        """
        mask = np.ones(len(self), dtype=bool)
        if start is not None:
            mask &= self.timestamps >= start
        if end is not None:
            mask &= self.timestamps <= end
        return TimeSeriesChannel(
            name=self.name,
            timestamps=self.timestamps[mask],
            values=self.values[mask],
        )


# ------------------------------------------------------------------
# TimeSeries — standalone entity
# ------------------------------------------------------------------


class TimeSeries:
    """A standalone time series stored in its own MongoDB collection.

    Each TimeSeries has a unique ``name`` and contains one or more channels
    of timestamped float data.  Samples link to time series by name via a
    many-to-many junction collection.

    Args:
        name: unique identifier for this time series
        channels: optional dict mapping channel names to
            :class:`TimeSeriesChannel` instances
    """

    def __init__(
        self,
        name: str,
        timestamps: Optional[np.ndarray] = None,
        values: Optional[np.ndarray] = None,
        channel_names: Optional[List[str]] = None,
    ):
        self._name = name

        if timestamps is not None and values is not None:
            timestamps = np.asarray(timestamps, dtype=np.float64)
            values = np.asarray(values, dtype=np.float64)

            if values.ndim == 1:
                values = values.reshape(-1, 1)

            if timestamps.shape[0] != values.shape[0]:
                raise ValueError(
                    f"timestamps length {timestamps.shape[0]} != "
                    f"values rows {values.shape[0]}"
                )

            num_channels = values.shape[1]
            if channel_names is None:
                channel_names = [f"channel_{i}" for i in range(num_channels)]

            if len(channel_names) != num_channels:
                raise ValueError(
                    f"Got {len(channel_names)} channel names but "
                    f"{num_channels} channels"
                )

            self._channels: Dict[str, TimeSeriesChannel] = {}
            for i, ch_name in enumerate(channel_names):
                self._channels[ch_name] = TimeSeriesChannel(
                    ch_name, timestamps.copy(), values[:, i]
                )
        else:
            self._channels = {}

        self.save()

    @classmethod
    def _from_channels(
        cls,
        name: str,
        channels: Dict[str, TimeSeriesChannel],
    ) -> "TimeSeries":
        """Internal constructor that skips save (for load/query/from_csv)."""
        instance = cls.__new__(cls)
        instance._name = name
        instance._channels = channels
        return instance

    # -- properties ------------------------------------------------

    @property
    def name(self) -> str:
        """The unique name of this time series."""
        return self._name

    @property
    def channel_names(self) -> List[str]:
        """The list of channel names."""
        return list(self._channels.keys())

    @property
    def channels(self) -> Dict[str, TimeSeriesChannel]:
        """Dict mapping channel names to :class:`TimeSeriesChannel`."""
        return self._channels

    def __len__(self) -> int:
        return len(self._channels)

    def __getitem__(self, channel_name: str) -> TimeSeriesChannel:
        return self._channels[channel_name]

    def __contains__(self, channel_name: str) -> bool:
        return channel_name in self._channels

    def __repr__(self) -> str:
        return (
            f"<TimeSeries: name={self._name!r}, "
            f"channels={self.channel_names}>"
        )

    # -- mutators --------------------------------------------------

    def add_channel(
        self,
        name: str,
        timestamps: np.ndarray,
        values: np.ndarray,
    ) -> None:
        """Add a channel of time series data.

        Args:
            name: the channel name
            timestamps: 1D array of timestamps (float seconds)
            values: 1D array of values
        """
        self._channels[name] = TimeSeriesChannel(name, timestamps, values)

    # -- factory methods -------------------------------------------

    @classmethod
    def from_csv(
        cls,
        name: str,
        filepath: str,
        timestamp_col: str = "timestamp",
        value_cols: Optional[List[str]] = None,
    ) -> "TimeSeries":
        """Create a TimeSeries from a CSV file (in-memory only).

        Args:
            name: unique name for this time series
            filepath: path to the CSV file
            timestamp_col: name of the timestamp column
            value_cols: optional list of value column names. If None,
                all columns except timestamp_col are used

        Returns:
            a :class:`TimeSeries`
        """
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames

            if timestamp_col not in fieldnames:
                raise ValueError(
                    f"Timestamp column {timestamp_col!r} not found in CSV. "
                    f"Available: {fieldnames}"
                )

            if value_cols is None:
                value_cols = [c for c in fieldnames if c != timestamp_col]

            for col in value_cols:
                if col not in fieldnames:
                    raise ValueError(
                        f"Value column {col!r} not found in CSV. "
                        f"Available: {fieldnames}"
                    )

            timestamps_list: List[float] = []
            values_dict: Dict[str, List[float]] = {
                col: [] for col in value_cols
            }

            for row in reader:
                timestamps_list.append(float(row[timestamp_col]))
                for col in value_cols:
                    values_dict[col].append(float(row[col]))

        timestamps = np.array(timestamps_list, dtype=np.float64)
        channels = {}
        for col in value_cols:
            channels[col] = TimeSeriesChannel(
                col,
                timestamps.copy(),
                np.array(values_dict[col], dtype=np.float64),
            )

        ts = cls._from_channels(name=name, channels=channels)
        ts.save()
        return ts

    # -- export ----------------------------------------------------

    def to_numpy(
        self,
        channels: Optional[List[str]] = None,
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Export to numpy arrays.

        Args:
            channels: optional subset of channel names to export

        Returns:
            a tuple of (timestamps, values, channel_names) where
            timestamps is 1D and values is 2D
            (num_timestamps x num_channels)
        """
        if channels is None:
            channels = self.channel_names

        if not channels:
            return np.array([]), np.array([]).reshape(0, 0), []

        first = self._channels[channels[0]]
        timestamps = first.timestamps

        values = np.column_stack(
            [self._channels[ch].values for ch in channels]
        )

        return timestamps, values, channels

    def to_plotly(
        self,
        channels: Optional[List[str]] = None,
    ) -> dict:
        """Convert to Plotly-compatible dict for rendering.

        Args:
            channels: optional subset of channel names

        Returns:
            a dict with "data" and "layout" keys
        """
        if channels is None:
            channels = self.channel_names

        traces = []
        for ch_name in channels:
            ch = self._channels[ch_name]
            traces.append(
                {
                    "x": ch.timestamps.tolist(),
                    "y": ch.values.tolist(),
                    "type": "scatter",
                    "mode": "lines",
                    "name": ch_name,
                }
            )

        layout = {
            "xaxis": {"title": "Time (s)"},
            "yaxis": {"title": "Value"},
            "margin": {"l": 50, "r": 20, "t": 30, "b": 40},
            "showlegend": len(traces) > 1,
        }

        return {"data": traces, "layout": layout}

    def plot(
        self,
        channels: Optional[List[str]] = None,
        title: Optional[str] = None,
    ) -> None:
        """Show an interactive Plotly plot in the browser.

        Blocks until the user presses Enter in the terminal.

        Args:
            channels: optional subset of channel names to plot
            title: optional plot title (defaults to the time series name)
        """
        import tempfile
        import webbrowser

        import plotly.graph_objects as go

        fig_dict = self.to_plotly(channels=channels)
        fig = go.Figure(fig_dict)
        fig.update_layout(title=title or self._name)

        html_path = tempfile.mktemp(suffix=".html")
        fig.write_html(html_path)
        webbrowser.open(f"file://{html_path}")
        input("Plot opened in browser. Press Enter to continue...")

    def query(
        self,
        start: Optional[float] = None,
        end: Optional[float] = None,
        channels: Optional[List[str]] = None,
    ) -> "TimeSeries":
        """Return a subset of this time series within [start, end].

        Args:
            start: start timestamp (inclusive)
            end: end timestamp (inclusive)
            channels: optional subset of channel names

        Returns:
            a new :class:`TimeSeries`
        """
        if channels is None:
            channels = self.channel_names

        new_channels = {}
        for ch_name in channels:
            new_channels[ch_name] = self._channels[ch_name].query(start, end)

        return TimeSeries._from_channels(
            name=self._name, channels=new_channels
        )

    # ------------------------------------------------------------------
    # MongoDB persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Save this time series to MongoDB.

        Registers the time series in the registry and writes all channel
        data to a dedicated MongoDB time series collection (``ts.<name>``).
        Overwrites any existing data.
        """
        db = get_db_conn()
        coll_name = _data_collection_name(self._name)

        # Register in registry (upsert)
        registry = _ensure_registry(db)
        registry.update_one(
            {"name": self._name},
            {
                "$set": {
                    "name": self._name,
                    "collection": coll_name,
                    "channels": self.channel_names,
                }
            },
            upsert=True,
        )

        # Write data
        data_coll = _ensure_data_collection(db, coll_name)
        data_coll.delete_many({})  # full replace

        docs = []
        for ch in self._channels.values():
            for i in range(len(ch)):
                docs.append(
                    {
                        "timestamp": _seconds_to_datetime(
                            float(ch.timestamps[i])
                        ),
                        "meta": {"channel": ch.name},
                        "value": float(ch.values[i]),
                    }
                )

        if docs:
            data_coll.insert_many(docs, ordered=False)

        logger.info(
            "Saved time series %r: %d channels, %d points",
            self._name,
            len(self._channels),
            len(docs),
        )

    @classmethod
    def load(
        cls,
        name: str,
        channels: Optional[List[str]] = None,
        start: Optional[float] = None,
        end: Optional[float] = None,
    ) -> "TimeSeries":
        """Load a time series from MongoDB.

        Args:
            name: the time series name
            channels: optional subset of channel names to load
            start: optional start timestamp filter (seconds)
            end: optional end timestamp filter (seconds)

        Returns:
            a :class:`TimeSeries`
        """
        db = get_db_conn()
        coll_name = _data_collection_name(name)
        coll = db[coll_name]

        query: dict = {}
        if channels:
            query["meta.channel"] = {"$in": channels}
        if start is not None or end is not None:
            ts_filter: dict = {}
            if start is not None:
                ts_filter["$gte"] = _seconds_to_datetime(start)
            if end is not None:
                ts_filter["$lte"] = _seconds_to_datetime(end)
            query["timestamp"] = ts_filter

        cursor = coll.find(query).sort("timestamp", pymongo.ASCENDING)

        channel_data: Dict[str, Tuple[List[float], List[float]]] = {}
        for doc in cursor:
            ch_name = doc["meta"]["channel"]
            if ch_name not in channel_data:
                channel_data[ch_name] = ([], [])
            channel_data[ch_name][0].append(
                _datetime_to_seconds(doc["timestamp"])
            )
            channel_data[ch_name][1].append(doc["value"])

        loaded_channels = {}
        for ch_name, (ts, vals) in channel_data.items():
            loaded_channels[ch_name] = TimeSeriesChannel(
                ch_name,
                np.array(ts, dtype=np.float64),
                np.array(vals, dtype=np.float64),
            )

        return cls._from_channels(name=name, channels=loaded_channels)

    @classmethod
    def exists(cls, name: str) -> bool:
        """Check if a time series with this name exists.

        Args:
            name: the time series name

        Returns:
            True if it exists in the registry
        """
        db = get_db_conn()
        registry = _ensure_registry(db)
        return registry.count_documents({"name": name}, limit=1) > 0

    @classmethod
    def list(cls) -> List[str]:
        """List all registered time series names.

        Returns:
            list of time series name strings
        """
        db = get_db_conn()
        registry = _ensure_registry(db)
        return [doc["name"] for doc in registry.find({}, {"name": 1})]

    @classmethod
    def delete(cls, name: str) -> None:
        """Delete a time series and all its data.

        Also removes all sample links to this time series.

        Args:
            name: the time series name
        """
        db = get_db_conn()
        coll_name = _data_collection_name(name)

        # Drop data collection
        if coll_name in db.list_collection_names():
            db.drop_collection(coll_name)

        # Remove from registry
        registry = _ensure_registry(db)
        registry.delete_one({"name": name})

        # Remove all links
        links = _ensure_links(db)
        links.delete_many({"timeseries_name": name})

        logger.info("Deleted time series %r", name)

    # ------------------------------------------------------------------
    # Sample linking (many-to-many)
    # ------------------------------------------------------------------

    @classmethod
    def link_sample(cls, sample_id: ObjectId, timeseries_name: str) -> None:
        """Link a sample to a time series.

        Args:
            sample_id: the sample ObjectId
            timeseries_name: the time series name
        """
        db = get_db_conn()
        links = _ensure_links(db)
        links.update_one(
            {"sample_id": sample_id, "timeseries_name": timeseries_name},
            {
                "$set": {
                    "sample_id": sample_id,
                    "timeseries_name": timeseries_name,
                }
            },
            upsert=True,
        )

    @classmethod
    def unlink_sample(cls, sample_id: ObjectId, timeseries_name: str) -> None:
        """Remove the link between a sample and a time series.

        Args:
            sample_id: the sample ObjectId
            timeseries_name: the time series name
        """
        db = get_db_conn()
        links = _ensure_links(db)
        links.delete_one(
            {"sample_id": sample_id, "timeseries_name": timeseries_name}
        )

    @classmethod
    def unlink_all_for_sample(cls, sample_id: ObjectId) -> None:
        """Remove all time series links for a sample.

        Args:
            sample_id: the sample ObjectId
        """
        db = get_db_conn()
        links = _ensure_links(db)
        links.delete_many({"sample_id": sample_id})

    @classmethod
    def get_timeseries_names_for_sample(cls, sample_id: ObjectId) -> List[str]:
        """Get the names of all time series linked to a sample.

        Args:
            sample_id: the sample ObjectId

        Returns:
            list of time series name strings
        """
        db = get_db_conn()
        links = _ensure_links(db)
        return [
            doc["timeseries_name"]
            for doc in links.find(
                {"sample_id": sample_id}, {"timeseries_name": 1}
            )
        ]

    @classmethod
    def get_sample_ids_for_timeseries(
        cls, timeseries_name: str
    ) -> List[ObjectId]:
        """Get the IDs of all samples linked to a time series.

        Args:
            timeseries_name: the time series name

        Returns:
            list of sample ObjectIds
        """
        db = get_db_conn()
        links = _ensure_links(db)
        return [
            doc["sample_id"]
            for doc in links.find(
                {"timeseries_name": timeseries_name}, {"sample_id": 1}
            )
        ]
