# Aplicación FastAPI: montaje de estáticos y routers.
# Ejecutar con:  uvicorn app.main:app --reload --port 8000
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import rutas_api, rutas_web
from app.ollama_manager import ollama_manager
from config import RAIZ

@asynccontextmanager
async def ciclo_vida(app: FastAPI):
    ollama_manager.preparar()
    try:
        yield
    finally:
        ollama_manager.cerrar()


app = FastAPI(
    title="Prototipo de plataforma de aprendizaje adaptativo",
    description=(
        "Motor de adaptación híbrido (reglas + aprendizaje automático) para la práctica de "
        "programación en Python. Proyecto académico — Universidad de Cundinamarca, Chía."
    ),
    version="1.0.0",
    lifespan=ciclo_vida,
)

app.mount("/estatico", StaticFiles(directory=str(RAIZ / "estatico")), name="estatico")

app.include_router(rutas_web.router)
app.include_router(rutas_api.router)
