from __future__ import annotations

from pathlib import Path

import ee
import requests

from .data_extract import BBox
from .raster_extractor import RasterExtractor


class WorldCoverImperviousExtractor(RasterExtractor):
    """
    Impervious surface fraction per grid cell using ESA WorldCover 2021.
    Class 50 (Built-up) is mapped to 1; all other classes to 0.
    The zonal mean gives fraction of built-up cover (0–1).
    """

    def __init__(
        self,
        grid_path: str | Path | None = None,
        output_dir: str | Path = "data/raw/worldcover",
        scale: int = 30,
    ) -> None:
        super().__init__(grid_path=grid_path)
        self.scale = scale
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def layer_name(self) -> str:
        return "impervious"

    @property
    def value_columns(self) -> tuple[str, ...]:
        return ("impervious_mean", "impervious_median", "impervious_min", "impervious_max", "impervious_std")

    def get_data(self, bbox: BBox) -> Path:
        self.validate_bbox(bbox)
        min_x, min_y, max_x, max_y = bbox
        region = ee.Geometry.Rectangle([min_x, min_y, max_x, max_y])

        built_up = (
            ee.ImageCollection("ESA/WorldCover/v200")
            .first()
            .eq(50)
            .rename("impervious")
            .toFloat()
            .clip(region)
        )

        output_path = self.output_dir / "worldcover_impervious.tif"
        url = built_up.getDownloadURL({
            "scale": self.scale,
            "region": region,
            "format": "GEO_TIFF",
            "crs": "EPSG:4326",
        })

        response = requests.get(url, timeout=300)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        return output_path
