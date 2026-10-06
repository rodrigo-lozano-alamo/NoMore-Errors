"""Contratos HTTP del motor de soluciones."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SolutionSearchRequest(BaseModel):
    """Entrada combinada desde texto manual u OCR.

    Basta con enviar uno de los dos campos; si solo llega el texto, la ruta
    intenta extraer el código de él.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    error_code: str | None = Field(default=None, max_length=120)
    error_text: str = Field(default="", max_length=4000)

    @field_validator("error_code", mode="before")
    @classmethod
    def _empty_code_as_none(cls, value: object) -> object:
        """Trata cadenas vacías como ausencia de código."""

        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("error_text", mode="before")
    @classmethod
    def _null_text_as_empty(cls, value: object) -> object:
        """Acepta `null` en el texto sin devolver un 422."""

        return "" if value is None else value

    @model_validator(mode="after")
    def _require_code_or_text(self) -> "SolutionSearchRequest":
        """Exige al menos un dato útil para buscar."""

        if not self.error_code and not self.error_text:
            raise ValueError("Envía 'error_code' o 'error_text'.")
        return self


class SolutionStep(BaseModel):
    """Paso accionable con representación visual y riesgo explícito."""

    number: int = Field(..., ge=1, le=12)
    text: str | None = Field(default=None, max_length=1000)
    type: Literal["configuracion", "configuración", "terminal", "advertencia", "reinicio"] | None = None
    title: str = Field(..., min_length=3, max_length=120)
    detail: str = Field(..., min_length=3, max_length=1000)
    how_to: str = Field(default="", max_length=1200)
    tipo: Literal["configuracion", "configuración", "terminal", "advertencia", "reinicio"] | None = None
    comando: str | None = Field(default=None, max_length=500)
    command_explanation: str | None = Field(default=None, max_length=500)
    tags: list[Literal["configuracion", "configuración", "terminal", "advertencia", "reinicio"]] = Field(
        ..., min_length=1, max_length=3
    )


class SolutionResponse(BaseModel):
    """Respuesta sencilla y estable para el frontend."""

    error_code: str
    solution_id: str
    simple_explanation: str
    causes: list[str] = Field(..., min_length=2, max_length=3)
    steps: list[SolutionStep]
    sources_summary: str
    effectiveness_percentage: float | None
    total_votes: int


class FeedbackRequest(BaseModel):
    """Voto de un usuario sobre una solución concreta."""

    error_code: str = Field(..., min_length=2, max_length=120)
    solution_id: str = Field(..., min_length=4, max_length=80)
    success: bool


class FeedbackResponse(BaseModel):
    """Métrica resultante después de guardar un voto."""

    solution_id: str
    success: bool
    effectiveness_percentage: float | None
    total_votes: int
    message: str