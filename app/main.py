from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from pathlib import Path

current_file_dir = Path(__file__).resolve().parent
load_dotenv(dotenv_path=current_file_dir.parent / ".env")
load_dotenv(dotenv_path=current_file_dir.parent.parent / "sgd_spring-boot" / ".env")

CORS_ORIGIN = os.getenv("CORS_ALLOWED_ORIGINS", "*")

from app.routers import ocr, reports, analytics

app = FastAPI(title="SGD-HC OCR Service & Reports", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[CORS_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ocr.router)
app.include_router(reports.router)
app.include_router(analytics.router) # <-- Agregas esta línea

@app.get("/health")
def health():
    return {"status": "ok"}