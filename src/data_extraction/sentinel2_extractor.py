from __future__ import annotations

from pathlib import Path

import ee
import requests

from .data_extract import BBox
from .raster_extractor import RasterExtractor


class Sentinel2NDVIExtractor(RasterExtractor):

    def __init__(
        self,
        start_date: str,
        end_date: str,
        grid_path: str | Path | None = None,
        output_dir: str | Path = "data/raw/sentinel2",
        max_cloud_cover: float = 20.0,
        scale: int = 30,
    ) -> None:
        super().__init__(grid_path=grid_path)
        self.start_date = start_date
        self.end_date = end_date
        self.max_cloud_cover = max_cloud_cover
        self.scale = scale
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def layer_name(self) -> str:
        return "ndvi"

    @property
    def value_columns(self) -> tuple[str, ...]:
        return ("ndvi_mean", "ndvi_median", "ndvi_min", "ndvi_max", "ndvi_std")

    def get_data(self, bbox: BBox) -> Path:
        self.validate_bbox(bbox)
        min_x, min_y, max_x, max_y = bbox
        region = ee.Geometry.Rectangle([min_x, min_y, max_x, max_y])

        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(region)
            .filterDate(self.start_date, self.end_date)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", self.max_cloud_cover))
            .map(self._mask_clouds)
            .map(lambda img: img.normalizedDifference(["B8", "B4"]).rename("ndvi"))
        )

        image = collection.median().clip(region)
        output_path = self.output_dir / f"ndvi_{self.start_date}_{self.end_date}.tif"

        url = image.getDownloadURL({
            "scale": self.scale,
            "region": region,
            "format": "GEO_TIFF",
            "crs": "EPSG:4326",
        })

        response = requests.get(url, timeout=300)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        return output_path

    @staticmethod
    def _mask_clouds(image: ee.Image) -> ee.Image:
        scl = image.select("SCL")
        mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
        return image.updateMask(mask)


class Sentinel2MNDWIExtractor(RasterExtractor):

    def __init__(
        self,
        start_date: str,
        end_date: str,
        grid_path: str | Path | None = None,
        output_dir: str | Path = "data/raw/sentinel2",
        max_cloud_cover: float = 20.0,
        scale: int = 30,
    ) -> None:
        super().__init__(grid_path=grid_path)
        self.start_date = start_date
        self.end_date = end_date
        self.max_cloud_cover = max_cloud_cover
        self.scale = scale
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def layer_name(self) -> str:
        return "mndwi"

    @property
    def value_columns(self) -> tuple[str, ...]:
        return ("mndwi_mean", "mndwi_median", "mndwi_min", "mndwi_max", "mndwi_std")

    def get_data(self, bbox: BBox) -> Path:
        self.validate_bbox(bbox)
        min_x, min_y, max_x, max_y = bbox
        region = ee.Geometry.Rectangle([min_x, min_y, max_x, max_y])

        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(region)
            .filterDate(self.start_date, self.end_date)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", self.max_cloud_cover))
            .map(Sentinel2NDVIExtractor._mask_clouds)
            .map(lambda img: img.normalizedDifference(["B3", "B11"]).rename("mndwi"))
        )

        image = collection.median().clip(region)
        output_path = self.output_dir / f"mndwi_{self.start_date}_{self.end_date}.tif"

        url = image.getDownloadURL({
            "scale": self.scale,
            "region": region,
            "format": "GEO_TIFF",
            "crs": "EPSG:4326",
        })

        response = requests.get(url, timeout=300)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        return output_path

    @staticmethod
    def _mask_clouds(image: ee.Image) -> ee.Image:
        scl = image.select("SCL")
        mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
        return image.updateMask(mask)


class Sentinel2NDBIExtractor(RasterExtractor):

    def __init__(
        self,
        start_date: str,
        end_date: str,
        grid_path: str | Path | None = None,
        output_dir: str | Path = "data/raw/sentinel2",
        max_cloud_cover: float = 20.0,
        scale: int = 30,
    ) -> None:
        super().__init__(grid_path=grid_path)
        self.start_date = start_date
        self.end_date = end_date
        self.max_cloud_cover = max_cloud_cover
        self.scale = scale
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def layer_name(self) -> str:
        return "ndbi"

    @property
    def value_columns(self) -> tuple[str, ...]:
        return ("ndbi_mean", "ndbi_median", "ndbi_min", "ndbi_max", "ndbi_std")

    def get_data(self, bbox: BBox) -> Path:
        self.validate_bbox(bbox)
        min_x, min_y, max_x, max_y = bbox
        region = ee.Geometry.Rectangle([min_x, min_y, max_x, max_y])

        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(region)
            .filterDate(self.start_date, self.end_date)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", self.max_cloud_cover))
            .map(Sentinel2NDVIExtractor._mask_clouds)
            .map(lambda img: img.normalizedDifference(["B11", "B8"]).rename("ndbi"))
        )

        image = collection.median().clip(region)
        output_path = self.output_dir / f"ndbi_{self.start_date}_{self.end_date}.tif"

        url = image.getDownloadURL({
            "scale": self.scale,
            "region": region,
            "format": "GEO_TIFF",
            "crs": "EPSG:4326",
        })

        response = requests.get(url, timeout=300)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        return output_path
