import os
import psycopg2
import uuid
import random
from faker import Faker
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
os.environ["PGCLIENTENCODING"] = "LATIN1"
fake = Faker('es_ES')

def seed_analytical_data():
    db_url = os.getenv("DB_URL", "")
    if db_url.startswith("jdbc:"):
        db_url = db_url.replace("jdbc:", "", 1)
        
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    print("🌟 Iniciando inyección masiva en tus clínicas reales...")

    # 1. Obtener todas las clínicas creadas por Java (excepto el system)
    cursor.execute("SELECT id FROM tenants WHERE slug != 'system'")
    tenants = [row[0] for row in cursor.fetchall()]

    start_date = datetime.now() - timedelta(days=180)
    estados_doc = ['DRAFT', 'PENDING_REVIEW', 'REJECTED', 'FINALIZED']

    for tenant_id in tenants:
        # Obtener un uploader válido para esta clínica
        cursor.execute("SELECT id FROM users WHERE tenant_id = %s LIMIT 1", (tenant_id,))
        uploader_id = cursor.fetchone()[0]

        # Obtener los pacientes creados por Java
        cursor.execute("SELECT id FROM patients WHERE tenant_id = %s", (tenant_id,))
        patients = [row[0] for row in cursor.fetchall()]

        # 2. Inyectar Documentos y DICOM
        for patient_id in patients:
            # Documentos normales (infla el embudo de aprobaciones)
            for _ in range(random.randint(2, 6)):
                doc_id = str(uuid.uuid4())
                issue_date = fake.date_between(start_date=start_date, end_date='today')
                expiry = issue_date + timedelta(days=random.randint(10, 40)) if random.random() > 0.8 else None
                
                cursor.execute("""
                    INSERT INTO documents (id, tenant_id, patient_id, uploader_id, status, is_external_source, issue_date, expiry_date)
                    VALUES (%s, %s, %s, %s, %s, true, %s, %s)
                """, (doc_id, tenant_id, patient_id, uploader_id, random.choice(estados_doc), issue_date, expiry))

            # Estudios DICOM (infla la métrica de almacenamiento)
            if random.random() > 0.4:
                study_id = str(uuid.uuid4())
                study_date = fake.date_between(start_date=start_date, end_date='today')
                cursor.execute("""
                    INSERT INTO dicom_studies (id, tenant_id, patient_id, uploader_id, study_instance_uid, study_date)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (study_id, tenant_id, patient_id, uploader_id, str(uuid.uuid4()), study_date))
                
                series_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO dicom_series (id, tenant_id, study_id, series_instance_uid, modality, series_number)
                    VALUES (%s, %s, %s, %s, %s, 1)
                """, (series_id, tenant_id, study_id, str(uuid.uuid4()), random.choice(['CT', 'MR', 'US'])))

                # Instancias de imágenes DICOM falsas
                for i in range(random.randint(10, 50)):
                    cursor.execute("""
                        INSERT INTO dicom_instances (id, tenant_id, series_id, sop_instance_uid, instance_number, file_path, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (str(uuid.uuid4()), tenant_id, series_id, str(uuid.uuid4()), i, f'/fake/image_{i}.dcm', study_date))

    conn.commit()
    cursor.close()
    conn.close()
    print("🚀 ¡Datos inyectados con éxito! Ve a recargar Angular.")

if __name__ == '__main__':
    seed_analytical_data()