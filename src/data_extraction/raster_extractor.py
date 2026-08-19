from abc import abstractmethod
from .data_extract import DataExtractor, BBox
import geopandas as gpd
from pathlib import Path
import rasterio
from rasterstats import zonal_stats


class RasterExtractor(DataExtractor):
    """
    Fetches a raster and summarizes it to the grid.
    """

    @property
    def value_columns(self) -> tuple[str, ...]:
        return (self.layer_name,)

    @abstractmethod
    def get_data(self, bbox: BBox) -> Path:
        """
        Fetch raster data for bbox and return path to a local GeoTIFF. 
        """
    
    def align_to_grid(
        self, 
        data: Path,
        grid: gpd.GeoDataFrame
    )->gpd.GeoDataFrame:
        """
        Summarize raster pixels inside each grid cell.
        """
        #Open the raster to get the crs
        with rasterio.open(data) as src:
            raster_crs = src.crs
        
        #Bring the GDF to the correct CRS
        grid_for_stats = grid.to_crs(raster_crs)

        stats = zonal_stats(
            vectors = grid_for_stats.geometry,
            raster = str(data),
            stats = ["mean", "median", "min", "max", "std"],
            nodata = None,
            all_touched = True,
        )

        out = grid.copy()
        out[f"{self.layer_name}_mean"] = [s["mean"] for s in stats]
        out[f"{self.layer_name}_median"] = [s["median"] for s in stats]
        out[f"{self.layer_name}_min"] = [s["min"] for s in stats]
        out[f"{self.layer_name}_max"] = [s["max"] for s in stats]
        out[f"{self.layer_name}_std"] = [s["std"] for s in stats]

        return out





