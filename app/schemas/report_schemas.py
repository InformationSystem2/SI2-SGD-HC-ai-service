import uuid
from datetime import datetime
from typing import Any, Optional, List, Dict
from pydantic import BaseModel, Field

class ReportFilter(BaseModel):
    field: str
    operator: str  # eq, ne, gt, lt, gte, lte, like, is_null, is_not_null
    value: Optional[Any] = None

class ReportRunRequest(BaseModel):
    reportType: str
    selectedFields: List[str] = Field(min_length=1)
    filters: List[ReportFilter] = []
    sortField: Optional[str] = None
    sortOrder: str = "asc"
    dateFrom: Optional[datetime] = None
    dateTo: Optional[datetime] = None
    limit: int = Field(default=100, le=5000)
    offset: int = 0
    translatedTitle: Optional[str] = None
    translatedCategory: Optional[str] = None
    translatedLabels: Optional[Dict[str, str]] = None

class ReportTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    department: Optional[str] = None
    reportType: str
    selectedFields: List[str] = Field(min_length=1)
    filters: List[ReportFilter] = []
    sortField: Optional[str] = None
    sortOrder: str = "asc"
    isShared: bool = False

class ReportTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    department: Optional[str] = None
    selectedFields: Optional[List[str]] = None
    filters: Optional[List[ReportFilter]] = None
    sortField: Optional[str] = None
    sortOrder: Optional[str] = None
    isShared: Optional[bool] = None

class ReportTemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    department: Optional[str] = None
    reportType: str
    selectedFields: List[str]
    filters: List[Any]
    sortField: Optional[str] = None
    sortOrder: str
    isShared: bool
    ownerId: uuid.UUID
    ownerName: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    class Config:
        from_attributes = True

class FieldOption(BaseModel):
    value: str
    label: str

class FieldDefinition(BaseModel):
    key: str
    label: str
    kind: str
    type: str
    options: Optional[List[FieldOption]] = None

class ReportTypeDefinition(BaseModel):
    key: str
    label: str
    category: str
    requiredAuthority: str
    fields: List[FieldDefinition]

class ReportResult(BaseModel):
    reportType: str
    reportLabel: str
    category: str
    columns: List[str]
    columnLabels: Dict[str, str]
    rows: List[Dict[str, Any]]
    total: int
    offset: int
    limit: int
    generatedAt: str
    appliedFilters: List[str]

class PromptReportRequest(BaseModel):
    prompt: str

class AIReportResponse(BaseModel):
    transcript: Optional[str] = None
    query: ReportRunRequest
    result: ReportResult

