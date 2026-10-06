"""Orquestación del motor de búsqueda y síntesis."""

import hashlib
import json
import logging

from fastapi import HTTPException
from google.genai import errors as genai_errors
from app.schemas.solutions import SolutionStep
from app.services.ai_service import synthesize_solution
from app.services.knowledge_service import get_catalog_entry, search_reddit, search_windows_database
from app.services.feedback_service import get_effectiveness


logger = logging.getLogger("nomore_errors")


def _create_solution_id(error_code: str, explanation: str, steps: list[dict[str, object]]) -> str:
    """Genera un identificador estable para la solución que se mostró."""

    payload = json.dumps(
        {"error_code": error_code, "explanation": explanation, "steps": steps},
        ensure_ascii=False,
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"sol_{digest}"


def _normalize_step(step: dict[str, object]) -> dict[str, object]:
    """Completa fichas antiguas para mantener una experiencia educativa uniforme."""

    detail = str(step.get("detail", "Sigue este paso con cuidado."))
    command = step.get("comando")
    return SolutionStep.model_validate({
        **step,
        "tags": step.get("tags") or [step.get("tipo", "configuracion")],
        "how_to": step.get("how_to") or detail,
        "command_explanation": (
            step.get("command_explanation")
            or ("Ejecuta este comando en Terminal de Windows como administrador." if command else None)
        ),
    }).model_dump()


def _local_synthesis(error_code: str) -> dict[str, object] | None:
    """Devuelve la ficha resuelta del catálogo local, si existe y está completa."""

    entry = get_catalog_entry(error_code)
    if not entry or not entry.get("steps"):
        return None
    causes = [str(cause) for cause in entry.get("probable_causes", [])][:3]
    if len(causes) < 2:
        return None
    return {
        "simple_explanation": str(entry.get("simple_explanation", "")),
        "causes": causes,
        "steps": entry["steps"],
    }


def _gemini_http_error(error_code: str, error: Exception) -> HTTPException:
    """Traduce un fallo de Gemini a un mensaje claro para el usuario."""

    if isinstance(error, genai_errors.APIError):
        logger.warning("Gemini respondió %s para %s: %s", error.code, error_code, error.message)
        if error.code == 429 or error.code >= 500:
            return HTTPException(
                status_code=503,
                detail="Gemini está saturado en este momento. Inténtalo de nuevo en unos minutos.",
            )
        return HTTPException(
            status_code=503,
            detail="No se pudo obtener una síntesis de Gemini. Comprueba GEMINI_API_KEY y GEMINI_MODEL.",
        )
    if isinstance(error, RuntimeError):
        return HTTPException(status_code=503, detail="Falta GEMINI_API_KEY en el archivo .env.")
    logger.exception("La síntesis de Gemini falló para %s", error_code, exc_info=error)
    return HTTPException(
        status_code=503,
        detail="Gemini devolvió una respuesta que no pudimos procesar. Inténtalo de nuevo.",
    )


async def build_solution(error_code: str, error_text: str = "") -> dict[str, object]:
    """Consulta fuentes y devuelve la solución lista para el contrato HTTP."""

    normalized_code = error_code.strip().upper()
    windows_items = search_windows_database(normalized_code)

    reddit_items = await search_reddit(normalized_code, error_text)
    try:
        synthesis = await synthesize_solution(normalized_code, windows_items, reddit_items, error_text)
    except Exception as error:
        synthesis = _local_synthesis(normalized_code)
        if synthesis is None:
            raise _gemini_http_error(normalized_code, error) from error
        logger.warning("Gemini no disponible para %s; se usa la solución del catálogo local.", normalized_code)
        sources_summary = (
            "La IA no está disponible ahora mismo; se muestra la solución verificada "
            "del catálogo local de NoMore Errors."
        )
    else:
        source_names = {item.source for item in [*windows_items, *reddit_items]}
        reddit_status = (
            f"{len(reddit_items)} hilo(s) real(es) de Reddit"
            if reddit_items
            else "Reddit consultado, sin hilos disponibles"
        )
        local_status = ", ".join(sorted(source_names - {item.source for item in reddit_items}))
        sources_summary = f"Síntesis consultada a Gemini; {reddit_status}."
        if local_status:
            sources_summary += f" Referencia local adicional: {local_status}."

    explanation = str(synthesis["simple_explanation"])
    steps = [_normalize_step(dict(step)) for step in synthesis["steps"]]
    solution_id = _create_solution_id(normalized_code, explanation, steps)
    effectiveness = get_effectiveness(normalized_code, solution_id)

    return {
        "error_code": normalized_code,
        "solution_id": solution_id,
        "simple_explanation": explanation,
        "causes": [str(cause) for cause in synthesis.get("causes", synthesis.get("probable_causes", []))],
        "steps": steps,
        "sources_summary": sources_summary,
        "effectiveness_percentage": effectiveness["effectiveness_percentage"],
        "total_votes": effectiveness["total_votes"],
    }