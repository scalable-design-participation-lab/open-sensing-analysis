from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
from pyproj import CRS
from shapely.geometry import box

from data_extract import BBox, DataExtractor


class TIGERRoadDensityExtractor(DataExtractor):
    """
    Extract road density from Census TIGER/Line roads.

    By default this pulls one county roads layer from TIGER. You can also pass
    `local_roads_path` to a local TIGER roads file (`.shp`, `.gpkg`, `.geojson`,
    or `.zip`).
    """

    TIGER_BASE_URL = "https://www2.census.gov/geo/tiger"

    def __init__(
        self,
        year: int = 2024,
        state_fips: str = "25",
        county_fips: str = "025",
        local_roads_path: str | Path | None = None,
        major_mtfcc: tuple[str, ...] = ("S1100", "S1200"),
        grid_path: str | Path | None = None,
    ) -> None:
        super().__init__(grid_path=grid_path)
        self.year = int(year)
        self.state_fips = str(state_fips).zfill(2)
        self.county_fips = str(county_fips).zfill(3)
        self.local_roads_path = Path(local_roads_path).expanduser().resolve() if local_roads_path else None
        self.major_mtfcc = tuple(m.strip().upper() for m in major_mtfcc)

    @property
    def layer_name(self) -> str:
        return "road_density"

    @property
    def value_columns(self) -> tuple[str, ...]:
        return ("road_density_km_km2", "major_road_density_km_km2")

    def get_data(self, bbox: BBox) -> gpd.GeoDataFrame:
        """
        Fetch TIGER roads for the configured county and clip to bbox.
        """

        self.validate_bbox(bbox)
        target_crs = self.get_target_crs()
        if target_crs is None:
            raise ValueError("Grid CRS is missing; cannot extract TIGER roads.")

        bbox_wgs84 = self._bbox_to_wgs84(bbox=bbox, source_crs=target_crs)
        roads = self._read_roads(bbox_wgs84=bbox_wgs84)
        if roads.empty:
            return gpd.GeoDataFrame(columns=["MTFCC", "geometry"], geometry="geometry", crs=target_crs)

        if roads.crs is None:
            roads = roads.set_crs("EPSG:4326")
        if roads.crs.to_string() != target_crs:
            roads = roads.to_crs(target_crs)

        if "MTFCC" not in roads.columns:
            roads["MTFCC"] = None
        roads = roads[["MTFCC", "geometry"]].copy()
        roads = roads[roads.geometry.notnull()].copy()
        roads = roads[roads.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()
        if roads.empty:
            return gpd.GeoDataFrame(columns=["MTFCC", "geometry"], geometry="geometry", crs=target_crs)

        clipped = self.clip_to_bbox(roads, bbox=bbox, crs=target_crs)
        if clipped.empty:
            return gpd.GeoDataFrame(columns=["MTFCC", "geometry"], geometry="geometry", crs=target_crs)
        return clipped

    def align_to_grid(
        self,
        data: gpd.GeoDataFrame,
        grid: gpd.GeoDataFrame,
    ) -> gpd.GeoDataFrame:
        """
        Aggregate line lengths into road density metrics per grid cell.
        """

        out = grid.copy()
        if "id" not in out.columns:
            out["id"] = np.arange(len(out))
        out = out[["id", "geometry"]].copy()
        out["road_density_km_km2"] = np.nan
        out["major_road_density_km_km2"] = np.nan
        if out.empty or data.empty:
            return out

        data_local = data
        if data_local.crs and out.crs and data_local.crs != out.crs:
            data_local = data_local.to_crs(out.crs)

        intersections = gpd.overlay(
            data_local[["MTFCC", "geometry"]],
            out[["id", "geometry"]],
            how="intersection",
            keep_geom_type=False,
        )
        intersections = intersections[
            intersections.geometry.notnull()
            & intersections.geometry.geom_type.isin(["LineString", "MultiLineString"])
        ].copy()
        if intersections.empty:
            return out

        metric_crs = self._metric_crs(out)
        out_metric = out.to_crs(metric_crs) if out.crs != metric_crs else out
        intersections_metric = (
            intersections.to_crs(metric_crs) if intersections.crs != metric_crs else intersections
        )

        intersections_metric["length_m"] = intersections_metric.geometry.length.astype(float)
        total_length_m = intersections_metric.groupby("id")["length_m"].sum()

        major_mask = intersections_metric["MTFCC"].fillna("").str.upper().isin(self.major_mtfcc)
        major_length_m = intersections_metric.loc[major_mask].groupby("id")["length_m"].sum()

        grid_area_m2 = out_metric.set_index("id").geometry.area.replace(0.0, np.nan)
        total_density = (total_length_m * 1000.0) / grid_area_m2
        major_density = (major_length_m * 1000.0) / grid_area_m2

        out.loc[out["id"].isin(total_density.index), "road_density_km_km2"] = out["id"].map(total_density)
        out.loc[out["id"].isin(major_density.index), "major_road_density_km_km2"] = out["id"].map(major_density)
        return out

    def _bbox_to_wgs84(self, bbox: BBox, source_crs: str) -> BBox:
        bbox_gdf = gpd.GeoDataFrame(geometry=[box(*bbox)], crs=source_crs).to_crs("EPSG:4326")
        min_x, min_y, max_x, max_y = bbox_gdf.total_bounds
        return float(min_x), float(min_y), float(max_x), float(max_y)

    def _build_tiger_url(self) -> str:
        filename = f"tl_{self.year}_{self.state_fips}{self.county_fips}_roads.zip"
        return f"{self.TIGER_BASE_URL}/TIGER{self.year}/ROADS/{filename}"

    def _read_roads(self, bbox_wgs84: BBox) -> gpd.GeoDataFrame:
        if self.local_roads_path is not None:
            if not self.local_roads_path.exists():
                raise ValueError(f"local_roads_path not found: {self.local_roads_path}")
            try:
                return gpd.read_file(self.local_roads_path, bbox=bbox_wgs84)
            except Exception:
                return gpd.read_file(self.local_roads_path)

        tiger_url = self._build_tiger_url()
        candidates = [
            tiger_url,
            f"/vsizip//vsicurl/{tiger_url}",
        ]
        last_error: Exception | None = None
        for path in candidates:
            try:
                return gpd.read_file(path, bbox=bbox_wgs84)
            except Exception as exc:
                last_error = exc
                continue

        raise ValueError(
            "Could not read TIGER roads layer. "
            "Set `local_roads_path` to a local TIGER roads file if remote read fails."
        ) from last_error

    def _metric_crs(self, gdf: gpd.GeoDataFrame) -> str:
        if gdf.crs is None:
            return "EPSG:3857"
        crs_obj = CRS.from_user_input(gdf.crs)
        return "EPSG:3857" if crs_obj.is_geographic else gdf.crs.to_string()
