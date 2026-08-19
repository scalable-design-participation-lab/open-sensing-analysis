from __future__ import annotations

from pathlib import Path

import ee
import requests

from .data_extract import BBox
from .raster_extractor import RasterExtractor


class MODISAlbedoExtractor(RasterExtractor):
    def __init__(
        self,
        start_date: str,
        end_date: str,
        grid_path: str | Path | None = None,
        output_dir: str | Path = "data/raw/modis_albedo",
        band: str = "Albedo_WSA_shortwave",
        composite_method: str = "median",
        scale: int = 500,
    ) -> None:
        super().__init__(grid_path=grid_path)
        self.start_date = start_date
        self.end_date = end_date
        self.output_dir = Path(output_dir)
        self.band = band
        self.composite_method = composite_method
        self.scale = scale
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def layer_name(self) -> str:
        return "albedo"

    @property
    def value_columns(self) -> tuple[str, ...]:
        return ("albedo_mean", "albedo_median", "albedo_min", "albedo_max", "albedo_std")

    def get_data(self, bbox: BBox) -> Path:
        self.validate_bbox(bbox)
        min_x, min_y, max_x, max_y = bbox
        region = ee.Geometry.Rectangle([min_x, min_y, max_x, max_y])

        collection = (
            ee.ImageCollection("MODIS/061/MCD43A3")
            .filterBounds(region)
            .filterDate(self.start_date, self.end_date)
            .map(lambda img: self._add_albedo(img, self.band))
        )

        if self.composite_method == "median":
            image = collection.select("albedo").median()
        elif self.composite_method == "mean":
            image = collection.select("albedo").mean()
        elif self.composite_method == "max":
            image = collection.select("albedo").max()
        elif self.composite_method == "min":
            image = collection.select("albedo").min()
        else:
            raise ValueError("Could not compose")

        image = image.clip(region)
        output_path = (
            self.output_dir
            / f"modis_albedo_{self.start_date}_{self.end_date}_{self.composite_method}.tif"
        )

        url = image.getDownloadURL(
            {
                "scale": self.scale,
                "region": region,
                "format": "GEO_TIFF",
                "crs": "EPSG:4326",
            }
        )

        response = requests.get(url, timeout=300)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        return output_path

    @staticmethod
    def _add_albedo(image: ee.Image, band: str) -> ee.Image:
        albedo = image.select(band).updateMask(image.select(band).lt(32767))
        return image.addBands(albedo.multiply(0.001).rename("albedo"))
