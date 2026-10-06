"""Persistencia SQLite y métricas de feedback de soluciones."""

from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[2]
DATABASE_PATH = Path(os.getenv("FEEDBACK_DB_PATH", BACKEND_DIR / "data" / "feedback.db"))


def _connect() -> sqlite3.Connection:
    """Abre una conexión corta y aislada para cada operación."""

    connection = sqlite3.connect(DATABASE_PATH, timeout=5)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    """Crea el esquema e índices necesarios si aún no existen."""

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_code TEXT NOT NULL,
                solution_id TEXT NOT NULL,
                success INTEGER NOT NULL CHECK (success IN (0, 1)),
                timestamp TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_feedback_solution
            ON feedback_votes (error_code, solution_id)
            """
        )


def get_effectiveness(error_code: str, solution_id: str) -> dict[str, Any]:
    """Calcula votos totales, éxitos y porcentaje de una solución."""

    with _connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total_votes,
                   COALESCE(SUM(success), 0) AS successful_votes
            FROM feedback_votes
            WHERE error_code = ? AND solution_id = ?
            """,
            (error_code, solution_id),
        ).fetchone()

    total_votes = int(row["total_votes"])
    successful_votes = int(row["successful_votes"])
    percentage = round(successful_votes / total_votes * 100, 2) if total_votes else None
    return {
        "effectiveness_percentage": percentage,
        "total_votes": total_votes,
        "successful_votes": successful_votes,
    }


def record_feedback(error_code: str, solution_id: str, success: bool) -> dict[str, Any]:
    """Guarda un voto y devuelve la métrica actualizada."""

    timestamp = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO feedback_votes (error_code, solution_id, success, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (error_code, solution_id, int(success), timestamp),
        )
        connection.commit()

    return get_effectiveness(error_code, solution_id)


initialize_database()