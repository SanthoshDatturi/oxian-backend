import asyncio
import json
import logging
from datetime import date
from typing import Any, List, Optional

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.ai.tools.weather import WEATHER_TOOLS
from app.core.config import settings
from app.workers.process_manager import process_manager
from app.workers.queue import enqueue
from app.ai.prompts.prompt_manager import PromptManager
from app.repositories import (
    crop_recommendation_repository,
    farm_profile_repository,
    process_repository,
)
from app.schemas.crop_recommendation import (
    CropRecommendation,
    CropRecommendationDocument,
    CropRecommendationFields,
    CropRecommendationRequest,
    SelectCropRequest,
)
from app.schemas.cultivation_crop import CropState, CultivationCropDocument
from app.schemas.generic_types import Area, PersistenceLanguage
from app.schemas.intercropping_details import (
    IntercroppingDetailsDocument,
    IntercroppingDetailsTranslatableFields,
)
from app.schemas.notification import (
    Destination,
    DestinationType,
    NotificationContent,
    NotificationRequest,
    NotificationTarget,
    NotificationTargetType,
    Screen,
)
from app.schemas.process import Process, ProcessError, State
from app.services import (
    crop_image_service,
    cultivation_crop_service,
    farm_profile_service,
    notification_service,
    translation_service,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_MONTH_SEASON: dict[int, str] = {
    1: "Winter / Rabi",
    2: "Winter / Rabi",
    3: "Spring / Pre-Kharif",
    4: "Spring / Pre-Kharif",
    5: "Summer / Zaid",
    6: "Early Kharif / Monsoon onset",
    7: "Kharif / Monsoon",
    8: "Kharif / Monsoon",
    9: "Late Kharif / Monsoon withdrawal",
    10: "Post-Kharif / Pre-Rabi",
    11: "Rabi sowing",
    12: "Rabi / Winter",
}


def _season_hint(today: date) -> str:
    return _MONTH_SEASON.get(today.month, "Unknown")


async def _send_recommendation_ready_notification(
    *,
    user_id: str,
    farm_name: str,
    recommendation_id: str,
) -> None:
    await notification_service.send_notification(
        NotificationRequest(
            target=NotificationTarget(
                type=NotificationTargetType.USER,
                user_id=user_id,
            ),
            content=NotificationContent(
                title="Crop recommendation ready",
                body=f"Crop recommendation for {farm_name} ready to view",
            ),
            destination=Destination(
                type=DestinationType.APP_ROUTE,
                screen=Screen.CROP_RECOMMENDATION,
                params={"recommendation_id": recommendation_id},
            ),
        )
    )


# ---------------------------------------------------------------------------
# Tool input schemas
# ---------------------------------------------------------------------------


class SearchCropImagesInput(BaseModel):
    """Input schema for search_crop_images tool."""

    crop_names: List[str] = Field(
        description="List of all crop names to search images for."
    )


class RequestCropImageGenerationInput(BaseModel):
    """Input schema for request_crop_image_generation tool."""

    crop_name: str = Field(description="Name of the crop to generate an image for.")
    aliases: Optional[List[str]] = Field(
        default=None,
        description="Alternative names or local names for the crop.",
    )


# ---------------------------------------------------------------------------
# Crop-image tools (LangChain @tool — run automatically by the agent)
# ---------------------------------------------------------------------------


@tool(args_schema=SearchCropImagesInput)
async def search_crop_images(
    crop_names: list[str],
) -> list[dict[str, Any]]:
    """Search the crop image library for existing images matching multiple crop names at once.

    Accepts a list of all crop names that need images.
    Returns a list of HybridCropImageSearchResult objects, one per crop name if image present,
    each containing keyword_matches and similarity_matches with their crop_name,
    id, and aliases.

    Use the returned matches to select the best image_file_id for each crop
    based on crop name and aliases. If no suitable match exists for a crop
    or crop_name is not present in results, call request_crop_image_generation for that crop.
    """
    try:
        results = await crop_image_service.crops_image_search(crop_names)
        return [r.model_dump(mode="json") for r in results if r is not None]
    except Exception:
        logger.exception("search_crop_images failed for crop_names=%s", crop_names)
        return [
            {
                "crop_name": name,
                "keyword_matches": [],
                "similarity_matches": [],
            }
            for name in crop_names
        ]


@tool(args_schema=RequestCropImageGenerationInput)
async def request_crop_image_generation(
    crop_name: str, aliases: list[str] | None = None
) -> str | None:
    """Register a new crop image generation request when no suitable image exists
    in the search results for a crop.

    Returns the file_id to use as image_file_id in the recommendation, or None on failure.
    """
    try:
        return await crop_image_service.generate_new_crop_image(
            crop_name=crop_name,
            aliases=aliases,
        )
    except Exception:
        logger.exception(
            "request_crop_image_generation failed for crop_name=%s", crop_name
        )
        return None


CROP_IMAGE_TOOLS = [search_crop_images, request_crop_image_generation]


# ---------------------------------------------------------------------------
# Prompt & user-message builders
# ---------------------------------------------------------------------------


def _build_system_prompt(
    *,
    output_schema_json: str,
) -> str:
    today = date.today()
    iso_week = today.isocalendar()
    return PromptManager.get_prompt(
        "crop_recommendation",
        current_date=today.isoformat(),
        current_iso_week=f"Year {iso_week.year} / Week {iso_week.week}",
        current_month=today.strftime("%B %Y"),
        current_season_hint=_season_hint(today),
        output_schema_json=output_schema_json,
    )


def _build_user_message(
    *,
    farm_profile_json: str,
    request_json: str,
) -> HumanMessage:
    """
    Inject farm profile and recommendation request as the user turn.

    Only data is placed here — all instructions live in the system prompt.
    """
    content = (
        "FARM PROFILE (English):\n"
        f"{farm_profile_json}\n\n"
        "RECOMMENDATION REQUEST:\n"
        f"{request_json}"
    )
    return HumanMessage(content=content)


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Core job — mirrors _run_turn in chat_service.py
# ---------------------------------------------------------------------------


async def _run_job(
    *,
    process: Process,
    user_id: str,
    farm_id: str,
    request: CropRecommendationRequest,
    future: asyncio.Future[CropRecommendation],
) -> None:
    try:
        process_task = asyncio.current_task()
        if process_task is None:
            raise RuntimeError("No running task for process execution.")
        process_manager.register(process.id, process_task)

        process.status = State.RUNNING
        await process_repository.save(process)

        # --- Load English farm profile -----------------------------------------
        farm_profile = await farm_profile_repository.get_by_id(
            farm_id=farm_id,
            language=PersistenceLanguage.ENGLISH,
            user_id=user_id,
        )
        if farm_profile is None:
            raise ValueError(f"Farm profile not found: farm_id={farm_id}")

        farm_profile_json = json.dumps(
            farm_profile.model_dump(
                mode="json",
                exclude={"id", "user_id", "created_at", "updated_at"},
                exclude_none=True,
            ),
            indent=2,
        )
        request_json = json.dumps(request.model_dump(mode="json"), indent=2)

        output_schema_json = json.dumps(
            CropRecommendationFields.model_json_schema(), indent=2
        )

        # --- Build prompt & user message ---------------------------------------
        system_prompt = _build_system_prompt(output_schema_json=output_schema_json)
        user_message = _build_user_message(
            farm_profile_json=farm_profile_json,
            request_json=request_json,
        )

        # --- save_crop_recommendation tool (defined inside _run_job) -----------
        saved_recommendation: CropRecommendation | None = None

        class SaveCropRecommendationInput(BaseModel):
            """Input schema for save_crop_recommendation tool."""

            recommendation_json: str = Field(
                description=(
                    "The complete crop recommendation as a single JSON string "
                    "matching the CropRecommendationFields schema provided in the "
                    "system prompt. Must include mono_crop_candidates, "
                    "inter_crop_candidates, reasoning_report, and expiration_date."
                )
            )

        @tool(args_schema=SaveCropRecommendationInput)
        async def save_crop_recommendation(
            recommendation_json: str,
        ) -> dict[str, str]:
            """Save the complete crop recommendation. Call this once all recommendation
            fields are ready. Pass the entire recommendation as a single JSON string."""

            nonlocal saved_recommendation

            try:
                raw_data = json.loads(recommendation_json)
            except json.JSONDecodeError as exc:
                return {"status": "error", "message": f"Invalid JSON: {exc}"}

            try:
                english_fields = CropRecommendationFields.model_validate(raw_data)
            except Exception as exc:
                return {
                    "status": "error",
                    "message": f"Schema validation failed: {exc}",
                }

            # --- Translate to user language ------------------------------------
            try:
                user_language_fields = await translation_service.to_user_language(
                    user_id=user_id, fields=english_fields
                )
            except Exception:
                logger.exception(
                    "Translation failed for farm_id=%s; using English for both slots.",
                    farm_id,
                )
                user_language_fields = english_fields

            # --- Persist -------------------------------------------------------
            doc = CropRecommendationDocument(
                farm_id=farm_id,
                request=request,
                english=english_fields,
                user_language=user_language_fields,
            )
            doc = await crop_recommendation_repository.create(doc)

            saved_recommendation = CropRecommendation.model_validate(
                {
                    **user_language_fields.model_dump(mode="json"),
                    "id": doc.id,
                    "farm_id": farm_id,
                    "request": request.model_dump(mode="json"),
                    "created_at": doc.created_at,
                }
            )

            return {
                "recommendation_id": doc.id,
                "farm_id": farm_id,
                "status": "saved",
            }

        # --- Create agent with all tools ---------------------------------------
        all_tools = [
            *WEATHER_TOOLS,
            *CROP_IMAGE_TOOLS,
            save_crop_recommendation,
        ]
        agent = create_agent(
            model=ChatGoogleGenerativeAI(
                model=settings.GEMINI_CHAT_MODEL,
                temperature=1.0,  # Required for Gemini 2.5 thinking mode
            ),
            tools=all_tools,
            system_prompt=system_prompt,
        )

        await agent.ainvoke({"messages": [user_message]})

        if saved_recommendation is None:
            raise RuntimeError("Agent did not call save_crop_recommendation tool.")

        try:
            await process_repository.delete(process.id)
        except Exception:
            logger.exception(
                "Failed to delete process after completion process_id=%s", process.id
            )

        try:
            future.set_result(saved_recommendation)
        except asyncio.InvalidStateError:
            logger.info(
                "Recommendation future already completed; sending notification process_id=%s recommendation_id=%s",
                process.id,
                saved_recommendation.id,
            )
            await _send_recommendation_ready_notification(
                user_id=user_id,
                farm_name=farm_profile.name,
                recommendation_id=saved_recommendation.id,
            )

    except asyncio.CancelledError:
        logger.info("Crop recommendation job was cancelled process_id=%s", process.id)
        try:
            await process_repository.delete(process.id)
        except Exception:
            logger.exception(
                "Failed to delete process after cancellation process_id=%s", process.id
            )
        future.cancel()
    except Exception as exc:
        logger.exception(
            "Failed to run crop recommendation job process_id=%s", process.id
        )
        process.status = State.FAILED
        process.error = ProcessError(
            code="recommendation_error",
            message="Failed to run crop recommendation job.",
        )
        await process_repository.save(process)
        try:
            future.set_exception(exc)
        except asyncio.InvalidStateError:
            logger.info(
                "Recommendation future already completed while reporting failure process_id=%s",
                process.id,
            )
    finally:
        process_manager.remove(process.id)


# ---------------------------------------------------------------------------
# Enqueue wrapper — mirrors _enqueue_turn in chat_service.py
# ---------------------------------------------------------------------------


async def _enqueue_job(
    *,
    process: Process,
    user_id: str,
    farm_id: str,
    request: CropRecommendationRequest,
    future: asyncio.Future[CropRecommendation],
) -> None:
    async def _job() -> None:
        await _run_job(
            process=process,
            user_id=user_id,
            farm_id=farm_id,
            request=request,
            future=future,
        )

    await enqueue(_job)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_crop_recommendation(
    *,
    user_id: str,
    farm_id: str,
    request: CropRecommendationRequest,
) -> CropRecommendation:
    """
    Start a crop recommendation job for a farm.

    Creates a Process, enqueues the job, and awaits the result.
    """
    if not await farm_profile_service.has_farm_access(farm_id=farm_id, user_id=user_id):
        raise ValueError(f"Farm profile not found: farm_id={farm_id}")

    process = Process(status=State.PENDING)
    process = await process_repository.create(process)

    future: asyncio.Future[CropRecommendation] = (
        asyncio.get_event_loop().create_future()
    )
    await _enqueue_job(
        process=process,
        user_id=user_id,
        farm_id=farm_id,
        request=request,
        future=future,
    )
    return await future


async def get_recommendation(
    *,
    user_id: str,
    recommendation_id: str,
    farm_id: str | None = None,
) -> CropRecommendation | None:
    """Fetch a single crop recommendation in the user's language."""

    recommendation = await crop_recommendation_repository.get_by_id(
        recommendation_id=recommendation_id,
        language=PersistenceLanguage.USER_LANGUAGE,
        farm_id=farm_id,
    )
    if recommendation is None:
        return None

    if not await farm_profile_service.has_farm_access(
        farm_id=recommendation.farm_id, user_id=user_id
    ):
        raise ValueError(f"Farm profile not found: farm_id={recommendation.farm_id}")

    return recommendation


async def _get_recommendation(
    *,
    recommendation_id: str,
    farm_id: str | None = None,
) -> CropRecommendation | None:
    """Fetch a single crop recommendation in English for system interaction."""
    return await crop_recommendation_repository.get_by_id(
        recommendation_id=recommendation_id,
        language=PersistenceLanguage.ENGLISH,
        farm_id=farm_id,
    )


async def list_recommendations(
    *,
    user_id: str,
    farm_id: str,
    limit: int = 20,
) -> list[CropRecommendation]:
    """List crop recommendations for a farm in the user's language, newest first."""
    if not await farm_profile_service.has_farm_access(farm_id=farm_id, user_id=user_id):
        return []

    return await crop_recommendation_repository.list_by_farm(
        farm_id=farm_id,
        language=PersistenceLanguage.USER_LANGUAGE,
        limit=limit,
    )


async def delete_recommendation(
    *,
    user_id: str,
    recommendation_id: str,
    farm_id: str | None = None,
) -> bool:
    """Delete a single crop recommendation by ID."""
    farm_id = farm_id or await crop_recommendation_repository.get_farm_id_by_id(
        recommendation_id
    )
    if not farm_id:
        return False
    if not await farm_profile_service.has_farm_access(farm_id=farm_id, user_id=user_id):
        raise ValueError(f"Farm profile not found: farm_id={farm_id}")

    return await crop_recommendation_repository.delete(
        recommendation_id=recommendation_id,
        farm_id=farm_id,
    )


async def delete_all_recommendations_for_farm(*, user_id: str, farm_id: str) -> int:
    """Delete all crop recommendations for a farm. Returns count deleted."""
    if not await farm_profile_service.has_farm_access(farm_id=farm_id, user_id=user_id):
        raise ValueError(f"Farm profile not found: farm_id={farm_id}")

    return await crop_recommendation_repository.delete_all_by_farm(farm_id=farm_id)


async def select_mono_crop_from_recommendation(
    *,
    user_id: str,
    farm_id: str,
    recommendation_id: str,
    crop_id: str,
    selected_area: Area,
) -> CultivationCropDocument:
    """
    Materialize a selected monocrop candidate from a recommendation into a CultivationCrop.
    """
    if not await farm_profile_service.has_farm_access(
        farm_id=farm_id,
        user_id=user_id,
    ):
        raise ValueError(f"Farm profile not found: farm_id={farm_id}")

    doc = await crop_recommendation_repository.get_document_by_id(
        recommendation_id=recommendation_id,
    )
    if not doc:
        raise ValueError("Recommendation not found")

    # Search in mono crop candidates
    for candidate_idx, candidate in enumerate(doc.english.mono_crop_candidates):
        if candidate.id == crop_id:
            user_lang_candidate = doc.user_language.mono_crop_candidates[candidate_idx]

            cultivation_crop = CultivationCropDocument(
                id=candidate.id,
                farm_id=farm_id,
                recommendation_id=recommendation_id,
                intercropping_id=None,
                crop_state=CropState.SELECTED,
                selected_area=selected_area,
                english=candidate,
                user_language=user_lang_candidate,
            )
            saved_crop = await cultivation_crop_service._create_cultivation_crop(
                cultivation_crop
            )
            return saved_crop

    raise ValueError(
        f"Mono crop candidate {crop_id} not found in recommendation {recommendation_id}"
    )


async def select_intercrop_from_recommendation(
    *,
    user_id: str,
    farm_id: str,
    recommendation_id: str,
    intercrop_id: str,
    payload: list[SelectCropRequest],
) -> tuple[list[CultivationCropDocument], IntercroppingDetailsDocument]:
    """
    Materialize a selected intercrop candidate from a recommendation into CultivationCrop(s)
    and an IntercroppingDetails document.
    """
    if not await farm_profile_service.has_farm_access(
        farm_id=farm_id,
        user_id=user_id,
    ):
        raise ValueError(f"Farm profile not found: farm_id={farm_id}")

    doc = await crop_recommendation_repository.get_document_by_id(
        recommendation_id=recommendation_id,
    )
    if not doc:
        raise ValueError("Recommendation not found")

    selected_areas = {req.crop_id: req.selected_area for req in payload}

    # Search in inter crop candidates
    for candidate_idx, candidate in enumerate(doc.english.inter_crop_candidates):
        if candidate.id == intercrop_id:
            user_lang_candidate = doc.user_language.inter_crop_candidates[candidate_idx]

            intercropping_details = IntercroppingDetailsDocument(
                id=candidate.id,
                recommendation_id=recommendation_id,
                intercrop_type=candidate.intercrop_type,
                english=IntercroppingDetailsTranslatableFields.model_validate(
                    candidate.model_dump()
                ),
                user_language=IntercroppingDetailsTranslatableFields.model_validate(
                    user_lang_candidate.model_dump()
                ),
            )
            saved_details = (
                await cultivation_crop_service._create_intercropping_details(
                    intercropping_details
                )
            )

            saved_crops = []
            for comp_idx, component in enumerate(candidate.crops):
                user_lang_component = user_lang_candidate.crops[comp_idx]
                area = selected_areas.get(component.id)
                if not area:
                    raise ValueError(f"Selected area missing for crop {component.id}")

                cultivation_crop = CultivationCropDocument(
                    id=component.id,
                    farm_id=farm_id,
                    recommendation_id=recommendation_id,
                    intercropping_id=saved_details.id,
                    crop_state=CropState.SELECTED,
                    selected_area=area,
                    english=component,
                    user_language=user_lang_component,
                )
                saved_crops.append(
                    await cultivation_crop_service._create_cultivation_crop(
                        cultivation_crop
                    )
                )

            return saved_crops, saved_details

    raise ValueError(
        f"Intercrop candidate {intercrop_id} not found in recommendation {recommendation_id}"
    )
