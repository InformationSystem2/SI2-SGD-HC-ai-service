# SGD-HC AI Microservice — Microservicio de IA y Reportes en FastAPI

**Sistemas de Información II — Universidad Autónoma Gabriel René Moreno (UAGRM)**

## Entregables

| Recurso | Enlace |
|---|---|
| Documento de Reportes Dinámicos (PDF) | [`docs/reportes_implementacion.md`](docs/reportes_implementacion.md) |
| Repositorio público | https://github.com/InformationSystem2/SI2-SGD-HC-fastapi |

---

## Información del Proyecto

**SGD-HC AI Microservice** es un componente especializado desarrollado en **FastAPI (Python 3.11+)** que actúa como motor analítico y de automatización para la plataforma principal.

Sus responsabilidades principales se dividen en:
* **Procesamiento OCR y Extracción de Metadatos**: Integración con motores de visión artificial para digitalizar expedientes médicos escaneados y estructurar su información automáticamente.
* **Motor Dinámico de Reportes (QBE & Analíticos)**: Generador dinámico de consultas SQL a partir de metadatos del catálogo, previniendo la inyección SQL y abstrayendo la complejidad de las uniones (Joins).
* **Exportador Multi-formato**: Generación de archivos Excel (`openpyxl`), PDF (`reportlab`), HTML y JSON alineados con los estándares estéticos del tenant.

---

## Arquitectura de Reportes y Flujo

```
   Petición HTTP (Cliente) ──► auth_dependency.py (Valida JWT del Backend)
          │  
          ▼
   API Router (reports.py) ──► Valida permiso RBAC (REPORT_READ)
          │
          ▼
   ReportService ──► Resuelve el catálogo de reportes (catalog.py)
          │
          ▼
   ReportRepository ──► Construye SQL dinámico seguro con SQLAlchemy
          │
          ├─ Joins Automáticos ──► Analiza tablas necesarias
          ├─ Parametrización ──► Evita inyección SQL (:p_f0, :p_f1, ...)
          │
          ▼
   Base de Datos PostgreSQL ──► Ejecuta la consulta
          │
          ▼
   Exporter (Excel/PDF/HTML) ──► Retorna archivo binario o JSON plano
```

---

## Estructura del Proyecto

```
sgd_fastapi/
├── app/
│   ├── models/                     # Modelos declarativos SQLAlchemy (ReportTemplate, etc.)
│   ├── repositories/               # Lógica de acceso a datos (ReportRepository)
│   ├── routers/                    # Controladores de la API (ocr, reports, analytics)
│   ├── schemas/                    # Pydantic Schemas para validación de entrada/salida
│   ├── services/                   # Motores lógicos (catalog, exporter, report_service)
│   ├── auth.py                     # Middleware de validación JWT y extracción de roles/permisos
│   ├── database.py                 # Conector SQLAlchemy y pools de conexión PostgreSQL
│   └── main.py                     # Punto de entrada de la aplicación FastAPI
│
├── docs/
│   └── reportes_implementacion.md  # Documentación detallada del motor dinámico y formatos
├── main.py                         # Punto de entrada raíz
├── requirements.txt                # Dependencias de Python
└── README.md
```

---

## Tecnologías

### Core & API
| Tecnología | Versión | Uso |
|---|---|---|
| Python | 3.11 / 3.12 | Lenguaje de desarrollo principal |
| FastAPI | 0.110.x | Framework de desarrollo de API rápido y asíncrono |
| SQLAlchemy | 2.0.x | ORM de base de datos SQL y constructor de consultas |
| PostgreSQL | 18 | Base de datos relacional compartida con Spring Boot |

### Procesamiento y Generación de Reportes
| Tecnología | Versión | Uso |
|---|---|---|
| OpenPyXL | 3.1.x | Generación interactiva de reportes de hoja de cálculo Excel |
| ReportLab | 4.1.x | Compilación en tiempo real de documentos y reportes PDF |
| PyTesseract / OCR | — | Motor de reconocimiento óptico de caracteres para historias clínicas |

---

## Instalación y Ejecución

### 1. Requisitos Previos
* Python 3.11 o superior instalado.
* Tesseract OCR instalado en el sistema operativo (para el procesamiento OCR).
* PostgreSQL corriendo.

### 2. Configurar Variables de Entorno
Cree un archivo `.env` en la raíz del proyecto basándose en las necesidades del sistema (o compartiendo el `.env` del backend de Spring Boot):

```env
PORT=8001
DB_URL=postgresql://postgres:postgres@localhost:5432/sgd_hc
JWT_SECRET=tu_clave_secreta_super_larga_en_base64_aqui
```

### 3. Compilar e Iniciar la Aplicación

Crear e inicializar el entorno virtual de Python:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

Instalar las dependencias del proyecto:
```bash
pip install -r requirements.txt
```

Iniciar el servidor de desarrollo Uvicorn:
```bash
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

La API y su documentación interactiva estarán disponibles en:
* API Base: `http://localhost:8001`
* Swagger UI: `http://localhost:8001/docs`

---

## Endpoints Principales

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/ocr/process` | Procesa un archivo PDF/Imagen, realiza OCR y devuelve metadatos |
| `GET` | `/api/reports/catalog` | Recupera el catálogo de metadatos de reportes permitidos para el usuario |
| `POST` | `/api/reports/run` | Ejecuta un reporte dinámico QBE o agregación y devuelve resultados paginados |
| `POST` | `/api/reports/export` | Genera y descarga el reporte resultante en formatos (.xlsx, .pdf, .html) |
| `GET` | `/api/reports/templates` | Lista las plantillas de consultas guardadas por el departamento |
| `POST` | `/api/reports/templates` | Guarda una nueva plantilla de diseño de filtros y campos QBE |
| `GET` | `/api/analytics/dashboard` | Retorna estadísticas en tiempo real y KPI clínicos del Tenant |

---

## Módulo de Seguridad y Generación Segura

### Autenticación y Autorización Distribuida
El microservicio no posee base de datos de usuarios propia; en su lugar, intercepta la cabecera `Authorization` de las peticiones HTTP. A través del componente `auth.py`, valida la firma del token JWT utilizando la clave secreta compartida con Spring Boot (`JWT_SECRET`). Posterior a la validación, decodifica los permisos del usuario y verifica de manera estricta que posea el rol o permiso necesario (como `REPORT_READ`) antes de permitir el acceso al motor.

### Prevención de Inyección SQL en Consultas Dinámicas
Dado que el motor QBE permite al usuario añadir filtros arbitrarios y elegir columnas personalizadas:
1. **Validación de Identificadores**: El catálogo (`catalog.py`) define de forma estática los nombres de las tablas y campos mapeados. El repositorio rechaza cualquier columna o tabla que no esté explícitamente listada en el diccionario de metadatos.
2. **Parametrización Estricta**: No se concatenan cadenas de texto procedentes de solicitudes HTTP en la consulta SQL. Todos los filtros son inyectados mediante marcadores de posición posicionales de SQLAlchemy (`execute(text(sql), params)`).

---

## Por qué control de accesos a nivel de atributos y no de endpoints simple

| Tipo de Control | Permite ocultar campos sensibles | Flexibilidad por Rol | Complejidad de API |
|---|---|---|---|
| **Control por Endpoint (`/paciente/{id}`)** | No (Retorna todo el objeto o nada) | Baja | Baja |
| **Control a nivel de Atributo (SGD-HC)** | **Sí** (El motor dinámico filtra campos según permisos) | **Alta** (Granular por permiso) | Media (Mapeo dinámico) |

---

## Documentación Técnica

- [`docs/reportes_implementacion.md`](docs/reportes_implementacion.md) — Análisis arquitectónico de la implementación de reportes QBE y analíticos.

---

## Equipo

| Integrante | Rol |
|---|---|
| **Evert Rodríguez Araúz** | Backend Developer / Arquitecto de Software |
| *[Integrante 2]* | *[Rol]* |
| *[Integrante 3]* | *[Rol]* |

---

*Proyecto desarrollado para la materia de Sistemas de Información II — UAGRM*
