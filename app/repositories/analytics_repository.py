from sqlalchemy import text
from sqlalchemy.orm import Session


# --- SUPER ADMIN ---

def get_financial_health(db: Session):
    query = text("""
                 SELECT subscription_status as status, COUNT(*) as total
                 FROM tenants
                 GROUP BY subscription_status
                 """)
    return db.execute(query).mappings().all()


def get_commercial_distribution(db: Session):
    query = text("""
                 SELECT subscription_plan as plan, COUNT(*) as total
                 FROM tenants
                 GROUP BY subscription_plan
                 """)
    return db.execute(query).mappings().all()


def get_storage_consumption(db: Session):
    query = text("""
                 WITH storage_data AS (SELECT issue_date as date_val
                                       FROM documents
                                       UNION ALL
                                       SELECT created_at::date as date_val
                                       FROM dicom_instances)
                 SELECT TO_CHAR(date_val, 'YYYY-MM') as month, COUNT(*) as total_documents
                 FROM storage_data
                 WHERE date_val IS NOT NULL
                 GROUP BY TO_CHAR(date_val, 'YYYY-MM')
                 ORDER BY month ASC
                 LIMIT 6
                 """)
    return db.execute(query).mappings().all()


# --- ADMIN DE CLÍNICA ---

def get_workflow_funnel(db: Session, tenant_id: str):
    query = text("""
                 SELECT status, COUNT(*) as total
                 FROM documents
                 WHERE tenant_id = :tenant_id
                 GROUP BY status
                 """)
    return db.execute(query, {"tenant_id": tenant_id}).mappings().all()


def get_medical_studies_volume(db: Session, tenant_id: str):
    query = text("""
                 SELECT COUNT(*) as total_studies
                 FROM dicom_studies
                 WHERE tenant_id = :tenant_id
                 """)
    return db.execute(query, {"tenant_id": tenant_id}).mappings().first()


def get_critical_alerts(db: Session, tenant_id: str):
    query = text("""
                 SELECT id, status, issue_date, expiry_date
                 FROM documents
                 WHERE tenant_id = :tenant_id
                   AND expiry_date IS NOT NULL
                   AND expiry_date <= CURRENT_DATE + INTERVAL '30 days'
                 ORDER BY expiry_date ASC
                 LIMIT 10
                 """)
    return db.execute(query, {"tenant_id": tenant_id}).mappings().all()


# --- PLAN USAGE ---

def get_plan_usage(db: Session, tenant_id: str):
    query = text("""
                 WITH plan_limits AS (SELECT pl.resource_key, pl.resource_value
                                      FROM plan_limits pl
                                               JOIN plans p ON pl.plan_id = p.id
                                               JOIN tenants t ON t.subscription_plan::text = p.name
                                      WHERE t.id = :tenant_id),
                      counts AS (SELECT (SELECT COUNT(*) FROM users WHERE tenant_id = :tenant_id)              AS user_count,
                                        (SELECT COUNT(*) FROM patients WHERE tenant_id = :tenant_id)           AS patient_count,
                                        (SELECT COUNT(*) FROM documents WHERE tenant_id = :tenant_id)          AS document_count,
                                        (SELECT COUNT(*) FROM document_templates WHERE tenant_id = :tenant_id) AS template_count,
                                        (SELECT COUNT(*) FROM dicom_studies WHERE tenant_id = :tenant_id)      AS dicom_count,
                                        (SELECT COUNT(*) FROM roles WHERE tenant_id = :tenant_id)              AS role_count,
                                        (SELECT COALESCE(SUM(file_size_bytes), 0)
                                         FROM documents
                                         WHERE tenant_id = :tenant_id)
                                            + (SELECT COALESCE(SUM(file_size_bytes), 0)
                                               FROM dicom_instances
                                               WHERE tenant_id = :tenant_id)
                                                                                                               AS storage_bytes,
                                        (SELECT COALESCE(call_count, 0)
                                         FROM api_call_usage
                                         WHERE tenant_id = :tenant_id
                                           AND year_month = to_char(CURRENT_DATE, 'YYYY-MM'))
                                                                                                               AS api_calls,
                                        (SELECT COALESCE(SUM(ocr.pages_processed), 0)
                                         FROM document_ocr_metadata ocr
                                                  JOIN documents d ON ocr.document_id = d.id
                                         WHERE d.tenant_id = :tenant_id
                                           AND ocr.created_at >= date_trunc('month', CURRENT_DATE))
                                                                                                               AS ocr_pages)
                 SELECT c.user_count,
                        c.patient_count,
                        c.document_count,
                        c.template_count,
                        c.dicom_count,
                        c.role_count,
                        c.storage_bytes,
                        c.api_calls,
                        c.ocr_pages,
                        MAX(CASE WHEN pl.resource_key = 'maxUsers' THEN pl.resource_value END)             AS max_users,
                        MAX(CASE WHEN pl.resource_key = 'maxStorageMB' THEN pl.resource_value END)         AS max_storage_mb,
                        MAX(CASE WHEN pl.resource_key = 'maxPatients' THEN pl.resource_value END)          AS max_patients,
                        MAX(CASE WHEN pl.resource_key = 'maxDocuments' THEN pl.resource_value END)         AS max_documents,
                        MAX(CASE
                                WHEN pl.resource_key = 'maxDocumentTemplates'
                                    THEN pl.resource_value END)                                            AS max_templates,
                        MAX(CASE WHEN pl.resource_key = 'maxDicomStudies' THEN pl.resource_value END)      AS max_dicom,
                        MAX(CASE WHEN pl.resource_key = 'maxStaffRoles' THEN pl.resource_value END)        AS max_roles,
                        MAX(CASE
                                WHEN pl.resource_key = 'maxApiCallsPerMonth'
                                    THEN pl.resource_value END)                                            AS max_api_calls,
                        MAX(CASE
                                WHEN pl.resource_key = 'maxOcrPagesPerMonth'
                                    THEN pl.resource_value END)                                            AS max_ocr_pages
                 FROM counts c,
                      plan_limits pl
                 GROUP BY c.user_count, c.patient_count, c.document_count,
                          c.template_count, c.dicom_count, c.role_count, c.storage_bytes,
                          c.api_calls, c.ocr_pages
                 """)
    return db.execute(query, {"tenant_id": tenant_id}).mappings().first()
