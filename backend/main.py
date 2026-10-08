"""Punto de entrada del backend inicial de NoMore Errors."""

from io import BytesIO
import logging
import os
import re
import sqlite3

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
import pytesseract

load_dotenv()

from app.schemas.solutions import (
    FeedbackRequest,
    FeedbackResponse,
    SolutionResponse,
    SolutionSearchRequest,
)
from app.services.feedback_service import get_effectiveness, record_feedback
from app.services.solution_service import build_solution


logger = logging.getLogger("nomore_errors")


app = FastAPI(
    title="NoMore Errors API",
    version="0.1.0",
    description="API inicial para identificar errores de Windows.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    allow_credentials=False,
)

MAX_IMAGE_SIZE = 5 * 1024 * 1024
TESSERACT_CMD = os.getenv("TESSERACT_CMD")
WINDOWS_ERROR_CODE_PATTERN = re.compile(r"\b0x[0-9A-F]{4,16}\b", re.IGNORECASE)
WINDOWS_ERROR_NAME_PATTERN = re.compile(
    r"\b(?:CRITICAL_PROCESS_DIED|KERNEL_SECURITY_CHECK_FAILURE|"
    r"SYSTEM_SERVICE_EXCEPTION|DRIVER_IRQL_NOT_LESS_OR_EQUAL|IRQL_NOT_LESS_OR_EQUAL|"
    r"PAGE_FAULT_IN_NONPAGED_AREA|INACCESSIBLE_BOOT_DEVICE|"
    r"DPC_WATCHDOG_VIOLATION|MEMORY_MANAGEMENT|VIDEO_TDR_FAILURE|"
    r"WHEA_UNCORRECTABLE_ERROR|KMODE_EXCEPTION_NOT_HANDLED|"
    r"SYSTEM_THREAD_EXCEPTION_NOT_HANDLED|UNEXPECTED_STORE_EXCEPTION|"
    r"CLOCK_WATCHDOG_TIMEOUT|DRIVER_POWER_STATE_FAILURE|BAD_SYSTEM_CONFIG_INFO|"
    r"NTFS_FILE_SYSTEM|FAT_FILE_SYSTEM|CRITICAL_STRUCTURE_CORRUPTION|"
    r"KERNEL_DATA_INPAGE_ERROR|BAD_POOL_HEADER|BAD_POOL_CALLER|UNMOUNTABLE_BOOT_VOLUME|"
    r"MACHINE_CHECK_EXCEPTION|VIDEO_SCHEDULER_INTERNAL_ERROR|PFN_LIST_CORRUPT|"
    r"ATTEMPTED_WRITE_TO_READONLY_MEMORY|KERNEL_MODE_HEAP_CORRUPTION|HYPERVISOR_ERROR|"
    r"INTERNAL_POWER_ERROR|CRITICAL_SERVICE_FAILED|DXGI_ERROR_[A-Z_]+|STATUS_[A-Z_]+|"
    r"DNS_PROBE_FINISHED_[A-Z_]+|ERR_[A-Z_]+|[A-Z0-9_-]+\.DLL)\b",
    re.IGNORECASE,
)

if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


class ErrorAnalysisRequest(BaseModel):
    """Datos mínimos para solicitar un análisis de demostración."""

    error_code: str = Field(..., min_length=2, max_length=120)


class ErrorAnalysisResponse(BaseModel):
    """Contrato de compatibilidad para el análisis directo."""

    error_code: str
    title: str
    summary: str
    confidence: float
    steps: list[str]
    sources: list[str]


class FeedbackStatsResponse(BaseModel):
    """Métrica de efectividad de una solución concreta."""

    effectiveness_percentage: float | None
    total_votes: int


class OcrResponse(BaseModel):
    """Texto detectado y errores Windows extraídos de una imagen."""

    extracted_text: str
    detected_errors: list[str]
    message: str = ""


def extract_windows_errors(text: str) -> list[str]:
    """Devuelve códigos y nombres conocidos en un texto OCR, sin duplicados."""

    matches = [
        match.upper()
        for match in WINDOWS_ERROR_CODE_PATTERN.findall(text)
        + WINDOWS_ERROR_NAME_PATTERN.findall(text)
    ]
    return list(dict.fromkeys(matches))


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
    """Evita exponer trazas internas y deja un registro para diagnóstico."""

    logger.exception("Error no controlado en %s %s", request.method, request.url.path, exc_info=error)
    return JSONResponse(
        status_code=500,
        content={"detail": "Ha ocurrido un problema inesperado. Inténtalo de nuevo."},
    )


@app.get("/health")
def health_check() -> dict[str, str]:
    """Confirma que el proceso está disponible."""

    return {"status": "ok"}


@app.post("/api/v1/errors/analyze", response_model=ErrorAnalysisResponse)
async def analyze_error(request: ErrorAnalysisRequest) -> ErrorAnalysisResponse:
    """Mantiene la ruta antigua usando el mismo flujo real de búsqueda y síntesis."""

    normalized_code = request.error_code.strip().upper()
    if not normalized_code:
        raise HTTPException(status_code=422, detail="Escribe un código de error válido.")

    solution = await build_solution(normalized_code)
    return ErrorAnalysisResponse(
        error_code=normalized_code,
        title=f"Solución para {normalized_code}",
        summary=str(solution["simple_explanation"]),
        confidence=1.0,
        steps=[str(step["detail"]) for step in solution["steps"]],
        sources=[str(solution["sources_summary"])],
    )


@app.post("/api/v1/errors/ocr", response_model=OcrResponse)
async def extract_error_from_image(file: UploadFile = File(...)) -> OcrResponse:
    """Extrae texto OCR de una imagen y detecta errores Windows conocidos."""

    if file.content_type is None or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="El archivo debe ser una imagen.")

    try:
        contents = await file.read(MAX_IMAGE_SIZE + 1)
    except OSError as error:
        logger.warning("No se pudo leer la imagen subida: %s", error)
        raise HTTPException(status_code=400, detail="No se pudo leer la imagen subida.") from error
    if len(contents) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="La imagen no puede superar 5 MB.")

    try:
        image = Image.open(BytesIO(contents))
        image.load()
    except (UnidentifiedImageError, OSError) as error:
        raise HTTPException(status_code=400, detail="No se pudo leer la imagen.") from error

    try:
        raw_text = pytesseract.image_to_string(image, timeout=15)
    except pytesseract.TesseractNotFoundError as error:
        raise HTTPException(
            status_code=503,
            detail="Tesseract OCR no está instalado o no está en PATH.",
        ) from error
    except (pytesseract.TesseractError, RuntimeError) as error:
        logger.warning("El OCR no pudo procesar la imagen: %s", error)
        raise HTTPException(
            status_code=503,
            detail="No pudimos leer el texto de la imagen. Prueba con una captura más clara.",
        ) from error

    cleaned_text = " ".join(raw_text.split())
    detected_errors = extract_windows_errors(cleaned_text)
    message = ""
    if not cleaned_text or not detected_errors:
        message = "No pudimos identificar un código claro. Escribe el código manualmente para continuar."
    return OcrResponse(
        extracted_text=cleaned_text,
        detected_errors=detected_errors,
        message=message,
    )


@app.post("/api/v1/solutions/search", response_model=SolutionResponse)
async def search_solution(request: SolutionSearchRequest) -> SolutionResponse:
    """Busca contexto y sintetiza una solución comprensible."""

    error_code = request.error_code
    if not error_code:
        detected_errors = extract_windows_errors(request.error_text)
        if not detected_errors:
            raise HTTPException(
                status_code=422,
                detail="No encontramos un código de error en el texto. Escribe el código en 'error_code'.",
            )
        error_code = detected_errors[0]
    if len(error_code) < 2:
        raise HTTPException(status_code=422, detail="Escribe un código de error válido.")

    solution = await build_solution(error_code, request.error_text)
    return SolutionResponse(**solution)


@app.post("/api/feedback", response_model=FeedbackResponse)
def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Guarda el voto y devuelve la efectividad actualizada."""

    normalized_code = request.error_code.strip().upper()
    if not normalized_code:
        raise HTTPException(status_code=422, detail="Falta el código del error.")

    try:
        metrics = record_feedback(normalized_code, request.solution_id, request.success)
    except (OSError, sqlite3.Error) as error:
        logger.exception("No se pudo guardar el feedback", exc_info=error)
        raise HTTPException(
            status_code=503,
            detail="No pudimos guardar tu respuesta. Inténtalo de nuevo en unos segundos.",
        ) from error
    return FeedbackResponse(
        solution_id=request.solution_id,
        success=request.success,
        effectiveness_percentage=metrics["effectiveness_percentage"],
        total_votes=metrics["total_votes"],
        message="Gracias por tu respuesta.",
    )


@app.get("/api/feedback/stats", response_model=FeedbackStatsResponse)
def feedback_stats(
    error_code: str = Query(..., min_length=2, max_length=120),
    solution_id: str = Query(..., min_length=4, max_length=80),
) -> FeedbackStatsResponse:
    """Devuelve la efectividad actual de una solución sin registrar votos."""

    try:
        metrics = get_effectiveness(error_code.strip().upper(), solution_id)
    except (OSError, sqlite3.Error) as error:
        logger.exception("No se pudo leer el feedback", exc_info=error)
        raise HTTPException(status_code=503, detail="No pudimos leer los votos ahora mismo.") from error
    return FeedbackStatsResponse(
        effectiveness_percentage=metrics["effectiveness_percentage"],
        total_votes=metrics["total_votes"],
    )
