# Endpoints JSON: para pruebas y trazabilidad. Documentados
# automáticamente por FastAPI en `/docs`.
import json
import threading

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app import llm_service
from app.dependencias import obtener_aprendiz_id, obtener_conexion_bd
from app.ollama_manager import ollama_manager
from config import COOKIE_NOMBRE, RUTA_COEFICIENTES, RUTA_MODELO
from ml.entrenar import entrenar as entrenar_modelo_ml
from nucleo import modelo_dominio, modelo_pedagogico
from persistencia import repositorio

router = APIRouter(prefix="/api")


class SolicitudExplicacion(BaseModel):
    """El navegador identifica el concepto y el ítem en pantalla; el resto lo obtiene el backend."""

    concepto_id: int = Field(ge=1, le=12)
    item_id: str | None = Field(default=None, max_length=40)


@router.get("/salud")
def salud():
    return {"estado": "ok", "modelo_entrenado": RUTA_MODELO.exists(), "tutor_llm": ollama_manager.estado()}


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
    # El ítem en pantalla da el contexto; solo se acepta si pertenece al
    # concepto pedido, y nunca se envía su solución al modelo.
    item = None
    if solicitud.item_id:
        try:
            item = modelo_dominio.obtener_item(solicitud.item_id)
        except KeyError:
            item = None
        if item is not None and item["concepto_id"] != solicitud.concepto_id:
            item = None
    # Personalización: práctica del aprendiz en el concepto y explicaciones
    # que ya recibió (él y, recientemente, otros aprendices del concepto).
    perfil = repositorio.perfil_practica_concepto(
        conexion, aprendiz_id, solicitud.concepto_id, item["id"] if item else None
    )
    previas = repositorio.explicaciones_llm_recientes(conexion, solicitud.concepto_id, aprendiz_id, propias=True)
    ajenas = repositorio.explicaciones_llm_recientes(conexion, solicitud.concepto_id, aprendiz_id, propias=False)
    contexto = llm_service.ContextoExplicacion(
        concepto=concepto["nombre"],
        dominio_estimado=estado_actual.p_dominio_previo,
        estado_concepto=estado_actual.estado,
        nivel_dificultad=estado_actual.nivel_dificultad_actual,
        enunciado_item=item["enunciado"] if item else "",
        codigo_item=(item.get("codigo") or "") if item else "",
        tipo_item=item["tipo"] if item else "",
        foco_item=llm_service.foco_de_item(item),
        errores_frecuentes=tuple(perfil["errores_frecuentes"]),
        racha_aciertos=estado_actual.racha_aciertos,
        racha_errores=estado_actual.racha_errores,
        total_intentos=estado_actual.total_intentos,
        total_aciertos=estado_actual.total_aciertos,
        fallos_item_actual=perfil["fallos_item_actual"],
        explicaciones_previas=tuple(fila["texto"] for fila in previas),
    )
    umbrales = modelo_pedagogico.cargar_reglas()["umbrales"]
    banda = llm_service.banda_dominio(contexto.dominio_estimado, umbrales["dominio_bajo"], umbrales["dominio_alto"])
    enfoque = llm_service.elegir_enfoque(banda, contexto.errores_frecuentes, [fila["enfoque"] for fila in previas])
    tema = llm_service.elegir_tema([fila["tema"] for fila in previas], [fila["tema"] for fila in ajenas[:3]])
    try:
        resultado = llm_service.generar_explicacion_personalizada(
            contexto, banda, item, enfoque, tuple(fila["texto"] for fila in ajenas), tema
        )
    except llm_service.OllamaServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    explicacion = resultado.texto
    repositorio.guardar_explicacion_llm(
        conexion, aprendiz_id, solicitud.concepto_id, item["id"] if item else None,
        contexto.dominio_estimado, banda, resultado.enfoque, resultado.tema, explicacion,
    )

    return {
        "concepto": contexto.concepto,
        "dominio": contexto.dominio_estimado,
        "nivel": contexto.nivel_dificultad,
        "estado": contexto.estado_concepto,
        "item_id": item["id"] if item else None,
        "banda_dominio": banda,
        "enfoque": resultado.enfoque,
        "tema": resultado.tema,
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


# Dos entrenamientos simultáneos escribirían los mismos CSV y el mismo modelo.
_entrenamiento_en_curso = threading.Lock()


@router.post("/entrenamiento")
def entrenar_modelo():
    """Dispara desde la interfaz el mismo entrenamiento de `python -m ml.entrenar`:
    simula datos nuevos, elige la regularización por validación cruzada y
    reentrena. El motor usa el modelo nuevo desde la siguiente respuesta."""
    if not _entrenamiento_en_curso.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Ya hay un entrenamiento en curso.")
    try:
        resultado = entrenar_modelo_ml()
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"No fue posible completar el entrenamiento: {exc}"
        ) from exc
    finally:
        _entrenamiento_en_curso.release()
    metricas = {k: v for k, v in resultado["metricas"].items() if k != "coeficientes"}
    return {"estado": "completado", "metricas": metricas}
