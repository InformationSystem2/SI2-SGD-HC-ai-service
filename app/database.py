import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Handle DB URL translation from JDBC (used in Spring Boot env) to SQLAlchemy
db_url = os.getenv("DB_URL", "postgresql://sgd_admin:sgd_admin@localhost:5432/sgd_default")
if db_url.startswith("jdbc:"):
    db_url = db_url.replace("jdbc:", "", 1)

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
