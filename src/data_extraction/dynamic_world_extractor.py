from __future__ import annotations

from pathlib import Path

import ee
import requests

from .data_extract import BBox
from .raster_extractor import RasterExtractor


class DynamicWorldExtractor(RasterExtractor):
    def __init__(
        self,
        start_date: str,
        end_date: str,
        grid_path: str | Path | None = None,
        output_dir: str | Path = "data/raw/dynamic_world",
        landcover_class: str = "built",
        composite_method: str = "median",
        scale: int = 10,
    ) -> None:
        super().__init__(grid_path=grid_path)
        self.start_date = start_date
        self.end_date = end_date
        self.output_dir = Path(output_dir)
        self.landcover_class = landcover_class
        self.composite_method = composite_method
        self.scale = scale
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def layer_name(self) -> str:
        return f"dw_{self.landcover_class}"

    @property
    def value_columns(self) -> tuple[str, ...]:
        return (
            f"{self.layer_name}_mean",
            f"{self.layer_name}_median",
            f"{self.layer_name}_min",
            f"{self.layer_name}_max",
            f"{self.layer_name}_std",
        )

    def get_data(self, bbox: BBox) -> Path:
        self.validate_bbox(bbox)
        min_x, min_y, max_x, max_y = bbox
        region = ee.Geometry.Rectangle([min_x, min_y, max_x, max_y])

        valid_classes = {
            "water",
            "trees",
            "grass",
            "flooded_vegetation",
            "crops",
            "shrub_and_scrub",
            "built",
            "bare",
            "snow_and_ice",
        }
        if self.landcover_class not in valid_classes:
            raise ValueError(f"landcover_class must be one of {sorted(valid_classes)}")

        collection = (
            ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
            .filterBounds(region)
            .filterDate(self.start_date, self.end_date)
            .select(self.landcover_class)
        )

        if self.composite_method == "median":
            image = collection.median()
        elif self.composite_method == "mean":
            image = collection.mean()
        elif self.composite_method == "max":
            image = collection.max()
        elif self.composite_method == "min":
            image = collection.min()
        else:
            raise ValueError("Could not compose")

        image = image.rename(self.layer_name).clip(region)
        output_path = (
            self.output_dir
            / f"dynamic_world_{self.landcover_class}_{self.start_date}_{self.end_date}_{self.composite_method}.tif"
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
