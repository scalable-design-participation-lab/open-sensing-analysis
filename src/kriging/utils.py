import json
from pathlib import Path
from typing import List
from shapely import Polygon

def get_bounding_box(
        points: List[tuple[float, float]],
        delta:float = 0) -> dict[str, float]:
    
    x_coords = [point[0] for point in points]
    y_coords = [point[1] for point in points]


    max_x = float("-inf")
    min_x = float("inf")
    max_y = float("-inf")
    min_y = float("inf")

    n = len(points)
    for i in range(0,n):
        x = x_coords[i]
        y = y_coords[i]

        if x > max_x:
            max_x = x
        if x < min_x:
            min_x = x
        if y > max_y:
            max_y = y
        if y < min_y:
            min_y = y
    
    if(delta > 0):
        max_x += delta
        min_x -= delta
        max_y += delta
        min_y -= delta
    
    return {
        "max_x": max_x,
        "min_x": min_x,
        "max_y": max_y,
        "min_y": min_y
    }




def get_area_grid(bounding_box: dict[str, float], n_cells: int = 10) -> list[Polygon]:
        """
        Return a list of shapely Polygons representing a grid of n_cells x n_cells covering the area defined by the bounding box.
        """
        max_x = bounding_box["max_x"]
        min_x = bounding_box["min_x"]
        max_y = bounding_box["max_y"]
        min_y = bounding_box["min_y"]

        x_step = (max_x - min_x) / n_cells
        y_step = (max_y - min_y) / n_cells

        grid_cells = []
        for i in range(n_cells):
            for j in range(n_cells):
                cell_min_x = min_x + i * x_step
                cell_max_x = min_x + (i + 1) * x_step
                cell_min_y = min_y + j * y_step
                cell_max_y = min_y + (j + 1) * y_step

                cell_polygon = Polygon([
                    (cell_min_x, cell_min_y),
                    (cell_max_x, cell_min_y),
                    (cell_max_x, cell_max_y),
                    (cell_min_x, cell_max_y)
                ])
                grid_cells.append(cell_polygon)

        return grid_cells
    


def get_square_dimensions(
    cell: Polygon
) -> tuple[float, float]:
    """
    Return the width and height of a square cell as a tuple (width, height).
    """
    min_x, min_y, max_x, max_y = cell.bounds
    width = max_x - min_x
    height = max_y - min_y
    return (width, height)


def export_bounding_box(
    bounding_box: dict[str, float],
    output_path: str | Path,
    crs: str | None = None,
) -> None:
    """
    Export a bounding box as a GeoJSON FeatureCollection with one Polygon feature.
    """
    required_keys = {"min_x", "min_y", "max_x", "max_y"}
    if not required_keys.issubset(bounding_box):
        missing = required_keys - set(bounding_box.keys())
        raise ValueError(f"Missing bounding box keys: {sorted(missing)}")

    min_x = bounding_box["min_x"]
    min_y = bounding_box["min_y"]
    max_x = bounding_box["max_x"]
    max_y = bounding_box["max_y"]

    polygon_coords = [[
        [min_x, min_y],
        [max_x, min_y],
        [max_x, max_y],
        [min_x, max_y],
        [min_x, min_y],
    ]]

    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "min_x": min_x,
                    "min_y": min_y,
                    "max_x": max_x,
                    "max_y": max_y,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": polygon_coords,
                },
            }
        ],
    }
    if crs:
        geojson["crs"] = {"type": "name", "properties": {"name": crs}}

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)


def export_grid_geojson(
    grid_cells: list[Polygon],
    output_path: str | Path,
    crs: str | None = None,
) -> None:
    """
    Export grid cells as a GeoJSON FeatureCollection of Polygon features.
    """
    features: list[dict] = []
    for idx, cell in enumerate(grid_cells):
        coordinates = [list(cell.exterior.coords)]
        feature = {
            "type": "Feature",
            "properties": {"id": idx},
            "geometry": {
                "type": "Polygon",
                "coordinates": coordinates,
            },
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }
    if crs:
        geojson["crs"] = {"type": "name", "properties": {"name": crs}}

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)
    

    
