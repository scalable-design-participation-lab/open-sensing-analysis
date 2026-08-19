from __future__ import annotations

from pathlib import Path

import ee
import requests

from .data_extract import BBox
from .raster_extractor import RasterExtractor


class ERA5LandExtractor(RasterExtractor):
    def __init__(
        self,
        start_date: str,
        end_date: str,
        grid_path: str | Path | None = None,
        output_dir: str | Path = "data/raw/era5_land",
        variable: str = "temperature_2m",
        composite_method: str = "mean",
        scale: int = 11132,
    ) -> None:
        super().__init__(grid_path=grid_path)
        self.start_date = start_date
        self.end_date = end_date
        self.output_dir = Path(output_dir)
        self.variable = variable
        self.composite_method = composite_method
        self.scale = scale
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def layer_name(self) -> str:
        if self.variable == "temperature_2m":
            return "era5_temperature_2m_c"
        if self.variable == "dewpoint_temperature_2m":
            return "era5_dewpoint_2m_c"
        if self.variable == "wind_speed_10m":
            return "era5_wind_speed_10m"
        return f"era5_{self.variable}"

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

        collection = (
            ee.ImageCollection("ECMWF/ERA5_LAND/HOURLY")
            .filterBounds(region)
            .filterDate(self.start_date, self.end_date)
            .map(lambda img: self._add_variable(img, self.variable, self.layer_name))
        )

        if self.composite_method == "median":
            image = collection.select(self.layer_name).median()
        elif self.composite_method == "mean":
            image = collection.select(self.layer_name).mean()
        elif self.composite_method == "max":
            image = collection.select(self.layer_name).max()
        elif self.composite_method == "min":
            image = collection.select(self.layer_name).min()
        else:
            raise ValueError("Could not compose")

        image = image.clip(region)
        output_path = (
            self.output_dir
            / f"{self.layer_name}_{self.start_date}_{self.end_date}_{self.composite_method}.tif"
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
    def _add_variable(image: ee.Image, variable: str, name: str) -> ee.Image:
        if variable in {"temperature_2m", "dewpoint_temperature_2m"}:
            value = image.select(variable).subtract(273.15).rename(name)
        elif variable == "wind_speed_10m":
            u = image.select("u_component_of_wind_10m")
            v = image.select("v_component_of_wind_10m")
            value = u.pow(2).add(v.pow(2)).sqrt().rename(name)
        else:
            value = image.select(variable).rename(name)
        return image.addBands(value)
