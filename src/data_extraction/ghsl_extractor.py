from __future__ import annotations

from pathlib import Path

import ee
import requests

from .data_extract import BBox
from .raster_extractor import RasterExtractor


class GHSLBuiltSurfaceExtractor(RasterExtractor):
    def __init__(
        self,
        grid_path: str | Path | None = None,
        output_dir: str | Path = "data/raw/ghsl",
        year: int = 2025,
        band: str = "built_surface",
        as_fraction: bool = True,
        scale: int = 100,
    ) -> None:
        super().__init__(grid_path=grid_path)
        self.output_dir = Path(output_dir)
        self.year = int(year)
        self.band = band
        self.as_fraction = as_fraction
        self.scale = scale
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def layer_name(self) -> str:
        return "ghsl_built_fraction" if self.as_fraction else "ghsl_built_surface"

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

        image = ee.Image(f"JRC/GHSL/P2023A/GHS_BUILT_S/{self.year}").select(self.band)
        if self.as_fraction:
            image = image.divide(10000)
        image = image.rename(self.layer_name).clip(region)

        output_path = self.output_dir / f"{self.layer_name}_{self.year}.tif"
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
