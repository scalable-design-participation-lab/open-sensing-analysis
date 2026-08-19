from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
from pyproj import CRS
from shapely.geometry import box

from .data_extract import BBox, DataExtractor


class NDBIExtractor(DataExtractor):
    """
    Extract NDBI for a bounding box using Landsat Collection 2 Level-2 STAC items.
    """

    STAC_API_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
    COLLECTION_ID = "landsat-c2-l2"

    def __init__(
        self,
        datetime_range: str | None = None,
        max_cloud_cover: float = 20.0,
        max_items: int = 30,
        grid_path: str | Path | None = None,
        resolution: float | None = None,
    ) -> None:
        super().__init__(grid_path=grid_path)
        self.datetime_range = datetime_range or self._default_datetime_range()
        self.max_cloud_cover = max_cloud_cover
        self.max_items = max_items
        self._eps = 1e-9
        self._resolution = resolution
        # USGS Landsat Collection 2 Level-2 SR scale and offset.
        self._sr_scale = 0.0000275
        self._sr_offset = -0.2

    @property
    def layer_name(self) -> str:
        return "ndbi"

    @property
    def value_columns(self) -> tuple[str, ...]:
        return ("ndbi",)

    def get_data(self, bbox: BBox) -> gpd.GeoDataFrame:
        """
        Fetch Landsat data, compute median NDBI in the requested bbox,
        and return a pixel-level GeoDataFrame with one `ndbi` value per polygon.
        """
        #Validate the bbox
        self.validate_bbox(bbox)
        target_crs = self.get_target_crs()
        if target_crs is None:
            raise ValueError("Grid CRS is missing; cannot request Landsat tiles.")

        #Gets the EPSG code. 
        target_epsg = self._crs_to_epsg(target_crs)
        #Gets bbox in lon lat.
        bbox_wgs84 = self._bbox_to_crs(bbox, source_crs=target_crs, target_crs="EPSG:4326")

        #Tries to import the libraries we need.
        try:
            import planetary_computer as pc
            import pystac_client
            import stackstac
            from rasterio.enums import Resampling
        except ImportError as exc:
            raise ImportError(
                "NDBI extraction requires `planetary-computer`, `pystac-client`, "
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
                "No Landsat items found for bbox "
                f"{bbox_wgs84} and datetime range {self.datetime_range}."
            )
        #Get the band names.
        swir_asset, nir_asset = self._resolve_assets(items)

        #The resolution that will be required.
        request_resolution = self._request_resolution()

        
        #stackstac basically is able to take the original items and 
        #stack them in a spatial grid. In this case we are interested purely
        #in the two bands that are needed to calculate NDBI, which are: nir and swir
        data_cube = stackstac.stack(
            items,
            assets=[nir_asset, swir_asset],
            epsg=target_epsg,
            bounds=bbox,
            resolution=request_resolution,
            resampling=Resampling.bilinear,
            fill_value=np.nan,
            dtype="float64",
            rescale=False,
            xy_coords="center",
        )

        nir_raw = data_cube.sel(band=nir_asset)
        swir_raw = data_cube.sel(band=swir_asset)
        nir = (nir_raw * self._sr_scale) + self._sr_offset
        swir = (swir_raw * self._sr_scale) + self._sr_offset

        ndbi_stack = (swir - nir) / (swir + nir + self._eps)
        #Obtain the data as array
        ndbi = ndbi_stack.median(dim="time", skipna=True).compute()
        
        return self._array_to_pixel_gdf(ndbi, crs=target_crs)

    def align_to_grid(
        self,
        data: gpd.GeoDataFrame,
        grid: gpd.GeoDataFrame,
    ) -> gpd.GeoDataFrame:
        """
        Aggregate pixel-level NDBI into one area-weighted value per grid cell.
        """

        if grid.empty:
            return gpd.GeoDataFrame(columns=["id", "ndbi", "geometry"], geometry="geometry", crs=grid.crs)

        grid_local = grid.copy()
        if "id" not in grid_local.columns:
            grid_local["id"] = np.arange(len(grid_local))

        data_local = data
        if data_local.crs and grid_local.crs and data_local.crs != grid_local.crs:
            data_local = data_local.to_crs(grid_local.crs)

        intersections = gpd.overlay(
            data_local[["ndbi", "geometry"]],
            grid_local[["id", "geometry"]],
            how="intersection",
        )

        out = grid_local[["id", "geometry"]].copy()
        out["ndbi"] = np.nan
        if intersections.empty:
            return out

        intersections["weight"] = intersections.geometry.area
        weighted_sum = (intersections["ndbi"] * intersections["weight"]).groupby(intersections["id"]).sum()
        weight_sum = intersections["weight"].groupby(intersections["id"]).sum()
        weighted_ndbi = (weighted_sum / weight_sum).astype(float)
        out.loc[out["id"].isin(weighted_ndbi.index), "ndbi"] = out["id"].map(weighted_ndbi)
        return out

    def _resolve_assets(self, items: list[Any]) -> tuple[str, str]:
        """
        Resolve SWIR and NIR asset keys from the first returned item.
        """

        asset_keys = set(items[0].assets.keys())
        #Possible band names.
        candidates = [
            ("swir16", "nir08"),
            ("SR_B6", "SR_B5"),
            ("SR_B5", "SR_B4"),
        ]
        
        for swir_asset, nir_asset in candidates:
            if swir_asset in asset_keys and nir_asset in asset_keys:
                return swir_asset, nir_asset

        raise ValueError(
            "Could not resolve NIR/SWIR assets for Landsat item. "
            f"Available assets include: {sorted(asset_keys)}"
        )

    def _request_resolution(self) -> float:
        if self._resolution is not None:
            return self._resolution
        cell_width, cell_height = self.get_target_resolution()
        return max(30.0, min(cell_width, cell_height))

    def _default_datetime_range(self) -> str:
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

    def _array_to_pixel_gdf(self, ndbi: Any, crs: str) -> gpd.GeoDataFrame:
        values = np.asarray(ndbi.values, dtype=float)
        x_coords = np.asarray(ndbi["x"].values, dtype=float)
        y_coords = np.asarray(ndbi["y"].values, dtype=float)

        if values.size == 0 or x_coords.size == 0 or y_coords.size == 0:
            return gpd.GeoDataFrame(columns=["ndbi", "geometry"], geometry="geometry", crs=crs)

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
                        "ndbi": float(value),
                        "geometry": box(x - half_x, y - half_y, x + half_x, y + half_y),
                    }
                )

        if not records:
            return gpd.GeoDataFrame(columns=["ndbi", "geometry"], geometry="geometry", crs=crs)
        return gpd.GeoDataFrame(records, geometry="geometry", crs=crs)
