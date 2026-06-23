import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.security import authenticate_rest
from app.integrations.storage.errors import StorageError
from app.schemas.crop_image import CropImageFile
from app.services import crop_image_service

router = APIRouter(prefix="/admin", tags=["Admin"])

templates = Jinja2Templates(directory="app/templates/admin")


def _firebase_web_config() -> dict[str, str | None]:
    return {
        "apiKey": settings.FIREBASE_WEB_API_KEY,
        "authDomain": settings.FIREBASE_AUTH_DOMAIN,
        "projectId": settings.FIREBASE_PROJECT_ID,
    }


def _firebase_template_context() -> dict[str, str]:
    firebase_config = _firebase_web_config()
    missing_config = not firebase_config["apiKey"] or not firebase_config["authDomain"]
    return {
        "firebase_config_json": json.dumps(firebase_config),
        "missing_config_json": json.dumps(missing_config),
    }


def _parse_aliases(aliases: str | None) -> list[str] | None:
    if not aliases:
        return None

    normalized = [
        alias.strip()
        for chunk in aliases.splitlines()
        for alias in chunk.split(",")
        if alias.strip()
    ]
    return normalized or None


async def require_admin(
    user_payload: dict = Depends(authenticate_rest),
) -> dict:
    if user_payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_payload


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context=_firebase_template_context(),
    )


@router.get("/crop-images", response_class=HTMLResponse)
async def crop_image_upload_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="crop_images.html",
        context=_firebase_template_context(),
    )


@router.post("/crop-images", response_model=CropImageFile, status_code=201)
async def upload_crop_image(
    file: UploadFile = File(...),
    crop_name: str = Form(...),
    aliases: str | None = Form(default=None),
    _: dict = Depends(require_admin),
) -> CropImageFile:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Image file is required")

    try:
        return await crop_image_service.upload_new_image(
            file_stream=file.file,
            crop_name=crop_name,
            mime_type=file.content_type,
            aliases=_parse_aliases(aliases),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
