import os
import json
import logging
from typing import Optional
from google import genai
from google.genai import types
from google.oauth2 import service_account
from dotenv import load_dotenv

from app.services.catalog import ReportCatalog
from app.schemas.report_schemas import ReportRunRequest, ReportFilter

logger = logging.getLogger(__name__)
load_dotenv()

VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
VERTEX_LOCATION   = os.getenv("VERTEX_LOCATION", "us-central1")
VERTEX_MODEL_NAME = os.getenv("VERTEX_MODEL_NAME", "gemini-2.5-flash")


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


class ReportAIService:
    @staticmethod
    def get_catalog_description() -> str:
        catalog = ReportCatalog()
        lines = []
        for r in catalog.all():
            lines.append(f"Tipo de Reporte (reportType): '{r.key}' (Etiqueta: {r.label}, Categoría: {r.category.value})")
            lines.append("Campos/Columnas permitidas:")
            for field in r.fields.values():
                lines.append(f"  - '{field.key}' ({field.label}) [Tipo: {field.type.value}, Tipo de Campo: {field.kind.value}]")
            lines.append("")
        return "\n".join(lines)

    @classmethod
    def parse_prompt(cls, prompt: str) -> Optional[dict]:
        if not VERTEX_PROJECT_ID:
            logger.warning("VERTEX_PROJECT_ID no configurado")
            return None

        catalog_desc = cls.get_catalog_description()
        instruction = (
            "Eres un asistente experto en análisis de datos para un sistema de gestión documental clínica (historias clínicas, pacientes, documentos, usuarios, plantillas).\n"
            "Tu tarea es interpretar la solicitud en lenguaje natural del usuario (en español o inglés) y traducirla a una consulta estructurada de reportes en formato JSON.\n\n"
            "Esquema del catálogo de reportes disponible:\n"
            f"{catalog_desc}\n\n"
            "INSTRUCCIONES DE TRADUCCIÓN:\n"
            "1. Determina el 'reportType' más adecuado según la solicitud del usuario.\n"
            "2. Selecciona en 'selectedFields' las columnas solicitadas por el usuario. Deben pertenecer a los campos permitidos del reporte seleccionado. Si el usuario no especifica columnas, selecciona al menos 3 a 5 campos clave por defecto (por ejemplo, id, nombre, estado, fecha de creación).\n"
            "3. Identifica filtros y mapea operadores (siempre en MAYÚSCULAS):\n"
            "   - 'igual a', 'es', 'del estado' -> 'EQ'\n"
            "   - 'diferente de', 'no es' -> 'NE'\n"
            "   - 'mayor que' -> 'GT'\n"
            "   - 'menor que' -> 'LT'\n"
            "   - 'mayor o igual que' -> 'GTE'\n"
            "   - 'menor o igual que' -> 'LTE'\n"
            "   - 'que contenga', 'contiene', 'como' -> 'LIKE'\n"
            "   - 'es nulo', 'no tiene', 'vacío' -> 'IS_NULL'\n"
            "   - 'no es nulo', 'tiene', 'no vacío' -> 'IS_NOT_NULL'\n"
            "4. Define el ordenamiento en 'sortField' y 'sortOrder' ('asc' o 'desc') si el usuario lo solicita.\n"
            "   - IMPORTANTE: Si el usuario pide 'los últimos registrados' o similar, debes ordenar por el campo de fecha correspondiente de forma descendente ('sortOrder': 'desc') y definir el 'limit' con la cantidad solicitada (ej. 10).\n"
            "5. Si el usuario pide una cantidad limitada de registros (ej. 'los primeros 5', 'los últimos 10'), asigna ese número al campo 'limit'.\n"
            "6. Genera la salida respetando estrictamente el formato JSON especificado. No incluyas texto adicional o explicaciones, solo devuelve el objeto JSON.\n\n"
            "Ejemplo de formato de salida esperado:\n"
            '{"reportType":"patients","selectedFields":["documentNumber","fullName","gender"],'
            '"filters":[{"field":"gender","operator":"EQ","value":"FEMALE"}],'
            '"sortField":"createdAt","sortOrder":"desc","limit":50,"offset":0}'
        )

        try:
            client = _get_client()
            response = client.models.generate_content(
                model=VERTEX_MODEL_NAME,
                contents=[instruction, f"Solicitud del usuario: {prompt}"],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    top_p=0.8,
                    response_mime_type="application/json",
                    thinking_config=types.ThinkingConfig(thinking_level="low"),
                ),
            )
            return _extract_json(response.text)
        except Exception as e:
            logger.exception("Error al parsear el prompt del reporte: %s", e)
            return None

    @classmethod
    def transcribe_audio(cls, file_bytes: bytes, filename: str) -> Optional[str]:
        _MIME_MAP = {
            ".webm": "audio/webm",
            ".m4a":  "audio/mp4",
            ".mp3":  "audio/mpeg",
            ".wav":  "audio/wav",
            ".ogg":  "audio/ogg",
            ".flac": "audio/flac",
        }
        suffix = os.path.splitext(filename)[1].lower() or ".webm"
        mime_type = _MIME_MAP.get(suffix, "audio/webm")

        try:
            if not VERTEX_PROJECT_ID:
                logger.warning("VERTEX_PROJECT_ID no configurado")
                return None

            logger.info("Transcribiendo audio con Vertex AI: %s (%s)", filename, mime_type)
            client = _get_client()
            audio_part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
            response = client.models.generate_content(
                model=VERTEX_MODEL_NAME,
                contents=[
                    audio_part,
                    "Por favor, transcribe este audio en español. Solo devuelve la transcripción literal, nada de texto adicional o introducciones.",
                ],
            )
            transcript = response.text.strip()
            logger.info("Transcripción exitosa: %s", transcript)
            return transcript
        except Exception as e:
            logger.exception("Error al transcribir el audio: %s", e)
            return None
