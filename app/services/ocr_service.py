import io
import os
import json

from PIL import Image
from pdf2image import convert_from_bytes
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.oauth2 import service_account

load_dotenv()

VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
VERTEX_LOCATION   = os.getenv("VERTEX_LOCATION", "us-central1")
VERTEX_MODEL_NAME = os.getenv("VERTEX_MODEL_NAME", "gemini-2.5-flash")

SUPPORTED_IMAGES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}
SUPPORTED_PDF    = {"application/pdf"}

_PROMPT = """
Eres un analista de datos experto. Observa la imagen del documento y extrae toda la información visible.

Reglas estrictas:
1. Identifica el 'tipo_documento' (ej. 'Hemograma', 'Receta Medica', 'Derivacion', 'Informe Imagenologia', 'Documento de Identidad', 'Ficha Veterinaria', 'Otro').
2. Extrae el 'paciente', 'fecha' y el 'medico_tratante' si aparecen.
3. En 'datos_clave' extrae todos los campos importantes del documento:
   - Si es receta: medicamentos y dosis.
   - Si es laboratorio/hemograma: valores y unidades.
   - Si es un informe: diagnóstico principal.
   - Si es carnet/pasaporte: número de documento.
   - Si es ficha veterinaria: especie, raza, sexo, peso, edad, color, fecha de nacimiento, propietario, dirección.
4. En 'raw_text' devuelve todo el texto visible en el documento tal como aparece.
5. Tu respuesta DEBE ser ÚNICAMENTE un objeto JSON válido. Sin texto adicional, sin formato Markdown.

Formato de salida:
{
  "tipo_documento": "...",
  "paciente": "...",
  "fecha": "...",
  "medico_tratante": "...",
  "datos_clave": {},
  "raw_text": "..."
}
"""


def _get_client() -> genai.Client:
    key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_VERTEX")
    creds = None
    if key_path and os.path.exists(key_path):
        creds = service_account.Credentials.from_service_account_file(
            key_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
    return genai.Client(
        vertexai=True,
        project=VERTEX_PROJECT_ID,
        location=VERTEX_LOCATION,
        credentials=creds,
    )


def _extract_json(raw: str) -> dict:
    text = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


def _call_vertex(contents: list) -> dict:
    client = _get_client()
    response = client.models.generate_content(
        model=VERTEX_MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0.1,
            top_p=0.8,
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(thinking_level="low"),
        ),
    )
    return _extract_json(response.text)


def _image_to_jpeg_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG")
    return buf.getvalue()


def extract_text(file_bytes: bytes, content_type: str) -> dict:
    if content_type in SUPPORTED_IMAGES:
        image_part = types.Part.from_bytes(data=file_bytes, mime_type=content_type)
        structured = _call_vertex([image_part, _PROMPT])
        raw_text = structured.pop("raw_text", "")
        return {
            "raw_text":         raw_text,
            "structured_data":  structured,
            "confidence_score": 1.0,
            "pages_processed":  1,
            "file_type":        "image",
        }

    elif content_type in SUPPORTED_PDF:
        pages = convert_from_bytes(file_bytes, dpi=200)
        contents = []
        for page in pages:
            jpeg_bytes = _image_to_jpeg_bytes(page)
            contents.append(types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"))
        contents.append(_PROMPT)
        structured = _call_vertex(contents)
        raw_text = structured.pop("raw_text", "")
        return {
            "raw_text":         raw_text,
            "structured_data":  structured,
            "confidence_score": 1.0,
            "pages_processed":  len(pages),
            "file_type":        "pdf",
        }

    else:
        raise ValueError(f"Tipo de archivo no soportado: {content_type}")


def estructurar_datos_medicos(raw_text: str) -> dict:
    """Mantiene compatibilidad con el endpoint extract-multiple."""
    try:
        prompt = (
            "Eres un analista de datos experto. Analiza el siguiente texto y estructúralo en JSON.\n"
            "Devuelve ÚNICAMENTE el JSON sin texto adicional.\n\n"
            "Formato:\n"
            '{"tipo_documento":"...","paciente":"...","fecha":"...","medico_tratante":"...","datos_clave":{}}\n\n'
            f"Texto:\n{raw_text}"
        )
        result = _call_vertex([prompt])
        result.pop("raw_text", None)
        return result
    except Exception as e:
        print(f"Error en Vertex AI: {e}")
        return {"tipo_documento": "Desconocido", "datos_clave": {}}
