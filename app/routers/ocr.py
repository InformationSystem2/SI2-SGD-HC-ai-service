from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.ocr_service import extract_text
from app.schemas.ocr_schema import OcrResponse

router = APIRouter(prefix="/ocr", tags=["OCR"])

@router.post("/extract", response_model=OcrResponse)
async def extract(file: UploadFile = File(...)):
    content_type = file.content_type or ""
    if not any(ct in content_type for ct in ["image/", "application/pdf"]):
        raise HTTPException(400, "Solo se aceptan imágenes o PDFs")
    
    file_bytes = await file.read()
    try:
        result = extract_text(file_bytes, content_type)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Error al procesar el archivo: {str(e)}")
    
    return OcrResponse(**result)