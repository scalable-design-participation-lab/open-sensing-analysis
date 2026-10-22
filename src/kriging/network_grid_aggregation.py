from __future__ import annotations

import geopandas as gpd
import pandas as pd

AGGREGATION_SUFFIXES = ("mean", "median", "std", "mean_weighted")
BASE_COLUMNS = ["grid_id", "geometry", "n_segments", "total_len"]


def aggregate_tagged_network_over_grid(
    tagged_network: gpd.GeoDataFrame,
    grid: gpd.GeoDataFrame,
    feature_columns: list[str],
) -> dict[str, gpd.GeoDataFrame]:
    """
    Aggregate a labelled street network onto grid cells.

    Reproduces the aggregation used to build the predictor grids the inference
    models were trained on, in notebooks/kriging_street_view/predictors_Export_2.ipynb
    cell 12. Streets are split at cell boundaries, then each feature is reduced per
    cell four ways: plain mean, median, standard deviation, and a length-weighted
    mean. The regression notebooks read the plain `<feature>_mean` column.

    Parameters
    ----------
    tagged_network
        Street segments as LineStrings, carrying one column per feature.
    grid
        Target cells. `grid_id` comes from the row position, as in the original.
    feature_columns
        Feature columns to aggregate.

    Returns
    -------
    dict
        One GeoDataFrame per feature, keyed by feature name, each holding
        `grid_id`, `geometry`, `n_segments`, `total_len` and the four
        `<feature>_*` columns. Cells the network does not reach hold NaN.
    """
    missing = [column for column in feature_columns if column not in tagged_network.columns]
    if missing:
        raise ValueError(f"Features not present in the tagged network: {missing}")

    if tagged_network.crs != grid.crs:
        tagged_network = tagged_network.to_crs(grid.crs)

    streets = tagged_network[feature_columns + ["geometry"]].copy()
    grid_ix = grid.reset_index(names="grid_id")[["grid_id", "geometry"]]

    parts = gpd.overlay(streets, grid_ix, how="intersection")
    parts["seg_len"] = parts.geometry.length

    aggregations: dict[str, tuple[str, str]] = {
        "n_segments": ("seg_len", "count"),
        "total_len": ("seg_len", "sum"),
    }
    for column in feature_columns:
        parts[f"{column}_len"] = parts[column]*parts["seg_len"]
        aggregations[f"{column}_mean"] = (column, "mean")
        aggregations[f"{column}_median"] = (column, "median")
        aggregations[f"{column}_std"] = (column, "std")
        aggregations[f"{column}_len_sum"] = (f"{column}_len", "sum")

    aggregated = parts.groupby("grid_id").agg(**aggregations).reset_index()

    for column in feature_columns:
        aggregated[f"{column}_mean_weighted"] = aggregated[f"{column}_len_sum"]/aggregated["total_len"]
        aggregated = aggregated.drop(columns=[f"{column}_len_sum"])

    grid_aggregated = grid_ix.merge(aggregated, on="grid_id", how="left")
    grid_aggregated = gpd.GeoDataFrame(grid_aggregated, geometry="geometry", crs=grid.crs)

    grid_aggregated_by_feature: dict[str, gpd.GeoDataFrame] = {}
    for column in feature_columns:
        columns = BASE_COLUMNS + [f"{column}_{suffix}" for suffix in AGGREGATION_SUFFIXES]
        grid_aggregated_by_feature[column] = grid_aggregated[columns].copy()

    return grid_aggregated_by_feature
