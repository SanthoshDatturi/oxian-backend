import logging

import httpx
from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user_id
from app.core.errors import (
    DependencyUnavailable,
    ErrorCode,
    ExternalServiceFailed,
    WeatherDataNotFound,
)
from app.infrastructure.weather import open_weather
from app.infrastructure.weather.errors import (
    WeatherConfigurationError,
    WeatherProviderError,
)
from app.schemas.weather import (
    AirPollutionResponse,
    CurrentWeatherResponse,
    ForecastResponse,
    WeatherMapResponse,
)

router = APIRouter(prefix="/weather", tags=["Weather"])
logger = logging.getLogger(__name__)


async def _fetch_weather_data(fetcher, *args):
    try:
        result = await fetcher(*args)
    except WeatherConfigurationError as exc:
        raise DependencyUnavailable(
            "Weather service is temporarily unavailable.",
            code=ErrorCode.DEPENDENCY_UNAVAILABLE,
        ) from exc
    except (WeatherProviderError, httpx.HTTPError) as exc:
        logger.exception("OpenWeather request failed.")
        raise ExternalServiceFailed("Unable to fetch weather data right now.") from exc

    if result is None:
        raise WeatherDataNotFound()
    return result


@router.get("/current", response_model=CurrentWeatherResponse)
async def get_current_weather(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    _: str = Depends(get_current_user_id),
) -> CurrentWeatherResponse:
    return await _fetch_weather_data(
        open_weather.get_current_weather,
        lat,
        lon,
    )


@router.get("/forecast", response_model=ForecastResponse)
async def get_forecast(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    _: str = Depends(get_current_user_id),
) -> ForecastResponse:
    return await _fetch_weather_data(
        open_weather.get_5_day_3_hour_forecast,
        lat,
        lon,
    )


@router.get("/air-pollution", response_model=AirPollutionResponse)
async def get_air_pollution(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    _: str = Depends(get_current_user_id),
) -> AirPollutionResponse:
    return await _fetch_weather_data(
        open_weather.get_air_pollution,
        lat,
        lon,
    )


@router.get("/map-layers", response_model=WeatherMapResponse)
async def get_weather_map_layers(
    _: str = Depends(get_current_user_id),
) -> WeatherMapResponse:
    try:
        return open_weather.get_weather_map_urls()
    except WeatherConfigurationError as exc:
        raise DependencyUnavailable(
            "Weather service is temporarily unavailable.",
            code=ErrorCode.DEPENDENCY_UNAVAILABLE,
        ) from exc
