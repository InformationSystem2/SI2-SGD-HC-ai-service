from sqlalchemy.orm import Session
from app.repositories import analytics_repository

# --- SUPER ADMIN ---
def get_superadmin_financial_health(db: Session):
    return analytics_repository.get_financial_health(db)

def get_superadmin_commercial_distribution(db: Session):
    return analytics_repository.get_commercial_distribution(db)

def get_superadmin_storage_consumption(db: Session):
    return analytics_repository.get_storage_consumption(db)

# --- ADMIN DE CLÍNICA ---
def get_clinic_workflow_funnel(db: Session, tenant_id: str):
    return analytics_repository.get_workflow_funnel(db, tenant_id)

def get_clinic_medical_studies(db: Session, tenant_id: str):
    return analytics_repository.get_medical_studies_volume(db, tenant_id)

def get_clinic_critical_alerts(db: Session, tenant_id: str):
    return analytics_repository.get_critical_alerts(db, tenant_id)

# --- PLAN USAGE ---
def get_clinic_plan_usage(db: Session, tenant_id: str):
    return analytics_repository.get_plan_usage(db, tenant_id)