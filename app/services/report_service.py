import uuid
import json
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from fastapi import HTTPException, status

from app.auth import CurrentUser
from app.repositories.report_repository import ReportRepository
from app.models.report_template import ReportTemplateModel
from app.services.catalog import ReportCatalog
from app.services.exporter import export_to_excel, export_to_pdf, export_to_html
from app.schemas.report_schemas import (
    ReportRunRequest,
    ReportResult,
    ReportTemplateCreate,
    ReportTemplateUpdate,
    ReportTemplateResponse,
    ReportTypeDefinition,
    FieldDefinition,
    FieldDefinition
)

class ReportService:
    def __init__(self, repo: ReportRepository):
        self.repo = repo
        self.catalog = ReportCatalog()

    def get_catalog(self, user: CurrentUser) -> List[ReportTypeDefinition]:
        is_superuser = "ROLE_SUPERUSER" in user.roles
        
        # Query tenants for options if superuser
        tenant_options = []
        if is_superuser:
            try:
                from sqlalchemy import text
                query = text("SELECT DISTINCT name FROM tenants ORDER BY name ASC")
                results = self.repo.db.execute(query).fetchall()
                tenant_options = [{"value": r[0], "label": r[0]} for r in results if r[0]]
            except Exception as e:
                # Fallback to empty if query fails
                tenant_options = []

        available_reports = []
        for r in self.catalog.all():
            if user.has_permission(r.required_authority):
                fields = []
                for f in r.fields.values():
                    if f.key == "tenantName" and not is_superuser:
                        continue
                    
                    opts = tenant_options if f.key == "tenantName" else None
                    
                    fields.append(
                        FieldDefinition(
                            key=f.key,
                            label=f.label,
                            kind=f.kind.value,
                            type=f.type.value,
                            options=opts
                        )
                    )
                available_reports.append(
                    ReportTypeDefinition(
                        key=r.key,
                        label=r.label,
                        category=r.category.value,
                        requiredAuthority=r.required_authority,
                        fields=fields
                    )
                )
        return available_reports

    def run_report(self, req: ReportRunRequest, user: CurrentUser) -> ReportResult:
        try:
            report_type = self.catalog.require(req.reportType)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        if not user.has_permission(report_type.required_authority):
            raise HTTPException(status_code=403, detail="Acceso denegado a este reporte")

        is_superuser = "ROLE_SUPERUSER" in user.roles

        if not is_superuser:
            if "tenantName" in req.selectedFields:
                req.selectedFields = [f for f in req.selectedFields if f != "tenantName"]
            req.filters = [f for f in req.filters if f.field != "tenantName"]
            if req.sortField == "tenantName":
                req.sortField = None

        columns, column_labels, rows, total, applied_filters = self.repo.execute_report_query(
            report_type=report_type,
            tenant_id=user.tenant_id,
            selected_fields=req.selectedFields,
            filters=req.filters,
            sort_field=req.sortField,
            sort_order=req.sortOrder,
            date_from=req.dateFrom.strftime("%Y-%m-%d") if req.dateFrom else None,
            date_to=req.dateTo.strftime("%Y-%m-%d") if req.dateTo else None,
            limit=req.limit,
            offset=req.offset,
            is_superuser=is_superuser
        )

        return ReportResult(
            reportType=report_type.key,
            reportLabel=report_type.label,
            category=report_type.category.value,
            columns=columns,
            columnLabels=column_labels,
            rows=rows,
            total=total,
            offset=req.offset,
            limit=req.limit,
            generatedAt=datetime.now().strftime("%Y-%m-%d %H:%M"),
            appliedFilters=applied_filters
        )

    def export_report(self, req: ReportRunRequest, format: str, user: CurrentUser) -> Tuple[bytes, str, str]:
        try:
            report_type = self.catalog.require(req.reportType)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        if not user.has_permission(report_type.required_authority):
            raise HTTPException(status_code=403, detail="Acceso denegado a este reporte")

        is_superuser = "ROLE_SUPERUSER" in user.roles

        if not is_superuser:
            if "tenantName" in req.selectedFields:
                req.selectedFields = [f for f in req.selectedFields if f != "tenantName"]
            req.filters = [f for f in req.filters if f.field != "tenantName"]
            if req.sortField == "tenantName":
                req.sortField = None

        # Force limit to 5000 for safety in exports
        columns, column_labels, rows, total, applied_filters = self.repo.execute_report_query(
            report_type=report_type,
            tenant_id=user.tenant_id,
            selected_fields=req.selectedFields,
            filters=req.filters,
            sort_field=req.sortField,
            sort_order=req.sortOrder,
            date_from=req.dateFrom.strftime("%Y-%m-%d") if req.dateFrom else None,
            date_to=req.dateTo.strftime("%Y-%m-%d") if req.dateTo else None,
            limit=5000,
            offset=0,
            is_superuser=is_superuser
        )

        # Overwrite column labels with translated labels if sent from frontend
        if req.translatedLabels:
            for k, v in req.translatedLabels.items():
                if v:
                    column_labels[k] = v

        report_title = req.translatedTitle or report_type.label
        report_category = req.translatedCategory or report_type.category.value
        filename = f"reporte_{report_type.key}_{int(datetime.now().timestamp())}"

        if format.lower() == "excel":
            file_bytes = export_to_excel(
                report_label=report_title,
                category=report_category,
                columns=columns,
                column_labels=column_labels,
                rows=rows,
                total=total,
                applied_filters=applied_filters
            )
            return file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"{filename}.xlsx"

        elif format.lower() == "json":
            json_data = {
                "reportLabel": report_title,
                "category": report_category,
                "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "appliedFilters": applied_filters,
                "total": total,
                "columns": columns,
                "columnLabels": column_labels,
                "rows": rows
            }
            file_bytes = json.dumps(json_data, indent=2, default=str).encode('utf-8')
            return file_bytes, "application/json", f"{filename}.json"

        elif format.lower() == "html":
            html_str = export_to_html(
                report_label=report_title,
                category=report_category,
                columns=columns,
                column_labels=column_labels,
                rows=rows,
                total=total,
                applied_filters=applied_filters
            )
            return html_str.encode('utf-8'), "text/html", f"{filename}.html"

        else:  # pdf
            file_bytes = export_to_pdf(
                report_label=report_title,
                category=report_category,
                columns=columns,
                column_labels=column_labels,
                rows=rows,
                total=total,
                applied_filters=applied_filters
            )
            return file_bytes, "application/pdf", f"{filename}.pdf"

    def list_templates(self, user: CurrentUser) -> List[ReportTemplateResponse]:
        user_db = self.repo.get_user_db_details(user.username, user.tenant_id)
        user_uuid = user_db["id"]

        results = self.repo.list_templates(user.tenant_id, user_uuid)
        
        templates = []
        for r in results:
            templates.append(
                ReportTemplateResponse(
                    id=r.id,
                    name=r.name,
                    description=r.description,
                    department=r.department,
                    reportType=r.report_type,
                    selectedFields=r.selected_fields,
                    filters=r.filters,
                    sortField=r.sort_field,
                    sortOrder=r.sort_order,
                    isShared=r.is_shared,
                    ownerId=r.owner_id,
                    ownerName=r.owner_name,
                    createdAt=r.created_at,
                    updatedAt=r.updated_at
                )
            )
        return templates

    def create_template(self, req: ReportTemplateCreate, user: CurrentUser) -> ReportTemplateResponse:
        user_db = self.repo.get_user_db_details(user.username, user.tenant_id)
        user_uuid = user_db["id"]

        try:
            self.catalog.require(req.reportType)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        new_template = ReportTemplateModel(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(user.tenant_id),
            owner_id=user_uuid,
            name=req.name,
            description=req.description,
            department=req.department,
            report_type=req.reportType,
            selected_fields=req.selectedFields,
            filters=[f.model_dump() for f in req.filters],
            sort_field=req.sortField,
            sort_order=req.sortOrder,
            is_shared=req.isShared
        )

        created = self.repo.create_template(new_template)

        return ReportTemplateResponse(
            id=created.id,
            name=created.name,
            description=created.description,
            department=created.department,
            reportType=created.report_type,
            selectedFields=created.selected_fields,
            filters=created.filters,
            sortField=created.sort_field,
            sortOrder=created.sort_order,
            isShared=created.is_shared,
            ownerId=created.owner_id,
            ownerName=user_db["full_name"],
            createdAt=created.created_at,
            updatedAt=created.updated_at
        )

    def update_template(self, template_id: uuid.UUID, req: ReportTemplateUpdate, user: CurrentUser) -> ReportTemplateResponse:
        user_db = self.repo.get_user_db_details(user.username, user.tenant_id)
        user_uuid = user_db["id"]

        template = self.repo.get_template_by_id(template_id, uuid.UUID(user.tenant_id))
        if not template:
            raise HTTPException(status_code=404, detail="Plantilla no encontrada")

        if template.owner_id != user_uuid:
            raise HTTPException(
                status_code=403,
                detail="Sólo el propietario puede modificar esta plantilla"
            )

        if req.name is not None:
            template.name = req.name
        if req.description is not None:
            template.description = req.description
        if req.department is not None:
            template.department = req.department
        if req.selectedFields is not None:
            template.selected_fields = req.selectedFields
        if req.filters is not None:
            template.filters = [f.model_dump() for f in req.filters]
        if req.sortField is not None:
            template.sort_field = req.sortField
        if req.sortOrder is not None:
            template.sort_order = req.sortOrder
        if req.isShared is not None:
            template.is_shared = req.isShared

        self.repo.update_template()

        return ReportTemplateResponse(
            id=template.id,
            name=template.name,
            description=template.description,
            department=template.department,
            reportType=template.report_type,
            selectedFields=template.selected_fields,
            filters=template.filters,
            sortField=template.sort_field,
            sortOrder=template.sort_order,
            isShared=template.is_shared,
            ownerId=template.owner_id,
            ownerName=user_db["full_name"],
            createdAt=template.created_at,
            updatedAt=template.updated_at
        )

    def delete_template(self, template_id: uuid.UUID, user: CurrentUser) -> None:
        user_db = self.repo.get_user_db_details(user.username, user.tenant_id)
        user_uuid = user_db["id"]

        template = self.repo.get_template_by_id(template_id, uuid.UUID(user.tenant_id))
        if not template:
            raise HTTPException(status_code=404, detail="Plantilla no encontrada")

        if template.owner_id != user_uuid:
            raise HTTPException(
                status_code=403,
                detail="Sólo el propietario puede eliminar esta plantilla"
            )

        self.repo.delete_template(template)
