from __future__ import annotations

from pathlib import Path
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd

from data_extract import BBox, DataExtractor


class CensusPopulationDensityExtractor(DataExtractor):
    """
    Extract population and population density from local Census polygons.

    Typical inputs are tract/block-group boundaries with a population field
    (e.g., ACS `B01003_001E` or Decennial `P1_001N`).
    """
    AREA_CRS = "EPSG:5070"

    def __init__(
        self,
        local_data_path: str | Path,
        population_column: str | None = None,
        grid_path: str | Path | None = None,
    ) -> None:
        super().__init__(grid_path=grid_path)
        self.local_data_path = Path(local_data_path).expanduser().resolve()
        self.population_column = population_column

    @property
    def layer_name(self) -> str:
        return "population_density"

    @property
    def value_columns(self) -> tuple[str, ...]:
        return ("population", "population_density_km2")

    def get_data(self, bbox: BBox) -> gpd.GeoDataFrame:
        """
        Read local Census polygons and clip to bbox.
        """

        self.validate_bbox(bbox)
        target_crs = self.get_target_crs()
        if target_crs is None:
            raise ValueError("Grid CRS is missing; cannot extract Census population.")
        if not self.local_data_path.exists():
            raise ValueError(f"local_data_path not found: {self.local_data_path}")

        census = self._read_local_census()
        if census.empty:
            return gpd.GeoDataFrame(columns=["population", "geometry"], geometry="geometry", crs=target_crs)

        population_col = self._resolve_population_column(census)
        census["population"] = pd.to_numeric(census[population_col], errors="coerce")
        census = census[census["population"].notna() & (census["population"] >= 0)].copy()
        census = census[census.geometry.notnull()].copy()
        census = census[census.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
        if census.empty:
            return gpd.GeoDataFrame(columns=["population", "geometry"], geometry="geometry", crs=target_crs)

        if census.crs is None:
            raise ValueError("Census population file has no CRS metadata.")
        if census.crs.to_string() != target_crs:
            census = census.to_crs(target_crs)

        clipped = self.clip_to_bbox(census[["population", "geometry"]], bbox=bbox, crs=target_crs)
        if clipped.empty:
            return gpd.GeoDataFrame(columns=["population", "geometry"], geometry="geometry", crs=target_crs)
        return clipped

    def align_to_grid(
        self,
        data: gpd.GeoDataFrame,
        grid: gpd.GeoDataFrame,
    ) -> gpd.GeoDataFrame:
        """
        Allocate Census polygon population to grid cells by area overlap.
        """

        out = grid.copy()
        if "id" not in out.columns:
            out["id"] = np.arange(len(out))
        out = out[["id", "geometry"]].copy()
        out["population"] = np.nan
        out["population_density_km2"] = np.nan
        if out.empty or data.empty:
            return out

        data_local = data.copy()
        if data_local.crs and out.crs and data_local.crs != out.crs:
            data_local = data_local.to_crs(out.crs)

        source_polys = data_local.reset_index(drop=False).rename(columns={"index": "src_id"})
        intersections = gpd.overlay(
            source_polys[["src_id", "population", "geometry"]],
            out[["id", "geometry"]],
            how="intersection",
        )
        if intersections.empty:
            return out

        metric_crs = self.AREA_CRS
        src_metric = source_polys.to_crs(metric_crs) if source_polys.crs != metric_crs else source_polys
        inter_metric = intersections.to_crs(metric_crs) if intersections.crs != metric_crs else intersections
        out_metric = out.to_crs(metric_crs) if out.crs != metric_crs else out

        src_area = src_metric.set_index("src_id").geometry.area.replace(0.0, np.nan)
        inter_metric["inter_area"] = inter_metric.geometry.area
        inter_metric["allocated_pop"] = (
            inter_metric["population"] * inter_metric["inter_area"] / inter_metric["src_id"].map(src_area)
        )

        pop_sum = inter_metric.groupby("id")["allocated_pop"].sum(min_count=1)
        grid_area_km2 = out_metric.set_index("id").geometry.area / 1_000_000.0
        density = pop_sum / grid_area_km2.replace(0.0, np.nan)

        out.loc[out["id"].isin(pop_sum.index), "population"] = out["id"].map(pop_sum)
        out.loc[out["id"].isin(density.index), "population_density_km2"] = out["id"].map(density)
        return out

    def _read_local_census(self) -> gpd.GeoDataFrame:
        suffix = self.local_data_path.suffix.lower()
        if suffix != ".zip":
            return gpd.read_file(self.local_data_path)

        with zipfile.ZipFile(self.local_data_path, "r") as archive:
            shp_names = [
                name
                for name in archive.namelist()
                if name.lower().endswith(".shp") and not name.startswith("__MACOSX/")
            ]
            if not shp_names:
                raise ValueError(f"No .shp file found in zip: {self.local_data_path}")
            selected = sorted(shp_names)[0]

        vsizip_path = f"/vsizip/{self.local_data_path}/{selected}"
        return gpd.read_file(vsizip_path)

    def _resolve_population_column(self, gdf: gpd.GeoDataFrame) -> str:
        if self.population_column is not None:
            if self.population_column not in gdf.columns:
                raise ValueError(f"Configured population_column not found: {self.population_column}")
            return self.population_column

        preferred = [
            "population",
            "POPULATION",
            "total_pop",
            "TOTAL_POP",
            "tot_pop",
            "TOT_POP",
            "B01003_001E",
            "P1_001N",
        ]
        for col in preferred:
            if col in gdf.columns:
                return col

        for col in gdf.columns:
            if "pop" in str(col).lower():
                return col

        raise ValueError(
            "Could not infer population column from Census file. "
            "Set `population_column` explicitly."
        )
