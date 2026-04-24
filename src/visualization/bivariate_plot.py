from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Literal, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure


AggName = Literal["mean", "median", "p90", "p95", "p99"]


@dataclass(frozen=True)
class BivariatePolarConfig:
    wd_bin_deg: float = 10.0
    ws_bins: Tuple[float, ...] = (0.0, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 10.0, 15.0, 20.0)
    calm_ws_min: float = 0.5
    agg: AggName = "median"
    cmap: Union[str, object] = "viridis"
    figsize: Tuple[float, float] = (7.0, 7.0)
    x_label: str = "Wind direction (deg)"
    y_label: str = "Wind speed (m/s)"
    colorbar_label: Optional[str] = None
    title: Optional[str] = None
    vmin: Optional[float] = None
    vmax: Optional[float] = None
    show: bool = True


def _as_1d_float_array(x_data: Union[Sequence[float], np.ndarray, pd.Series]) -> np.ndarray:
    x = np.asarray(x_data, dtype=float).reshape(-1)
    return x


def _agg_series(s: pd.Series, agg: AggName) -> float:
    if agg == "mean":
        return float(s.mean())
    if agg == "median":
        return float(s.median())
    if agg == "p90":
        return float(s.quantile(0.90))
    if agg == "p95":
        return float(s.quantile(0.95))
    if agg == "p99":
        return float(s.quantile(0.99))
    raise ValueError(f"Unknown agg: {agg}")


def bivariate_polar_plot_xy(
    x_data: Union[Sequence[float], np.ndarray, pd.Series],
    y_data: Union[Sequence[float], np.ndarray, pd.Series],
    z_data: Union[Sequence[float], np.ndarray, pd.Series],
    config: Optional[BivariatePolarConfig] = None,
    ax: Optional[Axes] = None,
    add_colorbar: bool = True,
) -> Tuple[Figure, Axes]:
    cfg = config or BivariatePolarConfig()

    x = _as_1d_float_array(x_data) % 360.0
    y = _as_1d_float_array(y_data)
    z = _as_1d_float_array(z_data)

    if not (len(x) == len(y) == len(z)):
        raise ValueError("x_data, y_data, z_data must have the same length")

    mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(z) & (y >= cfg.calm_ws_min)
    x = x[mask]
    y = y[mask]
    z = z[mask]

    if x.size == 0:
        raise ValueError("No valid data left after filtering (NaNs or calm wind threshold).")

    wd_edges = np.arange(0.0, 360.0 + cfg.wd_bin_deg, cfg.wd_bin_deg, dtype=float)
    ws_edges = np.asarray(cfg.ws_bins, dtype=float)

    if wd_edges.size < 2:
        raise ValueError("wd_bin_deg produces invalid bin edges")
    if ws_edges.size < 2 or not np.all(np.diff(ws_edges) > 0):
        raise ValueError("ws_bins must be strictly increasing and contain at least 2 edges")

    d = pd.DataFrame({"x": x, "y": y, "z": z})
    d["wd_bin"] = pd.cut(d["x"], wd_edges, right=False, include_lowest=True)
    d["ws_bin"] = pd.cut(d["y"], ws_edges, right=False, include_lowest=True)

    grouped = d.groupby(["ws_bin", "wd_bin"], observed=True)["z"].apply(lambda s: _agg_series(s, cfg.agg))
    Z = grouped.unstack("wd_bin")

    Z = Z.reindex(
        index=pd.IntervalIndex.from_breaks(ws_edges, closed="left"),
        columns=pd.IntervalIndex.from_breaks(wd_edges, closed="left"),
    )

    theta_edges = np.deg2rad(wd_edges)
    r_edges = ws_edges

    if ax is None:
        fig = plt.figure(figsize=cfg.figsize)
        ax = plt.subplot(111, projection="polar")
    else:
        # Ensure caller passed a polar axis
        if ax.name != "polar":
            raise ValueError("ax must be a polar axis. Create it with subplot(..., projection='polar').")
        fig = ax.figure

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)

    pcm = ax.pcolormesh(
        theta_edges,
        r_edges,
        Z.to_numpy(),
        shading="auto",
        cmap=cfg.cmap,
        vmin=cfg.vmin,
        vmax=cfg.vmax,
    )

    if add_colorbar:
        cbar = fig.colorbar(pcm, ax=ax, pad=0.1)
        cbar.set_label(cfg.colorbar_label or f"{cfg.agg}(z)")

    ax.set_xlabel(cfg.x_label)
    ax.set_ylabel(cfg.y_label, labelpad = 40)
    ax.yaxis.set_label_coords(-0.12, 0.5) 

    if cfg.title:
        ax.set_title(cfg.title)

    if cfg.show and ax is None:
        plt.show()

    return fig, ax


def bivariate_polar_plot_df(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    z_col: str,
    config: Optional[BivariatePolarConfig] = None,
    ax: Optional[Axes] = None,
) -> Tuple[Figure, Axes]:
    return bivariate_polar_plot_xy(
        x_data=df[x_col].to_numpy(),
        y_data=df[y_col].to_numpy(),
        z_data=df[z_col].to_numpy(),
        config=config,
        ax=ax,
)
