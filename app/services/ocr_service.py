import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes
import io
import sys # <-- Agregamos esta librería nativa de Python

# ... 

# Magia: Preguntamos si el sistema operativo es Windows ('win32')
if sys.platform == "win32":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# Si es Linux o Mac, no hacemos absolutamente nada porque el sistema lo encuentra solo.

SUPPORTED_IMAGES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}
SUPPORTED_PDF    = {"application/pdf"}

def extract_text(file_bytes: bytes, content_type: str) -> dict:
    config = "--oem 3 --psm 6 -l spa+eng"

    if content_type in SUPPORTED_IMAGES:
        img  = Image.open(io.BytesIO(file_bytes))
        data = pytesseract.image_to_data(img, config=config,
                                         output_type=pytesseract.Output.DICT)
        text        = pytesseract.image_to_string(img, config=config)
        confidences = [c for c in data["conf"] if c != -1]
        score       = sum(confidences) / len(confidences) / 100 if confidences else 0.0
        return {"raw_text": text.strip(), "confidence_score": round(score, 2),
                "pages_processed": 1, "file_type": "image"}

    elif content_type in SUPPORTED_PDF:
        pages = convert_from_bytes(file_bytes, dpi=200)
        all_text, all_conf = [], []
        for page in pages:
            data = pytesseract.image_to_data(page, config=config,
                                              output_type=pytesseract.Output.DICT)
            all_text.append(pytesseract.image_to_string(page, config=config))
            all_conf.extend([c for c in data["conf"] if c != -1])
        score = sum(all_conf) / len(all_conf) / 100 if all_conf else 0.0
        return {"raw_text": "\n\n".join(all_text).strip(),
                "confidence_score": round(score, 2),
                "pages_processed": len(pages), "file_type": "pdf"}

    else:
        raise ValueError(f"Tipo de archivo no soportado: {content_type}")