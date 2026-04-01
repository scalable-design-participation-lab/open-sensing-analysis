from __future__ import annotations

from typing import Iterable

import pandas as pd


def _prepare_resampled_series(
    df: pd.DataFrame,
    variable_name: str,
    time_column: str,
    sampling_interval: str,
) -> pd.Series:
    if time_column not in df.columns:
        raise ValueError(f"Missing time column: {time_column}")
    if variable_name not in df.columns:
        raise ValueError(f"Missing variable column: {variable_name}")

    ts = df.copy()
    ts[time_column] = pd.to_datetime(ts[time_column], utc=True).dt.tz_convert(None)
    ts[variable_name] = pd.to_numeric(ts[variable_name], errors="coerce")
    ts = ts.sort_values(time_column).set_index(time_column)
    return ts[variable_name].resample(sampling_interval).mean()


def align_sensor_series(
    sensor_dataframes: dict[str, pd.DataFrame],
    variable_name: str,
    time_column: str,
    sampling_interval: str = "1min",
    min_sensors: int | None = None,
    timestamp_tolerance: str | pd.Timedelta | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Align many sensor time series using common timestamps only (no lag shifting).

    How it works:
    1. Each sensor is parsed, sorted, and resampled to `sampling_interval`.
    2. If `timestamp_tolerance` is None, rows are aligned by exact timestamp.
    3. If `timestamp_tolerance` is provided, each sensor is matched to a shared
       timeline by nearest timestamp within that tolerance.
    4. Keep rows that have at least `min_sensors` available values.

    Returns:
    - aligned_df: aligned values, one column per sensor.
    - info_df: availability diagnostics per sensor.
    """
    if len(sensor_dataframes) < 2:
        raise ValueError("Provide at least two sensors to align.")

    names = list(sensor_dataframes.keys())
    required = len(names) if min_sensors is None else int(min_sensors)
    if required < 1 or required > len(names):
        raise ValueError(f"min_sensors must be between 1 and {len(names)} (got {required})")

    resampled = {
        sensor_name: _prepare_resampled_series(
            df=df,
            variable_name=variable_name,
            time_column=time_column,
            sampling_interval=sampling_interval,
        )
        for sensor_name, df in sensor_dataframes.items()
    }

    if timestamp_tolerance is None:
        aligned_df = pd.concat(resampled, axis=1)
    else:
        tol = pd.to_timedelta(timestamp_tolerance)
        valid = {name: s.dropna() for name, s in resampled.items()}
        starts = [s.index.min() for s in valid.values() if len(s) > 0]
        ends = [s.index.max() for s in valid.values() if len(s) > 0]

        if not starts or not ends:
            aligned_df = pd.DataFrame(columns=names)
        else:
            start = max(starts)
            end = min(ends)
            if start > end:
                aligned_df = pd.DataFrame(columns=names)
            else:
                master_index = pd.date_range(start=start, end=end, freq=sampling_interval)
                nearest = {
                    name: s.reindex(master_index, method="nearest", tolerance=tol)
                    for name, s in valid.items()
                }
                aligned_df = pd.concat(nearest, axis=1)

    aligned_df = aligned_df[aligned_df.notna().sum(axis=1) >= required]
    aligned_df.columns = [str(c) for c in aligned_df.columns]

    available_points = {name: int(s.dropna().shape[0]) for name, s in resampled.items()}
    start_times = {
        name: (s.dropna().index.min() if s.dropna().shape[0] > 0 else pd.NaT)
        for name, s in resampled.items()
    }
    end_times = {
        name: (s.dropna().index.max() if s.dropna().shape[0] > 0 else pd.NaT)
        for name, s in resampled.items()
    }
    info_df = pd.DataFrame(
        [
            {
                "sensor": sensor_name,
                "overlap_points": int(aligned_df.shape[0]),
                "required_sensors": required,
                "timestamp_tolerance": (
                    str(pd.to_timedelta(timestamp_tolerance))
                    if timestamp_tolerance is not None
                    else None
                ),
                "available_points": available_points[sensor_name],
                "start_time": start_times[sensor_name],
                "end_time": end_times[sensor_name],
            }
            for sensor_name in names
        ]
    ).sort_values("sensor").reset_index(drop=True)

    return aligned_df, info_df


def align_sensor_series_from_list(
    sensor_dataframes: Iterable[pd.DataFrame],
    variable_name: str,
    time_column: str,
    sensor_names: list[str] | None = None,
    sampling_interval: str = "1min",
    min_sensors: int | None = None,
    timestamp_tolerance: str | pd.Timedelta | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Same as align_sensor_series, but accepts a list/iterable of DataFrames.
    """
    frames = list(sensor_dataframes)
    if sensor_names is None:
        sensor_names = [f"sensor_{i + 1}" for i in range(len(frames))]
    if len(sensor_names) != len(frames):
        raise ValueError("sensor_names must have the same length as sensor_dataframes.")

    mapping = {name: frame for name, frame in zip(sensor_names, frames)}
    return align_sensor_series(
        sensor_dataframes=mapping,
        variable_name=variable_name,
        time_column=time_column,
        sampling_interval=sampling_interval,
        min_sensors=min_sensors,
        timestamp_tolerance=timestamp_tolerance,
    )
