"""Obtención de contexto desde Windows y Reddit."""

from dataclasses import dataclass
from functools import lru_cache
import json
import os
from pathlib import Path

import httpx


@dataclass(frozen=True)
class KnowledgeItem:
    """Fragmento de conocimiento que puede usar el sintetizador."""

    title: str
    text: str
    source: str
    url: str = ""


DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CATALOG_PATHS = (
    Path(os.getenv("WINDOWS_ERROR_CATALOG_PATH", DEFAULT_DATA_DIR / "errors_catalog.json")),
    Path(os.getenv("WINDOWS_ERROR_CATALOG_ADDITIONAL_PATH", DEFAULT_DATA_DIR / "errors_catalog_additional.json")),
    Path(os.getenv("WINDOWS_ERROR_CATALOG_ADDITIONAL_2_PATH", DEFAULT_DATA_DIR / "errors_catalog_additional_2.json")),
    Path(os.getenv("WINDOWS_ERROR_CATALOG_BULK_PATH", DEFAULT_DATA_DIR / "errors_catalog_bulk.json")),
    Path(os.getenv("WINDOWS_ERROR_CATALOG_BULK_2_PATH", DEFAULT_DATA_DIR / "errors_catalog_bulk_2.json")),
)


@lru_cache(maxsize=1)
def load_error_catalog() -> dict[str, dict[str, object]]:
    """Fusiona los catálogos JSON locales y los deja listos para consultas."""

    catalog: dict[str, dict[str, object]] = {}
    for catalog_path in dict.fromkeys(CATALOG_PATHS):
        try:
            with catalog_path.open(encoding="utf-8") as catalog_file:
                payload = json.load(catalog_file)
        except (OSError, json.JSONDecodeError):
            continue

        entries = payload.get("errors", []) if isinstance(payload, dict) else []
        if isinstance(payload, dict):
            for error_range in payload.get("ranges", []):
                if not isinstance(error_range, dict):
                    continue
                if error_range.get("format") != "hresult_win32":
                    continue
                start = error_range.get("start")
                end = error_range.get("end")
                if not isinstance(start, int) or not isinstance(end, int) or end < start:
                    continue
                generated_entries = [
                    {
                        "code": f"0X8007{error_id:04X}",
                        "title": f"Win32 system error {error_id}",
                        "simple_explanation": f"Windows devolvió el código de sistema {error_id} (0X8007{error_id:04X}). La IA debe interpretar el contexto del equipo para explicar la causa concreta.",
                        "probable_causes": [
                            "Fallo en un componente o servicio de Windows.",
                            "Configuración, controlador o recurso del sistema relacionado.",
                            "Interrupción durante la operación solicitada.",
                        ],
                        "steps": [],
                        "ai_required": bool(error_range.get("ai_required", True)),
                        "source": error_range.get("source", "Win32 system error index"),
                    }
                    for error_id in range(start, end + 1)
                ]
                entries = [*entries, *generated_entries]
        if not isinstance(entries, list):
            continue
        catalog.update({
            entry["code"].strip().upper(): entry
            for entry in entries
            if isinstance(entry, dict) and isinstance(entry.get("code"), str)
        })
    return catalog


def get_catalog_entry(error_code: str) -> dict[str, object] | None:
    """Devuelve una ficha local completa si el código está catalogado."""

    return load_error_catalog().get(error_code.strip().upper())


def search_windows_database(error_code: str) -> list[KnowledgeItem]:
    """Busca una explicación local mientras se integra una fuente oficial real."""

    normalized_code = error_code.strip().upper()
    catalog_entry = get_catalog_entry(normalized_code)
    if catalog_entry:
        return [
            KnowledgeItem(
                title=str(catalog_entry.get("title", normalized_code)),
                text=str(catalog_entry.get("simple_explanation", "")),
                source="Windows error catalog (local)",
            )
        ]

    return []


async def search_reddit(error_code: str, error_text: str = "") -> list[KnowledgeItem]:
    """Consulta la búsqueda JSON pública de r/WindowsHelp sin OAuth."""

    query = " ".join(filter(None, [error_code.strip(), error_text.strip()[:160]]))
    headers = {
        "User-Agent": os.getenv(
            "REDDIT_USER_AGENT", "NoMoreErrorsApp/1.0 (support@example.com)"
        )
    }
    params = {"q": query, "restrict_sr": "1", "sort": "relevance", "limit": 3, "raw_json": 1}

    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            response = await client.get(
                "https://www.reddit.com/r/WindowsHelp/search.json",
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.TimeoutException, httpx.HTTPError, ValueError):
        return []

    if not isinstance(payload, dict):
        return []
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return []
    children = data.get("children", [])
    if not isinstance(children, list):
        return []

    items: list[KnowledgeItem] = []
    for child in children:
        if not isinstance(child, dict):
            continue
        post = child.get("data", {})
        if not isinstance(post, dict):
            continue
        title = str(post.get("title", "")).strip()
        text = str(post.get("selftext", "")).strip()
        url = str(post.get("permalink", "")).strip()
        if title:
            items.append(
                KnowledgeItem(
                    title=title[:240],
                    text=text[:1200] or "Publicación sin texto adicional.",
                    source=f"Reddit r/{post.get('subreddit', 'unknown')}",
                    url=f"https://www.reddit.com{url}" if url.startswith("/") else url,
                )
            )
    return items