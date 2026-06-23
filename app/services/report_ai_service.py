import os
import json
import logging
import tempfile
import time
from typing import Optional, Tuple
import google.generativeai as genai
from dotenv import load_dotenv

from app.services.catalog import ReportCatalog
from app.schemas.report_schemas import ReportRunRequest, ReportFilter

logger = logging.getLogger(__name__)
load_dotenv()

# Initialize genai with API Key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

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
            "{\n"
            "  \"reportType\": \"patients\",\n"
            "  \"selectedFields\": [\"documentNumber\", \"fullName\", \"gender\"],\n"
            "  \"filters\": [\n"
            "    {\"field\": \"gender\", \"operator\": \"EQ\", \"value\": \"FEMALE\"}\n"
            "  ],\n"
            "  \"sortField\": \"createdAt\",\n"
            "  \"sortOrder\": \"desc\",\n"
            "  \"limit\": 50,\n"
            "  \"offset\": 0\n"
            "}"
        )

        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(
                [instruction, f"Solicitud del usuario: {prompt}"],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    top_p=0.8,
                    response_mime_type="application/json",
                )
            )

            raw_text = response.text.strip() if response.text else "{}"
            if raw_text.startswith("```"):
                raw_text = raw_text.strip("`")
                if raw_text.lower().startswith("json"):
                    raw_text = raw_text[4:].strip()

            start = raw_text.find("{")
            end = raw_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                raw_text = raw_text[start : end + 1]

            result_dict = json.loads(raw_text)
            return result_dict

        except Exception as e:
            logger.exception("Error al parsear el prompt del reporte usando Gemini: %s", e)
            return None

    @classmethod
    def transcribe_audio(cls, file_bytes: bytes, filename: str) -> Optional[str]:
        # Save bytes to a temporary local file
        suffix = os.path.splitext(filename)[1] or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(file_bytes)
            temp_file_path = temp_file.name

        try:
            logger.info("Subiendo archivo de audio temporal a la API de Gemini: %s", temp_file_path)
            uploaded_file = genai.upload_file(path=temp_file_path)

            for attempt in range(10):
                file_info = genai.get_file(uploaded_file.name)
                if file_info.state.name == "ACTIVE":
                    logger.info("Archivo ACTIVE después de %d intentos", attempt)
                    break
                logger.info("Archivo en estado %s, esperando... (intento %d)", file_info.state.name, attempt + 1)
                time.sleep(2)
            else:
                raise RuntimeError(f"El archivo {uploaded_file.name} no alcanzó estado ACTIVE tras 10 reintentos")

            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content([
                uploaded_file,
                "Por favor, transcribe este audio en español. Solo devuelve la transcripción literal, nada de texto adicional o introducciones."
            ])
            
            # Delete file from Gemini servers
            genai.delete_file(uploaded_file.name)
            
            transcript = response.text.strip()
            logger.info("Transcripción exitosa: %s", transcript)
            return transcript
        except Exception as e:
            logger.exception("Error al transcribir el audio usando Gemini: %s", e)
            return None
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
