from __future__ import annotations

from pathlib import Path

import ee
import requests

from .data_extract import BBox
from .raster_extractor import RasterExtractor


class VIIRSNighttimeLightsExtractor(RasterExtractor):
    def __init__(
        self,
        start_date: str,
        end_date: str,
        grid_path: str | Path | None = None,
        output_dir: str | Path = "data/raw/viirs",
        composite_method: str = "median",
        min_cloud_free_coverage: int = 0,
        scale: float = 463.83,
    ) -> None:
        super().__init__(grid_path=grid_path)
        self.start_date = start_date
        self.end_date = end_date
        self.output_dir = Path(output_dir)
        self.composite_method = composite_method
        self.min_cloud_free_coverage = min_cloud_free_coverage
        self.scale = scale
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def layer_name(self) -> str:
        return "viirs_nightlights"

    @property
    def value_columns(self) -> tuple[str, ...]:
        return (
            "viirs_nightlights_mean",
            "viirs_nightlights_median",
            "viirs_nightlights_min",
            "viirs_nightlights_max",
            "viirs_nightlights_std",
        )

    def get_data(self, bbox: BBox) -> Path:
        self.validate_bbox(bbox)
        min_x, min_y, max_x, max_y = bbox
        region = ee.Geometry.Rectangle([min_x, min_y, max_x, max_y])

        collection = (
            ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
            .filterBounds(region)
            .filterDate(self.start_date, self.end_date)
            .map(lambda img: self._add_nightlights(img, self.min_cloud_free_coverage))
        )

        if self.composite_method == "median":
            image = collection.select("viirs_nightlights").median()
        elif self.composite_method == "mean":
            image = collection.select("viirs_nightlights").mean()
        elif self.composite_method == "max":
            image = collection.select("viirs_nightlights").max()
        elif self.composite_method == "min":
            image = collection.select("viirs_nightlights").min()
        else:
            raise ValueError("Could not compose")

        image = image.clip(region)
        output_path = (
            self.output_dir
            / f"viirs_nightlights_{self.start_date}_{self.end_date}_{self.composite_method}.tif"
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
    def _add_nightlights(image: ee.Image, min_cloud_free_coverage: int) -> ee.Image:
        mask = image.select("cf_cvg").gte(min_cloud_free_coverage)
        return image.addBands(image.select("avg_rad").updateMask(mask).rename("viirs_nightlights"))
