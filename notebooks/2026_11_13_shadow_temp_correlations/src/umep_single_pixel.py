import numpy as np


def get_sun_ray(
    dsm,
    azimuth,
    altitude,
    pixel_size_meters
):
    n_steps = max(dsm.shape)
    steps = np.arange(0, n_steps + 1)
    azimuth_radians = np.radians(azimuth)
    altitude_radians = np.radians(altitude)

    sun_is_mostly_east_or_west = (45 <= azimuth < 135) or (225 <= azimuth < 315)
    if(sun_is_mostly_east_or_west):
        column_offsets = np.sign(np.sin(azimuth_radians)) * steps
        row_offsets = -np.sign(np.cos(azimuth_radians)) * np.abs(np.round(steps / np.tan(azimuth_radians)))
        step_length = np.abs(1 / np.sin(azimuth_radians))
    else:
        column_offsets = np.sign(np.sin(azimuth_radians)) * np.abs(np.round(steps * np.tan(azimuth_radians)))
        row_offsets = -np.sign(np.cos(azimuth_radians)) * steps
        step_length = np.abs(1 / np.cos(azimuth_radians))

    height_gains = step_length * steps * pixel_size_meters * np.tan(altitude_radians)
    previous_height_gains = np.concatenate([[0.0], height_gains[0:-1]])

    sun_ray = {
        "row_offsets": row_offsets.astype(int),
        "column_offsets": column_offsets.astype(int),
        "height_gains": height_gains,
        "previous_height_gains": previous_height_gains
    }

    return sun_ray


def get_sunlit_value(
    dsm,
    pixel,
    sun_ray
):
    n_rows, n_columns = dsm.shape
    ray_rows = pixel["row"] + sun_ray["row_offsets"]
    ray_columns = pixel["column"] + sun_ray["column_offsets"]
    is_inside_rows = (ray_rows >= 0) & (ray_rows < n_rows)
    is_inside_columns = (ray_columns >= 0) & (ray_columns < n_columns)
    is_inside_dsm = is_inside_rows & is_inside_columns

    surface_heights = dsm[ray_rows[is_inside_dsm], ray_columns[is_inside_dsm]]
    ray_heights = dsm[pixel["row"], pixel["column"]] + sun_ray["height_gains"][is_inside_dsm]
    is_blocked = np.any(surface_heights > ray_heights)

    if(is_blocked):
        return 0
    return 1


def get_pixels_on_sun_ray(
    raster_shape,
    pixel,
    sun_ray
):
    n_rows, n_columns = raster_shape
    ray_rows = pixel["row"] + sun_ray["row_offsets"]
    ray_columns = pixel["column"] + sun_ray["column_offsets"]
    is_inside_rows = (ray_rows >= 0) & (ray_rows < n_rows)
    is_inside_columns = (ray_columns >= 0) & (ray_columns < n_columns)
    is_inside_raster = is_inside_rows & is_inside_columns

    pixels_on_sun_ray = {
        "rows": ray_rows[is_inside_raster],
        "columns": ray_columns[is_inside_raster],
        "height_gains": sun_ray["height_gains"][is_inside_raster],
        "previous_height_gains": sun_ray["previous_height_gains"][is_inside_raster]
    }

    return pixels_on_sun_ray


def get_shadow_value(
    rasters,
    pixel,
    sun_ray,
    transmissivity
):
    pixels_on_sun_ray = get_pixels_on_sun_ray(
        raster_shape = rasters["buildings"].shape,
        pixel = pixel,
        sun_ray = sun_ray
    )
    rows = pixels_on_sun_ray["rows"]
    columns = pixels_on_sun_ray["columns"]
    pixel_height = rasters["buildings"][pixel["row"], pixel["column"]]
    ray_heights = pixel_height + pixels_on_sun_ray["height_gains"]
    previous_ray_heights = pixel_height + pixels_on_sun_ray["previous_height_gains"]

    building_heights = rasters["buildings"][rows, columns]
    is_blocked_by_building = np.any(building_heights > ray_heights)
    if(is_blocked_by_building):
        return 0.0

    crown_tops = rasters["crowns"][rows, columns]
    crown_bottoms = rasters["trunks"][rows, columns]
    is_ray_crossing_crown = (crown_tops > previous_ray_heights) & (crown_bottoms <= ray_heights)
    is_blocked_by_tree = np.any(is_ray_crossing_crown)
    if(is_blocked_by_tree):
        return transmissivity

    return 1.0


def get_shifted_window(
    raster,
    window,
    row_offset,
    column_offset
):
    first_row = window["top_row"] + row_offset
    first_column = window["left_column"] + column_offset
    end_row = first_row + window["n_rows"]
    end_column = first_column + window["n_columns"]
    n_rows, n_columns = raster.shape

    is_inside_raster = (first_row >= 0) and (first_column >= 0) and (end_row <= n_rows) and (end_column <= n_columns)
    if(is_inside_raster):
        return raster[first_row:end_row, first_column:end_column]

    shifted_window = np.zeros((window["n_rows"], window["n_columns"]), dtype = raster.dtype)
    source_top = max(first_row, 0)
    source_bottom = min(end_row, n_rows)
    source_left = max(first_column, 0)
    source_right = min(end_column, n_columns)
    is_outside_raster = (source_top >= source_bottom) or (source_left >= source_right)
    if(is_outside_raster):
        return shifted_window

    shifted_window[source_top - first_row:source_bottom - first_row, source_left - first_column:source_right - first_column] = raster[source_top:source_bottom, source_left:source_right]
    return shifted_window


def get_window_shadow_values(
    rasters,
    window,
    sun_ray,
    transmissivity
):
    pixel_heights = get_shifted_window(
        raster = rasters["buildings"],
        window = window,
        row_offset = 0,
        column_offset = 0
    )
    tallest_height = max(rasters["buildings"].max(), rasters["crowns"].max())
    is_blocked_by_building = np.zeros(pixel_heights.shape, dtype = bool)
    is_blocked_by_tree = np.zeros(pixel_heights.shape, dtype = bool)

    n_steps = len(sun_ray["height_gains"])
    for k in range(0, n_steps):
        ray_is_above_everything = sun_ray["previous_height_gains"][k] > tallest_height
        if(ray_is_above_everything):
            break

        building_heights = get_shifted_window(
            raster = rasters["buildings"],
            window = window,
            row_offset = sun_ray["row_offsets"][k],
            column_offset = sun_ray["column_offsets"][k]
        )
        crown_tops = get_shifted_window(
            raster = rasters["crowns"],
            window = window,
            row_offset = sun_ray["row_offsets"][k],
            column_offset = sun_ray["column_offsets"][k]
        )
        crown_bottoms = get_shifted_window(
            raster = rasters["trunks"],
            window = window,
            row_offset = sun_ray["row_offsets"][k],
            column_offset = sun_ray["column_offsets"][k]
        )
        ray_heights = pixel_heights + sun_ray["height_gains"][k]
        previous_ray_heights = pixel_heights + sun_ray["previous_height_gains"][k]

        is_blocked_by_building = is_blocked_by_building | (building_heights > ray_heights)
        is_ray_crossing_crown = (crown_tops > previous_ray_heights) & (crown_bottoms <= ray_heights)
        is_blocked_by_tree = is_blocked_by_tree | is_ray_crossing_crown

    shadow_values = np.ones(pixel_heights.shape)
    shadow_values[is_blocked_by_tree] = transmissivity
    shadow_values[is_blocked_by_building] = 0.0

    return shadow_values
