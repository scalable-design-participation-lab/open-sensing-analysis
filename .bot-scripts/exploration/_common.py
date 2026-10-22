"""Shared loading for the informal exploration scripts.

Nothing here belongs in the three formal notebooks. The formal pipeline is
notebooks/2026_09_16_site_built_environment_comparison/{svi_retrieval,built_environment_features,visual_features}.ipynb
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/legariapena.j/Documents/open-sensing-analysis/open-sensing-analysis")
DATA = ROOT/"data"/"2026_09_16_site_built_environment_comparison"
SENSORS = ROOT/"data"/"sensors"
COMPARISON = ROOT/"data"/"2026_08_26_sensor_comparisons"/"data"

sys.path.append(str(ROOT/"src"/"time_series"))
from series_aligner import align_sensor_series_from_list
from time_series_comparison_metrics import compute_rmse, compute_correlation_coefficient

COUNT_FEATURES = ["n_cars", "n_facades", "n_benches", "n_doors", "n_graffiti", "n_persons",
                  "n_signage", "n_street_lights", "n_trash", "n_utility_poles", "n_windows"]
RATIO_FEATURES = ["sky_ratio", "road_ratio", "sidewalk_ratio"]
VECTOR_FEATURES = ["gvi"] + RATIO_FEATURES + COUNT_FEATURES

EPA_STATION_TO_SITE_NAME = {"Roxbury (EPA)": "DUDLEY SQUARE ROXBURY",
                            "Von Hillern (EPA)": "VON HILLERN ST"}

SITE_TO_SENSOR = {
    "Carter Field": ("Boston Carter Field (ours)", "Carter (ours)", "boston_carter_field/boston_carter_field.csv"),
    "Carter Field — 2": ("Boston Carter Field (ref)", "Carter (ref)", "boston_carter_field_reference/MOD-00157-CarterField.csv"),
    "Robinson Hall": ("Boston Robinson Hall", "Robinson", "boston_robinson_hall/boston_robinson_hall.csv"),
    "Gainsborough Parking Garage": ("Boston Gainsborough Parking", "Gainsborough", "boston_gainsborough_parking/boston_gainsborough_parking.csv"),
    "West Village B": ("Boston West Village B", "West Village B", "boston_west_village_b/boston_west_village_b.csv"),
    "World Series Way ": ("Boston World Series Way", "World Series", "boston_world_series_way/boston_world_series_way.csv"),
}

MIN_VALID_PM25, MAX_VALID_PM25 = 0.05, 200
SAMPLING_INTERVAL = "24h"
EARTH_RADIUS_M = 6371000.0

PINK_DRACULA, GREEN_DRACULA = "#FF79C6", "#50FA7B"
EPA_STATION_TO_COLOR = {"Roxbury (EPA)": PINK_DRACULA, "Von Hillern (EPA)": GREEN_DRACULA}
VARIABLE_TO_LABEL = {"temperature": "Temperature RMSE (C)", "pm25": "PM2.5 RMSE (ug/m3)"}


def haversine_metres(latitude_1, longitude_1, latitude_2, longitude_2):
    phi_1, phi_2 = np.radians(latitude_1), np.radians(latitude_2)
    delta_phi = phi_2 - phi_1
    delta_lambda = np.radians(longitude_2 - longitude_1)
    a = np.sin(delta_phi/2)**2 + np.cos(phi_1)*np.cos(phi_2)*np.sin(delta_lambda/2)**2
    return 2*EARTH_RADIUS_M*np.arcsin(np.sqrt(a))


def fahrenheit_to_celsius(value):
    return (value - 32)*(5/9)


def load_features():
    return pd.read_csv(DATA/"built_environment_features.csv")


def load_sensor_coordinates():
    ecohub = pd.read_csv(ROOT/"data"/"spatial"/"data-1775857265051.csv")
    epa = pd.read_csv(COMPARISON/"boston_pm25_combined.csv")
    coordinates = {}
    for site_name in SITE_TO_SENSOR:
        if site_name == "Carter Field — 2":
            coordinates[site_name] = (42.3382, -71.0851)
            continue
        rows = ecohub[ecohub["ecohub_location"].str.strip() == site_name.strip()]
        coordinates[site_name] = (float(rows["lat"].iloc[0]), float(rows["lon"].iloc[0]))
    for station_name, epa_site in EPA_STATION_TO_SITE_NAME.items():
        rows = epa[epa["site_name"] == epa_site]
        coordinates[epa_site] = (float(rows["lat"].iloc[0]), float(rows["lon"].iloc[0]))
    return coordinates


def add_distance_to_sensor(features, coordinates):
    features = features.copy()
    features["distance_to_sensor_m"] = [
        haversine_metres(coordinates[s][0], coordinates[s][1], la, lo)
        for s, la, lo in zip(features["site_name"], features["latitude"], features["longitude"])
    ]
    return features


def site_summary_at(features, radius_m=None, columns=None):
    columns = columns or (["gvi"] + RATIO_FEATURES + COUNT_FEATURES)
    subset = features if radius_m is None else features[features["distance_to_sensor_m"] <= radius_m]
    return subset.groupby("site_name")[columns].mean()


def load_sensor_series():
    temperature = pd.read_csv(COMPARISON/"boston_temp_combined.csv")
    pm25 = pd.read_csv(COMPARISON/"boston_pm25_combined.csv")

    station_temperature, station_pm25 = {}, {}
    for station_name, epa_site in EPA_STATION_TO_SITE_NAME.items():
        t = temperature[temperature["site_name"] == epa_site].copy()
        t["temperature"] = t["temp_f"].map(fahrenheit_to_celsius)
        t["timestamp"] = t["date"]
        station_temperature[station_name] = t
        p = pm25[pm25["site_name"] == epa_site].copy()
        p["timestamp"] = p["date"]
        station_pm25[station_name] = p

    sensor_data, daily_humidity = {}, {}
    for site_name, (sensor_name, _, relative_path) in SITE_TO_SENSOR.items():
        d = pd.read_csv(SENSORS/relative_path)
        if "temperature" not in d.columns:
            d["temperature"] = d["temp"]
        p = pd.to_numeric(d["pm25"], errors="coerce")
        d["pm25"] = p.where((p >= MIN_VALID_PM25) & (p <= MAX_VALID_PM25))
        sensor_data[sensor_name] = d

        column = "relative_humidity" if "relative_humidity" in d.columns else "rh"
        frame = pd.DataFrame({"t": pd.to_datetime(d["timestamp"], errors="coerce", utc=True),
                              "rh": pd.to_numeric(d[column], errors="coerce")}).dropna()
        daily_humidity[sensor_name] = frame.set_index("t")["rh"].resample(SAMPLING_INTERVAL).mean()

    # daily_humidity: full per-sensor series, for day-level work.
    # shared_humidity: intersection across sensors, for comparing sensors to each other.
    shared_humidity = pd.DataFrame(daily_humidity).dropna()
    return station_temperature, station_pm25, sensor_data, daily_humidity, shared_humidity


def sensor_station_metrics(station_temperature, station_pm25, sensor_data):
    """Canonical pairing from notebooks/2026_08_26_sensor_comparisons/comparison_with_all_sensors_pm25.ipynb."""
    store = {"temperature": station_temperature, "pm25": station_pm25}
    rows = []
    for site_name, (sensor_name, abbreviation, _) in SITE_TO_SENSOR.items():
        for station_name in EPA_STATION_TO_SITE_NAME:
            for variable_name, stations in store.items():
                aligned, _ = align_sensor_series_from_list(
                    sensor_dataframes=[stations[station_name], sensor_data[sensor_name]],
                    variable_name=variable_name, time_column="timestamp",
                    sensor_names=[station_name, sensor_name], sampling_interval=SAMPLING_INTERVAL)
                if len(aligned) == 0:
                    rows.append(dict(sensor_name=sensor_name, abbreviation=abbreviation, site_name=site_name,
                                     epa_station=station_name, variable=variable_name,
                                     rmse=np.nan, coeff=np.nan, n_days=0))
                    continue
                station_series, sensor_series = list(aligned[station_name]), list(aligned[sensor_name])
                rows.append(dict(sensor_name=sensor_name, abbreviation=abbreviation, site_name=site_name,
                                 epa_station=station_name, variable=variable_name,
                                 rmse=compute_rmse(station_series, sensor_series),
                                 coeff=compute_correlation_coefficient(station_series, sensor_series),
                                 n_days=len(aligned)))
    return pd.DataFrame(rows)
