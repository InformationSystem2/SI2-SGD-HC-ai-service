import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
os.environ["PGCLIENTENCODING"] = "LATIN1"

def nuke_database():
    db_url = os.getenv("DB_URL", "")
    if db_url.startswith("jdbc:"):
        db_url = db_url.replace("jdbc:", "", 1)
        
    conn = psycopg2.connect(db_url)
    conn.autocommit = True # Necesario para comandos DROP SCHEMA
    cursor = conn.cursor()
    
    print("🔥 Destruyendo la base de datos antigua...")
    cursor.execute("DROP SCHEMA public CASCADE;")
    cursor.execute("CREATE SCHEMA public;")
    
    print("✨ ¡Base de datos nueva y brillante! Lista para que Spring Boot la construya.")
    cursor.close()
    conn.close()

if __name__ == '__main__':
    nuke_database()