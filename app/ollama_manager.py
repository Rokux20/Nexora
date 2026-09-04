# Gestión del servidor local de Ollama durante el ciclo de FastAPI.
# No contiene prompts ni lógica pedagógica. Solo reutiliza un servidor ya
# activo o inicia ``ollama serve`` si el ejecutable local está disponible.
import logging
import os
from pathlib import Path
import shutil
import subprocess
import time

import httpx

from config import (
    OLLAMA_ESPERA_INICIO_SEGUNDOS,
    OLLAMA_INTERVALO_COMPROBACION_SEGUNDOS,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SEGUNDOS,
    OLLAMA_URL,
)

logger = logging.getLogger(__name__)


class OllamaManager:
    def __init__(
        self,
        url: str = OLLAMA_URL,
        modelo: str = OLLAMA_MODEL,
        espera_inicio: float = OLLAMA_ESPERA_INICIO_SEGUNDOS,
        intervalo: float = OLLAMA_INTERVALO_COMPROBACION_SEGUNDOS,
    ):
        self.url = url.rstrip("/")
        self.modelo = modelo
        self.espera_inicio = espera_inicio
        self.intervalo = intervalo
        self.proceso: subprocess.Popen | None = None
        self.iniciado_por_aplicacion = False
        self.disponible = False
        self.modelo_disponible: bool | None = None

    def _tags(self) -> dict | None:
        try:
            respuesta = httpx.get(f"{self.url}/api/tags", timeout=OLLAMA_TIMEOUT_SEGUNDOS)
            respuesta.raise_for_status()
            return respuesta.json()
        except (httpx.HTTPError, ValueError):
            return None

    def esta_disponible(self) -> bool:
        self.disponible = self._tags() is not None
        return self.disponible

    def buscar_ejecutable(self) -> str | None:
        # Busca Ollama sin asumir un perfil de Windows concreto.
        encontrado = shutil.which("ollama")
        if encontrado:
            return encontrado

        if os.name != "nt":
            return None
        candidatos = []
        for variable in ("PROGRAMFILES", "LOCALAPPDATA"):
            base = os.environ.get(variable)
            if base:
                candidatos.append(Path(base) / "Ollama" / "ollama.exe")
                candidatos.append(Path(base) / "Programs" / "Ollama" / "ollama.exe")
        for candidato in candidatos:
            if candidato.is_file():
                return str(candidato)
        return None

    def iniciar(self) -> bool:
        ejecutable = self.buscar_ejecutable()
        if not ejecutable:
            logger.warning("[LLM] No fue posible iniciar Ollama: ejecutable no encontrado.")
            return False
        try:
            opciones: dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
            if os.name == "nt":
                opciones["creationflags"] = subprocess.CREATE_NO_WINDOW
            self.proceso = subprocess.Popen([ejecutable, "serve"], **opciones)
            self.iniciado_por_aplicacion = True
            logger.info("[LLM] Iniciando Ollama automáticamente...")
            return True
        except OSError:
            logger.warning("[LLM] No fue posible iniciar Ollama.")
            return False

    def esperar_disponibilidad(self) -> bool:
        limite = time.monotonic() + self.espera_inicio
        while time.monotonic() < limite:
            if self.esta_disponible():
                return True
            time.sleep(self.intervalo)
        self.disponible = False
        return False

    def comprobar_modelo(self) -> bool:
        tags = self._tags()
        if tags is None:
            self.disponible = False
            self.modelo_disponible = None
            return False
        self.disponible = True
        nombres = {modelo.get("name") for modelo in tags.get("models", []) if isinstance(modelo, dict)}
        self.modelo_disponible = self.modelo in nombres
        if self.modelo_disponible:
            logger.info("[LLM] Modelo %s disponible.", self.modelo)
        else:
            logger.warning(
                "[LLM] Ollama está disponible, pero el modelo %s no está instalado. "
                "Ejecute: ollama pull %s",
                self.modelo,
                self.modelo,
            )
        return self.modelo_disponible

    def preparar(self) -> None:
        # Prepara Ollama sin impedir que FastAPI atienda el resto del sistema.
        logger.info("[LLM] Comprobando disponibilidad de Ollama...")
        if self.esta_disponible():
            logger.info("[LLM] Ollama ya está ejecutándose.")
        else:
            logger.info("[LLM] Ollama no está ejecutándose.")
            if not self.iniciar() or not self.esperar_disponibilidad():
                logger.warning("[LLM] Ollama no está disponible; el tutor teórico permanecerá desactivado.")
                return
            logger.info("[LLM] Ollama disponible.")
        self.comprobar_modelo()

    def cerrar(self) -> None:
        # Solo finaliza el proceso hijo que esta instancia creó.
        if not self.iniciado_por_aplicacion or self.proceso is None:
            return
        if self.proceso.poll() is None:
            self.proceso.terminate()
            try:
                self.proceso.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proceso.kill()
        self.proceso = None
        self.iniciado_por_aplicacion = False


ollama_manager = OllamaManager()
