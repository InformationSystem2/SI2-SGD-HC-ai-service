from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session
from app.database import get_db # Asumiendo que tu get_db está en app.database
from app.services import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["Dashboard Analytics"])

# --- SUPER ADMIN ---
@router.get("/superadmin/subscriptions")
def get_subscriptions(db: Session = Depends(get_db)):
    return {"data": analytics_service.get_superadmin_financial_health(db)}

@router.get("/superadmin/commercial-distribution")
def get_commercial_distribution(db: Session = Depends(get_db)):
    return {"data": analytics_service.get_superadmin_commercial_distribution(db)}

@router.get("/superadmin/storage-consumption")
def get_storage_consumption(db: Session = Depends(get_db)):
    return {"data": analytics_service.get_superadmin_storage_consumption(db)}

# --- ADMIN DE CLÍNICA ---
@router.get("/clinic/{tenant_id}/workflow")
def get_workflow_funnel(tenant_id: str = Path(...), db: Session = Depends(get_db)):
    return {"data": analytics_service.get_clinic_workflow_funnel(db, tenant_id)}

@router.get("/clinic/{tenant_id}/medical-studies")
def get_medical_studies_volume(tenant_id: str = Path(...), db: Session = Depends(get_db)):
    return {"data": analytics_service.get_clinic_medical_studies(db, tenant_id)}

@router.get("/clinic/{tenant_id}/critical-alerts")
def get_critical_alerts(tenant_id: str = Path(...), db: Session = Depends(get_db)):
    return {"data": analytics_service.get_clinic_critical_alerts(db, tenant_id)}

@router.get("/clinic/{tenant_id}/plan-usage")
def get_plan_usage(tenant_id: str = Path(...), db: Session = Depends(get_db)):
    return {"data": analytics_service.get_clinic_plan_usage(db, tenant_id)}