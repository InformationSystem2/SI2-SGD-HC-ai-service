import uuid
from typing import List
from fastapi import APIRouter, Depends, Query, Response, status, File, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.database import get_db
from app.auth import CurrentUser, require_permission
from app.repositories.report_repository import ReportRepository
from app.services.report_service import ReportService
from app.services.report_ai_service import ReportAIService
from app.schemas.report_schemas import (
    ReportRunRequest,
    ReportResult,
    ReportTemplateCreate,
    ReportTemplateUpdate,
    ReportTemplateResponse,
    ReportTypeDefinition,
    PromptReportRequest,
    AIReportResponse
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


@router.post("/prompt", response_model=AIReportResponse)
def run_report_by_prompt(
    req: PromptReportRequest,
    user: CurrentUser = Depends(require_permission("report:read")),
    service: ReportService = Depends(get_report_service)
):
    parsed_req = ReportAIService.parse_prompt(req.prompt)
    if not parsed_req:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo interpretar el prompt del reporte. Intenta ser más específico."
        )

    report_type = parsed_req.get("reportType") or parsed_req.get("report_type")
    selected_fields = parsed_req.get("selectedFields") or parsed_req.get("selected_fields") or []
    
    if not report_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo identificar el tipo de reporte en la solicitud."
        )

    raw_filters = parsed_req.get("filters") or []
    filters = []
    for f in raw_filters:
        field = f.get("field")
        operator = str(f.get("operator") or "EQ").upper()
        value = f.get("value")
        if field:
            filters.append({
                "field": field,
                "operator": operator,
                "value": value
            })

    sort_field = parsed_req.get("sortField") or parsed_req.get("sort_field")
    sort_order = parsed_req.get("sortOrder") or parsed_req.get("sort_order") or "asc"
    limit = parsed_req.get("limit") or parsed_req.get("limit_val") or 50
    offset = parsed_req.get("offset") or 0

    run_req = ReportRunRequest(
        reportType=report_type,
        selectedFields=selected_fields,
        filters=filters,
        sortField=sort_field,
        sortOrder=sort_order,
        limit=limit,
        offset=offset
    )

    result = service.run_report(run_req, user)
    return AIReportResponse(query=run_req, result=result)


@router.post("/audio", response_model=AIReportResponse)
def run_report_by_audio(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(require_permission("report:read")),
    service: ReportService = Depends(get_report_service)
):
    file_bytes = file.file.read()
    
    transcript = ReportAIService.transcribe_audio(file_bytes, file.filename)
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo transcribir el audio o no contiene voz legible."
        )

    parsed_req = ReportAIService.parse_prompt(transcript)
    if not parsed_req:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transcripción: '{transcript}'. No se pudo interpretar como un reporte. Intenta hablar más claro."
        )

    report_type = parsed_req.get("reportType") or parsed_req.get("report_type")
    selected_fields = parsed_req.get("selectedFields") or parsed_req.get("selected_fields") or []
    
    if not report_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transcripción: '{transcript}'. No se pudo identificar el tipo de reporte en la solicitud."
        )

    raw_filters = parsed_req.get("filters") or []
    filters = []
    for f in raw_filters:
        field = f.get("field")
        operator = str(f.get("operator") or "EQ").upper()
        value = f.get("value")
        if field:
            filters.append({
                "field": field,
                "operator": operator,
                "value": value
            })

    sort_field = parsed_req.get("sortField") or parsed_req.get("sort_field")
    sort_order = parsed_req.get("sortOrder") or parsed_req.get("sort_order") or "asc"
    limit = parsed_req.get("limit") or parsed_req.get("limit_val") or 50
    offset = parsed_req.get("offset") or 0

    run_req = ReportRunRequest(
        reportType=report_type,
        selectedFields=selected_fields,
        filters=filters,
        sortField=sort_field,
        sortOrder=sort_order,
        limit=limit,
        offset=offset
    )

    result = service.run_report(run_req, user)
    return AIReportResponse(transcript=transcript, query=run_req, result=result)

