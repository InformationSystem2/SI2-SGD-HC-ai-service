from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import ocr

app = FastAPI(title="SGD-HC OCR Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en prod cambiás esto al dominio del backend Spring
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ocr.router)

@app.get("/health")
def health():
    return {"status": "ok"}