from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box


BBox = tuple[float, float, float, float]


class DataExtractor(ABC):
    """
    Base interface for extracting a spatial layer over the project study area.

    A concrete extractor should fetch raw data for a bounding box with `get_data`
    and then implement `align_to_grid` to convert the raw layer into one value
    per grid cell from `data/grid_rectangles.geojson`.
    """

    DEFAULT_GRID_PATH = Path("data/grid_rectangles.geojson")

    def __init__(self, grid_path: str | Path | None = None) -> None:
        self.grid_path = Path(grid_path) if grid_path else self.DEFAULT_GRID_PATH

    @property
    @abstractmethod
    def layer_name(self) -> str:
        """Short identifier for the extracted layer, such as `ndvi`."""

    @property
    def value_columns(self) -> tuple[str, ...]:
        """
        Output columns expected after grid alignment.

        Subclasses can override this when they produce one or more named values.
        """

        return ()

    @abstractmethod
    def get_data(self, bbox: BBox) -> gpd.GeoDataFrame:
        """
        Fetch raw source data for the requested bounding box.

        The bbox format is `(min_x, min_y, max_x, max_y)`.
        """

    @abstractmethod
    def align_to_grid(
        self,
        data: gpd.GeoDataFrame,
        grid: gpd.GeoDataFrame,
    ) -> gpd.GeoDataFrame:
        """
        Convert raw source data into grid-aligned features.

        Raster extractors may summarize pixel values per cell, while vector
        extractors may intersect, aggregate, or compute density per cell.
        """

    def extract_for_grid(
        self,
        bbox: BBox,
        grid: gpd.GeoDataFrame | None = None,
    ) -> gpd.GeoDataFrame:
        """
        Full extraction flow for this project: fetch raw data and align it to
        the project grid resolution.
        """

        target_grid = grid if grid is not None else self.load_grid()
        data = self.get_data(bbox)
        return self.align_to_grid(data, target_grid)

    def load_grid(self) -> gpd.GeoDataFrame:
        """Load the project grid used as the target extraction resolution."""

        return gpd.read_file(self.grid_path)

    def get_target_resolution(self) -> tuple[float, float]:
        """
        Return the width and height of one target grid cell.

        This is the spatial resolution extractors should try to match.
        """

        grid = self.load_grid()
        first_cell = grid.geometry.iloc[0]
        min_x, min_y, max_x, max_y = first_cell.bounds
        return max_x - min_x, max_y - min_y

    def get_target_crs(self) -> str | None:
        """Return the CRS used by the project grid."""

        grid = self.load_grid()
        return grid.crs.to_string() if grid.crs else None

    def bbox_to_gdf(self, bbox: BBox, crs: str | None = None) -> gpd.GeoDataFrame:
        """Wrap a bbox as a one-row GeoDataFrame."""

        min_x, min_y, max_x, max_y = self.validate_bbox(bbox)
        return gpd.GeoDataFrame(geometry=[box(min_x, min_y, max_x, max_y)], crs=crs)

    def clip_to_bbox(
        self,
        data: gpd.GeoDataFrame,
        bbox: BBox,
        crs: str | None = None,
    ) -> gpd.GeoDataFrame:
        """Clip a GeoDataFrame to the provided bbox."""

        clip_crs = crs or (data.crs.to_string() if data.crs else None)
        bbox_gdf = self.bbox_to_gdf(bbox, crs=clip_crs)
        if data.crs and bbox_gdf.crs and data.crs != bbox_gdf.crs:
            bbox_gdf = bbox_gdf.to_crs(data.crs)
        return gpd.clip(data, bbox_gdf)

    def validate_bbox(self, bbox: BBox) -> BBox:
        """Validate bbox ordering before running any extraction."""

        min_x, min_y, max_x, max_y = bbox
        if min_x >= max_x:
            raise ValueError("bbox min_x must be smaller than max_x")
        if min_y >= max_y:
            raise ValueError("bbox min_y must be smaller than max_y")
        return bbox
