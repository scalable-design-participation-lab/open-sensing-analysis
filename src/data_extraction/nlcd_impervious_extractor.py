from __future__ import annotations

from pathlib import Path
from typing import Any
import zipfile

import geopandas as gpd
import numpy as np
from pyproj import Transformer
from shapely.geometry import box

from .data_extract import BBox, DataExtractor


class NLCDImperviousExtractor(DataExtractor):
    """
    Extract Annual NLCD Fractional Impervious Surface for a bounding box.
    """

    AWS_BASE_URL = "https://usgs-landcover.s3.us-west-2.amazonaws.com"
    PRODUCT_CODE = "FctImp"

    def __init__(
        self,
        year: int = 2024,
        region: str = "CU",
        collection: int = 1,
        version: int = 1,
        local_raster_path: str | Path | None = None,
        grid_path: str | Path | None = None,
    ) -> None:
        super().__init__(grid_path=grid_path)
        self.year = year
        self.region = region.upper()
        self.collection = collection
        self.version = version
        self.local_raster_path = Path(local_raster_path).expanduser().resolve() if local_raster_path else None
        self._default_nodata = 250

    @property
    def layer_name(self) -> str:
        return "nlcd_impervious"

    @property
    def value_columns(self) -> tuple[str, ...]:
        return ("impervious",)

    def get_data(self, bbox: BBox) -> gpd.GeoDataFrame:
        """
        Fetch NLCD fractional impervious pixels for the requested bbox.
        """

        self.validate_bbox(bbox)
        target_crs = self.get_target_crs()
        if target_crs is None:
            raise ValueError("Grid CRS is missing; cannot extract NLCD impervious.")

        try:
            import rasterio
            from rasterio.errors import RasterioIOError
            from rasterio.windows import from_bounds
        except ImportError as exc:
            raise ImportError("NLCD impervious extraction requires `rasterio`.") from exc

        if self.local_raster_path is not None:
            candidate_paths = self._build_local_candidate_paths()
        else:
            candidate_paths = self._build_candidate_paths()
        last_error: Exception | None = None
        pixel_gdf = gpd.GeoDataFrame(columns=["impervious", "geometry"], geometry="geometry", crs=target_crs)

        try:
            for path in candidate_paths:
                env_kwargs = self._env_kwargs_for_path(path)
                try:
                    with rasterio.Env(**env_kwargs):
                        with rasterio.open(path) as src:
                            src_crs = src.crs.to_string() if src.crs else None
                            if src_crs is None:
                                raise ValueError("NLCD raster has no CRS metadata.")

                            bbox_in_src = self._transform_bbox(bbox, source_crs=target_crs, target_crs=src_crs)
                            window = from_bounds(*bbox_in_src, transform=src.transform)
                            window = window.round_offsets().round_lengths()

                            band = src.read(1, window=window, boundless=True, masked=True)
                            if band.size == 0:
                                return gpd.GeoDataFrame(
                                    columns=["impervious", "geometry"],
                                    geometry="geometry",
                                    crs=target_crs,
                                )

                            nodata = src.nodata if src.nodata is not None else self._default_nodata
                            data = np.ma.array(
                                band,
                                mask=np.ma.getmaskarray(band) | (band == nodata),
                            )
                            pixel_gdf = self._array_to_pixel_gdf(
                                data=data,
                                transform=src.window_transform(window),
                                crs=src_crs,
                            )
                            break
                except (RasterioIOError, ValueError) as exc:
                    last_error = exc
                    continue
        except RasterioIOError as exc:
            last_error = exc

        if last_error is not None and pixel_gdf.empty:
            raise ValueError(
                "Could not read NLCD impervious raster from candidate paths. "
                "If using AWS paths, note Annual NLCD on S3 is requester-pays. "
                "You can also pass `local_raster_path` to a local `.tif` or `.zip`."
            ) from last_error

        if pixel_gdf.empty:
            return gpd.GeoDataFrame(columns=["impervious", "geometry"], geometry="geometry", crs=target_crs)

        if pixel_gdf.crs and target_crs and pixel_gdf.crs != target_crs:
            pixel_gdf = pixel_gdf.to_crs(target_crs)
        return pixel_gdf

    def align_to_grid(
        self,
        data: gpd.GeoDataFrame,
        grid: gpd.GeoDataFrame,
    ) -> gpd.GeoDataFrame:
        """
        Aggregate NLCD impervious values into one area-weighted value per grid cell.
        """

        if grid.empty:
            return gpd.GeoDataFrame(columns=["id", "impervious", "geometry"], geometry="geometry", crs=grid.crs)

        grid_local = grid.copy()
        if "id" not in grid_local.columns:
            grid_local["id"] = np.arange(len(grid_local))

        data_local = data
        if data_local.crs and grid_local.crs and data_local.crs != grid_local.crs:
            data_local = data_local.to_crs(grid_local.crs)

        intersections = gpd.overlay(
            data_local[["impervious", "geometry"]],
            grid_local[["id", "geometry"]],
            how="intersection",
        )

        out = grid_local[["id", "geometry"]].copy()
        out["impervious"] = np.nan
        if intersections.empty:
            return out

        intersections["weight"] = intersections.geometry.area
        weighted_sum = (intersections["impervious"] * intersections["weight"]).groupby(intersections["id"]).sum()
        weight_sum = intersections["weight"].groupby(intersections["id"]).sum()
        weighted_vals = (weighted_sum / weight_sum).astype(float)
        out.loc[out["id"].isin(weighted_vals.index), "impervious"] = out["id"].map(weighted_vals)
        return out

    def _build_candidate_paths(self) -> list[str]:
        region_path = self.region.lower()
        versions = [self.version, 1, 0]
        ordered_versions: list[int] = []
        for v in versions:
            if v not in ordered_versions:
                ordered_versions.append(v)

        paths: list[str] = []
        for version in ordered_versions:
            filename = (
                f"Annual_NLCD_{self.PRODUCT_CODE}_{self.year}_{self.region}_"
                f"C{self.collection}V{version}.tif"
            )
            key_path = f"annual-nlcd/c{self.collection}/v{version}/{region_path}/mosaic/{filename}"
            paths.append(f"{self.AWS_BASE_URL}/{key_path}")
            paths.append(f"/vsis3/usgs-landcover/{key_path}")
            paths.append(f"s3://usgs-landcover/{key_path}")
        return paths

    def _build_local_candidate_paths(self) -> list[str]:
        if self.local_raster_path is None:
            return []

        local_path = self.local_raster_path
        if not local_path.exists():
            raise ValueError(f"local_raster_path not found: {local_path}")

        suffix = local_path.suffix.lower()
        if suffix in {".tif", ".tiff"}:
            return [str(local_path)]

        if suffix == ".zip":
            with zipfile.ZipFile(local_path, "r") as archive:
                preferred = [
                    name
                    for name in archive.namelist()
                    if name.lower().endswith(".tif")
                    and f"_{self.PRODUCT_CODE}_{self.year}_{self.region}_".lower() in Path(name).name.lower()
                ]
                fallback = [name for name in archive.namelist() if name.lower().endswith(".tif")]
                tif_names = preferred if preferred else fallback
                if not tif_names:
                    raise ValueError(f"No .tif raster found in zip: {local_path}")
                selected = sorted(tif_names)[0]
            return [f"/vsizip/{local_path}/{selected}"]

        raise ValueError("local_raster_path must point to a .tif/.tiff or .zip file.")

    def _env_kwargs_for_path(self, path: str) -> dict[str, str]:
        if path.startswith("/vsis3/") or path.startswith("s3://"):
            return {
                "AWS_NO_SIGN_REQUEST": "YES",
                "AWS_REQUEST_PAYER": "requester",
                "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
            }
        return {}

    def _transform_bbox(self, bbox: BBox, source_crs: str, target_crs: str) -> BBox:
        transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
        min_x, min_y, max_x, max_y = bbox
        xs, ys = transformer.transform(
            [min_x, max_x, max_x, min_x],
            [min_y, min_y, max_y, max_y],
        )
        return float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))

    def _array_to_pixel_gdf(self, data: Any, transform: Any, crs: str) -> gpd.GeoDataFrame:
        if data.size == 0:
            return gpd.GeoDataFrame(columns=["impervious", "geometry"], geometry="geometry", crs=crs)

        mask = np.ma.getmaskarray(data)
        records: list[dict[str, Any]] = []

        rows, cols = data.shape
        for row in range(rows):
            for col in range(cols):
                if mask[row, col]:
                    continue

                value = float(data[row, col])
                value = max(0.0, min(100.0, value))

                x1, y1 = transform * (col, row)
                x2, y2 = transform * (col + 1, row + 1)
                min_x, max_x = (x1, x2) if x1 <= x2 else (x2, x1)
                min_y, max_y = (y1, y2) if y1 <= y2 else (y2, y1)

                records.append(
                    {
                        "impervious": value,
                        "geometry": box(min_x, min_y, max_x, max_y),
                    }
                )

        if not records:
            return gpd.GeoDataFrame(columns=["impervious", "geometry"], geometry="geometry", crs=crs)
        return gpd.GeoDataFrame(records, geometry="geometry", crs=crs)
