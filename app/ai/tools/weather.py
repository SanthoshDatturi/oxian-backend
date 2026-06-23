from typing import Any

from langchain_core.tools import tool

from app.infrastructure.weather import open_weather


@tool
async def get_current_weather(lat: float, lon: float) -> dict[str, Any]:
    """Get current weather for latitude and longitude."""
    data = await open_weather.get_current_weather(lat=lat, lon=lon)
    return {"available": False} if data is None else data.model_dump(mode="json")


@tool
async def get_5_day_3_hour_forecast(lat: float, lon: float) -> dict[str, Any]:
    """Get 5 day forecast in 3 hour steps for latitude and longitude."""
    data = await open_weather.get_5_day_3_hour_forecast(lat=lat, lon=lon)
    return {"available": False} if data is None else data.model_dump(mode="json")


@tool
async def get_air_pollution(lat: float, lon: float) -> dict[str, Any]:
    """Get air pollution metrics for latitude and longitude."""
    data = await open_weather.get_air_pollution(lat=lat, lon=lon)
    return {"available": False} if data is None else data.model_dump(mode="json")


@tool
async def get_reverse_geocoding(lat: float, lon: float) -> dict[str, Any]:
    """Get reverse geocoding details for latitude and longitude."""
    data = await open_weather.get_reverse_geocoding(lat=lat, lon=lon)
    if data is None:
        return {"available": False}
    return {
        "available": True,
        "results": [item.model_dump(mode="json") for item in data],
    }


WEATHER_TOOLS = [
    get_current_weather,
    get_5_day_3_hour_forecast,
    get_air_pollution,
    get_reverse_geocoding,
]
