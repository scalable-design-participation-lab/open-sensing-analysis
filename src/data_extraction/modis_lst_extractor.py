from __future__ import annotations

from pathlib import Path

import ee
import requests

from .data_extract import BBox
from .raster_extractor import RasterExtractor


class MODISLSTExtractor(RasterExtractor):
    """
    MODIS daily land surface temperature in Celsius.
    """

    def __init__(
        self,
        start_date: str,
        end_date: str,
        grid_path: str | Path | None = None,
        output_dir: str | Path = "data/raw/modis_lst",
        satellite: str = "terra",
        pass_time: str = "day",
        composite_method: str = "median",
        scale: int = 1000,
    ) -> None:
        super().__init__(grid_path=grid_path)
        self.start_date = start_date
        self.end_date = end_date
        self.output_dir = Path(output_dir)
        self.satellite = satellite.lower()
        self.pass_time = pass_time.lower()
        self.composite_method = composite_method
        self.scale = scale
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def layer_name(self) -> str:
        return "lst_celsius"

    @property
    def value_columns(self) -> tuple[str, ...]:
        return (
            "lst_celsius_mean",
            "lst_celsius_median",
            "lst_celsius_min",
            "lst_celsius_max",
            "lst_celsius_std",
        )

    def get_data(self, bbox: BBox) -> Path:
        self.validate_bbox(bbox)
        min_x, min_y, max_x, max_y = bbox
        region = ee.Geometry.Rectangle([min_x, min_y, max_x, max_y])

        if self.satellite == "terra":
            collection_id = "MODIS/061/MOD11A1"
            collection = ee.ImageCollection(collection_id)
        elif self.satellite == "aqua":
            collection_id = "MODIS/061/MYD11A1"
            collection = ee.ImageCollection(collection_id)
        elif self.satellite == "both":
            collection = ee.ImageCollection("MODIS/061/MOD11A1").merge(
                ee.ImageCollection("MODIS/061/MYD11A1")
            )
        else:
            raise ValueError("satellite must be 'terra', 'aqua', or 'both'")

        if self.pass_time == "day":
            lst_band = "LST_Day_1km"
            qc_band = "QC_Day"
        elif self.pass_time == "night":
            lst_band = "LST_Night_1km"
            qc_band = "QC_Night"
        else:
            raise ValueError("pass_time must be 'day' or 'night'")

        collection = (
            collection
            .filterBounds(region)
            .filterDate(self.start_date, self.end_date)
            .map(lambda img: self._add_lst_celsius(img, lst_band, qc_band))
        )

        if self.composite_method == "median":
            image = collection.select("LST_C").median()
        elif self.composite_method == "mean":
            image = collection.select("LST_C").mean()
        elif self.composite_method == "max":
            image = collection.select("LST_C").max()
        elif self.composite_method == "min":
            image = collection.select("LST_C").min()
        else:
            raise ValueError("Could not compose")

        image = image.clip(region)
        output_path = (
            self.output_dir
            / f"modis_lst_celsius_{self.satellite}_{self.pass_time}_{self.start_date}_{self.end_date}_{self.composite_method}.tif"
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
    def _add_lst_celsius(image: ee.Image, lst_band: str, qc_band: str) -> ee.Image:
        qc = image.select(qc_band)
        mandatory_qa = qc.bitwiseAnd(3)
        mask = image.select(lst_band).gt(0).And(mandatory_qa.lte(1))
        lst_celsius = (
            image.select(lst_band)
            .multiply(0.02)
            .subtract(273.15)
            .updateMask(mask)
            .rename("LST_C")
        )
        return image.addBands(lst_celsius)
