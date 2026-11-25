# Gestión del servidor local de Ollama durante el ciclo de FastAPI.
# No contiene prompts ni lógica pedagógica. Reutiliza un servidor ya activo
# o inicia ``ollama serve`` si el ejecutable local está disponible, y
# descarga el modelo configurado en segundo plano si no está instalado.
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

import httpx

from config import (
    OLLAMA_DESCARGA_AUTOMATICA,
    OLLAMA_ESPERA_INICIO_SEGUNDOS,
    OLLAMA_INTERVALO_COMPROBACION_SEGUNDOS,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_TIMEOUT_GENERACION_SEGUNDOS,
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
        # Estado de la descarga del modelo: inactiva, descargando, completada o error.
        self.descarga_estado = "inactiva"
        self.descarga_progreso: float | None = None
        self.descarga_error: str | None = None
        self._hilo_descarga: threading.Thread | None = None
        # Precarga del modelo en memoria: inactiva, cargando, cargado o error.
        self.precarga_estado = "inactiva"
        self._hilo_precarga: threading.Thread | None = None

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
        # Un modelo configurado sin etiqueta ("qwen3") se lista como "qwen3:latest".
        self.modelo_disponible = self.modelo in nombres or f"{self.modelo}:latest" in nombres
        if self.modelo_disponible:
            logger.info("[LLM] Modelo %s disponible.", self.modelo)
        else:
            logger.warning("[LLM] Ollama está disponible, pero el modelo %s no está instalado.", self.modelo)
        return self.modelo_disponible

    def descargando(self) -> bool:
        return self.descarga_estado == "descargando"

    def descargar_modelo(self) -> bool:
        # Descarga el modelo con la API de Ollama (equivale a ``ollama pull``)
        # e informa el progreso. Ollama reanuda descargas interrumpidas.
        self.descarga_estado = "descargando"
        self.descarga_progreso = None
        self.descarga_error = None
        logger.info("[LLM] Descargando el modelo %s; puede tardar varios minutos...", self.modelo)
        ultimo_registro = -10.0
        try:
            # Sin límite de lectura: entre capas, Ollama puede tardar en enviar la siguiente línea.
            tiempo = httpx.Timeout(OLLAMA_TIMEOUT_SEGUNDOS, read=None)
            cuerpo = {"model": self.modelo, "stream": True}
            with httpx.stream("POST", f"{self.url}/api/pull", json=cuerpo, timeout=tiempo) as respuesta:
                respuesta.raise_for_status()
                for linea in respuesta.iter_lines():
                    if not linea:
                        continue
                    evento = json.loads(linea)
                    if evento.get("error"):
                        raise RuntimeError(evento["error"])
                    total, completado = evento.get("total"), evento.get("completed")
                    if total and completado is not None:
                        self.descarga_progreso = min(100.0, completado * 100 / total)
                        if self.descarga_progreso - ultimo_registro >= 10:
                            ultimo_registro = self.descarga_progreso
                            logger.info("[LLM] Descarga de %s: %.0f %%", self.modelo, self.descarga_progreso)
        except (httpx.HTTPError, ValueError, RuntimeError) as exc:
            self.descarga_estado = "error"
            self.descarga_error = str(exc) or exc.__class__.__name__
            logger.warning("[LLM] No fue posible descargar el modelo %s: %s", self.modelo, self.descarga_error)
            return False

        if not self.comprobar_modelo():
            self.descarga_estado = "error"
            self.descarga_error = "la descarga terminó, pero Ollama no lista el modelo"
            logger.warning("[LLM] No fue posible verificar el modelo %s tras la descarga.", self.modelo)
            return False
        self.descarga_estado = "completada"
        self.descarga_progreso = 100.0
        logger.info("[LLM] Modelo %s descargado e instalado.", self.modelo)
        self.precargar_modelo()
        return True

    def precargar_modelo(self) -> bool:
        # Carga el modelo en memoria con una petición sin prompt, con el mismo
        # `num_ctx` que las explicaciones, para que la primera no pague la
        # carga. `keep_alive` lo mantiene cargado durante la sesión.
        self.precarga_estado = "cargando"
        logger.info("[LLM] Cargando el modelo %s en memoria...", self.modelo)
        inicio = time.monotonic()
        try:
            respuesta = httpx.post(
                f"{self.url}/api/generate",
                json={
                    "model": self.modelo,
                    "keep_alive": OLLAMA_KEEP_ALIVE,
                    "options": {"num_ctx": OLLAMA_NUM_CTX},
                },
                timeout=OLLAMA_TIMEOUT_GENERACION_SEGUNDOS,
            )
            respuesta.raise_for_status()
        except httpx.HTTPError as exc:
            self.precarga_estado = "error"
            logger.warning("[LLM] No fue posible precargar el modelo %s: %s", self.modelo, exc)
            return False
        self.precarga_estado = "cargado"
        logger.info("[LLM] Modelo %s cargado en %.1f s.", self.modelo, time.monotonic() - inicio)
        return True

    def iniciar_precarga(self) -> None:
        if self._hilo_precarga is not None and self._hilo_precarga.is_alive():
            return
        self.precarga_estado = "cargando"
        self._hilo_precarga = threading.Thread(target=self.precargar_modelo, name="precarga-modelo-ollama", daemon=True)
        self._hilo_precarga.start()

    def liberar_modelo(self) -> None:
        # Con `keep_alive` indefinido el modelo seguiría ocupando la VRAM al
        # cerrar la aplicación; se descarga explícitamente.
        if self.precarga_estado != "cargado" and not self.modelo_disponible:
            return
        try:
            httpx.post(
                f"{self.url}/api/generate",
                json={"model": self.modelo, "keep_alive": 0},
                timeout=OLLAMA_TIMEOUT_SEGUNDOS,
            )
            logger.info("[LLM] Modelo %s liberado de memoria.", self.modelo)
        except httpx.HTTPError:
            pass
        self.precarga_estado = "inactiva"

    def iniciar_descarga(self) -> None:
        # Lanza la descarga en un hilo para no retrasar el arranque de FastAPI.
        if self._hilo_descarga is not None and self._hilo_descarga.is_alive():
            return
        # Se marca antes de lanzar el hilo para que quien consulte enseguida ya vea la descarga.
        self.descarga_estado = "descargando"
        self._hilo_descarga = threading.Thread(target=self.descargar_modelo, name="descarga-modelo-ollama", daemon=True)
        self._hilo_descarga.start()

    def estado(self) -> dict:
        return {
            "ollama_disponible": self.disponible,
            "modelo": self.modelo,
            "modelo_disponible": self.modelo_disponible,
            "modelo_en_memoria": self.precarga_estado,
            "descarga": {
                "estado": self.descarga_estado,
                "progreso": None if self.descarga_progreso is None else round(self.descarga_progreso, 1),
                "error": self.descarga_error,
            },
        }

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
        if self.comprobar_modelo():
            # En segundo plano para no retrasar el arranque de FastAPI.
            self.iniciar_precarga()
            return
        if OLLAMA_DESCARGA_AUTOMATICA:
            self.iniciar_descarga()
        else:
            logger.warning("[LLM] Descarga automática desactivada. Ejecute: ollama pull %s", self.modelo)

    def cerrar(self) -> None:
        self.liberar_modelo()
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
