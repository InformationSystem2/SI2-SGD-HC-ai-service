from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
from app.services.ocr_service import extract_text
from app.schemas.ocr_schema import OcrResponse
import io

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

@router.post("/extract-multiple", response_model=OcrResponse)
async def extract_multiple(files: List[UploadFile] = File(...)):
    """
    Recibe múltiples imágenes (simulando AdobeScan) y procesa todo en conjunto
    utilizando visión computacional y Gemini AI para extraer palabras clave y
    devolver los datos clínicos consolidados.
    """
    if not files:
        raise HTTPException(400, "Debe enviar al menos un archivo")

    all_raw_texts = []
    total_confidence = 0.0
    pages_processed = 0

    # Procesar cada imagen
    for index, file in enumerate(files):
        content_type = file.content_type or ""
        if not any(ct in content_type for ct in ["image/", "application/pdf"]):
            raise HTTPException(400, f"El archivo {file.filename} no es una imagen o PDF válido")
        
        file_bytes = await file.read()
        try:
            # Procesamiento individual de OCR
            result = extract_text(file_bytes, content_type)
            all_raw_texts.append(f"--- PÁGINA {index + 1} ({file.filename}) ---\n{result['raw_text']}")
            total_confidence += result['confidence_score']
            pages_processed += result['pages_processed']
        except Exception as e:
            raise HTTPException(500, f"Error procesando {file.filename}: {str(e)}")

    # Consolidar todos los textos
    consolidated_raw_text = "\n\n".join(all_raw_texts)
    avg_confidence = round(total_confidence / len(files), 2) if files else 0.0

    # Enviar el texto consolidado completo a Gemini para estructurar todo el documento clínico
    from app.services.ocr_service import estructurar_datos_medicos
    structured_data = estructurar_datos_medicos(consolidated_raw_text)

    return OcrResponse(
        raw_text=consolidated_raw_text,
        structured_data=structured_data,
        confidence_score=avg_confidence,
        pages_processed=pages_processed,
        file_type="multi-image"
    )