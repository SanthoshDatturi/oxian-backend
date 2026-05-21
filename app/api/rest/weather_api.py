import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import authenticate_rest
from app.integrations.weather import open_weather
from app.schemas.weather import (
    AirPollutionResponse,
    CurrentWeatherResponse,
    ForecastResponse,
    GeocodingResponse,
    WeatherMapResponse,
)

router = APIRouter(prefix="/weather", tags=["Weather"])
logger = logging.getLogger(__name__)


def _get_user_id(user_payload: dict) -> str:
    user_id = user_payload.get("uid") or user_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return user_id


async def _fetch_weather_data(fetcher, not_found_detail: str, *args):
    try:
        result = await fetcher(*args)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except httpx.HTTPError:
        logger.exception("OpenWeather request failed.")
        raise HTTPException(
            status_code=502,
            detail="Unable to fetch weather data right now.",
        )

    if result is None:
        raise HTTPException(status_code=404, detail=not_found_detail)
    return result


@router.get("/current", response_model=CurrentWeatherResponse)
async def get_current_weather(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    user_payload: dict = Depends(authenticate_rest),
) -> CurrentWeatherResponse:
    _get_user_id(user_payload)
    return await _fetch_weather_data(
        open_weather.get_current_weather,
        "Current weather data not found",
        lat,
        lon,
    )


@router.get("/forecast", response_model=ForecastResponse)
async def get_forecast(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    user_payload: dict = Depends(authenticate_rest),
) -> ForecastResponse:
    _get_user_id(user_payload)
    return await _fetch_weather_data(
        open_weather.get_5_day_3_hour_forecast,
        "Forecast data not found",
        lat,
        lon,
    )


@router.get("/air-pollution", response_model=AirPollutionResponse)
async def get_air_pollution(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    user_payload: dict = Depends(authenticate_rest),
) -> AirPollutionResponse:
    _get_user_id(user_payload)
    return await _fetch_weather_data(
        open_weather.get_air_pollution,
        "Air pollution data not found",
        lat,
        lon,
    )


@router.get("/reverse-geocoding", response_model=list[GeocodingResponse])
async def get_reverse_geocoding(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    user_payload: dict = Depends(authenticate_rest),
) -> list[GeocodingResponse]:
    _get_user_id(user_payload)
    return await _fetch_weather_data(
        open_weather.get_reverse_geocoding,
        "Reverse geocoding data not found",
        lat,
        lon,
    )


@router.get("/map-layers", response_model=WeatherMapResponse)
async def get_weather_map_layers(
    user_payload: dict = Depends(authenticate_rest),
) -> WeatherMapResponse:
    _get_user_id(user_payload)
    try:
        return open_weather.get_weather_map_urls()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
