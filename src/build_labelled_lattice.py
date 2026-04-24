"""
build_labelled_lattice.py
=========================
Merges all extracted layers (satellite predictors, street-view predictors,
and kriging outputs) onto the 900-cell grid and writes:

    data/labelled_lattice.geojson       — the consolidated lattice
    data/labelled_lattice_metadata.json — column documentation (static, not re-written)

Run from the project root:
    python src/build_labelled_lattice.py
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np


def find_project_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "data" / "spatial" / "grid_rectangles.geojson").exists():
            return candidate
    raise FileNotFoundError("Could not locate project root.")


ROOT = find_project_root(Path(__file__).resolve())
LAYERS = ROOT / "data" / "kriging_satellite" / "layers"
SV_DIR = ROOT / "data" / "kriging_street_view"
COMB_DIR = ROOT / "data" / "kriging_combined"
SPATIAL = ROOT / "data" / "spatial"
OUT_PATH = ROOT / "data" / "labelled_lattice.geojson"


def _join(
    base: gpd.GeoDataFrame,
    path: Path,
    cols: list[str],
    id_col: str = "id",
    rename: dict[str, str] | None = None,
) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)[[id_col] + cols].rename(columns={id_col: "cell_id"})
    if rename:
        gdf = gdf.rename(columns=rename)
    return base.merge(gdf, on="cell_id", how="left")


def build() -> gpd.GeoDataFrame:
    lattice = gpd.read_file(SPATIAL / "grid_rectangles.geojson").rename(columns={"id": "cell_id"})
    print(f"Base grid: {len(lattice)} cells  CRS={lattice.crs}")

    # ── Satellite predictor layers ────────────────────────────────────────────
    lattice = _join(lattice, LAYERS / "ndvi_grid.geojson", ["ndvi"])
    lattice = _join(lattice, LAYERS / "ndbi_grid.geojson", ["ndbi"])
    lattice = _join(
        lattice, LAYERS / "nlcd_impervious_grid.geojson", ["impervious"],
        rename={"impervious": "impervious_pct"},
    )
    lattice = _join(
        lattice, LAYERS / "road_density_grid.geojson",
        ["road_density_km_km2", "major_road_density_km_km2"],
    )
    lattice = _join(
        lattice, LAYERS / "population_density_grid.geojson", ["population_density_km2"],
    )
    lattice = _join(
        lattice, LAYERS / "nei_emissions_grid.geojson",
        ["emissions_tpy", "emissions_point_tpy", "emissions_area_tpy"],
        rename={
            "emissions_tpy": "nei_emissions_tpy",
            "emissions_point_tpy": "nei_point_emissions_tpy",
            "emissions_area_tpy": "nei_area_emissions_tpy",
        },
    )

    # ── Street-view predictor layers ──────────────────────────────────────────
    sv_layers = [
        ("grid_aggregated_gvi.geojson",          ["gvi_mean", "gvi_median", "gvi_std"]),
        ("grid_aggregated_facade_area.geojson",  ["facade_area_mean", "facade_area_median", "facade_area_std"]),
        ("grid_aggregated_n_cars.geojson",       ["n_cars_mean", "n_cars_median", "n_cars_std"]),
        ("grid_aggregated_sky_ratio.geojson",    ["sky_ratio_mean", "sky_ratio_median", "sky_ratio_std"]),
        ("grid_aggregated_road_ratio.geojson",   ["road_ratio_mean", "road_ratio_median", "road_ratio_std"]),
    ]
    for fname, cols in sv_layers:
        lattice = _join(lattice, SV_DIR / fname, cols, id_col="grid_id")

    # ── Satellite pipeline — PCA components + ridge + kriging ────────────────
    lattice = _join(
        lattice, LAYERS / "temperature_ridge_kriging_grid.geojson",
        ["sat_pc1", "sat_pc2", "predicted_temperature_ridge", "estimated_residual", "final_temperature"],
        id_col="grid_id",
        rename={
            "predicted_temperature_ridge": "temperature_sat_ridge",
            "estimated_residual": "temperature_sat_kriging_correction",
            "final_temperature": "temperature_sat",
        },
    )
    lattice = _join(
        lattice, LAYERS / "pm25_ridge_kriging_grid.geojson",
        ["predicted_pm25_ridge", "estimated_residual_log", "final_pm25"],
        id_col="grid_id",
        rename={
            "predicted_pm25_ridge": "pm25_sat_ridge",
            "estimated_residual_log": "pm25_sat_kriging_correction_log",
            "final_pm25": "pm25_sat",
        },
    )

    # ── Street-view pipeline — PCA components + ridge + kriging (optional) ────
    sv_kriging = [
        (
            "temperature_sv_kriging_grid.geojson",
            ["sv_pc1", "sv_pc2", "predicted_temperature_ridge", "estimated_residual", "final_temperature"],
            {
                "predicted_temperature_ridge": "temperature_sv_ridge",
                "estimated_residual": "temperature_sv_kriging_correction",
                "final_temperature": "temperature_sv",
            },
        ),
        (
            "pm25_sv_kriging_grid.geojson",
            ["predicted_pm25_ridge", "estimated_residual_log", "final_pm25"],
            {
                "predicted_pm25_ridge": "pm25_sv_ridge",
                "estimated_residual_log": "pm25_sv_kriging_correction_log",
                "final_pm25": "pm25_sv",
            },
        ),
    ]
    for fname, cols, rename in sv_kriging:
        p = SV_DIR / fname
        if p.exists():
            lattice = _join(lattice, p, cols, id_col="grid_id", rename=rename)
            print(f"  Joined {fname}")
        else:
            for new_col in list(rename.values()) + [c for c in cols if c not in rename]:
                lattice[new_col] = np.nan
            print(f"  {fname} not found — set to NaN (run kriging_street_view notebooks)")

    # ── Combined pipeline — joint PCA + ridge + kriging (optional) ───────────
    comb_kriging = [
        (
            "temperature_combined_kriging_grid.geojson",
            ["combined_pc1", "combined_pc2", "predicted_temperature_ridge", "estimated_residual", "final_temperature"],
            {
                "predicted_temperature_ridge": "temperature_combined_ridge",
                "estimated_residual": "temperature_combined_kriging_correction",
                "final_temperature": "temperature_combined",
            },
        ),
        (
            "pm25_combined_kriging_grid.geojson",
            ["predicted_log_pm25_ridge", "estimated_residual_log", "final_pm25"],
            {
                "predicted_log_pm25_ridge": "pm25_combined_ridge_log",
                "estimated_residual_log": "pm25_combined_kriging_correction_log",
                "final_pm25": "pm25_combined",
            },
        ),
    ]
    for fname, cols, rename in comb_kriging:
        p = COMB_DIR / fname
        if p.exists():
            lattice = _join(lattice, p, cols, id_col="grid_id", rename=rename)
            print(f"  Joined {fname}")
        else:
            for new_col in list(rename.values()) + [c for c in cols if c not in rename]:
                lattice[new_col] = np.nan
            print(f"  {fname} not found — set to NaN (run kriging_combined notebooks)")

    # ── Round and save ────────────────────────────────────────────────────────
    num_cols = lattice.select_dtypes(include="number").columns.tolist()
    lattice[num_cols] = lattice[num_cols].round(6)
    lattice = lattice.to_crs("EPSG:4326")
    lattice.to_file(OUT_PATH, driver="GeoJSON")
    print(f"\nSaved → {OUT_PATH}")
    print(f"Columns: {len(lattice.columns)}  ({', '.join(c for c in lattice.columns if c != 'geometry')})")
    return lattice


if __name__ == "__main__":
    build()
