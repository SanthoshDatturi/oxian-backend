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

from app.ai.prompts.prompt_manager import PromptManager
from app.ai.tools.weather import WEATHER_TOOLS
from app.core.config import settings
from app.core.errors import (
    CultivationCropNotFound,
    DependencyUnavailable,
    ErrorCode,
    FarmProfileNotFound,
    InternalOperationFailed,
)
from app.infrastructure.providers.gemini import is_gemini_dependency_error
from app.repositories import (
    process_repository,
)
from app.schemas.agricultural_input_recommendation import (
    AgriculturalInputRecommendationDocument,
    AgriculturalInputRecommendationTranslatableFields,
)
from app.schemas.cultivation_task import (
    CultivationTaskDocument,
    CultivationTaskTranslatableFields,
    Priority,
    TaskState,
)
from app.schemas.investment_breakdown import (
    InvestmentBreakdownDocument,
    InvestmentBreakdownTranslatableFields,
)
from app.schemas.process import Process, ProcessError, State
from app.services import (
    agricultural_input_service,
    cultivation_crop_service,
    cultivation_task_service,
    farm_profile_service,
    investment_breakdown_service,
    translation_service,
)
from app.workers.process_manager import process_manager
from app.workers.queue import enqueue

logger = logging.getLogger(__name__)


class CropPlan(BaseModel):
    tasks: List[CultivationTaskDocument]
    investment_breakdown: InvestmentBreakdownDocument
    inputs: List[AgriculturalInputRecommendationDocument]


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


def _build_system_prompt(
    *,
    cultivation_calendar_schema_json: str,
    investment_breakdown_schema_json: str,
    agricultural_input_recommendation_schema_json: str,
) -> str:
    today = date.today()
    iso_week = today.isocalendar()
    return PromptManager.get_prompt(
        "crop_planning",
        current_date=today.isoformat(),
        current_iso_week=f"Year {iso_week.year} / Week {iso_week.week}",
        current_month=today.strftime("%B %Y"),
        current_season_hint=_season_hint(today),
        cultivation_calendar_schema_json=cultivation_calendar_schema_json,
        investment_breakdown_schema_json=investment_breakdown_schema_json,
        agricultural_input_recommendation_schema_json=agricultural_input_recommendation_schema_json,
    )


def _build_user_message(
    *,
    farm_profile_json: str,
    crop_json: str,
    intercropping_details_json: str | None,
) -> HumanMessage:
    content = (
        "FARM PROFILE (English):\n"
        f"{farm_profile_json}\n\n"
        "SELECTED CROP (English):\n"
        f"{crop_json}\n\n"
    )
    if intercropping_details_json:
        content += f"INTERCROPPING DETAILS (English):\n{intercropping_details_json}"
    return HumanMessage(content=content)


async def _run_job(
    *,
    process: Process,
    user_id: str,
    farm_id: str,
    crop_id: str,
    future: asyncio.Future[CropPlan],
) -> None:
    try:
        process_task = asyncio.current_task()
        if process_task is None:
            raise InternalOperationFailed("No running task for process execution.")
        process_manager.register(process.id, process_task)

        process.status = State.RUNNING
        await process_repository.save(process)

        # Load English farm profile
        farm_profile = await farm_profile_service._get_farm_profile(
            farm_id=farm_id,
            user_id=user_id,
        )
        if farm_profile is None:
            raise FarmProfileNotFound(farm_id)

        farm_profile_json = json.dumps(
            farm_profile.model_dump(
                mode="json",
                exclude={"id", "user_id", "created_at", "updated_at"},
                exclude_none=True,
            ),
            indent=2,
        )

        crop = await cultivation_crop_service._get_cultivation_crop(
            crop_id=crop_id,
            farm_id=farm_id,
        )
        if crop is None:
            raise CultivationCropNotFound(crop_id)

        crop_json = json.dumps(
            crop.model_dump(
                mode="json",
                exclude={
                    "id",
                    "farm_id",
                    "created_at",
                    "updated_at",
                    "recommendation_id",
                    "intercropping_id",
                    "image_file_id",
                },
                exclude_none=True,
            ),
            indent=2,
        )

        intercropping_details_json = None
        if crop.intercropping_id:
            intercropping_details = (
                await cultivation_crop_service._get_intercropping_details(
                    intercropping_id=crop.intercropping_id
                )
            )
            if intercropping_details:
                intercropping_details_json = json.dumps(
                    intercropping_details.model_dump(
                        mode="json",
                        exclude={
                            "id",
                            "created_at",
                            "updated_at",
                            "recommendation_id",
                        },
                        exclude_none=True,
                    ),
                    indent=2,
                )

        class SaveInvestmentBreakdownInput(BaseModel):
            breakdown_json: str = Field(
                description="The complete investment breakdown as a single JSON string matching the InvestmentBreakdownTranslatableFields schema."
            )

        class SaveCultivationTasksInput(BaseModel):
            tasks_json: str = Field(
                description=(
                    "A JSON string representing a list of objects, each containing: "
                    "- 'task': CultivationTaskTranslatableFields (including sequence_number, planned_start_date, planned_end_date, priority, skippable inside the task object for planning purposes) "
                    "- 'input_recommendation': Optional AgriculturalInputRecommendationTranslatableFields"
                )
            )

        saved_breakdown: InvestmentBreakdownDocument | None = None
        saved_tasks: List[CultivationTaskDocument] = []
        saved_inputs: List[AgriculturalInputRecommendationDocument] = []

        @tool(args_schema=SaveInvestmentBreakdownInput)
        async def save_investment_breakdown(breakdown_json: str) -> dict[str, str]:
            """Save the complete investment breakdown. Call this once."""
            nonlocal saved_breakdown
            try:
                raw_data = json.loads(breakdown_json)
                english_fields = InvestmentBreakdownTranslatableFields.model_validate(
                    raw_data
                )
            except Exception as exc:
                return {"status": "error", "message": f"Validation failed: {exc}"}

            try:
                user_lang_fields = await translation_service.to_user_language(
                    user_id=user_id, fields=english_fields
                )
            except DependencyUnavailable:
                raise
            except Exception:
                logger.exception("Translation failed for investment breakdown")
                user_lang_fields = english_fields

            doc = InvestmentBreakdownDocument(
                crop_id=crop_id,
                english=english_fields,
                user_language=user_lang_fields,
            )
            saved_breakdown = (
                await investment_breakdown_service._create_investment_breakdown(doc)
            )
            return {"status": "saved", "breakdown_id": doc.id}

        @tool(args_schema=SaveCultivationTasksInput)
        async def save_cultivation_tasks(tasks_json: str) -> dict[str, Any]:
            """Save the cultivation tasks and their associated input recommendations. Call this once."""
            nonlocal saved_tasks, saved_inputs
            try:
                raw_data = json.loads(tasks_json)
                if not isinstance(raw_data, list):
                    return {"status": "error", "message": "Expected a list of objects."}

                for item in raw_data:
                    task_raw = item.get("task")
                    input_raw = item.get("input_recommendation")

                    if not task_raw:
                        continue

                    task_english = CultivationTaskTranslatableFields.model_validate(
                        task_raw
                    )
                    try:
                        task_user_lang = await translation_service.to_user_language(
                            user_id=user_id, fields=task_english
                        )
                    except DependencyUnavailable:
                        raise
                    except Exception:
                        task_user_lang = task_english

                    input_id = None
                    if input_raw:
                        input_english = AgriculturalInputRecommendationTranslatableFields.model_validate(
                            input_raw
                        )
                        try:
                            input_user_lang = (
                                await translation_service.to_user_language(
                                    user_id=user_id, fields=input_english
                                )
                            )
                        except DependencyUnavailable:
                            raise
                        except Exception:
                            input_user_lang = input_english

                        input_doc = AgriculturalInputRecommendationDocument(
                            cultivation_crop_id=crop_id,
                            english=input_english,
                            user_language=input_user_lang,
                        )
                        input_doc = await agricultural_input_service._create_agricultural_input_recommendation(
                            input_doc
                        )
                        saved_inputs.append(input_doc)
                        input_id = input_doc.id

                    # We extract invariant fields from the task_raw since the agent generated them
                    # inside the task object for planning purposes.
                    try:
                        seq_num = int(task_raw.get("sequence_number", 1))
                        start_date = date.fromisoformat(
                            task_raw.get("planned_start_date")
                        )
                        end_date = date.fromisoformat(task_raw.get("planned_end_date"))
                        priority = Priority(task_raw.get("priority", "medium"))
                        skippable = bool(task_raw.get("skippable", False))
                    except Exception as exc:
                        logger.warning(
                            f"Failed to parse invariant fields for task: {exc}"
                        )
                        seq_num = 1
                        start_date = date.today()
                        end_date = date.today()
                        priority = Priority.MEDIUM
                        skippable = False

                    task_english.agricultural_input_recommendation_id = input_id
                    task_user_lang.agricultural_input_recommendation_id = input_id

                    task_doc = CultivationTaskDocument(
                        crop_id=crop_id,
                        sequence_number=seq_num,
                        planned_start_date=start_date,
                        planned_end_date=end_date,
                        status=TaskState.PENDING,
                        priority=priority,
                        skippable=skippable,
                        english=task_english,
                        user_language=task_user_lang,
                    )
                    task_doc = await cultivation_task_service._create_cultivation_task(
                        task_doc
                    )
                    saved_tasks.append(task_doc)

            except Exception as exc:
                return {"status": "error", "message": f"Processing failed: {exc}"}

            return {
                "status": "saved",
                "tasks_count": len(saved_tasks),
                "inputs_count": len(saved_inputs),
            }

        # Schema JSONs for prompt
        class PlanningTaskSchema(CultivationTaskTranslatableFields):
            sequence_number: int
            planned_start_date: date
            planned_end_date: date
            priority: Priority
            skippable: bool

        class TaskInputCombined(BaseModel):
            task: PlanningTaskSchema
            input_recommendation: Optional[
                AgriculturalInputRecommendationTranslatableFields
            ]

        system_prompt = _build_system_prompt(
            cultivation_calendar_schema_json=json.dumps(
                TaskInputCombined.model_json_schema(), indent=2
            ),
            investment_breakdown_schema_json=json.dumps(
                InvestmentBreakdownTranslatableFields.model_json_schema(), indent=2
            ),
            agricultural_input_recommendation_schema_json=json.dumps(
                AgriculturalInputRecommendationTranslatableFields.model_json_schema(),
                indent=2,
            ),
        )

        user_message = _build_user_message(
            farm_profile_json=farm_profile_json,
            crop_json=crop_json,
            intercropping_details_json=intercropping_details_json,
        )

        all_tools = [
            *WEATHER_TOOLS,
            save_investment_breakdown,
            save_cultivation_tasks,
        ]

        agent = create_agent(
            model=ChatGoogleGenerativeAI(
                model=settings.GEMINI_CHAT_MODEL,
                temperature=0.8,
            ),
            tools=all_tools,
            system_prompt=system_prompt,
        )

        await agent.ainvoke({"messages": [user_message]})

        if not saved_breakdown or not saved_tasks:
            raise InternalOperationFailed("Agent did not complete the planning output.")

        try:
            await process_repository.delete(process.id)
        except Exception:
            logger.exception(
                "Failed to delete process after completion process_id=%s", process.id
            )

        try:
            future.set_result(
                CropPlan(
                    tasks=saved_tasks,
                    investment_breakdown=saved_breakdown,
                    inputs=saved_inputs,
                )
            )
        except asyncio.InvalidStateError:
            pass

    except asyncio.CancelledError:
        logger.info("Crop planning job was cancelled process_id=%s", process.id)
        try:
            await process_repository.delete(process.id)
        except Exception:
            logger.exception(
                "Failed to delete process after cancellation process_id=%s", process.id
            )
        future.cancel()
    except Exception as exc:
        if is_gemini_dependency_error(exc):
            exc = DependencyUnavailable(
                "Planning service is temporarily unavailable.",
                code=ErrorCode.AI_PROVIDER_UNAVAILABLE,
            )
        logger.exception("Failed to run crop planning job process_id=%s", process.id)
        process.status = State.FAILED
        process.error = ProcessError(
            code="planning_error",
            message="Failed to run crop planning job.",
        )
        await process_repository.save(process)
        try:
            future.set_exception(exc)
        except asyncio.InvalidStateError:
            pass
    finally:
        process_manager.remove(process.id)


async def generate_crop_plan(
    *,
    user_id: str,
    farm_id: str,
    crop_id: str,
) -> CropPlan:
    process = Process(status=State.PENDING)
    process = await process_repository.create(process)

    future: asyncio.Future[CropPlan] = asyncio.get_event_loop().create_future()

    async def _job() -> None:
        await _run_job(
            process=process,
            user_id=user_id,
            farm_id=farm_id,
            crop_id=crop_id,
            future=future,
        )

    await enqueue(_job)
    return await future
