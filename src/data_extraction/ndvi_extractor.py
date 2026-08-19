from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
from pyproj import CRS
from shapely.geometry import box

from .data_extract import BBox, DataExtractor


class NDVIExtractor(DataExtractor):
    """
    Extract NDVI for a bounding box using Sentinel-2 L2A STAC items.
    """

    #This is completely analogous to NDBI but we use distinct bands.
    STAC_API_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
    COLLECTION_ID = "sentinel-2-l2a"

    def __init__(
        self,
        datetime_range: str | None = None,
        max_cloud_cover: float = 20.0,
        max_items: int = 24,
        grid_path: str | Path | None = None,
        resolution: float | None = None,
    ) -> None:
        super().__init__(grid_path=grid_path)
        self.datetime_range = datetime_range or self._default_datetime_range()
        self.max_cloud_cover = max_cloud_cover
        self.max_items = max_items
        self._eps = 1e-9
        self._resolution = resolution

    @property
    def layer_name(self) -> str:
        return "ndvi"

    @property
    def value_columns(self) -> tuple[str, ...]:
        return ("ndvi",)

    def get_data(self, bbox: BBox) -> gpd.GeoDataFrame:
        """
        Fetch Sentinel-2 data, compute median NDVI in the requested bbox,
        and return a pixel-level GeoDataFrame with one `ndvi` value per polygon.
        """

        self.validate_bbox(bbox)
        target_crs = self.get_target_crs()
        if target_crs is None:
            raise ValueError("Grid CRS is missing; cannot request NDVI tiles.")

        target_epsg = self._crs_to_epsg(target_crs)
        bbox_wgs84 = self._bbox_to_crs(bbox, source_crs=target_crs, target_crs="EPSG:4326")

        try:
            import planetary_computer as pc
            import pystac_client
            import stackstac
            from rasterio.enums import Resampling
        except ImportError as exc:
            raise ImportError(
                "NDVI extraction requires `planetary-computer`, `pystac-client`, "
                "`stackstac`, and `rasterio`."
            ) from exc

        catalog = pystac_client.Client.open(self.STAC_API_URL, modifier=pc.sign_inplace)
        search = catalog.search(
            collections=[self.COLLECTION_ID],
            bbox=bbox_wgs84,
            datetime=self.datetime_range,
            query={"eo:cloud_cover": {"lt": self.max_cloud_cover}},
            limit=self.max_items,
            max_items=self.max_items,
        )

        items = list(search.items())
        if not items:
            raise ValueError(
                "No Sentinel-2 items found for bbox "
                f"{bbox_wgs84} and datetime range {self.datetime_range}."
            )

        request_resolution = self._request_resolution()
        data_cube = stackstac.stack(
            items,
            assets=["B04", "B08"],
            epsg=target_epsg,
            bounds=bbox,
            resolution=request_resolution,
            resampling=Resampling.bilinear,
            fill_value=np.nan,
            dtype="float64",
            rescale=False,
            xy_coords="center",
        )

        red = data_cube.sel(band="B04")
        nir = data_cube.sel(band="B08")
        ndvi_stack = (nir - red) / (nir + red + self._eps)
        ndvi = ndvi_stack.median(dim="time", skipna=True).compute()

        return self._array_to_pixel_gdf(ndvi, crs=target_crs)

    def align_to_grid(
        self,
        data: gpd.GeoDataFrame,
        grid: gpd.GeoDataFrame,
    ) -> gpd.GeoDataFrame:
        """
        Aggregate pixel-level NDVI into one area-weighted value per grid cell.
        """

        if grid.empty:
            return gpd.GeoDataFrame(columns=["id", "ndvi", "geometry"], geometry="geometry", crs=grid.crs)

        grid_local = grid.copy()
        if "id" not in grid_local.columns:
            grid_local["id"] = np.arange(len(grid_local))

        data_local = data
        if data_local.crs and grid_local.crs and data_local.crs != grid_local.crs:
            data_local = data_local.to_crs(grid_local.crs)

        intersections = gpd.overlay(
            data_local[["ndvi", "geometry"]],
            grid_local[["id", "geometry"]],
            how="intersection",
        )

        out = grid_local[["id", "geometry"]].copy()
        out["ndvi"] = np.nan
        if intersections.empty:
            return out

        intersections["weight"] = intersections.geometry.area
        weighted_sum = (intersections["ndvi"] * intersections["weight"]).groupby(intersections["id"]).sum()
        weight_sum = intersections["weight"].groupby(intersections["id"]).sum()
        weighted_ndvi = (weighted_sum / weight_sum).astype(float)
        out.loc[out["id"].isin(weighted_ndvi.index), "ndvi"] = out["id"].map(weighted_ndvi)
        return out

    def _request_resolution(self) -> float:
        if self._resolution is not None:
            return self._resolution
        cell_width, cell_height = self.get_target_resolution()
        return max(10.0, min(cell_width, cell_height))

    def _default_datetime_range(self) -> str:
        # NDVI is most useful in the local growing season.
        year = datetime.utcnow().year - 1
        return f"{year}-05-01/{year}-09-30"

    def _bbox_to_crs(self, bbox: BBox, source_crs: str, target_crs: str) -> BBox:
        bbox_gdf = gpd.GeoDataFrame(geometry=[box(*bbox)], crs=source_crs).to_crs(target_crs)
        min_x, min_y, max_x, max_y = bbox_gdf.total_bounds
        return float(min_x), float(min_y), float(max_x), float(max_y)

    def _crs_to_epsg(self, crs: str) -> int:
        epsg = CRS.from_user_input(crs).to_epsg()
        if epsg is None:
            raise ValueError(f"Could not resolve EPSG code from CRS '{crs}'.")
        return int(epsg)

    def _array_to_pixel_gdf(self, ndvi: Any, crs: str) -> gpd.GeoDataFrame:
        values = np.asarray(ndvi.values, dtype=float)
        x_coords = np.asarray(ndvi["x"].values, dtype=float)
        y_coords = np.asarray(ndvi["y"].values, dtype=float)

        if values.size == 0 or x_coords.size == 0 or y_coords.size == 0:
            return gpd.GeoDataFrame(columns=["ndvi", "geometry"], geometry="geometry", crs=crs)

        x_res = abs(float(x_coords[1] - x_coords[0])) if x_coords.size > 1 else self.get_target_resolution()[0]
        y_res = abs(float(y_coords[1] - y_coords[0])) if y_coords.size > 1 else self.get_target_resolution()[1]

        records: list[dict[str, Any]] = []
        half_x = x_res / 2.0
        half_y = y_res / 2.0

        for row, y in enumerate(y_coords):
            for col, x in enumerate(x_coords):
                value = values[row, col]
                if np.isnan(value):
                    continue
                records.append(
                    {
                        "ndvi": float(value),
                        "geometry": box(x - half_x, y - half_y, x + half_x, y + half_y),
                    }
                )

        if not records:
            return gpd.GeoDataFrame(columns=["ndvi", "geometry"], geometry="geometry", crs=crs)
        return gpd.GeoDataFrame(records, geometry="geometry", crs=crs)
