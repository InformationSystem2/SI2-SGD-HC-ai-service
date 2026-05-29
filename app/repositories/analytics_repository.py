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
        WITH storage_data AS (
            SELECT issue_date as date_val FROM documents
            UNION ALL
            SELECT created_at::date as date_val FROM dicom_instances
        )
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