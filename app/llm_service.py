from dataclasses import dataclass

import httpx

from config import OLLAMA_MODEL, OLLAMA_TIMEOUT_SEGUNDOS, OLLAMA_URL
from app.ollama_manager import ollama_manager


class OllamaServiceError(RuntimeError):
    # Error controlado al comunicarse con el servicio local de Ollama.
    pass


@dataclass(frozen=True)
class ContextoExplicacion:
    concepto: str
    dominio_estimado: float
    estado_concepto: str
    nivel_dificultad: int
    contexto_base: str = ""


def construir_prompt(contexto: ContextoExplicacion) -> str:
    # Construye un prompt cerrado con datos derivados por la aplicación.
    contenido_base = contexto.contexto_base or "No hay contenido teórico adicional disponible."
    return f"""Eres un tutor de programación Python dentro de una plataforma educativa.

Concepto: {contexto.concepto}
Dominio estimado registrado: {contexto.dominio_estimado:.2f}
Estado actual del concepto: {contexto.estado_concepto}
Nivel de dificultad actual: {contexto.nivel_dificultad}
Contexto disponible: {contenido_base}

Genera una explicación teórica adaptada al estado y nivel indicados.

Requisitos:
* Usa lenguaje claro para educación media.
* Explica correctamente el concepto y adapta la profundidad al nivel indicado.
* Incluye un ejemplo sencillo de Python solo si ayuda a explicarlo.
* No generes ejercicios ni evalúes al aprendiz.
* No determines, cambies ni menciones una decisión sobre su dominio o nivel.
* No introduzcas conceptos avanzados innecesarios ni inventes información.
* Mantén la explicación concisa.
* Devuelve únicamente la explicación."""


def generar_explicacion(contexto: ContextoExplicacion) -> str:
    # Solicita una explicación a Ollama y valida una respuesta mínima útil.
    if ollama_manager.modelo_disponible is False:
        raise OllamaServiceError(
            f"El modelo local {OLLAMA_MODEL} no está instalado. Ejecute: ollama pull {OLLAMA_MODEL}"
        )
    try:
        respuesta = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "stream": False, "prompt": construir_prompt(contexto)},
            timeout=OLLAMA_TIMEOUT_SEGUNDOS,
        )
        respuesta.raise_for_status()
    except httpx.TimeoutException as exc:
        raise OllamaServiceError("Ollama tardó demasiado en responder.") from exc
    except httpx.RequestError as exc:
        raise OllamaServiceError("El servicio local de Ollama no está disponible.") from exc
    except httpx.HTTPStatusError as exc:
        raise OllamaServiceError("Ollama no pudo generar la explicación solicitada.") from exc

    try:
        contenido = respuesta.json().get("response", "").strip()
    except ValueError as exc:
        raise OllamaServiceError("Ollama devolvió una respuesta inválida.") from exc
    if not contenido:
        raise OllamaServiceError("Ollama devolvió una explicación vacía.")
    return contenido
