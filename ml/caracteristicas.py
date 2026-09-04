import pandas as pd

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
    tiempo_relativo = (intento["tiempo_respuesta_ms"] / 1000) / item["tiempo_referencia_seg"]
    tiempo_relativo = max(0.0, min(5.0, tiempo_relativo))

    total_intentos = estado.get("total_intentos", 0)
    total_aciertos = estado.get("total_aciertos", 0)
    tasa_acierto_concepto = (total_aciertos / total_intentos) if total_intentos > 0 else 0.5

    fila = {
        "es_correcto": int(bool(intento["es_correcto"])),
        "numero_intento": intento["numero_intento"],
        "tiempo_relativo": tiempo_relativo,
        "dificultad": item["dificultad"],
        "p_dominio_previo": estado.get("p_dominio_previo", 0.25),
        "racha_aciertos": estado.get("racha_aciertos", 0),
        "racha_errores": estado.get("racha_errores", 0),
        "tasa_acierto_concepto": tasa_acierto_concepto,
        "categoria_error": intento.get("categoria_error") or "ninguna",
        "concepto_id": item["concepto_id"],
        "tipo_item": item["tipo"],
    }
    return pd.DataFrame([fila], columns=COLUMNAS)
