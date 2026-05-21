import io
import os
import json
import pytesseract
import cv2

from PIL import Image
from pdf2image import convert_from_bytes
from dotenv import load_dotenv
import google.generativeai as genai
import numpy as np

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

SUPPORTED_IMAGES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}
SUPPORTED_PDF    = {"application/pdf"}

def limpiar_imagen_para_ocr(file_bytes: bytes) -> Image:
    """Aplica filtros de visión computacional para que Tesseract lea perfecto"""
    # 1. Convertir los bytes a una matriz de imagen que OpenCV entienda
    nparr = np.frombuffer(file_bytes, np.uint8)
    img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # 2. Convertir a escala de grises
    gris = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

    # 3. Hacer la imagen más grande (ayuda a leer letras chiquitas)
    gris = cv2.resize(gris, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    # 4. Binarización (Blanco y Negro extremo). Resalta las letras y mata el fondo
    _, binarizada = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Convertir de vuelta a un formato que Tesseract (PIL) acepte
    return Image.fromarray(binarizada)


def estructurar_datos_medicos(raw_text: str) -> dict:
    prompt = """
    Eres un analista de datos clínicos experto trabajando para un sistema de historias clínicas. Analiza el siguiente texto extraído por OCR y estructúralo.
    
    Reglas estrictas:
    1. Identifica el 'tipo_documento' (ej. 'Hemograma', 'Receta Medica', 'Derivacion', 'Informe Imagenologia', 'Documento de Identidad', 'Otro').
    2. Extrae el 'paciente', 'fecha' y el 'medico_tratante' si aparecen en el texto.
    3. En el objeto 'datos_clave', extrae de forma resumida:
       - Si es receta: medicamentos y dosis.
       - Si es laboratorio/hemograma: valores importantes (ej. leucocitos, glucosa) y sus unidades.
       - Si es un informe: el diagnóstico principal.
       - Si es un carnet/pasaporte: el número de documento.
    4. Tu respuesta DEBE ser ÚNICAMENTE un objeto JSON válido. Cero texto adicional, cero formato Markdown (sin ```json).
    
    Ejemplo de salida esperada:
    {
      "tipo_documento": "Receta Medica",
      "paciente": "Maria Lopez",
      "fecha": "2026-05-20",
      "medico_tratante": "Dr. Perez",
      "datos_clave": {
        "Paracetamol": "500mg cada 8 horas",
        "Amoxicilina": "1 tableta al dia"
      }
    }
    
    Texto a procesar:
    """
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt + raw_text)
        texto_limpio = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(texto_limpio)
    except Exception as e:
        print(f"Error en Gemini: {e}")
        return {"tipo_documento": "Desconocido", "datos_clave": {}}


def extract_text(file_bytes: bytes, content_type: str) -> dict:
    config = "--oem 3 --psm 6 -l spa+eng"

    if content_type in SUPPORTED_IMAGES:
        img  = Image.open(io.BytesIO(file_bytes))
        img_limpia = limpiar_imagen_para_ocr(file_bytes)
        data = pytesseract.image_to_data(img, config=config,
                                         output_type=pytesseract.Output.DICT)
        raw  = pytesseract.image_to_string(img_limpia, config=config)

        confidences = [c for c in data["conf"] if c != -1]
        score = sum(confidences) / len(confidences) / 100 if confidences else 0.0

        structured = estructurar_datos_medicos(raw)

        return {
            "raw_text":         raw.strip(),
            "structured_data":  structured,
            "confidence_score": round(score, 2),
            "pages_processed":  1,
            "file_type":        "image",
        }

    elif content_type in SUPPORTED_PDF:
        pages = convert_from_bytes(file_bytes, dpi=200)
        all_raw, all_conf = [], []

        for page in pages:
            data = pytesseract.image_to_data(page, config=config,
                                              output_type=pytesseract.Output.DICT)
            all_raw.append(pytesseract.image_to_string(page, config=config))
            all_conf.extend([c for c in data["conf"] if c != -1])

        score = sum(all_conf) / len(all_conf) / 100 if all_conf else 0.0
        raw   = "\n\n".join(all_raw).strip()

        return {
            "raw_text":         raw,
            "structured_data":  estructurar_datos_medicos(raw),
            "confidence_score": round(score, 2),
            "pages_processed":  len(pages),
            "file_type":        "pdf",
        }

    else:
        raise ValueError(f"Tipo de archivo no soportado: {content_type}")