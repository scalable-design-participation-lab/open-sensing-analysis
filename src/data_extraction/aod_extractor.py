from __future__ import annotations

from pathlib import Path

import ee
import requests

from .data_extract import BBox
from .raster_extractor import RasterExtractor


class MODISAODExtractor(RasterExtractor):
    """
    Aerosol Optical Depth from MODIS MAIAC (MCD19A2) at 1 km resolution.
    Uses the 0.47 µm band, which is more sensitive to fine particles (PM2.5).
    """

    def __init__(
        self,
        start_date: str,
        end_date: str,
        grid_path: str | Path | None = None,
        output_dir: str | Path = "data/raw/aod",
        scale: int = 1000,
    ) -> None:
        super().__init__(grid_path=grid_path)
        self.start_date = start_date
        self.end_date = end_date
        self.scale = scale
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def layer_name(self) -> str:
        return "aod"

    @property
    def value_columns(self) -> tuple[str, ...]:
        return ("aod_mean", "aod_median", "aod_min", "aod_max", "aod_std")

    def get_data(self, bbox: BBox) -> Path:
        self.validate_bbox(bbox)
        min_x, min_y, max_x, max_y = bbox
        region = ee.Geometry.Rectangle([min_x, min_y, max_x, max_y])

        collection = (
            ee.ImageCollection("MODIS/061/MCD19A2_GRANULES")
            .filterBounds(region)
            .filterDate(self.start_date, self.end_date)
            .select("Optical_Depth_047")
            # Mask fill values (-28672) before scaling
            .map(lambda img: img.updateMask(img.gt(-28000)).multiply(0.001).rename("aod"))
        )

        aod = collection.median().clip(region)
        output_path = self.output_dir / f"aod_{self.start_date}_{self.end_date}.tif"

        url = aod.getDownloadURL({
            "scale": self.scale,
            "region": region,
            "format": "GEO_TIFF",
            "crs": "EPSG:4326",
        })

        response = requests.get(url, timeout=300)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        return output_path
