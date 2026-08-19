from __future__ import annotations

from pathlib import Path

import ee
import requests

from .data_extract import BBox
from .raster_extractor import RasterExtractor


class MODISVegetationIndexExtractor(RasterExtractor):
    def __init__(
        self,
        start_date: str,
        end_date: str,
        grid_path: str | Path | None = None,
        output_dir: str | Path = "data/raw/modis_vegetation",
        index: str = "evi",
        composite_method: str = "median",
        scale: int = 250,
    ) -> None:
        super().__init__(grid_path=grid_path)
        self.start_date = start_date
        self.end_date = end_date
        self.output_dir = Path(output_dir)
        self.index = index.lower()
        self.composite_method = composite_method
        self.scale = scale
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def layer_name(self) -> str:
        return self.index

    @property
    def value_columns(self) -> tuple[str, ...]:
        return (
            f"{self.index}_mean",
            f"{self.index}_median",
            f"{self.index}_min",
            f"{self.index}_max",
            f"{self.index}_std",
        )

    def get_data(self, bbox: BBox) -> Path:
        self.validate_bbox(bbox)
        min_x, min_y, max_x, max_y = bbox
        region = ee.Geometry.Rectangle([min_x, min_y, max_x, max_y])

        if self.index == "ndvi":
            band = "NDVI"
        elif self.index == "evi":
            band = "EVI"
        else:
            raise ValueError("index must be 'ndvi' or 'evi'")

        collection = (
            ee.ImageCollection("MODIS/061/MOD13Q1")
            .filterBounds(region)
            .filterDate(self.start_date, self.end_date)
            .map(lambda img: self._add_index(img, band, self.index))
        )

        if self.composite_method == "median":
            image = collection.select(self.index).median()
        elif self.composite_method == "mean":
            image = collection.select(self.index).mean()
        elif self.composite_method == "max":
            image = collection.select(self.index).max()
        elif self.composite_method == "min":
            image = collection.select(self.index).min()
        else:
            raise ValueError("Could not compose")

        image = image.clip(region)
        output_path = (
            self.output_dir
            / f"modis_{self.index}_{self.start_date}_{self.end_date}_{self.composite_method}.tif"
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
    def _add_index(image: ee.Image, band: str, name: str) -> ee.Image:
        summary_qa = image.select("SummaryQA")
        mask = summary_qa.lte(1)
        index = image.select(band).multiply(0.0001).updateMask(mask).rename(name)
        return image.addBands(index)
