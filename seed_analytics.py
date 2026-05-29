import os
import psycopg2
import uuid
import random
from faker import Faker
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 1. ¡OBLIGATORIO cargar el .env primero!
load_dotenv()

# 2. Arreglar los acentos para Windows
os.environ["PGCLIENTENCODING"] = "LATIN1"

fake = Faker('es_ES')

def get_db_connection():
    # 3. Leer la URL exacta de tu .env
    db_url = os.getenv("DB_URL")
    
    # 4. Aplicar la misma limpieza que ya usan en tu proyecto por si acaso
    if db_url and db_url.startswith("jdbc:"):
        db_url = db_url.replace("jdbc:", "", 1)
        
    # 5. psycopg2 acepta la URL completa sin problemas
    return psycopg2.connect(db_url)

def seed_analytical_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("🌟 Iniciando generación masiva de datos para el Dashboard...")

    # Parámetros Enum que tienes en tu base de datos
    planes = ['BASIC', 'PRO', 'ENTERPRISE']
    estados_suscripcion = ['ACTIVE', 'PAST_DUE', 'CANCELED', 'SUSPENDED']
    estados_doc = ['DRAFT', 'PENDING_REVIEW', 'REJECTED', 'FINALIZED']
    
    # 2. Generar 15 Clínicas (Tenants)
    tenants = []
    for _ in range(15):
        t_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO tenants (id, name, slug, email, subscription_plan, subscription_status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (t_id, fake.company(), fake.slug(), fake.company_email(), 
              random.choice(planes), random.choice(estados_suscripcion)))
        tenants.append(t_id)
    
    print(f"✅ 15 Clínicas ficticias creadas.")

    # Variables para distribuir datos en el tiempo (últimos 6 meses)
    start_date = datetime.now() - timedelta(days=180)

    for tenant_id in tenants:
        # Generar un usuario admin falso para el tenant (uploader)
        uploader_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO users (id, tenant_id, document_type, document_number, username, first_name, last_name, email, password, is_active)
            VALUES (%s, %s, 'CI', %s, %s, %s, %s, %s, 'hash', true)
        """, (uploader_id, tenant_id, fake.unique.random_number(digits=8), fake.user_name(), fake.first_name(), fake.last_name(), fake.email()))

        # 3. Generar entre 20 y 50 pacientes por clínica
        num_pacientes = random.randint(20, 50)
        for _ in range(num_pacientes):
            patient_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO patients (id, tenant_id, first_name, last_name, birth_date, gender)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (patient_id, tenant_id, fake.first_name(), fake.last_name(), fake.date_of_birth(minimum_age=1, maximum_age=90), random.choice(['MALE', 'FEMALE'])))

            # 4. Generar entre 5 y 15 Documentos Clínicos por paciente
            for _ in range(random.randint(5, 15)):
                doc_id = str(uuid.uuid4())
                issue_date = fake.date_between(start_date=start_date, end_date='today')
                
                cursor.execute("""
                    INSERT INTO documents (id, tenant_id, patient_id, uploader_id, status, is_external_source, issue_date)
                    VALUES (%s, %s, %s, %s, %s, true, %s)
                """, (doc_id, tenant_id, patient_id, uploader_id, random.choice(estados_doc), issue_date))

                # Agregar metadatos de OCR para ver el rendimiento del NLP
                cursor.execute("""
                    INSERT INTO document_ocr_metadata (document_id, confidence_score, pages_processed, file_type)
                    VALUES (%s, %s, %s, %s)
                """, (doc_id, round(random.uniform(40.0, 99.9), 2), random.randint(1, 5), random.choice(['PDF', 'JPG', 'PNG'])))

            # 5. Generar un Estudio Médico (DICOM) para algunos pacientes
            if random.random() > 0.5: # 50% de probabilidad de tener estudios
                study_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO dicom_studies (id, tenant_id, patient_id, uploader_id, study_instance_uid, study_date)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (study_id, tenant_id, patient_id, uploader_id, str(uuid.uuid4()), fake.date_between(start_date=start_date, end_date='today')))

    conn.commit()
    cursor.close()
    conn.close()
    print("🚀 ¡Semilla analítica inyectada con éxito! La base de datos está lista para el Dashboard.")

if __name__ == '__main__':
    seed_analytical_data()