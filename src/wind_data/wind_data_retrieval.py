import requests
import pandas as pd

def get_wind_data(
        latitude:float, 
        longitude:float, 
        start_date:str, 
        end_date:str)->pd.DataFrame:
    """
    Returns a DataFrame with hourly wind speed and direction data for the specified location and date range.

    latitude
        The latitude of the location.
    longitude
        The longitude of the location.
    start_date
        The start date for the data retrieval in 'YYYY-MM-DD' format.
    end_date
        The end date for the data retrieval in 'YYYY-MM-DD' format.
    """

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "wind_speed_10m,wind_direction_10m",
        "start_date": start_date,  
        "end_date": end_date,      
        "timezone": "UTC"
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    df = pd.DataFrame({
        "time": pd.to_datetime(data["hourly"]["time"]),
        "wind_speed": data["hourly"]["wind_speed_10m"],
        "wind_direction": data["hourly"]["wind_direction_10m"],
    })

    return df