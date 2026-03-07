import unittest
from unittest.mock import AsyncMock, patch

from app.schemas.chat import ChatMode
from app.schemas.farm_profile import (
    Area,
    AreaUnit,
    FarmProfile,
    Location,
    SoilType,
    WaterSource,
)
from app.schemas.generic_types import LatLang
from app.services.chat import service


class ChatServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_general_mode_exposes_only_weather_tools(self):
        tool_names = {
            tool.name for tool in service._get_tools_for_mode(ChatMode.GENERAL)
        }

        self.assertEqual(
            tool_names,
            {
                "get_current_weather",
                "get_5_day_3_hour_forecast",
                "get_air_pollution",
                "get_reverse_geocoding",
            },
        )

    def test_farm_survey_mode_exposes_only_save_tool(self):
        tool_names = {
            tool.name for tool in service._get_tools_for_mode(ChatMode.FARM_SURVEY)
        }

        self.assertEqual(tool_names, {"save_farm_profile"})

    async def test_save_farm_profile_tool_returns_saved_reference(self):
        profile = FarmProfile(
            user_id="user-1",
            name="My Farm",
            location=Location(
                lat_lang=LatLang(latitude=14.5, longitude=78.8),
                state="Andhra Pradesh",
                country="India",
                postal_code="516172",
            ),
            soil_type=SoilType.BLACK,
            total_area=Area(value=5, unit=AreaUnit.ACRE),
            cultivated_area=Area(value=4, unit=AreaUnit.ACRE),
            water_source=WaterSource.BOREWELL,
        )

        with patch.object(
            service.farm_profile_repository,
            "save",
            AsyncMock(return_value=profile),
        ) as save_mock:
            result = await service.save_farm_profile_tool.arun(
                {"profile": profile.model_dump(mode="json", exclude_none=True)}
            )

        save_mock.assert_awaited_once_with(profile)
        self.assertEqual(result, {"farm_id": profile.id, "name": "My Farm"})


if __name__ == "__main__":
    unittest.main()
