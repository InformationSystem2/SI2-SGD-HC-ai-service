import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Get absolute paths to env files relative to this file
current_file_dir = Path(__file__).parent.resolve()
local_env = current_file_dir.parent / ".env"
spring_env = current_file_dir.parent.parent / "sgd_spring-boot" / ".env"

load_dotenv(dotenv_path=local_env)
load_dotenv(dotenv_path=spring_env)

# Handle DB URL translation from JDBC (used in Spring Boot env) to SQLAlchemy
db_url = os.getenv("DB_URL", "postgresql://sgd_admin:sgd_admin@localhost:5432/sgd_default")
if db_url.startswith("jdbc:"):
    db_url = db_url.replace("jdbc:", "", 1)

if "://" in db_url and "@" not in db_url:
    db_username = os.getenv("DB_USERNAME")
    db_password = os.getenv("DB_PASSWORD")
    if db_username and db_password:
        prefix, rest = db_url.split("://", 1)
        db_url = f"{prefix}://{db_username}:{db_password}@{rest}"

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    db_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
