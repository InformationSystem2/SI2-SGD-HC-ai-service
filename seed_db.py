import os
import json
import uuid
import random
import bcrypt
import psycopg2
from datetime import datetime, timedelta
from dotenv import load_dotenv
from faker import Faker

load_dotenv()
os.environ["PGCLIENTENCODING"] = "UTF-8"
fake = Faker('es_ES')

def hash_password(password: str) -> str:
    # Generate a bcrypt hash fully compatible with Spring Security
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(10))
    return hashed.decode('utf-8')

def generate_clinical_content(template_name: str) -> dict:
    if template_name == "Ficha de Ingreso":
        return {
            "tipo_sangre": random.choice(["O_POS", "O_NEG", "A_POS", "B_POS"]),
            "observaciones": "Paciente ingresa por sus propios medios para revisión periódica."
        }
    elif template_name == "Receta Médica Estándar (Multi-Medicamento)":
        diagnosticos = [
            "Migraña tensional recurrente.",
            "Gastroenteritis aguda probablemente viral.",
            "Faringitis aguda no estreptocócica.",
            "Hipertensión arterial controlada."
        ]
        medicamentos_pool = [
            ("Amoxicilina", "500mg", "CADA_8_HRS", 7),
            ("Paracetamol", "1g", "CADA_6_HRS", 3),
            ("Ibuprofeno", "400mg", "CADA_8_HRS", 5),
            ("Omeprazol", "20mg", "CADA_24_HRS", 30),
            ("Losartán", "50mg", "CADA_24_HRS", 90),
            ("Metformina", "850mg", "CADA_12_HRS", 90)
        ]
        prescritos = []
        for m in random.sample(medicamentos_pool, random.randint(1, 3)):
            prescritos.append({
                "nombre_medicamento": m[0],
                "dosis": m[1],
                "frecuencia": m[2],
                "duracion": m[3]
            })
        return {
            "diagnostico_principal": random.choice(diagnosticos),
            "medicamentos_recetados": prescritos,
            "indicaciones_adicionales": "Tomar los medicamentos después de las comidas."
        }
    elif template_name == "Orden de Imagenología":
        estudios = [
            "Radiografía de Tórax AP",
            "Ecografía Abdominal Completa",
            "Resonancia Magnética de Cerebro",
            "Tomografía Computarizada de Abdomen"
        ]
        indicaciones = [
            "Paciente con tos persistente y sospecha de neumonía.",
            "Dolor agudo en hipocondrio derecho.",
            "Cefalea crónica progresiva con signos de focalización.",
            "Control evolutivo de quiste renal."
        ]
        return {
            "diagnostico_principal": "Bajo estudio clínico diagnóstico.",
            "estudio_solicitado": random.choice(estudios),
            "indicacion_clinica": random.choice(indicaciones),
            "notas_adicionales": "Solicitar con carácter de urgencia."
        }
    elif template_name == "Nota de Alta":
        ingreso = datetime.now() - timedelta(days=random.randint(3, 10))
        alta = datetime.now()
        diagnosticos = [
            "Gastroenteritis aguda deshidratante moderada.",
            "Neumonía adquirida en la comunidad corregida.",
            "Colecistitis aguda resuelta quirúrgicamente.",
            "Crisis hipertensiva resuelta."
        ]
        diagnostico_seleccionado = random.choice(diagnosticos)
        return {
            "fecha_ingreso": ingreso.strftime("%Y-%m-%d"),
            "fecha_alta": alta.strftime("%Y-%m-%d"),
            "diagnostico_principal": diagnostico_seleccionado,
            "diagnostico_alta": diagnostico_seleccionado + " (Resuelto)",
            "diagnosticos_secundarios": "Ninguno.",
            "procedimientos_realizados": "Hidratación endovenosa y monitoreo clínico de signos vitales.",
            "evolucion_clinica": "Paciente evoluciona favorablemente respondiendo al tratamiento médico instaurado.",
            "resumen_tratamiento": "Esquema completo de antibióticos y soporte electrolítico.",
            "medicinas_alta": "Paracetamol 500mg cada 8 horas vía oral por 3 días si presenta dolor.",
            "restricciones_actividad": "Reposo relativo por 48 horas.",
            "actividades_permitidas": "Caminatas leves, alimentación habitual sin grasas.",
            "restricciones_dieteticas": "Evitar alimentos irritantes y grasas saturadas.",
            "cuidados_heridas": "No aplica.",
            "instrucciones_seguimiento": "Acudir por consulta externa en 7 días para control médico general.",
            "fecha_recomendada_retorno": (alta + timedelta(days=7)).strftime("%Y-%m-%d")
        }
    return {}

def seed_database():
    db_url = os.getenv("DB_URL", "")
    if db_url.startswith("jdbc:"):
        db_url = db_url.replace("jdbc:", "", 1)
        
    print(f"🔌 Conectando a la base de datos...")
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    # 1. Cargar branding por defecto desde Spring Boot
    default_branding = {}
    branding_path = "../sgd_spring-boot/src/main/resources/default-branding.json"
    if os.path.exists(branding_path):
        try:
            with open(branding_path, "r", encoding="utf-8") as f:
                default_branding = json.load(f)
            print("🎨 Configuración de branding por defecto cargada exitosamente.")
        except Exception as e:
            print(f"⚠️ Error al leer default-branding.json: {e}")
            
    print("🧹 Limpiando tablas de datos dinámicos...")
    # Orden de limpieza para evitar violaciones de claves foráneas
    tables_to_clear = [
        "workflow_comments", "workflow_events", "workflow_documents", 
        "review_tasks", "workflows", "task_delegations", "notifications", 
        "user_push_tokens", "api_call_usage", "backup_history", 
        "document_ocr_metadata", "document_versions", "documents", 
        "dicom_instances", "dicom_series", "dicom_studies", "patients", 
        "report_templates", "document_templates",
        "role_user", "role_permission", "users", "roles", "tenants"
    ]
    for table in tables_to_clear:
        cursor.execute(f"DELETE FROM {table}")
    conn.commit()
    print("✅ Base de datos limpia.")

    # 2. Obtener los IDs de los Planes y Permisos ya cargados por Flyway
    cursor.execute("SELECT id, name FROM plans")
    plans = {row[1]: row[0] for row in cursor.fetchall()}
    
    cursor.execute("SELECT id FROM permissions")
    all_permission_ids = [row[0] for row in cursor.fetchall()]
    
    print(f"📋 Encontrados {len(plans)} planes y {len(all_permission_ids)} permisos cargados por Flyway.")

    def get_settings_for_plan(plan_name, plan_id):
        # Obtener los límites del plan de la base de datos
        cursor.execute("SELECT resource_key, resource_value FROM plan_limits WHERE plan_id = %s", (plan_id,))
        limits = {row[0]: int(row[1]) for row in cursor.fetchall()}
        
        return {
            "limits": limits,
            "regional": {
                "timezone": "America/Lima",
                "locale": "es-PE",
                "dateFormat": "DD/MM/YYYY",
                "currency": "PEN"
            },
            "notifications": {
                "emailEnabled": True,
                "smsEnabled": False,
                "pushEnabled": True
            },
            "security": {
                "sessionTimeoutMinutes": 30,
                "passwordExpiryDays": 90,
                "require2FA": False
            },
            "branding": default_branding
        }

    # 3. Crear el Tenant Maestro de Sistema (System)
    system_tenant_id = str(uuid.uuid4())
    system_settings = get_settings_for_plan("ENTERPRISE", plans["ENTERPRISE"])
    cursor.execute("""
        INSERT INTO tenants (id, name, slug, email, phone, address, subscription_plan, subscription_status, subscription_start_date, subscription_end_date, billing_cycle, settings)
        VALUES (%s, 'SGD Sistema Central', 'system', 'admin@sgd-sistema.com', '+591-000-0000', 'Sistema central', 'ENTERPRISE', 'ACTIVE', CURRENT_DATE, CURRENT_DATE + INTERVAL '100 years', 'YEARLY', %s)
    """, (system_tenant_id, json.dumps(system_settings)))
    print("🏢 Inquilino 'system' (Sistema Central) creado.")

    # 4. Crear el Tenant por Defecto (Default Demo)
    default_tenant_id = str(uuid.uuid4())
    default_settings = get_settings_for_plan("PRO", plans["PRO"])
    cursor.execute("""
        INSERT INTO tenants (id, name, slug, email, phone, address, subscription_plan, subscription_status, subscription_start_date, subscription_end_date, billing_cycle, settings)
        VALUES (%s, 'Hospital General (Demo)', 'default', 'admin@hospital.com', '+591-123-4567', 'Calle Principal #123', 'PRO', 'ACTIVE', CURRENT_DATE, CURRENT_DATE + INTERVAL '30 days', 'MONTHLY', %s)
    """, (default_tenant_id, json.dumps(default_settings)))
    print("🏢 Inquilino 'default' (Hospital General) creado.")

    # 5. Crear el Segundo Inquilino (Clinica del Sur)
    sur_tenant_id = str(uuid.uuid4())
    sur_settings = get_settings_for_plan("PRO", plans["PRO"])
    cursor.execute("""
        INSERT INTO tenants (id, name, slug, email, phone, address, subscription_plan, subscription_status, subscription_start_date, subscription_end_date, billing_cycle, settings)
        VALUES (%s, 'Clínica del Sur (Demo)', 'clinica-sur', 'admin@clinicasur.com', '+591-765-4321', 'Avenida Radial 26 #456', 'PRO', 'ACTIVE', CURRENT_DATE, CURRENT_DATE + INTERVAL '30 days', 'MONTHLY', %s)
    """, (sur_tenant_id, json.dumps(sur_settings)))
    print("🏢 Inquilino 'clinica-sur' (Clínica del Sur) creado.")

    # 6. Crear 13 Inquilinos Extra para Gráficos
    extra_tenants = []
    plan_names = list(plans.keys())
    statuses = ['ACTIVE', 'PAST_DUE', 'PENDING_PAYMENT']
    
    for i in range(1, 14):
        slug = f"clinica-extra-{i}"
        plan_name = random.choice(plan_names)
        status = random.choice(statuses)
        tenant_id = str(uuid.uuid4())
        extra_settings = get_settings_for_plan(plan_name, plans[plan_name])
        
        cursor.execute("""
            INSERT INTO tenants (id, name, slug, email, phone, address, subscription_plan, subscription_status, subscription_start_date, subscription_end_date, billing_cycle, settings)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE - %s, CURRENT_DATE + %s, 'MONTHLY', %s)
        """, (
            tenant_id, fake.company(), slug, f"admin@{slug}.com", 
            fake.phone_number(), fake.address(), plan_name, status, 
            random.randint(1, 100), random.randint(5, 60), json.dumps(extra_settings)
        ))
        extra_tenants.append((tenant_id, slug))
    print("🏢 13 Inquilinos extra creados para reportes y gráficos.")
    conn.commit()

    # 7. Generar Roles y Mapear Permisos por Tenant
    all_tenants = [(system_tenant_id, 'system'), (default_tenant_id, 'default'), (sur_tenant_id, 'clinica-sur')] + extra_tenants
    roles_map = {} # (tenant_id, role_name) -> role_id

    print("🔐 Creando roles y asignando permisos por inquilino...")
    for tenant_id, slug in all_tenants:
        roles_to_create = {
            "ROLE_ADMIN": "Administrador de la clínica",
            "ROLE_MEDICO": "Personal médico del sistema",
            "ROLE_ARCHIVO": "Encargado de archivo histórico",
            "ROLE_DIRECTOR": "Director del hospital"
        }
        if slug == 'system':
            roles_to_create["ROLE_SUPERUSER"] = "Superusuario con acceso total"
            
        for role_name, desc in roles_to_create.items():
            cursor.execute("""
                INSERT INTO roles (tenant_id, name, description, is_active)
                VALUES (%s, %s, %s, true)
                RETURNING id
            """, (tenant_id, role_name, desc))
            role_id = cursor.fetchone()[0]
            roles_map[(tenant_id, role_name)] = role_id
            
            # Mapear permisos (ROLE_ADMIN y ROLE_SUPERUSER obtienen todos los permisos del sistema)
            if role_name in ["ROLE_ADMIN", "ROLE_SUPERUSER"]:
                for perm_id in all_permission_ids:
                    cursor.execute("""
                        INSERT INTO role_permission (role_id, permission_id)
                        VALUES (%s, %s)
                    """, (role_id, perm_id))
    conn.commit()
    print("✅ Roles y permisos creados correctamente.")

    # 8. Crear Usuarios Semilla e Inyectar su Relación con Roles
    hashed_admin_pass = hash_password("admin123")
    hashed_super_pass = hash_password("superuser123")
    
    users_to_seed = [
        # (username, email, firstname, lastname, pass_hash, doc_num, role_name, tenant_id)
        ("superuser.system", "admin@sgd-sistema.com", "Super", "User", hashed_super_pass, "0000000", "ROLE_SUPERUSER", system_tenant_id),
        ("admin.default", "admin@hospital.com", "Admin", "Limited", hashed_admin_pass, "1111111", "ROLE_ADMIN", default_tenant_id),
        ("admin.sur", "admin@clinicasur.com", "Admin", "Sur", hashed_admin_pass, "2222222", "ROLE_ADMIN", sur_tenant_id),
    ]
    for tenant_id, slug in extra_tenants:
        users_to_seed.append((
            f"admin.{slug}", f"admin@{slug}.com", "Admin", f"Clínica {slug.split('-')[-1]}", 
            hashed_admin_pass, str(random.randint(1000000, 9999999)), "ROLE_ADMIN", tenant_id
        ))

    admin_users_by_tenant = {}
    print("👤 Creando usuarios administradores y asignando roles...")
    for username, email, first, last, p_hash, doc_num, role_name, tenant_id in users_to_seed:
        user_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO users (id, tenant_id, document_type, document_number, username, first_name, last_name, email, password, gender, is_active)
            VALUES (%s, %s, 'CI', %s, %s, %s, %s, %s, %s, 'M', true)
        """, (user_id, tenant_id, doc_num, username, first, last, email, p_hash))
        
        # Vincular usuario al rol
        role_id = roles_map[(tenant_id, role_name)]
        cursor.execute("""
            INSERT INTO role_user (user_id, role_id)
            VALUES (%s, %s)
        """, (user_id, role_id))
        
        if role_name in ("ROLE_ADMIN", "ROLE_SUPERUSER"):
            admin_users_by_tenant[tenant_id] = user_id
            
    # 8.5. Crear Plantillas de Documentos y Reportes por Inquilino
    print("📋 Creando plantillas de documentos y de reportes por clínica...")
    templates_by_tenant = {} # tenant_id -> list of (template_id, name)
    
    doc_templates_to_seed = [
        {
            "name": "Ficha de Ingreso",
            "description": "Datos básicos de admisión",
            "ui_schema": {
                "tipo_sangre": {
                    "type": "SELECT",
                    "required": True,
                    "label": "Grupo Sanguíneo",
                    "order": 1,
                    "options": {
                        "O_POS": "O Positivo",
                        "O_NEG": "O Negativo",
                        "A_POS": "A Positivo",
                        "B_POS": "B Positivo"
                    }
                },
                "observaciones": {
                    "type": "TEXTAREA",
                    "required": False,
                    "label": "Notas",
                    "order": 2
                }
            }
        },
        {
            "name": "Receta Médica Estándar (Multi-Medicamento)",
            "description": "Plantilla oficial que permite la prescripción de uno o múltiples medicamentos dentro de una lista dinámica.",
            "ui_schema": {
                "diagnostico_principal": {
                    "type": "TEXT",
                    "required": True,
                    "label": "Diagnóstico Principal",
                    "order": 1
                },
                "medicamentos_recetados": {
                    "type": "ARRAY",
                    "required": True,
                    "label": "Lista de Medicamentos Prescritos",
                    "order": 2,
                    "subSchema": {
                        "nombre_medicamento": {
                            "type": "TEXT",
                            "required": True,
                            "label": "Medicamento",
                            "order": 1
                        },
                        "dosis": {
                            "type": "TEXT",
                            "required": True,
                            "label": "Dosis y Presentación (Ej. 500mg, Comprimido)",
                            "order": 2
                        },
                        "frecuencia": {
                            "type": "SELECT",
                            "required": True,
                            "label": "Frecuencia de Toma",
                            "order": 3,
                            "options": {
                                "CADA_4_HRS": "Cada 4 horas",
                                "CADA_6_HRS": "Cada 6 horas",
                                "CADA_8_HRS": "Cada 8 horas",
                                "CADA_12_HRS": "Cada 12 horas",
                                "CADA_24_HRS": "Una vez al día (24 hrs)",
                                "CONDICIONAL": "Condicional al dolor o fiebre"
                            }
                        },
                        "duracion": {
                            "type": "NUMBER",
                            "required": True,
                            "label": "Duración (Días)",
                            "order": 4
                        }
                    }
                },
                "indicaciones_adicionales": {
                    "type": "TEXTAREA",
                    "required": False,
                    "label": "Indicaciones Generales / Recomendaciones de Cuidado",
                    "order": 3
                }
            }
        },
        {
            "name": "Orden de Imagenología",
            "description": "Solicitud de estudios radiológicos y de diagnóstico por imagen.",
            "ui_schema": {
                "diagnostico_principal": {
                    "type": "TEXTAREA",
                    "required": True,
                    "label": "Diagnóstico Principal",
                    "order": 1
                },
                "estudio_solicitado": {
                    "type": "TEXT",
                    "required": True,
                    "label": "Estudio Solicitado (Ej. Radiografía de Tórax)",
                    "order": 2
                },
                "indicacion_clinica": {
                    "type": "TEXTAREA",
                    "required": True,
                    "label": "Indicación Clínica / Motivo del Estudio",
                    "order": 3
                },
                "notes_adicionales": {
                    "type": "TEXTAREA",
                    "required": False,
                    "label": "Notas Adicionales",
                    "order": 4
                }
            }
        },
        {
            "name": "Nota de Alta",
            "description": "Resumen oficial de la evolución, tratamiento y recomendaciones al momento de la salida del paciente.",
            "ui_schema": {
                "fecha_ingreso": {
                    "type": "DATE",
                    "required": True,
                    "label": "Fecha de Ingreso",
                    "order": 1
                },
                "fecha_alta": {
                    "type": "DATE",
                    "required": True,
                    "label": "Fecha de Alta",
                    "order": 2
                },
                "diagnostico_principal": {
                    "type": "TEXT",
                    "required": True,
                    "label": "Diagnóstico Principal",
                    "order": 3
                },
                "diagnostico_alta": {
                    "type": "TEXT",
                    "required": True,
                    "label": "Diagnóstico de Alta",
                    "order": 4
                },
                "diagnosticos_secundarios": {
                    "type": "TEXTAREA",
                    "required": False,
                    "label": "Diagnósticos Secundarios",
                    "order": 5
                },
                "procedimientos_realizados": {
                    "type": "TEXTAREA",
                    "required": False,
                    "label": "Procedimientos Realizados",
                    "order": 6
                },
                "evolucion_clinica": {
                    "type": "TEXTAREA",
                    "required": True,
                    "label": "Evolución Clínica",
                    "order": 7
                },
                "resumen_tratamiento": {
                    "type": "TEXTAREA",
                    "required": True,
                    "label": "Resumen del Tratamiento",
                    "order": 8
                },
                "medicinas_alta": {
                    "type": "TEXTAREA",
                    "required": True,
                    "label": "Medicinas al Alta",
                    "order": 9
                },
                "restricciones_actividad": {
                    "type": "TEXTAREA",
                    "required": False,
                    "label": "Restricciones de Actividad",
                    "order": 10
                },
                "actividades_permitidas": {
                    "type": "TEXTAREA",
                    "required": False,
                    "label": "Actividades Permitidas",
                    "order": 11
                },
                "restricciones_dieteticas": {
                    "type": "TEXTAREA",
                    "required": False,
                    "label": "Restricciones Dietéticas",
                    "order": 12
                },
                "cuidados_heridas": {
                    "type": "TEXTAREA",
                    "required": False,
                    "label": "Cuidados de Heridas",
                    "order": 13
                },
                "instrucciones_seguimiento": {
                    "type": "TEXTAREA",
                    "required": True,
                    "label": "Instrucciones de Seguimiento",
                    "order": 14
                },
                "fecha_recomendada_retorno": {
                    "type": "DATE",
                    "required": False,
                    "label": "Fecha Recomendada para Retorno",
                    "order": 15
                }
            }
        }
    ]

    for tenant_id, slug in all_tenants:
            
        templates_by_tenant[tenant_id] = []
        for tpl in doc_templates_to_seed:
            tpl_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO document_templates (id, tenant_id, name, description, ui_schema, is_active)
                VALUES (%s, %s, %s, %s, %s, true)
            """, (tpl_id, tenant_id, tpl["name"], tpl["description"], json.dumps(tpl["ui_schema"])))
            templates_by_tenant[tenant_id].append((tpl_id, tpl["name"]))
            
        # Generar plantillas de reportes para el admin de este tenant
        admin_id = admin_users_by_tenant.get(tenant_id)
        if not admin_id:
            continue
            
        report_templates_to_seed = [
            {
                "name": "Reporte General de Pacientes",
                "description": "Listado completo de pacientes registrados en la clínica con datos de contacto y fecha de registro.",
                "department": "Administración",
                "report_type": "patients",
                "selected_fields": ["documentNumber", "documentType", "fullName", "gender", "birthDate", "phone", "createdAt"],
                "filters": [],
                "sort_field": "createdAt",
                "sort_order": "desc",
                "is_shared": True
            },
            {
                "name": "Pacientes Femeninos",
                "description": "Listado filtrado únicamente de pacientes de género femenino.",
                "department": "Ginecología / Obstetricia",
                "report_type": "patients",
                "selected_fields": ["documentNumber", "fullName", "birthDate", "phone"],
                "filters": [{"field": "gender", "operator": "EQ", "value": "FEMALE"}],
                "sort_field": "fullName",
                "sort_order": "asc",
                "is_shared": True
            },
            {
                "name": "Resumen de Documentos por Estado",
                "description": "Visualización consolidada de la cantidad de documentos clínicos según su estado actual.",
                "department": "Dirección Médica",
                "report_type": "documents_by_status",
                "selected_fields": ["status", "total"],
                "filters": [],
                "sort_field": "total",
                "sort_order": "desc",
                "is_shared": True
            },
            {
                "name": "Control de Documentos Clínicos Emitidos",
                "description": "Seguimiento operativo de los documentos de la clínica, sus autores y plantilla asociada.",
                "department": "Archivo",
                "report_type": "documents",
                "selected_fields": ["status", "issueDate", "patientName", "uploaderName", "templateName"],
                "filters": [],
                "sort_field": "issueDate",
                "sort_order": "desc",
                "is_shared": True
            }
        ]
        
        for r_tpl in report_templates_to_seed:
            cursor.execute("""
                INSERT INTO report_templates (id, tenant_id, owner_id, name, description, department, report_type, selected_fields, filters, sort_field, sort_order, is_shared)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()), tenant_id, admin_id, r_tpl["name"], r_tpl["description"],
                r_tpl["department"], r_tpl["report_type"], json.dumps(r_tpl["selected_fields"]),
                json.dumps(r_tpl["filters"]), r_tpl["sort_field"], r_tpl["sort_order"], r_tpl["is_shared"]
            ))
            
    conn.commit()
    print("✅ Usuarios y plantillas creados exitosamente.")

    # 9. Crear 50 Pacientes por Clínica (usando Faker)
    patients_by_tenant = {} # tenant_id -> list of patient_ids
    print("🩺 Generando 50 pacientes por clínica secundaria...")
    for tenant_id, slug in all_tenants:
        if slug == 'system':
            continue
            
        patients_by_tenant[tenant_id] = []
        for _ in range(50):
            patient_id = str(uuid.uuid4())
            doc_num = str(random.randint(1000000, 9999999))
            
            cursor.execute("""
                INSERT INTO patients (id, tenant_id, document_type, document_number, first_name, last_name, birth_date, gender, address, phone)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                patient_id, tenant_id, random.choice(['CI', 'PASAPORTE']), doc_num, 
                fake.first_name(), fake.last_name(), fake.date_of_birth(minimum_age=1, maximum_age=90), 
                random.choice(['MALE', 'FEMALE']), fake.address().replace("\n", ", "), fake.phone_number()
            ))
            patients_by_tenant[tenant_id].append(patient_id)
    conn.commit()
    print("✅ Pacientes semilla inyectados.")

    # 10. Inyectar Datos Analíticos (Documentos e imágenes DICOM para dashboards)
    print("📊 Generando historial analítico y clínico para reportes y gráficos...")
    start_date = datetime.now() - timedelta(days=180)
    estados_doc = ['DRAFT', 'PENDING_REVIEW', 'REJECTED', 'FINALIZED']
    
    for tenant_id, slug in all_tenants:
        if slug == 'system':
            continue
            
        # Obtener un ID de usuario uploader válido (el administrador recién creado)
        cursor.execute("SELECT id FROM users WHERE tenant_id = %s LIMIT 1", (tenant_id,))
        uploader_id = cursor.fetchone()[0]
        
        patient_ids = patients_by_tenant[tenant_id]
        tenant_tpls = templates_by_tenant.get(tenant_id, [])
        
        for patient_id in patient_ids:
            # 10.A Documentos normales (para embudo de estados)
            for _ in range(random.randint(2, 6)):
                doc_id = str(uuid.uuid4())
                issue_date = fake.date_between(start_date=start_date, end_date='today')
                expiry = issue_date + timedelta(days=random.randint(10, 40)) if random.random() > 0.8 else None
                file_size = random.randint(10240, 5242880) # 10 KB a 5 MB
                
                # Decidir si usar plantilla (70% de probabilidad) o ser externo (30%)
                if tenant_tpls and random.random() < 0.7:
                    tpl_id, tpl_name = random.choice(tenant_tpls)
                    is_external = False
                    clinical_content = json.dumps(generate_clinical_content(tpl_name))
                    file_url = None
                else:
                    tpl_id = None
                    is_external = True
                    clinical_content = None
                    file_url = "/fake/external_doc.pdf"
                
                cursor.execute("""
                    INSERT INTO documents (id, tenant_id, patient_id, uploader_id, template_id, status, is_external_source, clinical_content, file_url, issue_date, expiry_date, file_size_bytes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (doc_id, tenant_id, patient_id, uploader_id, tpl_id, random.choice(estados_doc), is_external, clinical_content, file_url, issue_date, expiry, file_size))
            
            # 10.B Estudios DICOM (para estadísticas de almacenamiento y radiología)
            if random.random() > 0.4:
                study_id = str(uuid.uuid4())
                study_date = fake.date_between(start_date=start_date, end_date='today')
                
                cursor.execute("""
                    INSERT INTO dicom_studies (id, tenant_id, patient_id, uploader_id, study_instance_uid, study_date)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (study_id, tenant_id, patient_id, uploader_id, str(uuid.uuid4()), study_date))
                
                series_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO dicom_series (id, tenant_id, study_id, series_instance_uid, modality, series_number)
                    VALUES (%s, %s, %s, %s, %s, 1)
                """, (series_id, tenant_id, study_id, str(uuid.uuid4()), random.choice(['CT', 'MR', 'US'])))
                
                # Instancias de imágenes DICOM
                for idx in range(random.randint(10, 50)):
                    cursor.execute("""
                        INSERT INTO dicom_instances (id, tenant_id, series_id, sop_instance_uid, instance_number, file_path, created_at, file_size_bytes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        str(uuid.uuid4()), tenant_id, series_id, str(uuid.uuid4()), idx, 
                        f'/fake/image_{idx}.dcm', study_date, random.randint(1048576, 15728640) # 1MB a 15MB
                    ))
    
    conn.commit()
    cursor.close()
    conn.close()
    print("🚀 ¡Base de datos sembrada completamente con éxito!")

if __name__ == '__main__':
    seed_database()
