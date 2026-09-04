# Endpoints JSON: para pruebas y trazabilidad. Documentados
# automáticamente por FastAPI en `/docs`.
import json

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app import llm_service
from app.dependencias import obtener_aprendiz_id, obtener_conexion_bd
from config import COOKIE_NOMBRE, RUTA_COEFICIENTES, RUTA_MODELO
from ml.entrenar import entrenar as entrenar_modelo_ml
from nucleo import modelo_dominio
from persistencia import repositorio

router = APIRouter(prefix="/api")


class SolicitudExplicacion(BaseModel):
    """El navegador identifica un concepto; el resto lo obtiene el backend."""

    concepto_id: int = Field(ge=1, le=12)


@router.get("/salud")
def salud():
    return {"estado": "ok", "modelo_entrenado": RUTA_MODELO.exists()}


@router.get("/estado")
def estado(request: Request, conexion=Depends(obtener_conexion_bd)):
    aprendiz_id = request.cookies.get(COOKIE_NOMBRE)
    if not aprendiz_id:
        raise HTTPException(status_code=404, detail="No hay un aprendiz identificado en esta sesión.")
    estados = repositorio.estados_de_aprendiz(conexion, aprendiz_id)
    return {"aprendiz_id": aprendiz_id, "estados": [vars(e) for e in estados]}


@router.post("/explicacion")
def generar_explicacion_teorica(
    solicitud: SolicitudExplicacion,
    request: Request,
    conexion=Depends(obtener_conexion_bd),
):
    """Genera teoría bajo demanda sin aceptar dominio, nivel ni prompts del cliente."""
    aprendiz_id = obtener_aprendiz_id(request, conexion)
    concepto = next(
        (c for c in repositorio.listar_conceptos(conexion) if c["id"] == solicitud.concepto_id),
        None,
    )
    if concepto is None:
        raise HTTPException(status_code=404, detail="El concepto solicitado no existe.")

    estado_actual = repositorio.obtener_estado_aprendiz(conexion, aprendiz_id, solicitud.concepto_id)
    items = modelo_dominio.items_de_concepto(solicitud.concepto_id)
    contexto_base = items[0].get("enunciado", "") if items else ""
    contexto = llm_service.ContextoExplicacion(
        concepto=concepto["nombre"],
        dominio_estimado=estado_actual.p_dominio_previo,
        estado_concepto=estado_actual.estado,
        nivel_dificultad=estado_actual.nivel_dificultad_actual,
        contexto_base=contexto_base,
    )
    try:
        explicacion = llm_service.generar_explicacion(contexto)
    except llm_service.OllamaServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "concepto": contexto.concepto,
        "dominio": contexto.dominio_estimado,
        "nivel": contexto.nivel_dificultad,
        "estado": contexto.estado_concepto,
        "explicacion": explicacion,
    }


@router.get("/traza/{intento_id}")
def traza(intento_id: int, conexion=Depends(obtener_conexion_bd)):
    intento = repositorio.obtener_intento(conexion, intento_id)
    if intento is None:
        raise HTTPException(status_code=404, detail="Intento no encontrado.")
    traza_fila = repositorio.obtener_traza_de_intento(conexion, intento_id)
    estimacion = repositorio.obtener_estimacion_de_intento(conexion, intento_id)
    return {
        "intento": dict(intento),
        "traza": {**dict(traza_fila), "factores": json.loads(traza_fila["factores_json"])},
        "estimacion": dict(estimacion),
    }


@router.get("/progreso")
def progreso(request: Request, conexion=Depends(obtener_conexion_bd)):
    aprendiz_id = request.cookies.get(COOKIE_NOMBRE)
    if not aprendiz_id:
        raise HTTPException(status_code=404, detail="No hay un aprendiz identificado en esta sesión.")
    estados = repositorio.estados_de_aprendiz(conexion, aprendiz_id)
    return {"aprendiz_id": aprendiz_id, "estados": [vars(e) for e in estados]}


@router.get("/modelo/coeficientes")
def coeficientes():
    if not RUTA_COEFICIENTES.exists():
        raise HTTPException(status_code=404, detail="El modelo aún no se ha entrenado.")
    df = pd.read_csv(RUTA_COEFICIENTES)
    return {"coeficientes": df.to_dict("records")}


@router.post("/entrenamiento")
def entrenar_modelo():
    """Dispara desde la interfaz el mismo entrenamiento de `python -m ml.entrenar`:
    no reimplementa la regresión logística, solo invoca la función existente."""
    try:
        resultado = entrenar_modelo_ml()
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"No fue posible completar el entrenamiento: {exc}"
        ) from exc
    return {"estado": "completado", "metricas": resultado["metricas"]}
