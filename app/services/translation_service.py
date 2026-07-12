import json
from typing import TypeVar

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from app.ai.prompts.prompt_manager import PromptManager
from app.core.config import settings
from app.core.errors import DependencyUnavailable, ErrorCode
from app.infrastructure.providers.gemini import is_gemini_dependency_error
from app.repositories import user_pref_repository

T = TypeVar("T", bound=BaseModel)


async def _get_user_preference_json(user_id: str) -> str:
    preference = await user_pref_repository.get_by_user_id(user_id)
    if preference is None:
        return json.dumps({"language_code": None}, indent=2)

    return json.dumps(preference.model_dump(mode="json"), indent=2)


async def _translate_model(
    *,
    user_id: str,
    fields: T,
    source_language: str,
    target_language: str,
) -> T:
    model_type = type(fields)
    model = ChatGoogleGenerativeAI(
        model=settings.GEMINI_CHAT_MODEL,
        temperature=0,
    ).with_structured_output(model_type)

    try:
        response = await model.ainvoke(
            PromptManager.get_prompt(
                "translation",
                source_language=source_language,
                target_language=target_language,
                user_preference_json=await _get_user_preference_json(user_id),
                data_json=json.dumps(fields.model_dump(mode="json"), indent=2),
                output_schema_json=json.dumps(model_type.model_json_schema(), indent=2),
            )
        )
    except Exception as exc:
        if not is_gemini_dependency_error(exc):
            raise
        raise DependencyUnavailable(
            "Translation service is temporarily unavailable.",
            code=ErrorCode.AI_PROVIDER_UNAVAILABLE,
        ) from exc

    return model_type.model_validate(response)


async def to_english(*, user_id: str, fields: T) -> T:
    return await _translate_model(
        user_id=user_id,
        fields=fields,
        source_language="user provided language, dialect, or slang",
        target_language="formal clear English for LLM analysis",
    )


async def to_user_language(*, user_id: str, fields: T) -> T:
    return await _translate_model(
        user_id=user_id,
        fields=fields,
        source_language="formal clear English",
        target_language="the user's preferred language, dialect, and locale from user preferences",
    )
