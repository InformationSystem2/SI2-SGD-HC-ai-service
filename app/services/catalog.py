from enum import Enum
from typing import List, Dict, Optional

class FieldType(str, Enum):
    STRING = "STRING"
    NUMBER = "NUMBER"
    DATE = "DATE"
    BOOLEAN = "BOOLEAN"

class FieldKind(str, Enum):
    PLAIN = "PLAIN"
    DIMENSION = "DIMENSION"
    MEASURE = "MEASURE"

class ReportCategory(str, Enum):
    QBE = "QBE"
    ANALYTICAL = "ANALYTICAL"
    MANAGERIAL = "MANAGERIAL"

class FilterOperator(str, Enum):
    EQ = "EQ"
    NE = "NE"
    GT = "GT"
    LT = "LT"
    GTE = "GTE"
    LTE = "LTE"
    LIKE = "LIKE"
    IS_NULL = "IS_NULL"
    IS_NOT_NULL = "IS_NOT_NULL"

    def sql_template(self) -> str:
        templates = {
            FilterOperator.EQ: "= :p",
            FilterOperator.NE: "!= :p",
            FilterOperator.GT: "> :p",
            FilterOperator.LT: "< :p",
            FilterOperator.GTE: ">= :p",
            FilterOperator.LTE: "<= :p",
            FilterOperator.LIKE: "LIKE :p",
            FilterOperator.IS_NULL: "IS NULL",
            FilterOperator.IS_NOT_NULL: "IS NOT NULL"
        }
        return templates.get(self, "= :p")

    def needs_value(self) -> bool:
        return self not in (FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL)

class ReportField:
    def __init__(self, key: str, label: str, sql: str, type: FieldType, kind: FieldKind = FieldKind.PLAIN, joins: List[str] = None):
        self.key = key
        self.label = label
        self.sql = sql
        self.type = type
        self.kind = kind
        self.joins = joins or []

    @classmethod
    def plain(cls, key: str, label: str, sql: str, type: FieldType, joins: List[str] = None):
        return cls(key, label, sql, type, FieldKind.PLAIN, joins)

    @classmethod
    def dimension(cls, key: str, label: str, sql: str, type: FieldType, joins: List[str] = None):
        return cls(key, label, sql, type, FieldKind.DIMENSION, joins)

    @classmethod
    def measure(cls, key: str, label: str, sql: str, type: FieldType, joins: List[str] = None):
        return cls(key, label, sql, type, FieldKind.MEASURE, joins)

    def to_dict(self):
        return {
            "key": self.key,
            "label": self.label,
            "type": self.type.value,
            "kind": self.kind.value
        }

class ReportType:
    def __init__(self, key: str, label: str, category: ReportCategory, required_authority: str,
                 from_clause: str, tenant_column: str, date_field: Optional[str],
                 joins: Dict[str, str], fields: List[ReportField]):
        self.key = key
        self.label = label
        self.category = category
        self.required_authority = required_authority
        self.from_clause = from_clause
        self.tenant_column = tenant_column
        self.date_field = date_field
        self.joins = joins
        self.fields = {f.key: f for f in fields}

    @property
    def is_aggregated(self) -> bool:
        return self.category in (ReportCategory.ANALYTICAL, ReportCategory.MANAGERIAL)

    def to_dict(self):
        return {
            "key": self.key,
            "label": self.label,
            "category": self.category.value,
            "isAggregated": self.is_aggregated,
            "fields": [f.to_dict() for f in self.fields.values()]
        }

class ReportCatalog:
    def __init__(self):
        self.types = {}
        self.register(self.build_patients())
        self.register(self.build_users())
        self.register(self.build_documents())
        self.register(self.build_templates())
        self.register(self.build_patients_by_gender())
        self.register(self.build_documents_by_status())
        self.register(self.build_documents_by_month())
        self.register(self.build_documents_by_template())

    def register(self, t: ReportType):
        self.types[t.key] = t

    def require(self, key: str) -> ReportType:
        if key not in self.types:
            raise ValueError(f"Tipo de reporte no encontrado: {key}")
        return self.types[key]

    def all(self) -> List[ReportType]:
        return list(self.types.values())

    # --- QBE / Detalle ---
    def build_patients(self) -> ReportType:
        return ReportType(
            key="patients",
            label="Pacientes",
            category=ReportCategory.QBE,
            required_authority="REPORT_READ",
            from_clause="patients p",
            tenant_column="p.tenant_id",
            date_field="p.created_at",
            joins={},
            fields=[
                ReportField.plain("documentNumber", "Nro. documento", "p.document_number", FieldType.STRING),
                ReportField.plain("documentType", "Tipo doc.", "CAST(p.document_type AS TEXT)", FieldType.STRING),
                ReportField.plain("firstName", "Nombre", "p.first_name", FieldType.STRING),
                ReportField.plain("lastName", "Apellido", "p.last_name", FieldType.STRING),
                ReportField.plain("fullName", "Nombre completo", "(p.first_name || ' ' || p.last_name)", FieldType.STRING),
                ReportField.plain("gender", "Género", "CAST(p.gender AS TEXT)", FieldType.STRING),
                ReportField.plain("birthDate", "Fecha nac.", "p.birth_date", FieldType.DATE),
                ReportField.plain("phone", "Teléfono", "p.phone", FieldType.STRING),
                ReportField.plain("address", "Dirección", "p.address", FieldType.STRING),
                ReportField.plain("createdAt", "Registrado", "p.created_at", FieldType.DATE)
            ]
        )

    def build_users(self) -> ReportType:
        return ReportType(
            key="users",
            label="Usuarios",
            category=ReportCategory.QBE,
            required_authority="REPORT_READ",
            from_clause="users u",
            tenant_column="u.tenant_id",
            date_field="u.created_at",
            joins={},
            fields=[
                ReportField.plain("username", "Usuario", "u.username", FieldType.STRING),
                ReportField.plain("firstName", "Nombre", "u.first_name", FieldType.STRING),
                ReportField.plain("lastName", "Apellido", "u.last_name", FieldType.STRING),
                ReportField.plain("email", "Email", "u.email", FieldType.STRING),
                ReportField.plain("documentNumber", "Nro. documento", "u.document_number", FieldType.STRING),
                ReportField.plain("phone", "Teléfono", "u.phone", FieldType.STRING),
                ReportField.plain("isActive", "Activo", "u.is_active", FieldType.BOOLEAN),
                ReportField.plain("roles", "Roles",
                                 "(SELECT string_agg(r.name, ', ') FROM role_user ru JOIN roles r ON r.id = ru.role_id WHERE ru.user_id = u.id)",
                                 FieldType.STRING),
                ReportField.plain("createdAt", "Registrado", "u.created_at", FieldType.DATE)
            ]
        )

    def build_documents(self) -> ReportType:
        return ReportType(
            key="documents",
            label="Documentos clínicos",
            category=ReportCategory.QBE,
            required_authority="REPORT_READ",
            from_clause="documents d",
            tenant_column="d.tenant_id",
            date_field="d.created_at",
            joins={
                "patient": "LEFT JOIN patients p ON p.id = d.patient_id",
                "uploader": "LEFT JOIN users u ON u.id = d.uploader_id",
                "template": "LEFT JOIN document_templates t ON t.id = d.template_id"
            },
            fields=[
                ReportField.plain("status", "Estado", "CAST(d.status AS TEXT)", FieldType.STRING),
                ReportField.plain("issueDate", "Fecha emisión", "d.issue_date", FieldType.DATE),
                ReportField.plain("expiryDate", "Vencimiento", "d.expiry_date", FieldType.DATE),
                ReportField.plain("versionNumber", "Versión", "d.version_number", FieldType.NUMBER),
                ReportField.plain("isExternal", "Origen externo", "d.is_external_source", FieldType.BOOLEAN),
                ReportField.plain("createdAt", "Creado", "d.created_at", FieldType.DATE),
                ReportField.plain("patientName", "Paciente", "(p.first_name || ' ' || p.last_name)", FieldType.STRING, ["patient"]),
                ReportField.plain("patientDocument", "Doc. paciente", "p.document_number", FieldType.STRING, ["patient"]),
                ReportField.plain("uploaderName", "Subido por", "(u.first_name || ' ' || u.last_name)", FieldType.STRING, ["uploader"]),
                ReportField.plain("templateName", "Plantilla", "COALESCE(t.name, '(sin plantilla)')", FieldType.STRING, ["template"])
            ]
        )

    def build_templates(self) -> ReportType:
        return ReportType(
            key="templates",
            label="Plantillas de documentos",
            category=ReportCategory.QBE,
            required_authority="REPORT_READ",
            from_clause="document_templates t",
            tenant_column="t.tenant_id",
            date_field="t.created_at",
            joins={},
            fields=[
                ReportField.plain("name", "Nombre", "t.name", FieldType.STRING),
                ReportField.plain("description", "Descripción", "t.description", FieldType.STRING),
                ReportField.plain("isActive", "Activa", "t.is_active", FieldType.BOOLEAN),
                ReportField.plain("fieldCount", "Nro. de campos", "(SELECT COUNT(*) FROM jsonb_object_keys(t.ui_schema))", FieldType.NUMBER),
                ReportField.plain("documentCount", "Documentos", "(SELECT COUNT(*) FROM documents d WHERE d.template_id = t.id)", FieldType.NUMBER),
                ReportField.plain("schemaDetail", "Detalle del esquema", 
                                  """(SELECT string_agg(
                                      CASE
                                        WHEN (fld.value->>'type') = 'ARRAY' THEN
                                          '[▼] ' || fld.key
                                            || ' [' || COALESCE(fld.value->>'type','?') || ']'
                                            || ' - ' || COALESCE(NULLIF(fld.value->>'label',''), fld.key)
                                            || CASE WHEN (fld.value->>'required')::boolean THEN ' *' ELSE '' END
                                            || COALESCE(
                                                (SELECT E'\\n' || string_agg(
                                                    '    › ' || sub.key
                                                    || ' [' || COALESCE(sub.value->>'type','?') || ']'
                                                    || ' - ' || COALESCE(NULLIF(sub.value->>'label',''), sub.key)
                                                    || CASE WHEN (sub.value->>'required')::boolean THEN ' *' ELSE '' END,
                                                    E'\\n' ORDER BY COALESCE(NULLIF(sub.value->>'order','')::int,0))
                                                 FROM jsonb_each(fld.value->'subSchema') AS sub
                                                 WHERE fld.value->'subSchema' IS NOT NULL
                                                ), '')
                                        ELSE
                                          fld.key
                                            || ' [' || COALESCE(fld.value->>'type','?') || ']'
                                            || ' - ' || COALESCE(NULLIF(fld.value->>'label',''), fld.key)
                                            || CASE WHEN (fld.value->>'required')::boolean THEN ' *' ELSE '' END
                                      END,
                                      E'\\n' ORDER BY COALESCE(NULLIF(fld.value->>'order','')::int,0))
                                     FROM jsonb_each(t.ui_schema) AS fld)""", FieldType.STRING),
                ReportField.plain("uiSchemaJson", "ui_schema (JSON)", "t.ui_schema::text", FieldType.STRING),
                ReportField.plain("formFields", "Campos (resumen)", 
                                  """(SELECT string_agg(COALESCE(NULLIF(fld.value->>'label', ''), fld.key), ', ' 
                                     ORDER BY COALESCE(NULLIF(fld.value->>'order', '')::int, 0)) 
                                     FROM jsonb_each(t.ui_schema) AS fld)""", FieldType.STRING),
                ReportField.plain("createdAt", "Creada", "t.created_at", FieldType.DATE),
                ReportField.plain("updatedAt", "Actualizada", "t.updated_at", FieldType.DATE)
            ]
        )

    # --- Analíticos / Gerenciales (agregados) ---
    def build_patients_by_gender(self) -> ReportType:
        return ReportType(
            key="patients_by_gender",
            label="Pacientes por género",
            category=ReportCategory.ANALYTICAL,
            required_authority="REPORT_READ",
            from_clause="patients p",
            tenant_column="p.tenant_id",
            date_field="p.created_at",
            joins={},
            fields=[
                ReportField.dimension("gender", "Género", "CAST(p.gender AS TEXT)", FieldType.STRING),
                ReportField.measure("total", "Total pacientes", "COUNT(*)", FieldType.NUMBER)
            ]
        )

    def build_documents_by_status(self) -> ReportType:
        return ReportType(
            key="documents_by_status",
            label="Documentos por estado",
            category=ReportCategory.MANAGERIAL,
            required_authority="REPORT_READ",
            from_clause="documents d",
            tenant_column="d.tenant_id",
            date_field="d.created_at",
            joins={},
            fields=[
                ReportField.dimension("status", "Estado", "CAST(d.status AS TEXT)", FieldType.STRING),
                ReportField.measure("total", "Total documentos", "COUNT(*)", FieldType.NUMBER)
            ]
        )

    def build_documents_by_month(self) -> ReportType:
        return ReportType(
            key="documents_by_month",
            label="Documentos por mes",
            category=ReportCategory.MANAGERIAL,
            required_authority="REPORT_READ",
            from_clause="documents d",
            tenant_column="d.tenant_id",
            date_field="d.created_at",
            joins={},
            fields=[
                ReportField.dimension("month", "Mes", "to_char(d.created_at, 'YYYY-MM')", FieldType.STRING),
                ReportField.measure("total", "Total documentos", "COUNT(*)", FieldType.NUMBER)
            ]
        )

    def build_documents_by_template(self) -> ReportType:
        return ReportType(
            key="documents_by_template",
            label="Documentos por plantilla",
            category=ReportCategory.MANAGERIAL,
            required_authority="REPORT_READ",
            from_clause="documents d",
            tenant_column="d.tenant_id",
            date_field="d.created_at",
            joins={
                "template": "LEFT JOIN document_templates t ON t.id = d.template_id"
            },
            fields=[
                ReportField.dimension("templateName", "Plantilla", "COALESCE(t.name, '(sin plantilla)')", FieldType.STRING, ["template"]),
                ReportField.measure("total", "Total documentos", "COUNT(*)", FieldType.NUMBER)
            ]
        )
