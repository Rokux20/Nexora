import json
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import explicaciones, graficas
from app.dependencias import fijar_cookie_aprendiz, obtener_aprendiz_id, obtener_conexion_bd
from config import MAX_LONGITUD_RESPUESTA, RAIZ, RUTA_COEFICIENTES, RUTA_METRICAS, RUTA_MODELO
from nucleo import modelo_dominio, modelo_pedagogico, motor_hibrido
from persistencia import repositorio

router = APIRouter()
templates = Jinja2Templates(directory=str(RAIZ / "plantillas"))


def _asegurar_sesion_activa(conexion, aprendiz_id: str) -> int:
    sesion = repositorio.obtener_sesion_activa(conexion, aprendiz_id)
    if sesion is None:
        return repositorio.crear_sesion(conexion, aprendiz_id)
    return sesion["id"]


def _validar_respuesta(conexion, aprendiz_id: str, item: dict, respuesta: str) -> str | None:
    # valida la entrada sin lanzar una excepción sin
    # capturar; el error se devuelve para mostrarse en la propia vista.
    if respuesta is None or not respuesta.strip():
        return "La respuesta no puede estar vacía."
    if len(respuesta) > MAX_LONGITUD_RESPUESTA:
        return f"La respuesta supera el máximo de {MAX_LONGITUD_RESPUESTA} caracteres."
    concepto_alcanzable = motor_hibrido.concepto_actual(conexion, aprendiz_id)
    if item["concepto_id"] > concepto_alcanzable:
        return "Este ítem no corresponde a tu progreso actual en la sesión."
    return None


def _leer_top_coeficientes(n: int = 3) -> list:
    try:
        df = pd.read_csv(RUTA_COEFICIENTES)
    except FileNotFoundError:
        return []
    return df.head(n).to_dict("records")


def _contexto_practica(conexion, sesion_id: int, item: dict | None, error: str | None = None) -> dict:
    if item is None:
        return {"item": None, "trayectoria_completa": True, "error": error}
    pistas_usadas = repositorio.contar_pistas_item_en_sesion(conexion, sesion_id, item["id"])
    ultimo_intento = repositorio.ultimo_intento_de_item_en_sesion(conexion, sesion_id, item["id"])
    pistas_entregadas = repositorio.pistas_de_item_en_sesion(conexion, sesion_id, item["id"])
    return {
        "item": item,
        "trayectoria_completa": False,
        "error": error,
        "pistas_usadas": pistas_usadas,
        "pistas_entregadas": pistas_entregadas,
        "puede_pedir_pista": ultimo_intento is not None and pistas_usadas < 3,
    }


# ================================================================
# CU-01 — Iniciar práctica
# ================================================================


@router.get("/")
def iniciar_practica(request: Request, conexion=Depends(obtener_conexion_bd)):
    aprendiz_id = obtener_aprendiz_id(request, conexion)
    respuesta = templates.TemplateResponse(request, "inicio.html", {})
    fijar_cookie_aprendiz(respuesta, aprendiz_id)
    return respuesta


# ================================================================
# CU-02 — Resolver ítem / CU-06 — Continuar práctica
# ================================================================


@router.get("/practica")
def ver_practica(request: Request, item: str | None = None, conexion=Depends(obtener_conexion_bd)):
    aprendiz_id = obtener_aprendiz_id(request, conexion)
    sesion_id = _asegurar_sesion_activa(conexion, aprendiz_id)

    if item:
        item_actual = modelo_dominio.obtener_item(item)
    else:
        item_id = motor_hibrido.seleccionar_item_inicial(conexion, sesion_id, aprendiz_id)
        item_actual = modelo_dominio.obtener_item(item_id) if item_id else None

    contexto = _contexto_practica(conexion, sesion_id, item_actual)
    respuesta = templates.TemplateResponse(request, "practica.html", contexto)
    fijar_cookie_aprendiz(respuesta, aprendiz_id)
    return respuesta


@router.post("/practica/responder")
def responder(
    request: Request,
    item_id: str = Form(...),
    respuesta: str = Form(""),
    tiempo_respuesta_ms: int = Form(0),
    conexion=Depends(obtener_conexion_bd),
):
    aprendiz_id = obtener_aprendiz_id(request, conexion)
    sesion_id = _asegurar_sesion_activa(conexion, aprendiz_id)
    item = modelo_dominio.obtener_item(item_id)

    error = _validar_respuesta(conexion, aprendiz_id, item, respuesta)
    if error:
        contexto = _contexto_practica(conexion, sesion_id, item, error=error)
        resp = templates.TemplateResponse(request, "practica.html", contexto, status_code=400)
        fijar_cookie_aprendiz(resp, aprendiz_id)
        return resp

    decision = motor_hibrido.ejecutar_ciclo(
        conexion, aprendiz_id, sesion_id, item_id, respuesta, max(0, tiempo_respuesta_ms)
    )

    umbrales = modelo_pedagogico.cargar_reglas()["umbrales"]
    categoria_nombre = None
    if decision.categoria_error:
        categoria_nombre = explicaciones.nombres_categoria_error().get(
            decision.categoria_error, decision.categoria_error
        )

    contexto = {
        "item": item,
        "decision": decision,
        "es_correcto": decision.es_correcto,
        "categoria_error_nombre": categoria_nombre,
        "p_dominio": decision.p_dominio,
        "p_dominio_previo": decision.p_dominio_previo,
        "umbrales": umbrales,
        "regla_id": decision.traza.regla_id,
        "regla_nombre": decision.traza.nombre,
        "accion_legible": decision.traza.explicacion_aprendiz,
        "intento_id": decision.intento_id,
        "modo_degradado": decision.modo_estimacion == "degradado",
        "siguiente_item_id": decision.siguiente_item_id,
        "pista": decision.pista,
        "concepto_completado": decision.concepto_completado,
    }
    resp = templates.TemplateResponse(request, "resultado.html", contexto)
    fijar_cookie_aprendiz(resp, aprendiz_id)
    return resp


# ================================================================
# CU-03 — Solicitar pista
# ================================================================


@router.post("/practica/pista")
def pedir_pista(request: Request, item_id: str = Form(...), conexion=Depends(obtener_conexion_bd)):
    aprendiz_id = obtener_aprendiz_id(request, conexion)
    sesion_id = _asegurar_sesion_activa(conexion, aprendiz_id)
    item = modelo_dominio.obtener_item(item_id)

    ultimo_intento = repositorio.ultimo_intento_de_item_en_sesion(conexion, sesion_id, item_id)
    pistas_usadas = repositorio.contar_pistas_item_en_sesion(conexion, sesion_id, item_id)

    error = None
    if ultimo_intento is None:
        error = "Responde primero este ítem para poder pedir una pista."
    elif pistas_usadas >= 3:
        error = "Ya recibiste las tres pistas disponibles para este ítem."
    else:
        nivel = pistas_usadas + 1
        pistas_ordenadas = sorted(item["pistas"], key=lambda p: p["nivel"])
        pista = next((p for p in pistas_ordenadas if p["nivel"] == nivel), pistas_ordenadas[-1])
        repositorio.guardar_pista(conexion, ultimo_intento["id"], pista["nivel"], nivel, pista["texto"])

    contexto = _contexto_practica(conexion, sesion_id, item, error=error)
    resp = templates.TemplateResponse(request, "practica.html", contexto)
    fijar_cookie_aprendiz(resp, aprendiz_id)
    return resp


# ================================================================
# CU-04 — Consultar explicación
# ================================================================


@router.get("/explicacion/{intento_id}")
def ver_explicacion(request: Request, intento_id: int, conexion=Depends(obtener_conexion_bd)):
    aprendiz_id = obtener_aprendiz_id(request, conexion)
    intento = repositorio.obtener_intento(conexion, intento_id)
    if intento is None:
        resp = templates.TemplateResponse(request, "explicacion.html", {"no_encontrado": True}, status_code=404)
        fijar_cookie_aprendiz(resp, aprendiz_id)
        return resp

    traza = repositorio.obtener_traza_de_intento(conexion, intento_id)
    estimacion = repositorio.obtener_estimacion_de_intento(conexion, intento_id)
    regla = repositorio.obtener_regla(conexion, traza["regla_id"])
    factores = json.loads(traza["factores_json"])
    filas_factores = explicaciones.traducir_factores(factores, traza["regla_id"])

    contexto = {
        "no_encontrado": False,
        "intento": intento,
        "traza": traza,
        "regla": regla,
        "estimacion": estimacion,
        "filas_factores": filas_factores,
        "coeficientes_top3": _leer_top_coeficientes(3),
        "modo_degradado": estimacion["modo"] == "degradado",
    }
    resp = templates.TemplateResponse(request, "explicacion.html", contexto)
    fijar_cookie_aprendiz(resp, aprendiz_id)
    return resp


# ================================================================
# CU-05 — Consultar progreso
# ================================================================


def _series_evolucion_dominio(conexion, aprendiz_id: str, conceptos_por_id: dict) -> dict:
    intentos = repositorio.intentos_de_aprendiz(conexion, aprendiz_id)
    series: dict = {}
    for indice, fila in enumerate(intentos):
        if fila["p_dominio"] is None:
            continue
        nombre = conceptos_por_id.get(fila["concepto_id"], f"Concepto {fila['concepto_id']}")
        series.setdefault(nombre, []).append((indice, fila["p_dominio"]))
    return series


def _conteo_errores_por_concepto_categoria(conexion, aprendiz_id: str, conceptos_por_id: dict) -> dict:
    filas = repositorio.errores_de_aprendiz_por_concepto_categoria(conexion, aprendiz_id)
    datos: dict = {}
    for fila in filas:
        nombre = conceptos_por_id.get(fila["concepto_id"], f"Concepto {fila['concepto_id']}")
        datos.setdefault(nombre, {}).setdefault(fila["categoria_codigo"], 0)
        datos[nombre][fila["categoria_codigo"]] += 1
    return datos


@router.get("/progreso")
def ver_progreso(request: Request, conexion=Depends(obtener_conexion_bd)):
    aprendiz_id = obtener_aprendiz_id(request, conexion)

    conceptos = repositorio.listar_conceptos(conexion)
    conceptos_por_id = {c["id"]: c["nombre"] for c in conceptos}
    estados = {e.concepto_id: e for e in repositorio.estados_de_aprendiz(conexion, aprendiz_id)}
    umbrales = modelo_pedagogico.cargar_reglas()["umbrales"]

    dominados = sum(1 for e in estados.values() if e.estado == "dominado")
    total_intentos = sum(e.total_intentos for e in estados.values())
    total_aciertos = sum(e.total_aciertos for e in estados.values())
    tasa_global = (total_aciertos / total_intentos) if total_intentos else None
    pistas_totales = sum(e.pistas_acumuladas for e in estados.values())

    conteo_acciones = {}
    for fila in repositorio.acciones_de_aprendiz(conexion, aprendiz_id):
        conteo_acciones[fila["accion"]] = conteo_acciones.get(fila["accion"], 0) + 1

    graficas_progreso = [
        graficas.grafica_dominio_por_concepto(conceptos, estados, umbrales),
        graficas.grafica_evolucion_dominio(_series_evolucion_dominio(conexion, aprendiz_id, conceptos_por_id), umbrales),
        graficas.grafica_errores_por_concepto_categoria(
            _conteo_errores_por_concepto_categoria(conexion, aprendiz_id, conceptos_por_id)
        ),
        graficas.grafica_acciones_pedagogicas(conteo_acciones),
        graficas.grafica_rejilla_trayectoria(conceptos, estados),
    ]

    contexto = {
        "conceptos": conceptos,
        "estados": estados,
        "dominados": dominados,
        "total_conceptos": len(conceptos),
        "total_intentos": total_intentos,
        "tasa_global": tasa_global,
        "pistas_totales": pistas_totales,
        "graficas_progreso": graficas_progreso,
    }
    resp = templates.TemplateResponse(request, "progreso.html", contexto)
    fijar_cookie_aprendiz(resp, aprendiz_id)
    return resp


# ================================================================
# CU-07 — Finalizar práctica
# ================================================================


@router.post("/practica/finalizar")
def finalizar_practica(request: Request, conexion=Depends(obtener_conexion_bd)):
    aprendiz_id = obtener_aprendiz_id(request, conexion)
    sesion = repositorio.obtener_sesion_activa(conexion, aprendiz_id)

    if sesion is not None:
        repositorio.finalizar_sesion(conexion, sesion["id"])
        sesion_id = sesion["id"]
    else:
        sesiones = repositorio.sesiones_de_aprendiz(conexion, aprendiz_id)
        sesion_id = sesiones[-1]["id"] if sesiones else None

    destino = f"/resumen/{sesion_id}" if sesion_id else "/practica"
    resp = RedirectResponse(url=destino, status_code=303)
    fijar_cookie_aprendiz(resp, aprendiz_id)
    return resp


@router.get("/resumen/{sesion_id}")
def ver_resumen(request: Request, sesion_id: int, conexion=Depends(obtener_conexion_bd)):
    aprendiz_id = obtener_aprendiz_id(request, conexion)
    sesion = repositorio.obtener_sesion(conexion, sesion_id)
    if sesion is None:
        resp = templates.TemplateResponse(request, "resumen.html", {"no_encontrada": True}, status_code=404)
        fijar_cookie_aprendiz(resp, aprendiz_id)
        return resp

    detalle = repositorio.detalle_intentos_sesion(conexion, sesion_id)
    pistas_usadas = repositorio.contar_pistas_de_sesion(conexion, sesion_id)
    conceptos_por_id = {c["id"]: c["nombre"] for c in repositorio.listar_conceptos(conexion)}

    items_resueltos = len(detalle)
    aciertos = sum(1 for f in detalle if f["es_correcto"])
    tasa_acierto = (aciertos / items_resueltos) if items_resueltos else None
    conceptos_avanzados = sum(1 for f in detalle if f["accion"] == "avanzar_concepto")

    conteo_reglas: dict = {}
    for f in detalle:
        conteo_reglas[f["regla_id"]] = conteo_reglas.get(f["regla_id"], 0) + 1
    regla_mas_activada = max(conteo_reglas, key=conteo_reglas.get) if conteo_reglas else None

    duracion_seg = None
    if sesion["fin"]:
        duracion_seg = (datetime.fromisoformat(sesion["fin"]) - datetime.fromisoformat(sesion["inicio"])).total_seconds()

    puntos_trayectoria = [
        {
            "p_dominio": f["p_dominio"],
            "es_correcto": bool(f["es_correcto"]),
            "concepto_id": f["concepto_id"],
            "regla_id": f["regla_id"],
        }
        for f in detalle
    ]

    aciertos_errores_concepto: dict = {}
    for f in detalle:
        nombre = conceptos_por_id.get(f["concepto_id"], f"Concepto {f['concepto_id']}")
        entrada = aciertos_errores_concepto.setdefault(nombre, {"aciertos": 0, "errores": 0})
        entrada["aciertos" if f["es_correcto"] else "errores"] += 1

    conteo_categorias: dict = {}
    for f in detalle:
        if f["categoria_codigo"]:
            conteo_categorias[f["categoria_codigo"]] = conteo_categorias.get(f["categoria_codigo"], 0) + 1

    tiempos_relativos = []
    for f in detalle:
        item = modelo_dominio.obtener_item(f["item_id"])
        tiempos_relativos.append(min(5.0, max(0.0, (f["tiempo_respuesta_ms"] / 1000) / item["tiempo_referencia_seg"])))

    graficas_resumen = [
        graficas.grafica_trayectoria_sesion(puntos_trayectoria),
        graficas.grafica_aciertos_errores_por_concepto(aciertos_errores_concepto),
        graficas.grafica_distribucion_categorias_error(conteo_categorias),
        graficas.grafica_tiempo_vs_referencia(tiempos_relativos),
    ]

    contexto = {
        "no_encontrada": False,
        "sesion": sesion,
        "items_resueltos": items_resueltos,
        "aciertos": aciertos,
        "tasa_acierto": tasa_acierto,
        "pistas_usadas": pistas_usadas,
        "conceptos_avanzados": conceptos_avanzados,
        "regla_mas_activada": regla_mas_activada,
        "duracion_seg": duracion_seg,
        "graficas_resumen": graficas_resumen,
    }
    resp = templates.TemplateResponse(request, "resumen.html", contexto)
    fijar_cookie_aprendiz(resp, aprendiz_id)
    return resp


# ================================================================
# Pantalla de entrenamiento — dispara `ml.entrenar.entrenar()`
# ================================================================


@router.get("/entrenamiento")
def ver_entrenamiento(request: Request, conexion=Depends(obtener_conexion_bd)):
    aprendiz_id = obtener_aprendiz_id(request, conexion)

    metricas_previas = None
    if RUTA_METRICAS.exists():
        metricas_previas = json.loads(RUTA_METRICAS.read_text(encoding="utf-8"))

    contexto = {
        "modelo_entrenado": RUTA_MODELO.exists(),
        "metricas_previas": metricas_previas,
    }
    resp = templates.TemplateResponse(request, "entrenamiento.html", contexto)
    fijar_cookie_aprendiz(resp, aprendiz_id)
    return resp
