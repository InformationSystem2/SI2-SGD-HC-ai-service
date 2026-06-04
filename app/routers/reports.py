import uuid
from typing import List
from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import CurrentUser, require_permission
from app.repositories.report_repository import ReportRepository
from app.services.report_service import ReportService
from app.schemas.report_schemas import (
    ReportRunRequest,
    ReportResult,
    ReportTemplateCreate,
    ReportTemplateUpdate,
    ReportTemplateResponse,
    ReportTypeDefinition
)

router = APIRouter(prefix="/api/reports", tags=["Reports"])

def get_report_service(db: Session = Depends(get_db)) -> ReportService:
    repo = ReportRepository(db)
    return ReportService(repo)

@router.get("/catalog", response_model=List[ReportTypeDefinition])
def get_catalog(
    user: CurrentUser = Depends(require_permission("report:read")),
    service: ReportService = Depends(get_report_service)
):
    return service.get_catalog(user)

@router.post("/run", response_model=ReportResult)
def run_report(
    req: ReportRunRequest,
    user: CurrentUser = Depends(require_permission("report:read")),
    service: ReportService = Depends(get_report_service)
):
    return service.run_report(req, user)

@router.post("/export")
def export_report(
    req: ReportRunRequest,
    format: str = Query("pdf"),
    user: CurrentUser = Depends(require_permission("report:read")),
    service: ReportService = Depends(get_report_service)
):
    file_bytes, media_type, filename = service.export_report(req, format, user)
    
    # HTML response is handled specifically as HTMLResponse
    if format.lower() == "html":
        return HTMLResponse(content=file_bytes.decode('utf-8'))
        
    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

# --- Plantillas QBE CRUD ---

@router.get("/templates", response_model=List[ReportTemplateResponse])
def list_templates(
    user: CurrentUser = Depends(require_permission("report:read")),
    service: ReportService = Depends(get_report_service)
):
    return service.list_templates(user)

@router.post("/templates", response_model=ReportTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(
    req: ReportTemplateCreate,
    user: CurrentUser = Depends(require_permission("template:create")),
    service: ReportService = Depends(get_report_service)
):
    return service.create_template(req, user)

@router.put("/templates/{id}", response_model=ReportTemplateResponse)
def update_template(
    id: uuid.UUID,
    req: ReportTemplateUpdate,
    user: CurrentUser = Depends(require_permission("template:update")),
    service: ReportService = Depends(get_report_service)
):
    return service.update_template(id, req, user)

@router.delete("/templates/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    id: uuid.UUID,
    user: CurrentUser = Depends(require_permission("template:delete")),
    service: ReportService = Depends(get_report_service)
):
    service.delete_template(id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
