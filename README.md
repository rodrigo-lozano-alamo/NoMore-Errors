# NoMore Errors

> Entiende y resuelve errores de Windows sin ser técnico.

NoMore Errors convierte un **código de error** o una **captura de pantalla** en una explicación clara, una guía paso a paso y una forma sencilla de indicar si la solución funcionó.

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)
![Gemini](https://img.shields.io/badge/IA-Google%20Gemini-4285F4?logo=google&logoColor=white)
![Estado](https://img.shields.io/badge/estado-en%20desarrollo-orange)

## Características

- **OCR de capturas**: extrae el texto con Tesseract y detecta códigos como `0x80070005` o `KERNEL_SECURITY_CHECK_FAILURE`.
- **Catálogo local de errores**: base de conocimiento propia en JSON con soluciones verificadas.
- **Contexto de la comunidad**: consulta hilos públicos de Reddit (tratados como datos no confiables).
- **Síntesis con IA**: Google Gemini genera pasos numerados, dificultad, riesgo y fuentes. Si la IA no está disponible, se usa la solución del catálogo local.
- **Feedback "¿Te funcionó?"**: los votos se guardan en SQLite y se muestra el porcentaje de efectividad junto al número de respuestas.

## Arquitectura

```text
Frontend estático (HTML/CSS/JS)
        │  HTTP
        ▼
API FastAPI ──► OCR (Tesseract)
            ├─► Catálogo de errores (backend/data/*.json)
            ├─► Reddit (búsqueda pública)
            ├─► Gemini (síntesis)
            └─► SQLite (feedback)
```

```text
backend/
├── main.py                 # Endpoints y configuración de la API
├── requirements.txt
├── .env.example
├── app/
│   ├── schemas/            # Modelos Pydantic
│   └── services/           # IA, conocimiento, soluciones y feedback
└── data/                   # Catálogos de errores en JSON
frontend/
├── index.html
├── app.js
└── styles.css
PROJECT_BLUEPRINT.md        # Diseño detallado, fases y hoja de ruta
```

## Puesta en marcha (Windows)

**Requisitos:** Python 3.12+ y [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki).

```powershell
git clone <url-del-repositorio>
cd "NoMore Errors"

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

Copy-Item backend\.env.example backend\.env   # y añade tu GEMINI_API_KEY
```

Arranca la API (terminal 1):

```powershell
cd backend
python -m uvicorn main:app --reload --port 8000
```

Sirve el frontend (terminal 2):

```powershell
cd frontend
python -m http.server 5500
```

Abre <http://127.0.0.1:5500>. La documentación interactiva de la API está en <http://127.0.0.1:8000/docs>.

> No abras `index.html` directamente como `file://`: el navegador bloquearía las peticiones a la API.

## Variables de entorno

| Variable | Descripción |
| --- | --- |
| `GEMINI_API_KEY` | Clave de Google Gemini. Sin ella solo se usan las soluciones del catálogo local. |
| `GEMINI_MODEL` | Modelo principal (por defecto `gemini-3.5-flash`). |
| `GEMINI_FALLBACK_MODELS` | Modelos alternativos separados por comas. |
| `REDDIT_USER_AGENT` | User-Agent para las consultas a Reddit. |
| `TESSERACT_CMD` | Ruta a `tesseract.exe` si no está en el `PATH`. |
| `FEEDBACK_DB_PATH` | Ruta de la base SQLite de feedback. |

## API

| Método | Ruta | Descripción |
| --- | --- | --- |
| `GET` | `/health` | Estado del servicio |
| `POST` | `/api/v1/errors/analyze` | Normaliza un código de error introducido a mano |
| `POST` | `/api/v1/errors/ocr` | Extrae el error de una imagen (máx. 5 MB) |
| `POST` | `/api/v1/solutions/search` | Devuelve la solución, pasos, fuentes y efectividad |
| `POST` | `/api/feedback` | Registra si la solución funcionó |

## Hoja de ruta

Pruebas automáticas, caché y rate limiting, migración del frontend a React/Tauri y despliegue con Docker. Detalles en [PROJECT_BLUEPRINT.md](PROJECT_BLUEPRINT.md).
