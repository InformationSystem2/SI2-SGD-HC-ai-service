import os
import json
import uuid
import random
import bcrypt
import psycopg2
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
from faker import Faker
import io
from fpdf import FPDF
try:
    from azure.storage.blob import BlobServiceClient
    _AZURE_SDK_AVAILABLE = True
except ImportError:
    _AZURE_SDK_AVAILABLE = False

load_dotenv()
os.environ["PGCLIENTENCODING"] = "UTF-8"

PDF_STORAGE_DIR = os.getenv("PDF_STORAGE_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage", "pdfs"))
DATE_START = date(2026, 1, 1)
DATE_END   = date(2026, 7, 23)
fake = Faker('es_ES')

# ── Constantes clínicas ───────────────────────────────────────────────────────

BLOOD_TYPES = ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"]

DIAGNOSTICS = [
    "Gastritis crónica erosiva.", "Hipertensión arterial estadio I.",
    "Diabetes mellitus tipo 2 compensada.", "Neumonía adquirida en la comunidad.",
    "Infección del tracto urinario.", "Colecistitis aguda litiásica.",
    "Migraña sin aura.", "Lumbalgia mecánica aguda.",
    "Anemia ferropénica leve.", "Faringitis aguda bacteriana.",
    "Insuficiencia cardíaca congestiva.", "Epilepsia focal sintomática.",
]

PROCEDIMIENTOS_QX = [
    "Apendicectomía laparoscópica.", "Colecistectomía laparoscópica.",
    "Cesárea segmentaria.", "Herniorrafia inguinal derecha.",
    "Lavado quirúrgico de herida.", "Biopsia excisional de nódulo mamario.",
    "Histerectomía total abdominal.", "Nefrectomía radical laparoscópica.",
]

EXTRA_CLINIC_DATA = [
    ("Hospital San Juan de Dios",       "hospital-san-juan"),
    ("Clínica Santa María",             "clinica-santa-maria"),
    ("Hospital Municipal de La Paz",    "hospital-municipal-lp"),
    ("Clínica Los Ángeles",             "clinica-los-angeles"),
    ("Hospital Obrero N°2",             "hospital-obrero-2"),
    ("Clínica San Pedro",               "clinica-san-pedro"),
    ("Hospital de la Mujer",            "hospital-mujer"),
    ("Clínica Americana",               "clinica-americana"),
    ("Hospital Materno Infantil",       "hospital-materno"),
    ("Clínica Boliviano-Belga",         "clinica-boliviano-belga"),
    ("Hospital Arco Iris",              "hospital-arco-iris"),
    ("Clínica San Lucas",               "clinica-san-lucas"),
    ("Hospital Regional Trinidad",      "hospital-trinidad"),
]

ALLERGEN_POOL = [
    ("Penicilina",    "Alta",   "Urticaria generalizada y angioedema"),
    ("Sulfonamidas",  "Alta",   "Exantema maculopapular"),
    ("AINEs",         "Media",  "Broncoespasmo y rinitis"),
    ("Látex",         "Media",  "Dermatitis de contacto"),
    ("Mariscos",      "Baja",   "Náuseas y prurito"),
    ("Polen",         "Baja",   "Rinitis alérgica estacional"),
]

MED_POOL = [
    ("Metformina",   "850 mg",  "Cada 12 horas con alimentos"),
    ("Losartán",     "50 mg",   "Una vez al día"),
    ("Atorvastatina","20 mg",   "Una vez al día en la noche"),
    ("Levotiroxina", "100 mcg", "En ayunas cada mañana"),
    ("Amlodipino",   "5 mg",    "Una vez al día"),
    ("Omeprazol",    "20 mg",   "30 min antes del desayuno"),
]


def bolivian_phone() -> str:
    """Genera un número de celular boliviano: +591 6/7XXXXXXX"""
    prefix = random.choice([6, 7])
    number = random.randint(1000000, 9999999)
    return f"+591 {prefix}{number}"


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(10))
    return hashed.decode('utf-8')


def _safe(text: str) -> str:
    """Elimina caracteres no soportados por fuentes core de fpdf2 (Latin-1)."""
    replacements = {
        '—': '-', '–': '-', '‘': "'", '’': "'",
        '“': '"', '”': '"', '…': '...',
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode('latin-1', errors='replace').decode('latin-1')


def generate_clinical_pdf(
    doc_id: str,
    template_name: str,
    patient_first: str,
    patient_last: str,
    patient_doc: str,
    tenant_name: str,
    issue_date,
    clinical_content: dict,
    azure_container=None,
) -> tuple[str, int]:
    """
    Genera un PDF clínico.
    - Si azure_container está presente: sube a Azure y devuelve ('/uploads/{filename}', bytes).
    - Si no: guarda en disco local y devuelve (ruta_absoluta, bytes).
    """

    pdf = FPDF()
    pdf.set_margins(15, 15, 15)
    pdf.add_page()

    # ── Encabezado ────────────────────────────────────────────────────────────
    pdf.set_fill_color(30, 90, 160)
    pdf.rect(0, 0, 210, 28, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_y(6)
    pdf.cell(0, 8, _safe(tenant_name.upper()), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _safe(template_name), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)

    # ── Datos del paciente ────────────────────────────────────────────────────
    pdf.set_fill_color(240, 245, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, "DATOS DEL PACIENTE", new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.set_font("Helvetica", "", 10)
    nombre = _safe(f"{patient_first} {patient_last}")
    fecha  = issue_date.strftime("%d/%m/%Y") if hasattr(issue_date, 'strftime') else str(issue_date)
    pdf.cell(95, 6, _safe(f"Paciente: {nombre}"), new_x="END", new_y="TOP")
    pdf.cell(0,  6, _safe(f"CI/Documento: {patient_doc}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(95, 6, _safe(f"Fecha de emision: {fecha}"), new_x="END", new_y="TOP")
    pdf.cell(0,  6, _safe(f"Tipo: {template_name}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_draw_color(30, 90, 160)
    pdf.set_line_width(0.5)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(4)

    # ── Contenido clínico ─────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, "CONTENIDO DEL DOCUMENTO", new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.set_fill_color(240, 245, 255)

    SKIP_KEYS = {'medicamentos_induccion', 'medicamentos_administrados',
                 'tratamientos_vigentes', 'examenes_solicitados',
                 'medicamentos_recetados', 'signos_vitales'}

    for key, value in clinical_content.items():
        if key in SKIP_KEYS or isinstance(value, (list, dict)):
            continue
        label = _safe(key.replace("_", " ").title())
        text  = _safe(str(value))

        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(55, 6, f"{label}:", new_x="END", new_y="TOP")
        pdf.set_font("Helvetica", "", 9)
        # multi_cell avanza de línea automáticamente
        x_after_label = pdf.get_x()
        remaining_w = 195 - x_after_label
        pdf.multi_cell(remaining_w, 6, text, new_x="LMARGIN", new_y="NEXT")

    # Listas simples: medicamentos
    for list_key in ('medicamentos_recetados', 'examenes_solicitados',
                     'medicamentos_induccion', 'medicamentos_administrados',
                     'tratamientos_vigentes'):
        items = clinical_content.get(list_key)
        if not items or not isinstance(items, list):
            continue
        label = _safe(list_key.replace("_", " ").title())
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, f"{label}:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for item in items:
            if isinstance(item, dict):
                line = "  - " + "  |  ".join(f"{k}: {v}" for k, v in item.items()
                                              if not isinstance(v, (list, dict)))
            else:
                line = f"  - {item}"
            pdf.multi_cell(0, 5, _safe(line), new_x="LMARGIN", new_y="NEXT")

    # ── Pie de página ─────────────────────────────────────────────────────────
    pdf.set_y(-18)
    pdf.set_draw_color(30, 90, 160)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, _safe(f"Documento generado digitalmente | SGD | ID: {doc_id}"), align="C")

    filename = f"{doc_id}.pdf"
    pdf_bytes = pdf.output()          # fpdf2 devuelve bytes cuando no se pasa nombre

    if azure_container is not None:
        blob_client = azure_container.get_blob_client(filename)
        blob_client.upload_blob(io.BytesIO(pdf_bytes), length=len(pdf_bytes), overwrite=True)
        return f"/uploads/{filename}", len(pdf_bytes)
    else:
        os.makedirs(PDF_STORAGE_DIR, exist_ok=True)
        local_path = os.path.join(PDF_STORAGE_DIR, filename)
        with open(local_path, "wb") as f:
            f.write(pdf_bytes)
        return f"/uploads/{filename}", len(pdf_bytes)


# ── Generadores de contenido clínico ─────────────────────────────────────────

def generate_clinical_content(template_name: str) -> dict:
    if template_name == "Ficha de Ingreso":
        return {
            "tipo_sangre": random.choice(["O_POS", "O_NEG", "A_POS", "B_POS"]),
            "observaciones": random.choice([
                "Paciente ingresa por sus propios medios para revisión periódica.",
                "Ingreso referido desde puesto de salud periférico.",
                "Paciente trae estudios previos externos para evaluación.",
            ])
        }

    elif template_name == "Historia Clínica":
        return {
            "motivo_consulta": random.choice([
                "Dolor abdominal persistente de 3 días de evolución.",
                "Cefalea intensa frontal con fotofobia y náuseas.",
                "Dificultad respiratoria progresiva de inicio insidioso.",
                "Control médico de rutina y revisión de exámenes recientes.",
                "Fiebre alta sostenida de más de 72 horas sin foco aparente.",
                "Pérdida de peso involuntaria de 8 kg en los últimos 2 meses.",
            ]),
            "antecedentes_familiares": random.choice([
                "Padre con diabetes tipo 2. Madre con hipertensión arterial crónica.",
                "Abuela materna fallecida por cáncer gástrico a los 68 años.",
                "Sin antecedentes familiares de relevancia clínica.",
                "Padre fallecido por infarto agudo al miocardio a los 62 años.",
                "Hermano con epilepsia. Madre con lupus eritematoso sistémico.",
            ]),
            "antecedentes_patologicos": random.choice([
                "Hipertensión arterial diagnosticada hace 5 años. En tratamiento con Losartán 50 mg.",
                "Diabetes mellitus tipo 2 de 8 años de evolución. Metformina 850 mg c/12h.",
                "Sin antecedentes patológicos personales de importancia.",
                "Asma bronquial desde la infancia. Salbutamol a demanda.",
                "Hipotiroidismo primario. Levotiroxina 100 mcg cada mañana en ayunas.",
            ]),
            "antecedentes_no_patologicos": random.choice([
                "Tabaquismo activo: 10 cigarrillos/día por 15 años. Niega alcoholismo.",
                "Sedentarismo. Dieta hipercalórica. Niega consumo de tabaco ni alcohol.",
                "Sin hábitos nocivos. Actividad física leve 3 veces por semana.",
                "Etilismo ocasional (fines de semana). Niega tabaquismo.",
            ]),
            "alergias_declaradas": random.choice([
                "Penicilina — urticaria generalizada.", "Sulfonamidas — angioedema.",
                "Sin alergias medicamentosas conocidas a la fecha.", "AINEs (Ibuprofeno) — broncoespasmo.",
            ]),
            "exploracion_fisica": (
                f"Paciente consciente, orientado en tiempo y espacio. "
                f"TA {random.randint(110,145)}/{random.randint(60,90)} mmHg. "
                f"FC {random.randint(62,98)} lpm. FR {random.randint(14,22)} rpm. "
                f"T° {round(random.uniform(36.2, 38.5), 1)} °C. "
                f"Talla {random.randint(155,185)} cm. Peso {random.randint(50,105)} kg."
            ),
            "diagnostico_presuntivo": random.choice(DIAGNOSTICS),
            "plan_tratamiento": "Se solicitan estudios complementarios y se inicia tratamiento según protocolo institucional.",
        }

    elif template_name == "Nota de Ingreso":
        return {
            "servicio_ingreso": random.choice(["Urgencias", "Medicina Interna", "Cirugía General", "Pediatría", "Ginecología"]),
            "fecha_hora_ingreso": (datetime.now() - timedelta(hours=random.randint(1, 72))).strftime("%Y-%m-%dT%H:%M"),
            "motivo_ingreso": random.choice([
                "Dolor torácico opresivo irradiado al brazo izquierdo con diaforesis.",
                "Vómitos persistentes con signos de deshidratación moderada y alteración electrolítica.",
                "Crisis convulsiva tónico-clónica generalizada de 5 minutos de duración.",
                "Hemorragia digestiva alta con hematemesis de aproximadamente 300 cc.",
                "Politraumatismo por accidente de tránsito. TEC moderado y fractura de clavícula derecha.",
            ]),
            "estado_general": random.choice(["Estable", "Regular", "Malo", "Crítico"]),
            "pa": f"{random.randint(90,160)}/{random.randint(50,100)} mmHg",
            "fc": f"{random.randint(50,130)} lpm",
            "fr": f"{random.randint(12,30)} rpm",
            "temperatura": f"{round(random.uniform(35.8, 39.5), 1)} °C",
            "spo2": f"{random.randint(88,100)}%",
            "impresion_diagnostica": random.choice(DIAGNOSTICS),
            "plan_inicial": "Monitoreo continuo de signos vitales, hidratación endovenosa, analgesia y solicitud de estudios de urgencia.",
        }

    elif template_name == "Nota de Evolución":
        return {
            "fecha_hora": datetime.now().strftime("%Y-%m-%dT%H:%M"),
            "turno": random.choice(["Mañana (07:00-13:00)", "Tarde (13:00-19:00)", "Noche (19:00-07:00)"]),
            "pa": f"{random.randint(100,145)}/{random.randint(60,90)} mmHg",
            "fc": f"{random.randint(60,100)} lpm",
            "fr": f"{random.randint(14,22)} rpm",
            "temperatura": f"{round(random.uniform(36.0, 38.5), 1)} °C",
            "evolucion_subjetiva": random.choice([
                "Paciente refiere mejoría del dolor. Tolera vía oral con líquidos claros.",
                "Persiste fiebre vespertina. Sin cambios en el patrón de deposiciones.",
                "Paciente con mayor movilidad espontánea. Sin dolor en reposo.",
                "Refiere náuseas ocasionales pero sin vómitos. Apetito reducido.",
            ]),
            "examen_fisico": random.choice([
                "Abdomen blando, depresible, sin signos de irritación peritoneal.",
                "Pulmones con murmullo vesicular conservado bilateralmente, sin crepitantes.",
                "Herida quirúrgica sin signos locales de infección. Sutura íntegra y afrontada.",
                "Edema de miembros inferiores ++/++++. Pulsos pedios presentes.",
            ]),
            "respuesta_tratamiento": random.choice(["Favorable", "Parcial", "Sin cambios", "Tórpida"]),
            "ajuste_plan": "Se mantiene esquema terapéutico actual. Se reevalúa en próximo turno médico.",
        }

    elif template_name == "Nota de Interconsulta":
        especialidades = ["Cardiología", "Neurología", "Nefrología", "Endocrinología", "Traumatología", "Psiquiatría", "Oncología"]
        esp_sol = random.choice(especialidades)
        esp_resp = random.choice([e for e in especialidades if e != esp_sol])
        dx = random.choice(DIAGNOSTICS)
        return {
            "especialidad_solicitante": esp_resp,
            "especialidad_interconsultada": esp_sol,
            "fecha_solicitud": datetime.now().strftime("%Y-%m-%d"),
            "motivo_interconsulta": f"Paciente con {dx.lower()} requiere valoración especializada de {esp_sol} por evolución no satisfactoria.",
            "resumen_clinico": "Paciente de sexo masculino, ingresado hace 3 días por el cuadro descrito, con evolución tórpida pese al tratamiento instaurado. Se adjuntan resultados de laboratorio e imagenología.",
            "respuesta_interconsulta": random.choice([
                f"Valorado por {esp_sol}. Se sugiere ajuste de medicación y control ambulatorio en 15 días.",
                f"Hallazgos compatibles con diagnóstico diferencial planteado. Se recomienda estudio ampliado con TAC contrastado.",
                f"Paciente evaluado. Sin indicación quirúrgica de momento. Continuar tratamiento médico actual.",
                f"Se confirma diagnóstico de {dx.lower()} Se agregan {esp_sol} al plan terapéutico.",
            ]),
            "fecha_respuesta": datetime.now().strftime("%Y-%m-%d"),
        }

    elif template_name == "Receta Médica Estándar (Multi-Medicamento)":
        medicamentos_pool = [
            ("Amoxicilina",  "500mg",  "CADA_8_HRS",  7),
            ("Paracetamol",  "1g",     "CADA_6_HRS",  3),
            ("Ibuprofeno",   "400mg",  "CADA_8_HRS",  5),
            ("Omeprazol",    "20mg",   "CADA_24_HRS", 30),
            ("Losartán",     "50mg",   "CADA_24_HRS", 90),
            ("Metformina",   "850mg",  "CADA_12_HRS", 90),
        ]
        prescritos = []
        for m in random.sample(medicamentos_pool, random.randint(1, 3)):
            prescritos.append({"nombre_medicamento": m[0], "dosis": m[1], "frecuencia": m[2], "duracion": m[3]})
        return {
            "diagnostico_principal": random.choice(DIAGNOSTICS),
            "medicamentos_recetados": prescritos,
            "indicaciones_adicionales": "Tomar los medicamentos después de las comidas. Regresar si los síntomas persisten.",
        }

    elif template_name == "Orden de Laboratorio":
        examenes_pool = [
            "Hemograma completo con diferencial",
            "Glucosa en ayunas",
            "Creatinina sérica y BUN",
            "Perfil lipídico completo (CT, HDL, LDL, TG)",
            "TSH ultrasensible",
            "Proteína C reactiva cuantitativa (PCR)",
            "Urocultivo y antibiograma",
            "Hemocultivo x2 (aeróbio/anaeróbio)",
            "Pruebas de función hepática (TGO, TGP, BT, BD, FA)",
            "Electrolitos séricos (Na, K, Cl, Ca)",
            "Tiempo de protrombina (TP) y TTPa",
            "Grupo sanguíneo y factor Rh",
            "HbA1c (hemoglobina glicosilada)",
            "Sedimento urinario y proteínas en orina de 24h",
        ]
        return {
            "diagnostico_clinico": random.choice(DIAGNOSTICS),
            "examenes_solicitados": random.sample(examenes_pool, random.randint(2, 5)),
            "indicacion_clinica": random.choice([
                "Control de enfermedad crónica y ajuste de tratamiento farmacológico.",
                "Estudio de síndrome febril prolongado sin foco identificado.",
                "Preoperatorio de cirugía electiva programada.",
                "Seguimiento post-infeccioso y evaluación de respuesta terapéutica.",
            ]),
            "prioridad": random.choice(["Urgente", "Rutina"]),
            "notas": "Paciente en ayunas de 8 horas para extracción de muestra.",
        }

    elif template_name == "Orden de Imagenología":
        estudios = [
            "Radiografía de Tórax AP y Lateral",
            "Ecografía Abdominal Completa",
            "Resonancia Magnética de Cerebro sin contraste",
            "Tomografía Computarizada de Abdomen y Pelvis con contraste",
            "Ecografía Doppler de miembros inferiores",
        ]
        return {
            "diagnostico_principal": random.choice(DIAGNOSTICS),
            "estudio_solicitado": random.choice(estudios),
            "indicacion_clinica": random.choice([
                "Paciente con tos persistente y sospecha clínica de neumonía.",
                "Dolor agudo en hipocondrio derecho. Descartar colecistitis aguda.",
                "Cefalea crónica progresiva con signos de focalización neurológica.",
                "Control evolutivo de proceso oncológico conocido.",
            ]),
            "notas_adicionales": random.choice([
                "Con carácter urgente. Informar al médico solicitante.",
                "Electivo. Programar en las próximas 48 horas.",
                "Traer estudios previos para comparación radiológica.",
            ]),
        }

    elif template_name == "Informe de Imagenología":
        tipo = random.choice(["Radiografía", "Ecografía", "TAC", "Resonancia Magnética", "Mamografía"])
        region = random.choice(["Tórax", "Abdomen", "Pelvis", "Cráneo", "Columna Lumbar", "Rodilla derecha"])
        hallazgos_map = {
            "Radiografía": "Infiltrado alveolar en lóbulo inferior derecho, de bordes mal definidos, compatible con proceso neumónico en evolución. Senos costofrénicos libres.",
            "Ecografía":   "Vesícula biliar con múltiples cálculos hiperecogénicos, el mayor de 15 mm. Paredes engrosadas a 4 mm. Sin dilatación de vía biliar. Sin líquido libre peritoneal.",
            "TAC":         "Apéndice cecal engrosado de 10 mm de diámetro con realce mural y líquido periapendicular. Hallazgos compatibles con apendicitis aguda no perforada.",
            "Resonancia Magnética": "Sin lesiones focales parenquimatosas. Sistema ventricular de tamaño y morfología normales. Sin evidencia de sangrado ni efecto de masa.",
            "Mamografía":  "Densidad mamaria tipo B (ACR). Sin nódulos, distorsiones arquitecturales ni microcalcificaciones sospechosas. BI-RADS 1.",
        }
        conclusiones_map = {
            "Radiografía": "Hallazgos compatibles con neumonía lobar derecha. Correlacionar clínicamente y con laboratorio.",
            "Ecografía":   "Colelitiasis múltiple con signos de colecistitis crónica. Se recomienda valoración por Cirugía General.",
            "TAC":         "Apendicitis aguda no perforada. Urgencia quirúrgica. Comunicar a cirujano de guardia.",
            "Resonancia Magnética": "Estudio dentro de límites normales para la edad del paciente.",
            "Mamografía":  "Mamografía sin hallazgos de malignidad. Control anual recomendado según protocolo.",
        }
        return {
            "tipo_estudio": tipo,
            "region_anatomica": region,
            "fecha_estudio": datetime.now().strftime("%Y-%m-%d"),
            "hallazgos": hallazgos_map.get(tipo, "Sin hallazgos patológicos significativos."),
            "conclusion": conclusiones_map.get(tipo, "Estudio dentro de parámetros normales."),
            "medico_radiologo": fake.name(),
        }

    elif template_name == "Informe de Patología":
        tejidos = [
            ("Apéndice cecal",       "Apendicitis aguda supurada con peritonitis focal."),
            ("Vesícula biliar",       "Colecistitis crónica calculosa con metaplasia intestinal focal."),
            ("Nódulo mamario",        "Fibroadenoma mamario benigno. Sin atipia epitelial."),
            ("Fragmento gástrico",    "Gastritis crónica atrófica con metaplasia intestinal. H. pylori negativo."),
            ("Pólipo colónico",       "Adenoma tubular con displasia de bajo grado. Márgenes libres."),
            ("Ganglio linfático",     "Hiperplasia linfoide reactiva. Sin evidencia de malignidad."),
        ]
        tejido, dx = random.choice(tejidos)
        return {
            "material_recibido": tejido,
            "fecha_recepcion": datetime.now().strftime("%Y-%m-%d"),
            "descripcion_macroscopica": (
                f"Se recibe fragmento de tejido de {tejido.lower()} de aproximadamente "
                f"{random.randint(2,8)} x {random.randint(1,5)} cm, superficie externa irregular, "
                f"consistencia firme, coloración parduzca al corte."
            ),
            "descripcion_microscopica": (
                "Cortes histológicos con tinción H-E que muestran alteraciones inflamatorias crónicas "
                "con infiltrado linfocitario periglandular difuso. No se identifican células malignas "
                "en el material estudiado."
            ),
            "diagnostico_histopatologico": dx,
            "observaciones": "Estudio inmunohistoquímico no requerido en esta instancia. Correlacionar con hallazgos clínicos.",
            "patologo": fake.name(),
        }

    elif template_name == "Nota Preoperatoria":
        proc = random.choice(PROCEDIMIENTOS_QX)
        return {
            "procedimiento_programado": proc,
            "fecha_programada": (datetime.now() + timedelta(days=random.randint(1, 5))).strftime("%Y-%m-%d"),
            "evaluacion_preoperatoria": random.choice([
                "Paciente ASA II. Función cardiorrespiratoria compensada. Apto para cirugía electiva.",
                "Paciente ASA III por HTA y DM2. Riesgo quirúrgico moderado. Requiere monitoreo intraoperatorio intensivo.",
                "Paciente ASA I. Sin comorbilidades relevantes. Bajo riesgo anestésico-quirúrgico.",
                "Paciente ASA II. Antecedente de HTA controlada. Exámenes preoperatorios dentro de rangos aceptables.",
            ]),
            "riesgo_anestesico": random.choice(["ASA I", "ASA II", "ASA III"]),
            "tipo_anestesia_planificada": random.choice([
                "Anestesia General balanceada",
                "Anestesia Regional (espinal)",
                "Anestesia Regional (epidural)",
                "Sedación consciente con propofol",
            ]),
            "plan_quirurgico": f"Proceder con {proc.lower()} bajo protocolo estándar. Profilaxis antibiótica 30 min antes de incisión.",
            "consentimiento_firmado": "Sí — firmado por el paciente y archivado en expediente clínico.",
        }

    elif template_name == "Registro Anestésico":
        inicio = datetime.now() - timedelta(hours=random.randint(2, 6))
        fin = datetime.now()
        return {
            "tipo_anestesia": random.choice(["General balanceada", "Espinal", "Epidural", "Sedación con propofol"]),
            "hora_inicio": inicio.strftime("%H:%M"),
            "hora_fin": fin.strftime("%H:%M"),
            "duracion_minutos": int((fin - inicio).total_seconds() / 60),
            "medicamentos_induccion": [
                {"medicamento": "Propofol",      "dosis": f"{random.randint(100,200)} mg IV"},
                {"medicamento": "Fentanilo",      "dosis": f"{random.randint(50,150)} mcg IV"},
                {"medicamento": "Succinilcolina", "dosis": f"{random.randint(80,120)} mg IV"},
            ],
            "agentes_mantenimiento": random.choice([
                "Sevoflurano 2% + O2/N2O 50/50%",
                "Propofol en infusión continua TCI + Remifentanilo",
                "Isoflurano 1.5% + O2 100%",
            ]),
            "pa_min": f"{random.randint(85,110)}/{random.randint(50,70)} mmHg",
            "pa_max": f"{random.randint(120,155)}/{random.randint(75,95)} mmHg",
            "fc_media": f"{random.randint(60,100)} lpm",
            "spo2_min": f"{random.randint(94,99)}%",
            "incidentes_complicaciones": random.choice([
                "Sin incidentes. Procedimiento transcurrió sin complicaciones anestésicas.",
                "Hipotensión transitoria en inducción, corregida con efedrina 10 mg IV. Evolución posterior sin novedad.",
                "Laringoespasmo leve al inicio de inducción, resuelto con presión positiva de 10 cmH2O.",
            ]),
            "egreso": random.choice(["Sala de Recuperación Postanestésica (SRPA)", "UCI para monitoreo intensivo"]),
        }

    elif template_name == "Nota Postoperatoria":
        proc = random.choice(PROCEDIMIENTOS_QX)
        inicio = datetime.now() - timedelta(hours=random.randint(2, 5))
        return {
            "procedimiento_realizado": proc,
            "fecha_hora_inicio": inicio.strftime("%Y-%m-%dT%H:%M"),
            "fecha_hora_fin": datetime.now().strftime("%Y-%m-%dT%H:%M"),
            "cirujano_principal": fake.name(),
            "primer_ayudante": fake.name(),
            "hallazgos_intraoperatorios": random.choice([
                "Apéndice cecal perforado con plastrón periapendicular y escaso líquido libre purulento en FID.",
                "Vesícula con múltiples cálculos, paredes engrosadas a 5 mm, sin colédoco dilatado. Sin líquido libre.",
                "Hernia inguinal indirecta derecha con saco herniario pequeño y contenido epiplóico. Sin compromiso vascular.",
                "Útero de tamaño aumentado con miomas subserosos múltiples, el mayor de 6 cm en cara anterior.",
            ]),
            "tecnica_utilizada": random.choice([
                "Técnica laparoscópica con 3 trócares (10 mm umbilical + 2 x 5 mm)",
                "Técnica abierta con incisión de Pfannenstiel y Kerr uterino segmentario",
                "Técnica laparoscópica hand-assisted con conversión sin incidentes",
            ]),
            "sangrado_estimado": f"{random.randint(50, 500)} cc",
            "conteo_gasas_instrumental": "Correcto. Conteo completo de gasas, compresas e instrumental al cierre de cavidad.",
            "condicion_egreso": random.choice([
                "Extubado en quirófano con buen patrón ventilatorio. Pasa a sala de recuperación.",
                "Estable hemodinámicamente. Pasa a UCI para monitoreo postquirúrgico de 24h.",
                "Toleró bien el procedimiento. Extubado. Traslado a sala de hospitalización.",
            ]),
        }

    elif template_name == "Hoja de Enfermería":
        meds_admin = random.sample([
            {"medicamento": "Metronidazol",    "dosis": "500 mg IV",  "hora": "08:00"},
            {"medicamento": "Ketorolaco",       "dosis": "30 mg IV",   "hora": "08:00"},
            {"medicamento": "Omeprazol",        "dosis": "40 mg IV",   "hora": "12:00"},
            {"medicamento": "Ceftriaxona",      "dosis": "1 g IV",     "hora": "06:00"},
            {"medicamento": "Metoclopramida",   "dosis": "10 mg IV",   "hora": "14:00"},
        ], random.randint(1, 3))
        return {
            "fecha_turno": datetime.now().strftime("%Y-%m-%d"),
            "turno": random.choice(["Mañana", "Tarde", "Noche"]),
            "enfermera_responsable": fake.name(),
            "medicamentos_administrados": meds_admin,
            "ingresos_vo": f"{random.randint(200, 800)} ml",
            "ingresos_ev": f"{random.randint(500, 2000)} ml",
            "diuresis": f"{random.randint(400, 2000)} ml",
            "otras_perdidas": f"{random.randint(0, 300)} ml (drenaje quirúrgico / herida)",
            "balance_neto": f"{random.randint(-200, 600)} ml",
            "cuidados_aplicados": random.choice([
                "Curación de herida quirúrgica con solución salina. Cambio de apósito. Herida limpia y seca.",
                "Movilización pasiva en cama cada 2 horas. Posición semisentado a 30°. Aspiración de secreciones PRN.",
                "Control de drenaje quirúrgico: 30 cc de líquido serohemático en 8 horas de turno.",
            ]),
            "observaciones_enfermeria": random.choice([
                "Paciente refiere dolor EVA 4/10. Se administró analgesia con mejoría parcial.",
                "Paciente tranquilo y colaborador. Diuresis espontánea conservada. Sin cambios.",
                "Se notifica al médico de guardia por fiebre de 38.4 °C. Se indica paracetamol.",
            ]),
        }

    elif template_name == "Kardex":
        trts = random.sample([
            {"medicamento": "Ceftriaxona",    "dosis": "1g IV",   "frecuencia": "Cada 12 horas"},
            {"medicamento": "Ketorolaco",     "dosis": "30mg IV", "frecuencia": "Cada 8 horas SOS dolor"},
            {"medicamento": "Metoclopramida", "dosis": "10mg IV", "frecuencia": "Cada 8 horas"},
            {"medicamento": "Omeprazol",      "dosis": "40mg IV", "frecuencia": "Cada 24 horas"},
            {"medicamento": "Heparina",       "dosis": "5000 UI SC", "frecuencia": "Cada 12 horas profilaxis"},
        ], random.randint(2, 4))
        return {
            "fecha_actualizacion": datetime.now().strftime("%Y-%m-%d"),
            "diagnostico_actual": random.choice(DIAGNOSTICS),
            "alergias": random.choice(["Penicilina", "Ninguna conocida", "AINEs", "Sulfonamidas"]),
            "dieta_prescrita": random.choice([
                "Dieta blanda hiposódica", "Dieta absoluta (NPO)", "Dieta hiperproteica", "Dieta libre habitual",
            ]),
            "tratamientos_vigentes": trts,
            "actividad_prescrita": random.choice([
                "Reposo absoluto en cama con barandas elevadas",
                "Reposo relativo con movilización asistida por enfermería",
                "Deambulación progresiva con ayuda desde hoy",
            ]),
            "cuidados_especiales": random.choice([
                "Control de diuresis horaria. Balance hídrico estricto cada 8 horas.",
                "Curación de herida cada 24 h. Observar signos de infección (rubor, calor, exudado).",
                "Monitoreo de glucemia capilar cada 6 horas. Corrección con insulina cristalina según escala.",
            ]),
        }

    elif template_name == "Notas de Trabajo Social / Psicología":
        return {
            "tipo_nota": random.choice(["Trabajo Social", "Psicología"]),
            "fecha_evaluacion": datetime.now().strftime("%Y-%m-%d"),
            "profesional": fake.name(),
            "motivo_evaluacion": random.choice([
                "Valoración socioeconómica por riesgo de abandono de tratamiento médico.",
                "Evaluación psicológica por diagnóstico oncológico reciente y respuesta emocional.",
                "Intervención en crisis situacional tras pérdida de familiar durante hospitalización.",
                "Detección de redes de apoyo familiar y social para planificación del alta.",
            ]),
            "evaluacion_psicosocial": random.choice([
                "Paciente con red familiar de apoyo adecuada. Condiciones económicas limitadas. Se gestiona acceso a medicamentos gratuitos mediante SEDES.",
                "Paciente presenta tristeza reactiva al diagnóstico. Sin ideación suicida. Orientado, colaborador y con insight conservado.",
                "Familia informada sobre diagnóstico y pronóstico. Buena adherencia terapéutica esperada. Ambiente familiar contenedor.",
                "Se detecta consumo de alcohol crónico. Se deriva a grupo de apoyo y psiquiatría para evaluación integral.",
            ]),
            "plan_intervencion": random.choice([
                "Seguimiento semanal en consulta externa. Coordinación con trabajo social del SEDES.",
                "Sesiones de psicoterapia de apoyo cognitivo-conductual. Psicoeducación a la familia.",
                "Gestión de subsidio de movilidad y medicamentos de alto costo. Próxima evaluación en 15 días.",
            ]),
        }

    elif template_name == "Consentimiento Informado":
        proc = random.choice(PROCEDIMIENTOS_QX)
        return {
            "procedimiento": proc,
            "medico_informante": fake.name(),
            "fecha_firma": datetime.now().strftime("%Y-%m-%d"),
            "descripcion_procedimiento": (
                f"Se explicó al paciente y/o familiar responsable en qué consiste el procedimiento de "
                f"{proc.lower()}, sus objetivos terapéuticos, la técnica a utilizar, la anestesia "
                f"requerida y las posibles alternativas no quirúrgicas."
            ),
            "riesgos_explicados": random.choice([
                "Sangrado intraoperatorio, infección del sitio quirúrgico, reacciones adversas a la anestesia, lesión de estructuras adyacentes.",
                "Hemorragia postoperatoria, dehiscencia de herida, fístula, trombosis venosa profunda, embolismo pulmonar.",
                "Reacción adversa al medio de contraste, nefrotoxicidad, hematoma en sitio de punción vascular.",
            ]),
            "beneficios_explicados": "Resolución definitiva del cuadro patológico actual, con mejoría esperada de calidad de vida y reducción del riesgo de complicaciones mayores.",
            "paciente_comprende": "Sí",
            "firma_responsable": "Firmado por el paciente / representante legal debidamente identificado. Copia entregada al paciente.",
        }

    elif template_name == "Certificado Médico":
        dias = random.randint(1, 15)
        inicio = datetime.now()
        return {
            "proposito": random.choice([
                "Justificación de inasistencia laboral",
                "Trámite de seguro médico",
                "Inscripción o baja en institución educativa",
                "Solicitud de licencia por enfermedad ante empleador",
                "Apto físico para actividad deportiva",
            ]),
            "diagnostico_certificado": random.choice(DIAGNOSTICS),
            "dias_reposo_indicados": dias,
            "fecha_inicio_reposo": inicio.strftime("%Y-%m-%d"),
            "fecha_fin_reposo": (inicio + timedelta(days=dias)).strftime("%Y-%m-%d"),
            "observaciones": random.choice([
                "El paciente requiere reposo absoluto durante el período indicado. No conducir ni operar maquinaria.",
                "Puede realizar actividades de baja demanda física con supervisión. Evitar esfuerzos físicos intensos.",
                "Paciente en tratamiento médico activo. Se recomienda control médico en 7 días para reevaluación.",
            ]),
            "medico_emisor": fake.name(),
            "fecha_emision": inicio.strftime("%Y-%m-%d"),
        }

    elif template_name == "Hoja de Alta Voluntaria":
        return {
            "fecha_hora": datetime.now().strftime("%Y-%m-%dT%H:%M"),
            "servicio": random.choice(["Medicina Interna", "Cirugía General", "Urgencias", "Pediatría", "Ginecología"]),
            "motivo_alta_voluntaria": random.choice([
                "Paciente solicita alta voluntaria por motivos personales y familiares impostergables.",
                "Familiar responsable solicita traslado a institución de salud de su preferencia.",
                "Paciente refiere sentirse bien y desea continuar tratamiento de forma ambulatoria.",
            ]),
            "riesgos_informados": (
                "Se explicaron detalladamente los riesgos que implica abandonar el tratamiento hospitalario "
                "antes del alta médica, incluyendo agravamiento del cuadro clínico, complicaciones graves "
                "y posible riesgo vital. El paciente/representante declara comprender la información."
            ),
            "paciente_comprende_riesgos": "Sí",
            "medico_que_informa": fake.name(),
            "firma_responsable": "Firmado por el paciente / representante legal debidamente identificado.",
        }

    elif template_name == "Certificado de Defunción":
        causas = [
            ("Paro cardiorrespiratorio",    "Infarto agudo de miocardio (STEMI anterior extenso)", "Cardiopatía isquémica crónica"),
            ("Shock séptico refractario",   "Sepsis de foco pulmonar por Klebsiella pneumoniae",   "Neumonía nosocomial grave"),
            ("Falla hepática aguda",        "Cirrosis hepática descompensada con peritonitis bacteriana espontánea", "Hepatitis crónica por VHC"),
            ("Paro cardiorrespiratorio",    "Traumatismo craneoencefálico severo con herniación transtentorial", "Accidente de tránsito"),
            ("Falla multiorgánica",         "Sepsis de foco abdominal", "Peritonitis secundaria a perforación de víscera hueca"),
        ]
        cd, cs, cb = random.choice(causas)
        return {
            "fecha_defuncion": datetime.now().strftime("%Y-%m-%d"),
            "hora_defuncion": datetime.now().strftime("%H:%M"),
            "lugar_defuncion": random.choice([
                "Sala de UCI — cama N°" + str(random.randint(1, 12)),
                "Sala de emergencias — box de reanimación",
                "Sala de hospitalización — piso " + str(random.randint(2, 5)),
            ]),
            "causa_directa": cd,
            "causa_subyacente": cs,
            "causa_basica": cb,
            "otras_condiciones_contribuyentes": random.choice([
                "Diabetes mellitus tipo 2. Hipertensión arterial crónica. Insuficiencia renal crónica.",
                "Sin otras condiciones contribuyentes registradas en el expediente.",
                "Obesidad grado II. Tabaquismo crónico. Enfermedad pulmonar obstructiva crónica.",
            ]),
            "tipo_muerte": random.choice(["Natural", "Accidental"]),
            "medico_certificante": fake.name(),
            "numero_registro": f"DEF-{datetime.now().year}-{random.randint(1000, 9999)}",
        }

    elif template_name == "Nota de Alta":
        ingreso = datetime.now() - timedelta(days=random.randint(3, 10))
        alta = datetime.now()
        dx = random.choice(DIAGNOSTICS)
        return {
            "fecha_ingreso": ingreso.strftime("%Y-%m-%d"),
            "fecha_alta": alta.strftime("%Y-%m-%d"),
            "diagnostico_principal": dx,
            "diagnostico_alta": dx.rstrip('.') + " (Resuelto).",
            "diagnosticos_secundarios": "Ninguno de relevancia.",
            "procedimientos_realizados": "Hidratación endovenosa y monitoreo clínico continuo de signos vitales.",
            "evolucion_clinica": "Paciente evoluciona favorablemente respondiendo al tratamiento médico instaurado.",
            "resumen_tratamiento": "Esquema completo de antibióticos y soporte electrolítico endovenoso durante la internación.",
            "medicinas_alta": "Paracetamol 500mg cada 8 horas vía oral por 3 días si presenta dolor o fiebre.",
            "restricciones_actividad": "Reposo relativo por 48 horas. Evitar esfuerzos físicos intensos.",
            "actividades_permitidas": "Caminatas leves, alimentación habitual sin grasas saturadas ni irritantes.",
            "restricciones_dieteticas": "Evitar alimentos irritantes, bebidas alcohólicas y grasas saturadas.",
            "cuidados_heridas": "No aplica en este caso.",
            "instrucciones_seguimiento": "Acudir por consulta externa en 7 días para control médico general y revisión de resultados.",
            "fecha_recomendada_retorno": (alta + timedelta(days=7)).strftime("%Y-%m-%d"),
        }

    return {}


# ── Definición de plantillas ──────────────────────────────────────────────────

DOC_TEMPLATES = [
    {
        "name": "Ficha de Ingreso",
        "description": "Datos básicos de admisión del paciente al establecimiento.",
        "ui_schema": {
            "tipo_sangre": {
                "type": "SELECT", "required": True, "label": "Grupo Sanguíneo", "order": 1,
                "options": {"O_POS": "O Positivo", "O_NEG": "O Negativo", "A_POS": "A Positivo", "B_POS": "B Positivo"}
            },
            "observaciones": {"type": "TEXTAREA", "required": False, "label": "Notas de Admisión", "order": 2}
        }
    },
    {
        "name": "Historia Clínica",
        "description": "Documento inicial completo con motivo de consulta, antecedentes familiares, patológicos y estilo de vida.",
        "ui_schema": {
            "motivo_consulta":          {"type": "TEXTAREA", "required": True,  "label": "Motivo de Consulta",                "order": 1},
            "antecedentes_familiares":  {"type": "TEXTAREA", "required": False, "label": "Antecedentes Familiares",           "order": 2},
            "antecedentes_patologicos": {"type": "TEXTAREA", "required": False, "label": "Antecedentes Patológicos Personales","order": 3},
            "antecedentes_no_patologicos": {"type": "TEXTAREA", "required": False, "label": "Antecedentes No Patológicos (Hábitos)", "order": 4},
            "alergias_declaradas":      {"type": "TEXT",     "required": False, "label": "Alergias Declaradas",               "order": 5},
            "exploracion_fisica":       {"type": "TEXTAREA", "required": True,  "label": "Exploración Física",                "order": 6},
            "diagnostico_presuntivo":   {"type": "TEXT",     "required": True,  "label": "Diagnóstico Presuntivo",            "order": 7},
            "plan_tratamiento":         {"type": "TEXTAREA", "required": False, "label": "Plan de Tratamiento",               "order": 8},
        }
    },
    {
        "name": "Nota de Ingreso",
        "description": "Registro detallado cuando un paciente es admitido en urgencias o piso de hospitalización.",
        "ui_schema": {
            "servicio_ingreso":      {"type": "SELECT",   "required": True,  "label": "Servicio de Ingreso", "order": 1,
                                      "options": {"URGENCIAS": "Urgencias", "MED_INTERNA": "Medicina Interna", "CIRUGIA": "Cirugía General", "PEDIATRIA": "Pediatría", "GINECOLOGIA": "Ginecología"}},
            "fecha_hora_ingreso":    {"type": "DATE",     "required": True,  "label": "Fecha y Hora de Ingreso",             "order": 2},
            "motivo_ingreso":        {"type": "TEXTAREA", "required": True,  "label": "Motivo de Ingreso",                   "order": 3},
            "estado_general":        {"type": "SELECT",   "required": True,  "label": "Estado General", "order": 4,
                                      "options": {"ESTABLE": "Estable", "REGULAR": "Regular", "MALO": "Malo", "CRITICO": "Crítico"}},
            "pa":                    {"type": "TEXT",     "required": True,  "label": "Presión Arterial (mmHg)",             "order": 5},
            "fc":                    {"type": "TEXT",     "required": True,  "label": "Frecuencia Cardíaca (lpm)",           "order": 6},
            "fr":                    {"type": "TEXT",     "required": True,  "label": "Frecuencia Respiratoria (rpm)",       "order": 7},
            "temperatura":           {"type": "TEXT",     "required": True,  "label": "Temperatura (°C)",                   "order": 8},
            "spo2":                  {"type": "TEXT",     "required": False, "label": "Saturación O2 (%)",                  "order": 9},
            "impresion_diagnostica": {"type": "TEXT",     "required": True,  "label": "Impresión Diagnóstica",              "order": 10},
            "plan_inicial":          {"type": "TEXTAREA", "required": True,  "label": "Plan Inicial",                       "order": 11},
        }
    },
    {
        "name": "Nota de Evolución",
        "description": "Reporte diario (o por turno) sobre los cambios del paciente, signos vitales y respuesta al tratamiento.",
        "ui_schema": {
            "fecha_hora":            {"type": "DATE",     "required": True,  "label": "Fecha y Hora de la Nota",   "order": 1},
            "turno":                 {"type": "SELECT",   "required": True,  "label": "Turno", "order": 2,
                                      "options": {"MANANA": "Mañana (07:00-13:00)", "TARDE": "Tarde (13:00-19:00)", "NOCHE": "Noche (19:00-07:00)"}},
            "pa":                    {"type": "TEXT",     "required": True,  "label": "Presión Arterial (mmHg)",   "order": 3},
            "fc":                    {"type": "TEXT",     "required": True,  "label": "Frecuencia Cardíaca (lpm)", "order": 4},
            "fr":                    {"type": "TEXT",     "required": False, "label": "Frecuencia Respiratoria",   "order": 5},
            "temperatura":           {"type": "TEXT",     "required": True,  "label": "Temperatura (°C)",          "order": 6},
            "evolucion_subjetiva":   {"type": "TEXTAREA", "required": True,  "label": "Evolución Subjetiva (Anamnesis del turno)", "order": 7},
            "examen_fisico":         {"type": "TEXTAREA", "required": True,  "label": "Examen Físico",             "order": 8},
            "respuesta_tratamiento": {"type": "SELECT",   "required": True,  "label": "Respuesta al Tratamiento", "order": 9,
                                      "options": {"FAVORABLE": "Favorable", "PARCIAL": "Parcial", "SIN_CAMBIOS": "Sin cambios", "TORPIDA": "Tórpida"}},
            "ajuste_plan":           {"type": "TEXTAREA", "required": False, "label": "Ajuste de Plan Terapéutico", "order": 10},
        }
    },
    {
        "name": "Nota de Interconsulta",
        "description": "Solicitud formal y respuesta entre médicos cuando se requiere la opinión de otra especialidad.",
        "ui_schema": {
            "especialidad_solicitante":    {"type": "TEXT",     "required": True,  "label": "Especialidad Solicitante",       "order": 1},
            "especialidad_interconsultada":{"type": "SELECT",   "required": True,  "label": "Especialidad Interconsultada",   "order": 2,
                                            "options": {"CARDIOLOGIA": "Cardiología", "NEUROLOGIA": "Neurología", "NEFROLOGIA": "Nefrología",
                                                        "ENDOCRINOLOGIA": "Endocrinología", "TRAUMATOLOGIA": "Traumatología", "PSIQUIATRIA": "Psiquiatría", "ONCOLOGIA": "Oncología"}},
            "fecha_solicitud":             {"type": "DATE",     "required": True,  "label": "Fecha de Solicitud",            "order": 3},
            "motivo_interconsulta":        {"type": "TEXTAREA", "required": True,  "label": "Motivo de Interconsulta",        "order": 4},
            "resumen_clinico":             {"type": "TEXTAREA", "required": True,  "label": "Resumen Clínico del Paciente",   "order": 5},
            "respuesta_interconsulta":     {"type": "TEXTAREA", "required": False, "label": "Respuesta de Interconsulta",     "order": 6},
            "fecha_respuesta":             {"type": "DATE",     "required": False, "label": "Fecha de Respuesta",             "order": 7},
        }
    },
    {
        "name": "Receta Médica Estándar (Multi-Medicamento)",
        "description": "Plantilla oficial que permite la prescripción de uno o múltiples medicamentos dentro de una lista dinámica.",
        "ui_schema": {
            "diagnostico_principal": {"type": "TEXT", "required": True, "label": "Diagnóstico Principal", "order": 1},
            "medicamentos_recetados": {
                "type": "ARRAY", "required": True, "label": "Lista de Medicamentos Prescritos", "order": 2,
                "subSchema": {
                    "nombre_medicamento": {"type": "TEXT",   "required": True, "label": "Medicamento",                        "order": 1},
                    "dosis":              {"type": "TEXT",   "required": True, "label": "Dosis y Presentación",               "order": 2},
                    "frecuencia":         {"type": "SELECT", "required": True, "label": "Frecuencia de Toma",                 "order": 3,
                                           "options": {"CADA_4_HRS": "Cada 4 horas", "CADA_6_HRS": "Cada 6 horas",
                                                       "CADA_8_HRS": "Cada 8 horas", "CADA_12_HRS": "Cada 12 horas",
                                                       "CADA_24_HRS": "Una vez al día", "CONDICIONAL": "Condicional al dolor"}},
                    "duracion":           {"type": "NUMBER", "required": True, "label": "Duración (Días)",                    "order": 4},
                }
            },
            "indicaciones_adicionales": {"type": "TEXTAREA", "required": False, "label": "Indicaciones Generales", "order": 3},
        }
    },
    {
        "name": "Orden de Laboratorio",
        "description": "Solicitud para análisis de sangre, orina, cultivos u otros fluidos biológicos.",
        "ui_schema": {
            "diagnostico_clinico":    {"type": "TEXT",     "required": True,  "label": "Diagnóstico Clínico",          "order": 1},
            "examenes_solicitados":   {
                "type": "ARRAY", "required": True, "label": "Exámenes Solicitados", "order": 2,
                "subSchema": {"examen": {"type": "TEXT", "required": True, "label": "Nombre del Examen", "order": 1}}
            },
            "indicacion_clinica":     {"type": "TEXTAREA", "required": True,  "label": "Indicación Clínica / Justificación", "order": 3},
            "prioridad":              {"type": "SELECT",   "required": True,  "label": "Prioridad", "order": 4,
                                       "options": {"URGENTE": "Urgente", "RUTINA": "Rutina"}},
            "notas":                  {"type": "TEXTAREA", "required": False, "label": "Notas Adicionales para el Laboratorio", "order": 5},
        }
    },
    {
        "name": "Orden de Imagenología",
        "description": "Solicitud de estudios radiológicos y de diagnóstico por imagen.",
        "ui_schema": {
            "diagnostico_principal": {"type": "TEXTAREA", "required": True,  "label": "Diagnóstico Principal",                  "order": 1},
            "estudio_solicitado":    {"type": "TEXT",     "required": True,  "label": "Estudio Solicitado (Ej. TAC de Tórax)",  "order": 2},
            "indicacion_clinica":    {"type": "TEXTAREA", "required": True,  "label": "Indicación Clínica / Motivo del Estudio","order": 3},
            "notas_adicionales":     {"type": "TEXTAREA", "required": False, "label": "Notas Adicionales",                      "order": 4},
        }
    },
    {
        "name": "Informe de Imagenología",
        "description": "Resultados e interpretación de radiografías, tomografías (TAC), resonancias o ecografías.",
        "ui_schema": {
            "tipo_estudio":      {"type": "SELECT",   "required": True,  "label": "Tipo de Estudio", "order": 1,
                                  "options": {"RX": "Radiografía", "ECO": "Ecografía", "TAC": "Tomografía Computarizada (TAC)",
                                              "RM": "Resonancia Magnética", "MAMOGRAFIA": "Mamografía"}},
            "region_anatomica":  {"type": "TEXT",     "required": True,  "label": "Región Anatómica Estudiada",     "order": 2},
            "fecha_estudio":     {"type": "DATE",     "required": True,  "label": "Fecha del Estudio",              "order": 3},
            "hallazgos":         {"type": "TEXTAREA", "required": True,  "label": "Hallazgos Radiológicos",         "order": 4},
            "conclusion":        {"type": "TEXTAREA", "required": True,  "label": "Conclusión / Diagnóstico",       "order": 5},
            "medico_radiologo":  {"type": "TEXT",     "required": True,  "label": "Médico Radiólogo Informante",    "order": 6},
        }
    },
    {
        "name": "Informe de Patología",
        "description": "Análisis de biopsias o tejidos extraídos en cirugías para confirmar diagnósticos histológicos.",
        "ui_schema": {
            "material_recibido":              {"type": "TEXT",     "required": True,  "label": "Material / Tejido Recibido",          "order": 1},
            "fecha_recepcion":                {"type": "DATE",     "required": True,  "label": "Fecha de Recepción de Muestra",       "order": 2},
            "descripcion_macroscopica":       {"type": "TEXTAREA", "required": False, "label": "Descripción Macroscópica",            "order": 3},
            "descripcion_microscopica":       {"type": "TEXTAREA", "required": True,  "label": "Descripción Microscópica (H-E)",      "order": 4},
            "diagnostico_histopatologico":    {"type": "TEXT",     "required": True,  "label": "Diagnóstico Histopatológico",         "order": 5},
            "observaciones":                  {"type": "TEXTAREA", "required": False, "label": "Observaciones / Estudios Adicionales","order": 6},
            "patologo":                       {"type": "TEXT",     "required": True,  "label": "Médico Patólogo",                     "order": 7},
        }
    },
    {
        "name": "Nota Preoperatoria",
        "description": "Evaluación previa a cirugía: plan quirúrgico, riesgo anestésico y pronóstico del paciente.",
        "ui_schema": {
            "procedimiento_programado":   {"type": "TEXT",     "required": True,  "label": "Procedimiento Quirúrgico Programado",    "order": 1},
            "fecha_programada":           {"type": "DATE",     "required": True,  "label": "Fecha Programada de Cirugía",            "order": 2},
            "evaluacion_preoperatoria":   {"type": "TEXTAREA", "required": True,  "label": "Evaluación Preoperatoria",               "order": 3},
            "riesgo_anestesico":          {"type": "SELECT",   "required": True,  "label": "Riesgo Anestésico (ASA)", "order": 4,
                                           "options": {"ASA_I": "ASA I — Sin enf. sistémica", "ASA_II": "ASA II — Enf. sistémica leve",
                                                       "ASA_III": "ASA III — Enf. sistémica grave", "ASA_IV": "ASA IV — Riesgo vital constante"}},
            "tipo_anestesia_planificada": {"type": "SELECT",   "required": True,  "label": "Tipo de Anestesia Planificada", "order": 5,
                                           "options": {"GENERAL": "Anestesia General", "ESPINAL": "Regional (Espinal)",
                                                       "EPIDURAL": "Regional (Epidural)", "SEDACION": "Sedación Consciente"}},
            "plan_quirurgico":            {"type": "TEXTAREA", "required": True,  "label": "Plan Quirúrgico",                        "order": 6},
            "consentimiento_firmado":     {"type": "SELECT",   "required": True,  "label": "Consentimiento Informado Firmado", "order": 7,
                                           "options": {"SI": "Sí — Archivado en expediente", "NO": "No — Pendiente"}},
        }
    },
    {
        "name": "Registro Anestésico",
        "description": "Gráfica detallada de medicamentos, agentes anestésicos y signos vitales durante la cirugía.",
        "ui_schema": {
            "tipo_anestesia":          {"type": "SELECT",   "required": True,  "label": "Tipo de Anestesia", "order": 1,
                                        "options": {"GENERAL": "General balanceada", "ESPINAL": "Espinal", "EPIDURAL": "Epidural", "SEDACION": "Sedación con propofol"}},
            "hora_inicio":             {"type": "TEXT",     "required": True,  "label": "Hora de Inicio (HH:MM)",              "order": 2},
            "hora_fin":                {"type": "TEXT",     "required": True,  "label": "Hora de Fin (HH:MM)",                 "order": 3},
            "duracion_minutos":        {"type": "NUMBER",   "required": False, "label": "Duración (minutos)",                  "order": 4},
            "medicamentos_induccion":  {
                "type": "ARRAY", "required": True, "label": "Medicamentos de Inducción", "order": 5,
                "subSchema": {
                    "medicamento": {"type": "TEXT", "required": True, "label": "Medicamento", "order": 1},
                    "dosis":       {"type": "TEXT", "required": True, "label": "Dosis",       "order": 2},
                }
            },
            "agentes_mantenimiento":   {"type": "TEXT",     "required": True,  "label": "Agentes de Mantenimiento",            "order": 6},
            "pa_min":                  {"type": "TEXT",     "required": True,  "label": "PA Mínima Intraoperatoria",           "order": 7},
            "pa_max":                  {"type": "TEXT",     "required": True,  "label": "PA Máxima Intraoperatoria",           "order": 8},
            "fc_media":                {"type": "TEXT",     "required": False, "label": "FC Media Intraoperatoria",            "order": 9},
            "spo2_min":                {"type": "TEXT",     "required": False, "label": "SpO2 Mínima (%)",                     "order": 10},
            "incidentes_complicaciones":{"type": "TEXTAREA","required": True,  "label": "Incidentes / Complicaciones",         "order": 11},
            "egreso":                  {"type": "TEXT",     "required": True,  "label": "Destino al Egreso de Quirófano",      "order": 12},
        }
    },
    {
        "name": "Nota Postoperatoria",
        "description": "Descripción detallada del procedimiento quirúrgico, hallazgos, sangrado y condición al egreso.",
        "ui_schema": {
            "procedimiento_realizado":      {"type": "TEXT",     "required": True,  "label": "Procedimiento Realizado",              "order": 1},
            "fecha_hora_inicio":            {"type": "DATE",     "required": True,  "label": "Fecha y Hora de Inicio de Cirugía",    "order": 2},
            "fecha_hora_fin":               {"type": "DATE",     "required": True,  "label": "Fecha y Hora de Fin de Cirugía",       "order": 3},
            "cirujano_principal":           {"type": "TEXT",     "required": True,  "label": "Cirujano Principal",                   "order": 4},
            "primer_ayudante":              {"type": "TEXT",     "required": False, "label": "Primer Ayudante",                      "order": 5},
            "hallazgos_intraoperatorios":   {"type": "TEXTAREA", "required": True,  "label": "Hallazgos Intraoperatorios",           "order": 6},
            "tecnica_utilizada":            {"type": "TEXT",     "required": True,  "label": "Técnica Quirúrgica Utilizada",         "order": 7},
            "sangrado_estimado":            {"type": "TEXT",     "required": True,  "label": "Sangrado Estimado (cc)",               "order": 8},
            "conteo_gasas_instrumental":    {"type": "TEXT",     "required": True,  "label": "Conteo de Gasas e Instrumental",       "order": 9},
            "condicion_egreso":             {"type": "TEXTAREA", "required": True,  "label": "Condición al Egreso de Quirófano",     "order": 10},
        }
    },
    {
        "name": "Hoja de Enfermería",
        "description": "Registro de administración de medicamentos, balance de líquidos y cuidados de enfermería por turno.",
        "ui_schema": {
            "fecha_turno":              {"type": "DATE",     "required": True,  "label": "Fecha",                                    "order": 1},
            "turno":                    {"type": "SELECT",   "required": True,  "label": "Turno", "order": 2,
                                         "options": {"MANANA": "Mañana", "TARDE": "Tarde", "NOCHE": "Noche"}},
            "enfermera_responsable":    {"type": "TEXT",     "required": True,  "label": "Enfermera/o Responsable del Turno",        "order": 3},
            "medicamentos_administrados":{
                "type": "ARRAY", "required": True, "label": "Medicamentos Administrados", "order": 4,
                "subSchema": {
                    "medicamento": {"type": "TEXT", "required": True, "label": "Medicamento", "order": 1},
                    "dosis":       {"type": "TEXT", "required": True, "label": "Dosis",       "order": 2},
                    "hora":        {"type": "TEXT", "required": True, "label": "Hora (HH:MM)","order": 3},
                }
            },
            "ingresos_vo":           {"type": "TEXT",     "required": False, "label": "Ingresos Vía Oral (ml)",                  "order": 5},
            "ingresos_ev":           {"type": "TEXT",     "required": False, "label": "Ingresos Endovenosos (ml)",               "order": 6},
            "diuresis":              {"type": "TEXT",     "required": False, "label": "Diuresis (ml)",                           "order": 7},
            "otras_perdidas":        {"type": "TEXT",     "required": False, "label": "Otras Pérdidas (drenajes, heridas)",      "order": 8},
            "balance_neto":          {"type": "TEXT",     "required": False, "label": "Balance Hídrico Neto (ml)",               "order": 9},
            "cuidados_aplicados":    {"type": "TEXTAREA", "required": True,  "label": "Cuidados de Enfermería Aplicados",        "order": 10},
            "observaciones_enfermeria":{"type": "TEXTAREA","required": False,"label": "Observaciones y Novedades del Turno",     "order": 11},
        }
    },
    {
        "name": "Kardex",
        "description": "Resumen dinámico de tratamientos vigentes del paciente para el turno de enfermería.",
        "ui_schema": {
            "fecha_actualizacion":  {"type": "DATE",     "required": True,  "label": "Fecha de Actualización",           "order": 1},
            "diagnostico_actual":   {"type": "TEXT",     "required": True,  "label": "Diagnóstico Actual",               "order": 2},
            "alergias":             {"type": "TEXT",     "required": True,  "label": "Alergias Conocidas",               "order": 3},
            "dieta_prescrita":      {"type": "SELECT",   "required": True,  "label": "Dieta Prescrita", "order": 4,
                                     "options": {"BLANDA": "Dieta blanda hiposódica", "NPO": "Dieta absoluta (NPO)",
                                                 "HIPERPROTEICA": "Dieta hiperproteica", "LIBRE": "Dieta libre habitual"}},
            "tratamientos_vigentes":{
                "type": "ARRAY", "required": True, "label": "Tratamientos Vigentes del Turno", "order": 5,
                "subSchema": {
                    "medicamento": {"type": "TEXT", "required": True, "label": "Medicamento", "order": 1},
                    "dosis":       {"type": "TEXT", "required": True, "label": "Dosis",       "order": 2},
                    "frecuencia":  {"type": "TEXT", "required": True, "label": "Frecuencia",  "order": 3},
                }
            },
            "actividad_prescrita": {"type": "SELECT",   "required": True,  "label": "Actividad Prescrita", "order": 6,
                                    "options": {"REPOSO_ABS": "Reposo absoluto en cama", "REPOSO_REL": "Reposo relativo con asistencia", "DEAMBULACION": "Deambulación progresiva"}},
            "cuidados_especiales": {"type": "TEXTAREA", "required": False, "label": "Cuidados Especiales e Indicaciones",    "order": 7},
        }
    },
    {
        "name": "Notas de Trabajo Social / Psicología",
        "description": "Reportes sobre el entorno socioeconómico o el estado mental del paciente.",
        "ui_schema": {
            "tipo_nota":              {"type": "SELECT",   "required": True,  "label": "Tipo de Nota", "order": 1,
                                       "options": {"TRABAJO_SOCIAL": "Trabajo Social", "PSICOLOGIA": "Psicología"}},
            "fecha_evaluacion":       {"type": "DATE",     "required": True,  "label": "Fecha de Evaluación",              "order": 2},
            "profesional":            {"type": "TEXT",     "required": True,  "label": "Profesional a Cargo",              "order": 3},
            "motivo_evaluacion":      {"type": "TEXTAREA", "required": True,  "label": "Motivo de Evaluación",             "order": 4},
            "evaluacion_psicosocial": {"type": "TEXTAREA", "required": True,  "label": "Evaluación Psicosocial",           "order": 5},
            "plan_intervencion":      {"type": "TEXTAREA", "required": True,  "label": "Plan de Intervención",             "order": 6},
        }
    },
    {
        "name": "Consentimiento Informado",
        "description": "Documento firmado por el paciente autorizando un procedimiento tras conocer sus riesgos y beneficios.",
        "ui_schema": {
            "procedimiento":              {"type": "TEXT",     "required": True,  "label": "Procedimiento a Realizar",              "order": 1},
            "medico_informante":          {"type": "TEXT",     "required": True,  "label": "Médico que Informa",                    "order": 2},
            "fecha_firma":                {"type": "DATE",     "required": True,  "label": "Fecha de Firma",                        "order": 3},
            "descripcion_procedimiento":  {"type": "TEXTAREA", "required": True,  "label": "Descripción del Procedimiento",          "order": 4},
            "riesgos_explicados":         {"type": "TEXTAREA", "required": True,  "label": "Riesgos Explicados al Paciente",         "order": 5},
            "beneficios_explicados":      {"type": "TEXTAREA", "required": False, "label": "Beneficios Esperados",                   "order": 6},
            "paciente_comprende":         {"type": "SELECT",   "required": True,  "label": "El Paciente Comprende y Acepta", "order": 7,
                                           "options": {"SI": "Sí — Acepta el procedimiento", "NO": "No — Rechaza el procedimiento"}},
            "firma_responsable":          {"type": "TEXT",     "required": True,  "label": "Firma del Paciente / Representante",     "order": 8},
        }
    },
    {
        "name": "Certificado Médico",
        "description": "Documento que acredita el estado de salud para trámites escolares, laborales o de seguros.",
        "ui_schema": {
            "proposito":              {"type": "SELECT",   "required": True,  "label": "Propósito del Certificado", "order": 1,
                                       "options": {"LABORAL": "Justificación laboral", "SEGURO": "Trámite de seguro",
                                                   "EDUCATIVO": "Institución educativa", "LICENCIA": "Licencia por enfermedad", "APTO_FISICO": "Apto físico deportivo"}},
            "diagnostico_certificado":{"type": "TEXT",     "required": True,  "label": "Diagnóstico Certificado",              "order": 2},
            "dias_reposo_indicados":  {"type": "NUMBER",   "required": False, "label": "Días de Reposo Indicados",             "order": 3},
            "fecha_inicio_reposo":    {"type": "DATE",     "required": False, "label": "Fecha de Inicio de Reposo",            "order": 4},
            "fecha_fin_reposo":       {"type": "DATE",     "required": False, "label": "Fecha de Fin de Reposo",               "order": 5},
            "observaciones":          {"type": "TEXTAREA", "required": False, "label": "Observaciones Médicas",                "order": 6},
            "medico_emisor":          {"type": "TEXT",     "required": True,  "label": "Médico Emisor",                        "order": 7},
            "fecha_emision":          {"type": "DATE",     "required": True,  "label": "Fecha de Emisión",                     "order": 8},
        }
    },
    {
        "name": "Hoja de Alta Voluntaria",
        "description": "Formato que firma el paciente cuando decide abandonar el hospital bajo su propio riesgo.",
        "ui_schema": {
            "fecha_hora":                 {"type": "DATE",     "required": True,  "label": "Fecha y Hora de Solicitud de Alta",    "order": 1},
            "servicio":                   {"type": "SELECT",   "required": True,  "label": "Servicio de Hospitalización", "order": 2,
                                           "options": {"MED_INTERNA": "Medicina Interna", "CIRUGIA": "Cirugía General",
                                                       "URGENCIAS": "Urgencias", "PEDIATRIA": "Pediatría", "GINECOLOGIA": "Ginecología"}},
            "motivo_alta_voluntaria":     {"type": "TEXTAREA", "required": True,  "label": "Motivo Declarado por el Paciente",     "order": 3},
            "riesgos_informados":         {"type": "TEXTAREA", "required": True,  "label": "Riesgos Explicados al Paciente",       "order": 4},
            "paciente_comprende_riesgos": {"type": "SELECT",   "required": True,  "label": "El Paciente Comprende los Riesgos", "order": 5,
                                           "options": {"SI": "Sí — Comprende y acepta los riesgos", "NO": "No — Se niega a firmar"}},
            "medico_que_informa":         {"type": "TEXT",     "required": True,  "label": "Médico que Informa y Firma",           "order": 6},
            "firma_responsable":          {"type": "TEXT",     "required": True,  "label": "Firma del Paciente / Representante",   "order": 7},
        }
    },
    {
        "name": "Certificado de Defunción",
        "description": "Documento legal obligatorio que acredita el fallecimiento y las causas del mismo.",
        "ui_schema": {
            "fecha_defuncion":                   {"type": "DATE",     "required": True,  "label": "Fecha de Defunción",                          "order": 1},
            "hora_defuncion":                    {"type": "TEXT",     "required": True,  "label": "Hora de Defunción (HH:MM)",                   "order": 2},
            "lugar_defuncion":                   {"type": "SELECT",   "required": True,  "label": "Lugar de Defunción", "order": 3,
                                                  "options": {"UCI": "Sala de UCI", "EMERGENCIAS": "Sala de Emergencias",
                                                              "HOSPITALIZACION": "Sala de Hospitalización", "DOMICILIO": "Domicilio del paciente"}},
            "causa_directa":                     {"type": "TEXT",     "required": True,  "label": "Causa Directa de Muerte (Ia)",                "order": 4},
            "causa_subyacente":                  {"type": "TEXT",     "required": True,  "label": "Causa Subyacente (Ib)",                       "order": 5},
            "causa_basica":                      {"type": "TEXT",     "required": True,  "label": "Causa Básica / Fundamental (Ic)",             "order": 6},
            "otras_condiciones_contribuyentes":  {"type": "TEXTAREA", "required": False, "label": "Otras Condiciones Contribuyentes (II)",       "order": 7},
            "tipo_muerte":                       {"type": "SELECT",   "required": True,  "label": "Tipo de Muerte", "order": 8,
                                                  "options": {"NATURAL": "Natural", "ACCIDENTAL": "Accidental", "VIOLENTA": "Violenta"}},
            "medico_certificante":               {"type": "TEXT",     "required": True,  "label": "Médico Certificante",                         "order": 9},
            "numero_registro":                   {"type": "TEXT",     "required": True,  "label": "Número de Registro Civil",                    "order": 10},
        }
    },
    {
        "name": "Nota de Alta",
        "description": "Resumen oficial de evolución, tratamiento y recomendaciones al momento de la salida del paciente.",
        "ui_schema": {
            "fecha_ingreso":               {"type": "DATE",     "required": True,  "label": "Fecha de Ingreso",                    "order": 1},
            "fecha_alta":                  {"type": "DATE",     "required": True,  "label": "Fecha de Alta",                       "order": 2},
            "diagnostico_principal":       {"type": "TEXT",     "required": True,  "label": "Diagnóstico Principal",               "order": 3},
            "diagnostico_alta":            {"type": "TEXT",     "required": True,  "label": "Diagnóstico de Alta",                 "order": 4},
            "diagnosticos_secundarios":    {"type": "TEXTAREA", "required": False, "label": "Diagnósticos Secundarios",            "order": 5},
            "procedimientos_realizados":   {"type": "TEXTAREA", "required": False, "label": "Procedimientos Realizados",           "order": 6},
            "evolucion_clinica":           {"type": "TEXTAREA", "required": True,  "label": "Evolución Clínica",                   "order": 7},
            "resumen_tratamiento":         {"type": "TEXTAREA", "required": True,  "label": "Resumen del Tratamiento",             "order": 8},
            "medicinas_alta":              {"type": "TEXTAREA", "required": True,  "label": "Medicinas al Alta",                   "order": 9},
            "restricciones_actividad":     {"type": "TEXTAREA", "required": False, "label": "Restricciones de Actividad",          "order": 10},
            "actividades_permitidas":      {"type": "TEXTAREA", "required": False, "label": "Actividades Permitidas",              "order": 11},
            "restricciones_dieteticas":    {"type": "TEXTAREA", "required": False, "label": "Restricciones Dietéticas",            "order": 12},
            "cuidados_heridas":            {"type": "TEXTAREA", "required": False, "label": "Cuidados de Heridas",                 "order": 13},
            "instrucciones_seguimiento":   {"type": "TEXTAREA", "required": True,  "label": "Instrucciones de Seguimiento",        "order": 14},
            "fecha_recomendada_retorno":   {"type": "DATE",     "required": False, "label": "Fecha Recomendada para Retorno",      "order": 15},
        }
    },
]


# ── Seed principal ────────────────────────────────────────────────────────────

def seed_database():
    # Leer URL de BD: DATABASE_URL tiene prioridad (prod), luego DB_URL (.env local)
    db_url = os.getenv("DATABASE_URL") or os.getenv("DB_URL", "")
    if db_url.startswith("jdbc:"):
        db_url = db_url.replace("jdbc:", "", 1)

    print("🔌 Conectando a la base de datos...")
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    # 1. Cargar branding por defecto
    default_branding = {}
    branding_path = "../sgd_spring-boot/src/main/resources/default-branding.json"
    if os.path.exists(branding_path):
        try:
            with open(branding_path, "r", encoding="utf-8") as f:
                default_branding = json.load(f)
            print("🎨 Branding por defecto cargado.")
        except Exception as e:
            print(f"⚠️ Error al leer default-branding.json: {e}")

    # Configurar Azure Blob Storage (si está disponible)
    azure_container = None
    azure_conn_str   = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip().strip('"')
    azure_container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "uploads")
    if azure_conn_str and _AZURE_SDK_AVAILABLE:
        try:
            blob_service = BlobServiceClient.from_connection_string(azure_conn_str)
            azure_container = blob_service.get_container_client(azure_container_name)
            if not azure_container.exists():
                azure_container.create_container()
            print(f"☁️  Azure Storage: conectado al contenedor '{azure_container_name}'.")
        except Exception as e:
            print(f"⚠️  Azure Storage: no se pudo conectar ({e}). Se usará almacenamiento local.")
            azure_container = None
    else:
        print(f"💾  Almacenamiento local: {PDF_STORAGE_DIR}")

    print("🧹 Limpiando tablas...")
    tables_to_clear = [
        "workflow_comments", "workflow_events", "workflow_documents",
        "review_tasks", "workflows", "task_delegations", "notifications",
        "user_push_tokens", "api_call_usage", "backup_history",
        "document_ocr_metadata", "document_versions", "documents",
        "clinical_histories",
        "dicom_instances", "dicom_series", "dicom_studies", "patients",
        "report_templates", "document_templates",
        "role_user", "role_permission", "users", "roles", "tenants"
    ]
    existing_tables = []
    for table in tables_to_clear:
        try:
            cursor.execute(f"SELECT 1 FROM {table} LIMIT 0")
            existing_tables.append(table)
        except psycopg2.errors.UndefinedTable:
            conn.rollback()
    if existing_tables:
        cursor.execute(f"TRUNCATE TABLE {', '.join(existing_tables)} RESTART IDENTITY CASCADE")
        conn.commit()
    print("✅ Base de datos limpia.")

    # 2. Planes y permisos
    cursor.execute("SELECT id, name FROM plans")
    plans = {row[1]: row[0] for row in cursor.fetchall()}
    cursor.execute("SELECT id FROM permissions")
    all_permission_ids = [row[0] for row in cursor.fetchall()]
    print(f"📋 {len(plans)} planes y {len(all_permission_ids)} permisos cargados.")

    def get_settings_for_plan(plan_name, plan_id):
        cursor.execute("SELECT resource_key, resource_value FROM plan_limits WHERE plan_id = %s", (plan_id,))
        limits = {row[0]: int(row[1]) for row in cursor.fetchall()}
        return {
            "limits": limits,
            "regional": {"timezone": "America/La_Paz", "locale": "es-BO", "dateFormat": "DD/MM/YYYY", "currency": "BOB"},
            "notifications": {"emailEnabled": True, "smsEnabled": False, "pushEnabled": True},
            "security": {"sessionTimeoutMinutes": 30, "passwordExpiryDays": 90, "require2FA": False},
            "branding": default_branding
        }

    # 3. Tenant Sistema Central
    system_tenant_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO tenants (id, name, slug, email, phone, address, subscription_plan, subscription_status,
            subscription_start_date, subscription_end_date, billing_cycle, settings)
        VALUES (%s, 'SGD Sistema Central', 'system', 'admin@sgd-sistema.com', '+591-000-0000',
            'Sistema central', 'ENTERPRISE', 'ACTIVE', CURRENT_DATE, CURRENT_DATE + INTERVAL '100 years', 'YEARLY', %s)
    """, (system_tenant_id, json.dumps(get_settings_for_plan("ENTERPRISE", plans["ENTERPRISE"]))))

    # 4. Tenant Hospital General (Demo)
    default_tenant_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO tenants (id, name, slug, email, phone, address, subscription_plan, subscription_status,
            subscription_start_date, subscription_end_date, billing_cycle, settings)
        VALUES (%s, 'Hospital General (Demo)', 'default', 'admin@hospital.com', '+591-2-2123456',
            'Calle Potosí #123, La Paz', 'PRO', 'ACTIVE', CURRENT_DATE, CURRENT_DATE + INTERVAL '30 days', 'MONTHLY', %s)
    """, (default_tenant_id, json.dumps(get_settings_for_plan("PRO", plans["PRO"]))))

    # 5. Tenant Clínica del Sur
    sur_tenant_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO tenants (id, name, slug, email, phone, address, subscription_plan, subscription_status,
            subscription_start_date, subscription_end_date, billing_cycle, settings)
        VALUES (%s, 'Clínica del Sur (Demo)', 'clinica-sur', 'admin@clinicasur.com', '+591-3-3456789',
            'Avenida Radial 26 #456, Santa Cruz', 'PRO', 'ACTIVE', CURRENT_DATE, CURRENT_DATE + INTERVAL '30 days', 'MONTHLY', %s)
    """, (sur_tenant_id, json.dumps(get_settings_for_plan("PRO", plans["PRO"]))))

    # 6. 13 Tenants extra con nombres reales
    extra_tenants = []
    plan_names = list(plans.keys())
    statuses = ['ACTIVE', 'PAST_DUE', 'PENDING_PAYMENT']

    for clinic_name, slug in EXTRA_CLINIC_DATA:
        plan_name = random.choice(plan_names)
        status = random.choice(statuses)
        tenant_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO tenants (id, name, slug, email, phone, address, subscription_plan, subscription_status,
                subscription_start_date, subscription_end_date, billing_cycle, settings)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                CURRENT_DATE - %s, CURRENT_DATE + %s, 'MONTHLY', %s)
        """, (
            tenant_id, clinic_name, slug, f"admin@{slug}.com",
            bolivian_phone(), fake.address().replace("\n", ", "),
            plan_name, status,
            random.randint(1, 100), random.randint(5, 60),
            json.dumps(get_settings_for_plan(plan_name, plans[plan_name]))
        ))
        extra_tenants.append((tenant_id, slug, clinic_name))

    print("🏢 Tenants creados.")
    conn.commit()

    # 7. Roles y permisos
    all_tenants = (
        [(system_tenant_id, 'system', 'SGD Sistema Central'),
         (default_tenant_id, 'default', 'Hospital General'),
         (sur_tenant_id, 'clinica-sur', 'Clínica del Sur')]
        + extra_tenants
    )
    roles_map = {}

    for tenant_id, slug, _ in all_tenants:
        roles_to_create = {
            "ROLE_ADMIN":    "Administrador de la clínica",
            "ROLE_MEDICO":   "Personal médico del sistema",
            "ROLE_ARCHIVO":  "Encargado de archivo histórico",
            "ROLE_DIRECTOR": "Director del hospital",
        }
        if slug == 'system':
            roles_to_create["ROLE_SUPERUSER"] = "Superusuario con acceso total"

        for role_name, desc in roles_to_create.items():
            cursor.execute("""
                INSERT INTO roles (tenant_id, name, description, is_active)
                VALUES (%s, %s, %s, true) RETURNING id
            """, (tenant_id, role_name, desc))
            role_id = cursor.fetchone()[0]
            roles_map[(tenant_id, role_name)] = role_id
            if role_name in ("ROLE_ADMIN", "ROLE_SUPERUSER"):
                for perm_id in all_permission_ids:
                    cursor.execute("INSERT INTO role_permission (role_id, permission_id) VALUES (%s, %s)", (role_id, perm_id))

    conn.commit()
    print("🔐 Roles y permisos asignados.")

    # 8. Usuarios semilla
    hashed_admin = hash_password("admin123")
    hashed_super = hash_password("superuser123")

    users_to_seed = [
        ("superuser.system", "admin@sgd-sistema.com",   "Super",   "User",             hashed_super, "0000000", "ROLE_SUPERUSER", system_tenant_id),
        ("admin.default",    "admin@hospital.com",      "Admin",   "Rodríguez",        hashed_admin, "1111111", "ROLE_ADMIN",     default_tenant_id),
        ("admin.sur",        "admin@clinicasur.com",    "Admin",   "Montero",          hashed_admin, "2222222", "ROLE_ADMIN",     sur_tenant_id),
    ]
    for tenant_id, slug, clinic_name in extra_tenants:
        users_to_seed.append((
            f"admin.{slug}", f"admin@{slug}.com",
            fake.first_name(), fake.last_name(),
            hashed_admin, str(random.randint(1000000, 9999999)),
            "ROLE_ADMIN", tenant_id
        ))

    admin_users_by_tenant = {}
    for username, email, first, last, p_hash, doc_num, role_name, tenant_id in users_to_seed:
        user_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO users (id, tenant_id, document_type, document_number, username,
                first_name, last_name, email, password, gender, is_active)
            VALUES (%s, %s, 'CI', %s, %s, %s, %s, %s, %s, 'M', true)
        """, (user_id, tenant_id, doc_num, username, first, last, email, p_hash))
        cursor.execute("INSERT INTO role_user (user_id, role_id) VALUES (%s, %s)",
                       (user_id, roles_map[(tenant_id, role_name)]))
        if role_name in ("ROLE_ADMIN", "ROLE_SUPERUSER"):
            admin_users_by_tenant[tenant_id] = user_id

    # 8.1 Médicos por tenant (2-3 por clínica, usados como asignados en workflows)
    medicos_by_tenant = {}
    hashed_medico = hash_password("medico123")
    MEDICO_SPECIALTIES = ["Medicina Interna", "Cirugía General", "Pediatría", "Ginecología", "Cardiología"]
    for tenant_id, slug, _ in all_tenants:
        if slug == 'system':
            continue
        medicos_by_tenant[tenant_id] = []
        for i in range(1, random.randint(3, 4)):
            m_id = str(uuid.uuid4())
            m_first = fake.first_name()
            m_last = fake.last_name()
            cursor.execute("""
                INSERT INTO users (id, tenant_id, document_type, document_number, username,
                    first_name, last_name, email, password, gender, is_active)
                VALUES (%s, %s, 'CI', %s, %s, %s, %s, %s, %s, %s, true)
            """, (
                m_id, tenant_id,
                str(random.randint(1000000, 9999999)),
                f"dr.{slug}.{i}",
                m_first, m_last,
                f"dr{i}@{slug}.com",
                hashed_medico,
                random.choice(['M', 'F'])
            ))
            cursor.execute("INSERT INTO role_user (user_id, role_id) VALUES (%s, %s)",
                           (m_id, roles_map[(tenant_id, "ROLE_MEDICO")]))
            medicos_by_tenant[tenant_id].append(m_id)

    # 8.5 Plantillas de documentos y reportes
    print("📋 Creando plantillas de documentos...")
    templates_by_tenant = {}

    for tenant_id, slug, _ in all_tenants:
        templates_by_tenant[tenant_id] = []
        for tpl in DOC_TEMPLATES:
            tpl_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO document_templates (id, tenant_id, name, description, ui_schema, is_active)
                VALUES (%s, %s, %s, %s, %s, true)
            """, (tpl_id, tenant_id, tpl["name"], tpl["description"], json.dumps(tpl["ui_schema"])))
            templates_by_tenant[tenant_id].append((tpl_id, tpl["name"]))

        admin_id = admin_users_by_tenant.get(tenant_id)
        if not admin_id:
            continue

        report_templates = [
            {
                "name": "Reporte General de Pacientes",
                "description": "Listado completo de pacientes registrados con datos de contacto.",
                "department": "Administración", "report_type": "patients",
                "selected_fields": ["documentNumber", "documentType", "fullName", "gender", "birthDate", "phone", "createdAt"],
                "filters": [], "sort_field": "createdAt", "sort_order": "desc", "is_shared": True
            },
            {
                "name": "Pacientes Femeninos",
                "description": "Listado filtrado de pacientes de género femenino.",
                "department": "Ginecología / Obstetricia", "report_type": "patients",
                "selected_fields": ["documentNumber", "fullName", "birthDate", "phone"],
                "filters": [{"field": "gender", "operator": "EQ", "value": "FEMALE"}],
                "sort_field": "fullName", "sort_order": "asc", "is_shared": True
            },
            {
                "name": "Resumen de Documentos por Estado",
                "description": "Cantidad de documentos clínicos según su estado actual.",
                "department": "Dirección Médica", "report_type": "documents_by_status",
                "selected_fields": ["status", "total"],
                "filters": [], "sort_field": "total", "sort_order": "desc", "is_shared": True
            },
            {
                "name": "Control de Documentos Clínicos",
                "description": "Seguimiento de documentos, autores y plantilla asociada.",
                "department": "Archivo", "report_type": "documents",
                "selected_fields": ["status", "issueDate", "patientName", "uploaderName", "templateName"],
                "filters": [], "sort_field": "issueDate", "sort_order": "desc", "is_shared": True
            },
        ]
        for r in report_templates:
            cursor.execute("""
                INSERT INTO report_templates (id, tenant_id, owner_id, name, description, department,
                    report_type, selected_fields, filters, sort_field, sort_order, is_shared)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (str(uuid.uuid4()), tenant_id, admin_id, r["name"], r["description"],
                  r["department"], r["report_type"], json.dumps(r["selected_fields"]),
                  json.dumps(r["filters"]), r["sort_field"], r["sort_order"], r["is_shared"]))

    conn.commit()
    print("✅ Usuarios, plantillas y reportes creados.")

    # 9. Pacientes (50 por clínica)
    patients_by_tenant = {}
    print("🩺 Generando 50 pacientes por clínica...")
    for tenant_id, slug, _ in all_tenants:
        if slug == 'system':
            continue
        patients_by_tenant[tenant_id] = []
        for _ in range(50):
            patient_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO patients (id, tenant_id, document_type, document_number,
                    first_name, last_name, birth_date, gender, address, phone)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                patient_id, tenant_id, random.choice(['CI', 'PASAPORTE']),
                str(random.randint(1000000, 9999999)),
                fake.first_name(), fake.last_name(),
                fake.date_of_birth(minimum_age=1, maximum_age=90),
                random.choice(['MALE', 'FEMALE']),
                fake.address().replace("\n", ", "), bolivian_phone()
            ))
            patients_by_tenant[tenant_id].append(patient_id)
    conn.commit()
    print("✅ Pacientes creados.")

    # 10. Historias clínicas y documentos (Ene–Jul 2026, sin DICOM)
    print("📊 Generando historias clínicas y documentos clínicos...")
    estados_doc = ['DRAFT', 'PENDING_REVIEW', 'REJECTED', 'FINALIZED']
    # Colección de documentos con plantilla para generar PDFs después
    docs_for_pdf = []   # [(doc_id, tpl_name, patient_id, tenant_id)]

    # Plantillas NO-Historia para documentos secundarios
    secondary_template_names = [n for n in [t["name"] for t in DOC_TEMPLATES] if n != "Historia Clínica"]

    tenant_idx = 0
    for tenant_id, slug, _ in all_tenants:
        if slug == 'system':
            continue
        tenant_idx += 1

        cursor.execute("SELECT id FROM users WHERE tenant_id = %s LIMIT 1", (tenant_id,))
        uploader_id = cursor.fetchone()[0]

        patient_ids = patients_by_tenant[tenant_id]
        tenant_tpls = templates_by_tenant.get(tenant_id, [])

        # Índice de plantillas por nombre para búsqueda rápida
        tpl_by_name = {name: tid for tid, name in tenant_tpls}
        secondary_tpls = [(tid, name) for tid, name in tenant_tpls if name in secondary_template_names]

        for hist_idx, patient_id in enumerate(patient_ids, start=1):
            # ── Crear Historia Clínica estructurada ──────────────────────────
            history_id = str(uuid.uuid4())
            code = f"HC-{tenant_idx:02d}-{hist_idx:04d}"
            blood_type = random.choice(BLOOD_TYPES)

            allergies = []
            if random.random() > 0.45:
                ag = random.choice(ALLERGEN_POOL)
                allergies.append({"allergen": ag[0], "severity": ag[1], "reaction": ag[2]})

            medications = []
            if random.random() > 0.5:
                for med in random.sample(MED_POOL, random.randint(1, 2)):
                    medications.append({"medication": med[0], "dose": med[1], "frequency": med[2]})

            path_ant = random.choice([
                "Hipertensión arterial esencial diagnosticada hace 5 años.",
                "Diabetes mellitus tipo 2 de 8 años de evolución.",
                "Sin antecedentes patológicos de importancia.",
                "Asma bronquial desde la infancia.",
                "Hipotiroidismo primario en tratamiento.",
            ])
            non_path_ant = random.choice([
                "Tabaquismo activo moderado. Niega alcoholismo.",
                "Sedentarismo. Dieta hipercalórica. Sin tabaco ni alcohol.",
                "Sin hábitos nocivos. Actividad física leve 3 veces/semana.",
                "Etilismo ocasional. Niega tabaquismo.",
            ])
            fam_ant = random.choice([
                "Padre con DM2. Madre con HTA.",
                "Sin antecedentes familiares relevantes.",
                "Padre fallecido por IAM. Abuela con cáncer gástrico.",
                "Madre con hipotiroidismo. Hermano con epilepsia.",
            ])
            chronic = random.choice([
                "Hipertensión arterial, Dislipidemia.",
                "Diabetes mellitus tipo 2.",
                "Sin enfermedades crónicas diagnosticadas.",
                "Hipotiroidismo primario.",
                None,
            ])
            observations = random.choice([
                "Paciente cumplidor del tratamiento. Acude a controles periódicos.",
                "Paciente con adherencia irregular al tratamiento farmacológico.",
                "Sin observaciones adicionales de relevancia clínica.",
                None,
            ])

            cursor.execute("""
                INSERT INTO clinical_histories (id, tenant_id, patient_id, code, blood_type,
                    pathological_antecedents, non_pathological_antecedents, family_antecedents,
                    allergies, chronic_conditions, current_medications, observations)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                history_id, tenant_id, patient_id, code, blood_type,
                path_ant, non_path_ant, fam_ant,
                json.dumps(allergies), chronic,
                json.dumps(medications), observations
            ))

            # ── Documento Historia Clínica (obligatorio, fecha coherente) ────
            hc_tpl_id = tpl_by_name.get("Historia Clínica")
            if hc_tpl_id:
                hc_doc_id  = str(uuid.uuid4())
                hc_issue   = fake.date_between(start_date=DATE_START, end_date=DATE_END)
                hc_content = generate_clinical_content("Historia Clínica")
                cursor.execute("""
                    INSERT INTO documents (id, tenant_id, patient_id, uploader_id, template_id,
                        clinical_history_id, status, is_external_source, clinical_content,
                        file_url, issue_date, expiry_date, file_size_bytes)
                    VALUES (%s, %s, %s, %s, %s, %s, 'FINALIZED', false, %s, NULL, %s, NULL, %s)
                """, (
                    hc_doc_id, tenant_id, patient_id, uploader_id, hc_tpl_id,
                    history_id, json.dumps(hc_content), hc_issue,
                    random.randint(20480, 1048576)
                ))
                docs_for_pdf.append((hc_doc_id, "Historia Clínica", patient_id, tenant_id,
                                     hc_issue, hc_content))

            # ── Documentos clínicos adicionales (2-5, fechas posteriores a HC)
            num_docs = random.randint(2, 5)
            selected  = random.sample(secondary_tpls, min(num_docs, len(secondary_tpls)))
            prev_date = hc_issue if hc_tpl_id else DATE_START
            for tpl_id, tpl_name in selected:
                # Fecha de este doc >= fecha del doc anterior (coherencia temporal)
                max_gap = (DATE_END - prev_date).days
                gap     = random.randint(0, max(0, max_gap))
                issue_date = prev_date + timedelta(days=gap)
                if issue_date > DATE_END:
                    issue_date = DATE_END
                prev_date = issue_date

                expiry = (issue_date + timedelta(days=random.randint(14, 60))
                          if random.random() > 0.75 else None)
                doc_id   = str(uuid.uuid4())
                content  = generate_clinical_content(tpl_name)
                status   = random.choice(estados_doc)
                cursor.execute("""
                    INSERT INTO documents (id, tenant_id, patient_id, uploader_id, template_id,
                        clinical_history_id, status, is_external_source, clinical_content,
                        file_url, issue_date, expiry_date, file_size_bytes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, false, %s, NULL, %s, %s, %s)
                """, (
                    doc_id, tenant_id, patient_id, uploader_id, tpl_id,
                    history_id, status, json.dumps(content),
                    issue_date, expiry, random.randint(10240, 2097152)
                ))
                docs_for_pdf.append((doc_id, tpl_name, patient_id, tenant_id,
                                     issue_date, content))

    conn.commit()

    # 10.B Generar 90 PDFs físicos y vincularlos a documentos existentes
    print("📄 Generando 90 documentos PDF físicos...")
    random.shuffle(docs_for_pdf)
    pdf_candidates = docs_for_pdf[:90]

    # Cargar nombres de pacientes y clínicas en memoria para los PDFs
    cursor.execute("SELECT id, first_name, last_name, document_number FROM patients")
    patients_info = {row[0]: (row[1], row[2], row[3]) for row in cursor.fetchall()}

    cursor.execute("SELECT id, name FROM tenants")
    tenants_info = {row[0]: row[1] for row in cursor.fetchall()}

    storage_label = f"Azure ({azure_container_name})" if azure_container else PDF_STORAGE_DIR
    pdf_generated = 0
    for doc_id, tpl_name, patient_id, tenant_id, issue_date, content in pdf_candidates:
        pat = patients_info.get(patient_id, ("Paciente", "Desconocido", "0000000"))
        clinic = tenants_info.get(tenant_id, "SGD Sistema")
        try:
            file_path, file_size = generate_clinical_pdf(
                doc_id, tpl_name, pat[0], pat[1], pat[2],
                clinic, issue_date, content,
                azure_container=azure_container
            )
            cursor.execute("""
                UPDATE documents
                SET file_url = %s, file_size_bytes = %s, is_external_source = true
                WHERE id = %s
            """, (file_path, file_size, doc_id))
            pdf_generated += 1
        except Exception as e:
            print(f"  ⚠️ PDF {doc_id[:8]}... omitido: {e}")

    conn.commit()
    print(f"✅ {pdf_generated} PDFs generados en: {storage_label}")

    # 11. Workflows de revisión documental
    print("🔄 Generando flujos de trabajo (workflows)...")

    WF_TITLES = [
        "Revisión de Expediente Clínico — Alta Médica",
        "Auditoría de Documentación Quirúrgica",
        "Validación de Consentimientos Informados",
        "Control de Calidad — Documentos de Urgencias",
        "Revisión Pre-Alta: Documentación Completa",
        "Aprobación de Certificados Médicos Emitidos",
        "Revisión de Informes de Laboratorio e Imagenología",
        "Validación de Notas Médicas de Evolución",
        "Auditoría de Historias Clínicas — Nuevo Ingreso",
        "Revisión de Documentos Pendientes de Firma",
    ]
    WF_MESSAGES = [
        "Por favor revisar y aprobar los documentos adjuntos antes del alta del paciente.",
        "Revisión urgente requerida. Los documentos deben estar validados antes de las 18:00.",
        "Documentación pendiente de validación médica para cierre de expediente.",
        "Se requiere verificar la integridad y completitud de la documentación clínica.",
        "Control de calidad trimestral. Revisar documentos según protocolo institucional.",
    ]
    WF_COMMENTS = [
        "Documentación completa y en orden. Se aprueba para archivo definitivo.",
        "Falta la firma del médico responsable en la nota de evolución del turno noche.",
        "Por favor corregir la fecha de ingreso registrada en la Historia Clínica.",
        "Pendiente adjuntar resultado de laboratorio para completar el expediente.",
        "Se solicita adjuntar el consentimiento informado firmado por el familiar.",
        "Historia clínica revisada y validada. Sin observaciones adicionales.",
        "El diagnóstico de alta no coincide con los registros de evolución. Favor corregir.",
        "Documentos revisados. Se requiere versión actualizada del informe de patología.",
        "Aprobado. Expediente completo listo para archivo histórico.",
        "Revisión completada. Sin inconsistencias detectadas en la documentación.",
    ]

    WF_STATUSES = ['ACTIVE', 'ACTIVE', 'ACTIVE', 'COMPLETED', 'CANCELLED']

    for tenant_id, slug, _ in all_tenants:
        if slug == 'system':
            continue

        admin_id = admin_users_by_tenant.get(tenant_id)
        if not admin_id:
            continue

        tenant_medicos = medicos_by_tenant.get(tenant_id, [])
        if not tenant_medicos:
            tenant_medicos = [admin_id]  # fallback si no hay médicos

        # Obtener documentos disponibles para asignar a workflows
        cursor.execute("""
            SELECT id FROM documents
            WHERE tenant_id = %s AND status IN ('PENDING_REVIEW', 'FINALIZED', 'DRAFT')
            ORDER BY RANDOM()
            LIMIT 80
        """, (tenant_id,))
        available_docs = [row[0] for row in cursor.fetchall()]

        if len(available_docs) < 2:
            continue

        doc_pool = list(available_docs)
        num_workflows = random.randint(4, 8)

        for _ in range(num_workflows):
            if len(doc_pool) < 2:
                break

            wf_id = str(uuid.uuid4())
            medico_id = random.choice(tenant_medicos)
            wf_status = random.choice(WF_STATUSES)
            wf_priority = random.choice([1, 2, 3, 3, 3, 4, 5])
            # Fechas dentro del rango Jan-Jul 2026
            created_ago = datetime.combine(
                fake.date_between(start_date=DATE_START, end_date=DATE_END),
                datetime.min.time()
            )
            due_date = created_ago + timedelta(days=random.randint(3, 30))

            # Tomar 2-4 documentos del pool
            num_docs = min(random.randint(2, 4), len(doc_pool))
            wf_doc_ids = doc_pool[:num_docs]
            doc_pool = doc_pool[num_docs:]

            cursor.execute("""
                INSERT INTO workflows (id, tenant_id, title, message, creator_id, assignee_id,
                    status, priority, due_date, send_email_notifications, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, false, %s, %s)
            """, (
                wf_id, tenant_id,
                random.choice(WF_TITLES),
                random.choice(WF_MESSAGES),
                admin_id, medico_id,
                wf_status, wf_priority,
                due_date, created_ago, created_ago
            ))

            # Notificación DOC_REVIEW al médico asignado (nuevo flujo para revisar)
            cursor.execute("""
                INSERT INTO notifications (id, tenant_id, user_id, channel, type,
                    title, message, document_id, review_task_id, is_read, created_at)
                VALUES (%s, %s, %s, 'IN_APP', 'DOC_REVIEW',
                    'Documentos pendientes de revision',
                    %s, %s, NULL, false, %s)
            """, (
                str(uuid.uuid4()), tenant_id, medico_id,
                f'Tienes {len(wf_doc_ids)} documento(s) asignados para revision en un nuevo flujo de trabajo.',
                wf_doc_ids[0] if wf_doc_ids else None,
                created_ago + timedelta(minutes=1)
            ))

            # Vincular documentos al workflow
            for doc_id in wf_doc_ids:
                cursor.execute("""
                    INSERT INTO workflow_documents (id, workflow_id, document_id, added_at)
                    VALUES (%s, %s, %s, %s)
                """, (str(uuid.uuid4()), wf_id, doc_id, created_ago))

            # Review tasks (una por documento)
            task_records = []
            for doc_id in wf_doc_ids:
                task_id = str(uuid.uuid4())
                if wf_status == 'ACTIVE':
                    task_status = random.choice(['PENDING', 'PENDING', 'IN_PROGRESS'])
                    outcome = None
                    completed_at = None
                    completed_by = None
                elif wf_status == 'COMPLETED':
                    task_status = 'COMPLETED'
                    outcome = random.choice(['APPROVED', 'APPROVED', 'REJECTED'])
                    completed_at = datetime.now() - timedelta(days=random.randint(0, 5))
                    completed_by = medico_id
                else:  # CANCELLED
                    task_status = 'CANCELLED'
                    outcome = None
                    completed_at = None
                    completed_by = None

                cursor.execute("""
                    INSERT INTO review_tasks (id, tenant_id, workflow_id, document_id,
                        assigned_to, status, outcome, priority, due_date,
                        created_at, started_at, completed_at, completed_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    task_id, tenant_id, wf_id, doc_id,
                    medico_id, task_status, outcome,
                    wf_priority, due_date, created_ago,
                    created_ago if task_status in ('IN_PROGRESS', 'COMPLETED') else None,
                    completed_at, completed_by
                ))
                task_records.append((task_id, doc_id))

                # ── Notificación TASK_ASSIGNED al médico asignado ────────────
                cursor.execute("""
                    INSERT INTO notifications (id, tenant_id, user_id, channel, type,
                        title, message, document_id, review_task_id, is_read, created_at)
                    VALUES (%s, %s, %s, 'IN_APP', 'TASK_ASSIGNED',
                        'Tarea de revision asignada',
                        'Se te asigno un documento para revisar en el flujo de trabajo.',
                        %s, %s, false, %s)
                """, (
                    str(uuid.uuid4()), tenant_id, medico_id,
                    doc_id, task_id, created_ago + timedelta(minutes=3)
                ))

                # ── Notificación TASK_APPROVED / TASK_REJECTED al admin (creador) ──
                if outcome in ('APPROVED', 'REJECTED') and completed_at:
                    notif_type  = 'TASK_APPROVED' if outcome == 'APPROVED' else 'TASK_REJECTED'
                    notif_title = 'Documento aprobado' if outcome == 'APPROVED' else 'Documento rechazado'
                    notif_msg   = (
                        'La revision fue completada. El documento fue aprobado y archivado correctamente.'
                        if outcome == 'APPROVED' else
                        'El documento fue rechazado en la revision. Corrige los errores indicados y vuelve a enviarlo.'
                    )
                    cursor.execute("""
                        INSERT INTO notifications (id, tenant_id, user_id, channel, type,
                            title, message, document_id, review_task_id, is_read, created_at)
                        VALUES (%s, %s, %s, 'IN_APP', %s, %s, %s, %s, %s, false, %s)
                    """, (
                        str(uuid.uuid4()), tenant_id, admin_id,
                        notif_type, notif_title, notif_msg,
                        doc_id, task_id,
                        completed_at + timedelta(seconds=random.randint(10, 120))
                    ))

            # Workflow events (historial del ciclo de vida)
            # admin crea el workflow; médico ejecuta las tareas
            events_to_create = [
                ('WORKFLOW_CREATED', None, "Flujo de trabajo iniciado.", created_ago, admin_id),
            ]
            if len(wf_doc_ids) > 0:
                events_to_create.append(
                    ('DOCUMENT_ADDED', None, f"{len(wf_doc_ids)} documento(s) adjuntado(s) al flujo.",
                     created_ago + timedelta(minutes=2), admin_id)
                )
            if wf_status == 'ACTIVE' and random.random() > 0.5:
                events_to_create.append(
                    ('TASK_STARTED', None, "Revision iniciada por el medico asignado.",
                     created_ago + timedelta(hours=random.randint(1, 24)), medico_id)
                )
            elif wf_status == 'COMPLETED':
                events_to_create.append(
                    ('TASK_COMPLETED', 'APPROVED' if random.random() > 0.3 else 'REJECTED',
                     "Revision completada.", datetime.now() - timedelta(days=random.randint(0, 3)), medico_id)
                )
                events_to_create.append(
                    ('WORKFLOW_COMPLETED', 'APPROVED', "Flujo de trabajo cerrado exitosamente.",
                     datetime.now() - timedelta(days=random.randint(0, 2)), admin_id)
                )
            elif wf_status == 'CANCELLED':
                events_to_create.append(
                    ('WORKFLOW_CANCELLED', 'CANCELLED', "Flujo cancelado por el administrador.",
                     datetime.now() - timedelta(days=random.randint(0, 5)), admin_id)
                )

            for evt_type, result, comment, performed_at, evt_actor in events_to_create:
                first_task_id = task_records[0][0] if task_records else None
                first_doc_id = wf_doc_ids[0] if wf_doc_ids else None
                cursor.execute("""
                    INSERT INTO workflow_events (id, tenant_id, workflow_id, document_id,
                        review_task_id, event_type, performed_by, performed_at, result, comment)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    str(uuid.uuid4()), tenant_id, wf_id, first_doc_id,
                    first_task_id, evt_type, evt_actor, performed_at, result, comment
                ))

            # Workflow comments: médico y admin comentan alternado
            if wf_status in ('ACTIVE', 'COMPLETED') and random.random() > 0.35:
                num_comments = random.randint(1, 4)
                comment_actors = [admin_id, medico_id]
                for c_idx in range(num_comments):
                    task_id, doc_id = random.choice(task_records)
                    comment_at = created_ago + timedelta(hours=random.randint(1, 72))
                    cursor.execute("""
                        INSERT INTO workflow_comments (id, tenant_id, workflow_id, document_id,
                            review_task_id, author_id, comment_text, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        str(uuid.uuid4()), tenant_id, wf_id, doc_id,
                        task_id, comment_actors[c_idx % 2],
                        random.choice(WF_COMMENTS),
                        comment_at
                    ))

    conn.commit()
    cursor.close()
    conn.close()
    print("🚀 ¡Base de datos sembrada completamente con éxito!")


if __name__ == '__main__':
    seed_database()
