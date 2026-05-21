from fastapi import FastAPI

app = FastAPI(
    title="SSGD-HC AI Microservice",
    description="Microservicio para procesamiento OCR y extracción de metadatos clínicos",
    version="1.0.0"
)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "¡El microservicio de IA está corriendo perfecto!"
    }