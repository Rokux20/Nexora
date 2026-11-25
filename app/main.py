# Aplicación FastAPI: montaje de estáticos y routers.
# Ejecutar con:  uvicorn app.main:app --reload --port 8000
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import rutas_api, rutas_web
from app.ollama_manager import ollama_manager
from config import RAIZ, RUTA_BD
from persistencia import repositorio
from persistencia.inicializar import crear_esquema

def _actualizar_esquema() -> None:
    # El esquema solo usa `CREATE ... IF NOT EXISTS`: aplicarlo al arrancar
    # añade las tablas nuevas (p. ej. `explicacion_llm`) a una base existente
    # sin tocar sus datos.
    conexion = repositorio.obtener_conexion(RUTA_BD)
    try:
        crear_esquema(conexion)
        conexion.commit()
    finally:
        conexion.close()


@asynccontextmanager
async def ciclo_vida(app: FastAPI):
    _actualizar_esquema()
    ollama_manager.preparar()
    try:
        yield
    finally:
        ollama_manager.cerrar()


app = FastAPI(
    title="Nexora · Prototipo de plataforma de aprendizaje adaptativo",
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


# Peticiones automáticas del navegador y de herramientas externas que antes
# respondían 404 en el registro del servidor.
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(RAIZ / "estatico" / "img" / "favicon.ico", media_type="image/x-icon")


@app.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
def chrome_devtools():
    # Chrome DevTools sondea esta ruta para vincular carpetas locales; el
    # prototipo no lo usa, así que responde sin contenido.
    return Response(status_code=204)


@app.get("/health", include_in_schema=False)
def health():
    return rutas_api.salud()
