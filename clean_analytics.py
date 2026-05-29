import os
import psycopg2
from dotenv import load_dotenv

# Cargar configuración del .env
load_dotenv()
os.environ["PGCLIENTENCODING"] = "LATIN1"

def get_db_connection():
    db_url = os.getenv("DB_URL")
    if db_url and db_url.startswith("jdbc:"):
        db_url = db_url.replace("jdbc:", "", 1)
    return psycopg2.connect(db_url)

def clean_analytical_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("🧹 Iniciando limpieza de datos analíticos del dashboard...")

    try:
        # 1. Borrar todas las transacciones generadas (Documentos y Estudios DICOM)
        # Se hace desde las tablas "hijas" hacia las tablas "padre" para evitar errores de llaves foráneas
        cursor.execute("DELETE FROM dicom_instances;")
        cursor.execute("DELETE FROM dicom_series;")
        cursor.execute("DELETE FROM dicom_studies;")
        cursor.execute("DELETE FROM document_ocr_metadata;")
        cursor.execute("DELETE FROM documents;")
        print("✅ Documentos y estudios médicos eliminados.")
        
        # 2. Identificar los tenants "falsos" 
        # Protegemos los 3 slugs oficiales de tu DataInitializer
        slugs_oficiales = ('system', 'default', 'clinica-sur')
        cursor.execute("SELECT id FROM tenants WHERE slug NOT IN %s", (slugs_oficiales,))
        fake_tenants = [row[0] for row in cursor.fetchall()]

        if fake_tenants:
            fake_tenants_tuple = tuple(fake_tenants)
            
            # 3. Borrar todo lo que dependa estrictamente de esos tenants falsos
            cursor.execute("DELETE FROM patients WHERE tenant_id IN %s", (fake_tenants_tuple,))
            cursor.execute("DELETE FROM role_user WHERE user_id IN (SELECT id FROM users WHERE tenant_id IN %s)", (fake_tenants_tuple,))
            cursor.execute("DELETE FROM users WHERE tenant_id IN %s", (fake_tenants_tuple,))
            cursor.execute("DELETE FROM tenants WHERE id IN %s", (fake_tenants_tuple,))
            print("✅ Clínicas ficticias y sus pacientes eliminados.")
        
        conn.commit()
        print("✨ ¡Limpieza exitosa! Tu base de datos quedó pulcra y lista para volver a ser sembrada.")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error durante la limpieza: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    clean_analytical_data()