import pandas as pd
import numpy as np

def resample_and_align(
    time_series_1: pd.DataFrame,
    time_series_2: pd.DataFrame,
    variable_name: str,
    time_column: str,
    sampling_interval: str = "1min",
) -> pd.DataFrame:

    ts1 = time_series_1.copy()
    ts2 = time_series_2.copy()

    ts1[time_column] = pd.to_datetime(ts1[time_column])
    ts2[time_column] = pd.to_datetime(ts2[time_column])

    ts1 = ts1.sort_values(time_column).set_index(time_column)
    ts2 = ts2.sort_values(time_column).set_index(time_column)

    s1 = ts1[variable_name].resample(sampling_interval).mean()
    s2 = ts2[variable_name].resample(sampling_interval).mean()

    aligned = pd.concat([s1, s2], axis=1)
    aligned.columns = [f"{variable_name}_1", f"{variable_name}_2"]
    aligned = aligned.dropna()

    x = aligned[f"{variable_name}_1"].to_numpy()
    y = aligned[f"{variable_name}_2"].to_numpy()

    x = x - np.mean(x)
    y = y - np.mean(y)

    corr = np.correlate(x, y, mode="full")
    lags = np.arange(-len(x) + 1, len(x))
    best_lag = int(lags[np.argmax(corr)])

    # Shift series 1 to best align with series 2
    aligned[f"{variable_name}_1_aligned"] = aligned[f"{variable_name}_1"].shift(-best_lag)
    aligned = aligned.dropna()

    step = pd.to_timedelta(sampling_interval)
    aligned["lag_steps"] = best_lag
    aligned["lag_timedelta"] = best_lag * step

    return aligned