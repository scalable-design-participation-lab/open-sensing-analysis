from __future__ import annotations

from pathlib import Path

import ee
import requests

from .data_extract import BBox
from .raster_extractor import RasterExtractor


class SRTMTerrainExtractor(RasterExtractor):
    def __init__(
        self,
        grid_path: str | Path | None = None,
        output_dir: str | Path = "data/raw/srtm",
        variable: str = "elevation",
        scale: int = 30,
    ) -> None:
        super().__init__(grid_path=grid_path)
        self.output_dir = Path(output_dir)
        self.variable = variable.lower()
        self.scale = scale
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def layer_name(self) -> str:
        return self.variable

    @property
    def value_columns(self) -> tuple[str, ...]:
        return (
            f"{self.variable}_mean",
            f"{self.variable}_median",
            f"{self.variable}_min",
            f"{self.variable}_max",
            f"{self.variable}_std",
        )

    def get_data(self, bbox: BBox) -> Path:
        self.validate_bbox(bbox)
        min_x, min_y, max_x, max_y = bbox
        region = ee.Geometry.Rectangle([min_x, min_y, max_x, max_y])

        dem = ee.Image("USGS/SRTMGL1_003")
        terrain = ee.Terrain.products(dem)

        if self.variable == "elevation":
            image = dem.select("elevation").rename("elevation")
        elif self.variable == "slope":
            image = terrain.select("slope").rename("slope")
        elif self.variable == "aspect":
            image = terrain.select("aspect").rename("aspect")
        else:
            raise ValueError("variable must be 'elevation', 'slope', or 'aspect'")

        image = image.clip(region)
        output_path = self.output_dir / f"srtm_{self.variable}.tif"

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
