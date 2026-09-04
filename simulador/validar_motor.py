
import json

import numpy as np

from config import RUTA_VALIDACION_MOTOR, SEMILLA
from nucleo import modelo_dominio, modelo_pedagogico, motor_hibrido
from persistencia.inicializar import cargar_categorias_error, cargar_conceptos, cargar_reglas, crear_esquema
from persistencia.repositorio import crear_sesion, obtener_conexion, obtener_o_crear_aprendiz
from simulador.aprendiz_virtual import (
    AprendizVirtual,
    actualizar_dominio_tras_interaccion,
    probabilidad_acierto,
    simular_tiempo_respuesta_ms,
)

NUM_APRENDICES = 60
NUM_CONCEPTOS = 12
MAX_INTERACCIONES_POR_APRENDIZ = 60


def _construir_respuesta(item: dict, correcta: bool, rng: np.random.Generator) -> str:
    tipo = item["tipo"]
    if tipo == "opcion_multiple":
        if correcta:
            return item["solucion"]
        otras = [o["clave"] for o in item["opciones"] if o["clave"] != item["solucion"]]
        return otras[int(rng.integers(0, len(otras)))]
    if tipo == "prediccion_salida":
        return item["solucion"] if correcta else "salida_incorrecta_simulada"
    if tipo == "completar_codigo":
        return item["solucion"][0] if correcta else "__expresion_incorrecta_simulada__"
    if tipo == "parsons":
        orden_correcto = item["solucion"]
        if correcta:
            return json.dumps(orden_correcto)
        invertido = list(reversed(orden_correcto))
        if invertido == orden_correcto:
            invertido = orden_correcto[1:] + orden_correcto[:1]
        return json.dumps(invertido)
    raise ValueError(f"Tipo de ítem desconocido: {tipo}")


def _simular_aprendiz(conexion, aprendiz: AprendizVirtual, rng: np.random.Generator) -> list:
    aprendiz_id = obtener_o_crear_aprendiz(conexion, None)
    sesion_id = crear_sesion(conexion, aprendiz_id)
    conexion.commit()

    filas = []
    item_id = motor_hibrido.seleccionar_item_inicial(conexion, sesion_id, aprendiz_id)
    interacciones = 0

    while item_id and interacciones < MAX_INTERACCIONES_POR_APRENDIZ:
        item = modelo_dominio.obtener_item(item_id)
        concepto_id = item["concepto_id"]
        nivel = item["dificultad"]

        p_acierto = probabilidad_acierto(aprendiz, concepto_id, nivel)
        es_correcto_deseado = bool(rng.uniform() < p_acierto)
        respuesta = _construir_respuesta(item, es_correcto_deseado, rng)
        tiempo_ms = simular_tiempo_respuesta_ms(aprendiz, concepto_id, nivel, item["tiempo_referencia_seg"], rng)

        decision = motor_hibrido.ejecutar_ciclo(conexion, aprendiz_id, sesion_id, item_id, respuesta, tiempo_ms)
        conexion.commit()

        filas.append({
            "concepto_id": concepto_id,
            "dominio_latente": aprendiz.dominio_latente[concepto_id],
            "p_dominio": decision.p_dominio,
            "modo_estimacion": decision.modo_estimacion,
            "regla_id": decision.traza.regla_id,
            "accion": decision.traza.accion,
            "es_correcto": decision.es_correcto,
        })

        actualizar_dominio_tras_interaccion(aprendiz, concepto_id, decision.es_correcto)
        item_id = decision.siguiente_item_id
        interacciones += 1

    return filas


def _banda(valor: float, umbrales: dict) -> str:
    if valor >= umbrales["dominio_alto"]:
        return "alto"
    if valor >= umbrales["dominio_bajo"]:
        return "intermedio"
    return "bajo"


def validar() -> dict:
    conexion = obtener_conexion(":memory:")
    crear_esquema(conexion)
    cargar_conceptos(conexion)
    cargar_categorias_error(conexion)
    cargar_reglas(conexion)
    conexion.commit()

    rng = np.random.default_rng(SEMILLA)
    umbrales = modelo_pedagogico.cargar_reglas()["umbrales"]

    filas = []
    for i in range(NUM_APRENDICES):
        aprendiz = AprendizVirtual.generar(f"val-{i:03d}", NUM_CONCEPTOS, rng)
        filas.extend(_simular_aprendiz(conexion, aprendiz, rng))
    conexion.close()

    p_dominio = np.array([f["p_dominio"] for f in filas])
    dominio_latente = np.array([f["dominio_latente"] for f in filas])
    error_absoluto = np.abs(p_dominio - dominio_latente)
    correlacion = float(np.corrcoef(p_dominio, dominio_latente)[0, 1])

    distribucion_por_banda: dict = {}
    for f in filas:
        banda = _banda(f["dominio_latente"], umbrales)
        distribucion_por_banda.setdefault(banda, {})
        distribucion_por_banda[banda][f["regla_id"]] = distribucion_por_banda[banda].get(f["regla_id"], 0) + 1

    elegibles_avance = [f for f in filas if f["es_correcto"] and f["dominio_latente"] >= umbrales["dominio_alto"]]
    avanzaron = [f for f in elegibles_avance if f["accion"] == "avanzar_concepto"]

    elegibles_refuerzo = [f for f in filas if f["regla_id"] in ("R7", "R8") and f["dominio_latente"] < umbrales["dominio_bajo"]]
    bloquearon = [f for f in elegibles_refuerzo if f["accion"] == "reforzar_bloqueando_avance"]

    resultado = {
        "aprendices_simulados": NUM_APRENDICES,
        "interacciones_totales": len(filas),
        "correlacion_pearson_p_dominio_vs_dominio_latente": correlacion,
        "mae_p_dominio_vs_dominio_latente": float(error_absoluto.mean()),
        "distribucion_reglas_por_banda_dominio_latente": distribucion_por_banda,
        "verificacion_avanzar_concepto_en_dominio_alto": {
            "elegibles": len(elegibles_avance),
            "avanzaron": len(avanzaron),
            "proporcion": (len(avanzaron) / len(elegibles_avance)) if elegibles_avance else None,
        },
        "verificacion_reforzar_bloqueo_en_dominio_bajo": {
            "elegibles": len(elegibles_refuerzo),
            "bloquearon": len(bloquearon),
            "proporcion": (len(bloquearon) / len(elegibles_refuerzo)) if elegibles_refuerzo else None,
        },
    }

    RUTA_VALIDACION_MOTOR.parent.mkdir(parents=True, exist_ok=True)
    RUTA_VALIDACION_MOTOR.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultado


if __name__ == "__main__":
    resultado = validar()
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    print(f"\nReporte guardado en: {RUTA_VALIDACION_MOTOR}")
