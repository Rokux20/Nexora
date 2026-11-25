import numpy as np
import pandas as pd

from config import P_DOMINIO_INICIAL

COLUMNAS = [
    "es_correcto",
    "numero_intento",
    "tiempo_relativo",
    "dificultad",
    "p_dominio_previo",
    "racha_aciertos",
    "racha_errores",
    "tasa_acierto_concepto",
    "categoria_error",
    "concepto_id",
    "tipo_item",
]

COLUMNAS_NUMERICAS = [
    "es_correcto",
    "numero_intento",
    "tiempo_relativo",
    "dificultad",
    "p_dominio_previo",
    "racha_aciertos",
    "racha_errores",
    "tasa_acierto_concepto",
]

COLUMNAS_CATEGORICAS = ["categoria_error", "concepto_id", "tipo_item"]


def construir_vector(estado: dict, intento: dict, item: dict) -> pd.DataFrame:
    return pd.DataFrame([construir_fila(estado, intento, item)], columns=COLUMNAS)


def construir_fila(estado: dict, intento: dict, item: dict) -> dict:
    # Misma construcción que `construir_vector`, como diccionario: el
    # simulador genera cientos de miles de filas y crear un DataFrame por
    # fila lo hacía unas 30 veces más lento.
    tiempo_relativo = (intento["tiempo_respuesta_ms"] / 1000) / item["tiempo_referencia_seg"]
    tiempo_relativo = max(0.0, min(5.0, tiempo_relativo))

    total_intentos = estado.get("total_intentos", 0)
    total_aciertos = estado.get("total_aciertos", 0)
    tasa_acierto_concepto = (total_aciertos / total_intentos) if total_intentos > 0 else 0.5

    return {
        "es_correcto": int(bool(intento["es_correcto"])),
        "numero_intento": intento["numero_intento"],
        "tiempo_relativo": tiempo_relativo,
        "dificultad": item["dificultad"],
        "p_dominio_previo": estado.get("p_dominio_previo", P_DOMINIO_INICIAL),
        "racha_aciertos": estado.get("racha_aciertos", 0),
        "racha_errores": estado.get("racha_errores", 0),
        "tasa_acierto_concepto": tasa_acierto_concepto,
        "categoria_error": intento.get("categoria_error") or "ninguna",
        "concepto_id": item["concepto_id"],
        "tipo_item": item["tipo"],
    }


def aplicar_coherencia(p_dominio, p_dominio_previo, es_correcto):
    # Restricción de coherencia direccional del estimador: una respuesta
    # incorrecta es evidencia en contra del dominio y no puede subir la
    # estimación; una correcta no puede bajarla. La regresión logística por
    # sí sola no lo garantiza, porque en el simulador el dominio latente
    # crece con cada interacción (también tras un error) y el modelo
    # aprende parte de esa tendencia. Funciona con escalares y con arreglos.
    p_dominio = np.asarray(p_dominio, dtype=float)
    p_dominio_previo = np.asarray(p_dominio_previo, dtype=float)
    es_correcto = np.asarray(es_correcto).astype(bool)
    resultado = np.where(es_correcto, np.maximum(p_dominio, p_dominio_previo), np.minimum(p_dominio, p_dominio_previo))
    return float(resultado) if resultado.ndim == 0 else resultado
