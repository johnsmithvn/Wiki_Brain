from fastapi import APIRouter, HTTPException, Query

from backend.models.schemas import TemplateContent, TemplateListResponse
from backend.services.template_service import template_service

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=TemplateListResponse)
async def list_templates(folder: str = Query("template")):
    try:
        templates = template_service.list_templates(folder=folder)
        return TemplateListResponse(templates=templates, total=len(templates))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{path:path}", response_model=TemplateContent)
async def get_template(path: str):
    try:
        return template_service.read_template(path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Template not found: {path}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
