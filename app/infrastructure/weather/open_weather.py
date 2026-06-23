import json

import os
from typing import List, Optional

import httpx
from app.core.config import settings
from app.schemas.weather import (
    AirPollutionResponse,
    CurrentWeatherResponse,
    ForecastResponse,
    GeocodingResponse,
    WeatherMapLayer,
    WeatherMapResponse,
)

BASE_URL = "https://api.openweathermap.org/data/2.5"
GEO_BASE_URL = "http://api.openweathermap.org/geo/1.0"
MAP_BASE_URL = "https://tile.openweathermap.org/map"


def _require_api_key() -> str:
    api_key = settings.OPENWEATHERMAP_API_KEY
    if not api_key:
        raise ValueError("OPENWEATHERMAP_API_KEY is not configured.")
    return api_key


async def get_current_weather(
    lat: float, lon: float
) -> Optional[CurrentWeatherResponse]:
    """
    Fetches the current weather for a given latitude and longitude.

    Args:
        lat: Latitude.
        lon: Longitude.

    Returns:
        A CurrentWeatherResponse object or None if the request fails.
    """
    # For dev purpose, store data locally
    cache_dir = os.path.join(os.path.dirname(__file__), ".cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(
        cache_dir, f"get_current_weather_lat_{lat}_lon_{lon}.json"
    )

    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            return CurrentWeatherResponse(**json.load(f))

    params = {"lat": lat, "lon": lon, "appid": _require_api_key(), "units": "metric"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/weather", params=params)
        if response.status_code == 200:
            data = response.json()
            with open(cache_file, "w") as f:
                json.dump(data, f)
            return CurrentWeatherResponse(**data)
    return None


async def get_5_day_3_hour_forecast(
    lat: float, lon: float
) -> Optional[ForecastResponse]:
    """
    Fetches the 5-day forecast (with 3-hour intervals) for a given location.

    Args:
        lat: Latitude.
        lon: Longitude.

    Returns:
        A ForecastResponse object or None if the request fails.
    """
    # For dev purpose, store data locally
    cache_dir = os.path.join(os.path.dirname(__file__), ".cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(
        cache_dir, f"get_5_day_3_hour_forecast_lat_{lat}_lon_{lon}.json"
    )

    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            return ForecastResponse(**json.load(f))

    params = {"lat": lat, "lon": lon, "appid": _require_api_key(), "units": "metric"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/forecast", params=params)
        if response.status_code == 200:
            data = response.json()
            with open(cache_file, "w") as f:
                json.dump(data, f)
            return ForecastResponse(**data)
    return None


async def get_air_pollution(lat: float, lon: float) -> Optional[AirPollutionResponse]:
    """
    Fetches air pollution data for a given latitude and longitude.

    Args:
        lat: Latitude.
        lon: Longitude.

    Returns:
        An AirPollutionResponse object or None if the request fails.
    """
    params = {"lat": lat, "lon": lon, "appid": _require_api_key()}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/air_pollution", params=params)
        if response.status_code == 200:
            return AirPollutionResponse(**response.json())
    return None


async def get_reverse_geocoding(
    lat: float, lon: float
) -> Optional[List[GeocodingResponse]]:
    """
    Performs reverse geocoding to find location names from coordinates.

    Args:
        lat: Latitude.
        lon: Longitude.

    Returns:
        A list of GeocodingResponse objects or None if the request fails.
    """
    params = {"lat": lat, "lon": lon, "limit": 5, "appid": _require_api_key()}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{GEO_BASE_URL}/reverse", params=params)
        if response.status_code == 200:
            return [GeocodingResponse(**item) for item in response.json()]
    return None


def get_weather_map_urls() -> WeatherMapResponse:
    """
    Generates tile URL templates for various weather map layers.
    Note: This function does not make an API call but constructs the URLs
    based on the OpenWeatherMap tile server structure. The API key is
    embedded in the URL.

    Returns:
        A WeatherMapResponse object containing URLs for different layers.
    """
    layers = {
        "precipitation": "precipitation_new",
        "clouds": "clouds_new",
        "pressure": "pressure_new",
        "temperature": "temp_new",
        "wind": "wind_new",
    }

    map_layers = {}
    api_key = _require_api_key()
    for name, layer_code in layers.items():
        url = f"{MAP_BASE_URL}/{layer_code}/{{z}}/{{x}}/{{y}}.png?appid={api_key}"
        map_layers[name] = WeatherMapLayer(layer=layer_code, url=url)

    return WeatherMapResponse(**map_layers)


# Example of how to use the map URL function:
#
# map_urls = get_weather_map_urls()
# print(f"Temperature Map URL: {map_urls.temperature.url}")
#
# # To get a specific tile, you would replace {z}, {x}, and {y}
# # e.g., for zoom level 1, x=0, y=0
# specific_tile_url = map_urls.temperature.url.format(z=1, x=0, y=0)
# print(f"Specific Tile URL: {specific_tile_url}")
