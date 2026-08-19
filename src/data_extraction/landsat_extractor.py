from .raster_extractor import RasterExtractor
from datetime import date
from pathlib import Path
import tempfile
import requests

import ee
import geopandas as gpd
from .data_extract import BBox

class LandsatTemperatureExtractor(RasterExtractor):

    def __init__(
        self,
        start_date:str,
        end_date:str,
        grid_path: str|Path|None = None,
        output_dir:str|Path = "data/raw/landsat",
        composite_method:str = "mean",
    )->None:
        
        super().__init__(grid_path = grid_path)
        self.start_date = start_date
        self.end_date = end_date
        self.output_dir = Path(output_dir)
        self.composite_method = composite_method
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def layer_name(self)->str:
        return "lst_celsius"
    

    @property
    def value_columns(self)->tuple[str, ...]:
        return(
            "lst_celsius_mean",
            "lst_celsius_median",
            "lst_celsius_min",
            "lst_celsius_max",
            "lst_celsius_std"
        )
    
    def get_data(self, bbox:BBox)->Path:
        """
        Fetch Landsat LST as a alocal GeoTIFF
        """
        self.validate_bbox(bbox)
        min_x, min_y, max_x, max_y = bbox
        region = ee.Geometry.Rectangle([min_x, min_y, max_x, max_y])

        landsat8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        landsat9 = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
        collection = (
            landsat8.merge(landsat9)
            .filterBounds(region)
            .filterDate(self.start_date, self.end_date)
            .filter(ee.Filter.eq("PROCESSING_LEVEL", "L2SP"))
            .map(self._mask_clouds)
            .map(self._add_lst_celsius)
        )

        if self.composite_method == "median":
            image = collection.select("LST_C").median()
        elif self.composite_method == "mean":
            image = collection.select("LST_C").mean()
        elif self.composite_method == "max":
            image = collection.select("LST_C").max()
        else:
            raise ValueError("Could not compose")
        

        image = image.clip(region)
        filename = (f"landsat_lst_celsius_"f"{self.start_date}_{self.end_date}_{self.composite_method}.tif")

        output_path = self.output_dir/filename
        url = image.getDownloadURL(
            {
                "scale":30,
                "region":region,
                "format":"GEO_TIFF",
                "crs":"EPSG:4326"
            }
        )

        #Save the geotiff
        response = requests.get(url, timeout = 120)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        return output_path
    
    @staticmethod

    def _mask_clouds(image: ee.Image) -> ee.Image:
        qa = image.select("QA_PIXEL")

        # Landsat Collection 2 QA_PIXEL common masks:
        # bit 0: fill
        # bit 1: dilated cloud
        # bit 2: cirrus
        # bit 3: cloud
        # bit 4: cloud shadow

        mask = (
            qa.bitwiseAnd(1 << 0).eq(0)
            .And(qa.bitwiseAnd(1 << 1).eq(0))
            .And(qa.bitwiseAnd(1 << 2).eq(0))
            .And(qa.bitwiseAnd(1 << 3).eq(0))
            .And(qa.bitwiseAnd(1 << 4).eq(0))
        )

        return image.updateMask(mask)
    

    @staticmethod
    def _add_lst_celsius(image: ee.Image) -> ee.Image:
        lst_celsius = (
            image.select("ST_B10")
            .multiply(0.00341802)
            .add(149.0)
            .subtract(273.15)
            .rename("LST_C")
        )

        return image.addBands(lst_celsius)

        





