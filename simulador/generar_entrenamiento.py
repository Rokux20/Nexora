
import numpy as np
import pandas as pd

from config import INTENTOS_MAXIMOS_POR_ITEM, RUTA_ENTRENAMIENTO_CSV, RUTA_VALIDACION_CSV, SEMILLA
from ml.caracteristicas import COLUMNAS, aplicar_coherencia, construir_fila
from nucleo.modelo_dominio import items_de_concepto_y_nivel
from simulador.aprendiz_virtual import (
    AprendizVirtual,
    actualizar_dominio_tras_interaccion,
    dominio_efectivo,
    muestrear_categoria_error,
    simular_respuesta,
)

NUM_APRENDICES = 500
NUM_CONCEPTOS = 12
INTERACCIONES_POR_CONCEPTO = 20
RACHA_PARA_SUBIR_NIVEL = 3
RACHA_PARA_BAJAR_NIVEL = 3
TIPOS_EN_CICLO = ["opcion_multiple", "prediccion_salida", "completar_codigo", "parsons"]
P_DOMINIO_INICIAL = 0.25
# Rondas de reestimación de `p_dominio_previo` (ver `_reestimar_p_dominio_previo`).
RONDAS_REESTIMACION = 4


def _simular_aprendiz(aprendiz: AprendizVirtual, rng: np.random.Generator) -> list[dict]:
    filas = []
    for concepto_id in range(1, NUM_CONCEPTOS + 1):
        estado = {
            "p_dominio_previo": P_DOMINIO_INICIAL,
            "racha_aciertos": 0,
            "racha_errores": 0,
            "total_intentos": 0,
            "total_aciertos": 0,
        }
        nivel = 1
        racha_nivel_aciertos = 0
        racha_nivel_errores = 0
        indice_item = 0
        interacciones = 0

        while interacciones < INTERACCIONES_POR_CONCEPTO:
            items_nivel = items_de_concepto_y_nivel(concepto_id, nivel)
            tipo_preferido = TIPOS_EN_CICLO[indice_item % len(TIPOS_EN_CICLO)]
            candidatos = [it for it in items_nivel if it["tipo"] == tipo_preferido] or items_nivel
            item = candidatos[int(rng.integers(0, len(candidatos)))]
            indice_item += 1

            # Hasta 3 intentos sobre el mismo ítem (Tabla 11): cada intento
            # es una interacción y una fila del conjunto de datos.
            for numero_intento in range(1, INTENTOS_MAXIMOS_POR_ITEM + 1):
                # Cada reintento llega después de una pista (R5/R6).
                es_correcto, tiempo_ms = simular_respuesta(
                    aprendiz, concepto_id, nivel, item["tiempo_referencia_seg"], rng,
                    pistas_recibidas=numero_intento - 1,
                )
                efectivo = dominio_efectivo(aprendiz.dominio_latente[concepto_id], nivel)
                categoria_error = None if es_correcto else muestrear_categoria_error(efectivo, rng)

                intento = {
                    "es_correcto": es_correcto,
                    "numero_intento": numero_intento,
                    "tiempo_respuesta_ms": tiempo_ms,
                    "categoria_error": categoria_error,
                }
                fila = construir_fila(estado, intento, item)
                fila["aprendiz_id"] = aprendiz.id

                estado["total_intentos"] += 1
                if es_correcto:
                    estado["total_aciertos"] += 1
                    estado["racha_aciertos"] += 1
                    estado["racha_errores"] = 0
                else:
                    estado["racha_errores"] += 1
                    estado["racha_aciertos"] = 0

                actualizar_dominio_tras_interaccion(aprendiz, concepto_id, es_correcto)
                # Valor provisional: se sustituye por la estimación del
                # propio modelo en `_reestimar_p_dominio_previo`.
                estado["p_dominio_previo"] = aprendiz.dominio_latente[concepto_id]

                fila["dominio_latente_real"] = aprendiz.dominio_latente[concepto_id]
                fila["etiqueta"] = int(aprendiz.dominio_latente[concepto_id] >= 0.5)
                filas.append(fila)
                interacciones += 1

                termino_item = es_correcto or numero_intento == INTENTOS_MAXIMOS_POR_ITEM
                if termino_item or interacciones >= INTERACCIONES_POR_CONCEPTO:
                    break

            # Progresión de dificultad por rachas de ítems resueltos (no por
            # intentos), separada de las rachas que alimentan al estimador.
            if es_correcto:
                racha_nivel_aciertos += 1
                racha_nivel_errores = 0
            else:
                racha_nivel_errores += 1
                racha_nivel_aciertos = 0
            if racha_nivel_aciertos >= RACHA_PARA_SUBIR_NIVEL:
                nivel = min(3, nivel + 1)
                racha_nivel_aciertos = 0
            elif racha_nivel_errores >= RACHA_PARA_BAJAR_NIVEL:
                nivel = max(1, nivel - 1)
                racha_nivel_errores = 0

    return filas


def _reestimar_p_dominio_previo(df: pd.DataFrame, pipeline) -> pd.DataFrame:
    # En ejecución, `p_dominio_previo` es la estimación que el propio modelo
    # produjo en la interacción anterior (sección 8.3.3), no el dominio
    # latente, que no es observable. Entrenar con el latente filtra la
    # etiqueta en una de las entradas: el modelo aprende a copiarla, ignora
    # el resultado de la respuesta y, al realimentarse en ejecución, puede
    # subir el dominio aun con respuestas incorrectas. Aquí se recalcula la
    # columna recorriendo cada trayectoria (aprendiz, concepto) en orden y
    # encadenando las predicciones del modelo (con la misma restricción de
    # coherencia que `modelo_estudiante.estimar_dominio`), igual que el
    # motor híbrido.
    df = df.copy()
    trayectoria = df.groupby(["aprendiz_id", "concepto_id"], sort=False).ngroup().to_numpy()
    paso = df.groupby(["aprendiz_id", "concepto_id"], sort=False).cumcount().to_numpy()
    p_actual = np.full(trayectoria.max() + 1, P_DOMINIO_INICIAL)
    columna = df.columns.get_loc("p_dominio_previo")
    for t in range(paso.max() + 1):
        filas = np.flatnonzero(paso == t)
        df.iloc[filas, columna] = p_actual[trayectoria[filas]]
        p_modelo = pipeline.predict_proba(df.iloc[filas][COLUMNAS])[:, 1]
        es_correcto = df.iloc[filas]["es_correcto"].to_numpy()
        p_actual[trayectoria[filas]] = aplicar_coherencia(p_modelo, p_actual[trayectoria[filas]], es_correcto)
    return df


def ajustar_consistencia(
    df_train: pd.DataFrame, df_val: pd.DataFrame, c_regularizacion: float
):
    # Punto fijo entre datos y modelo: se entrena, se recalcula
    # `p_dominio_previo` con ese modelo y se repite hasta que la columna
    # refleja lo que el estimador verá en ejecución. La validación se
    # recalcula con el modelo ajustado solo sobre entrenamiento, que también
    # se devuelve.
    from ml.entrenar import construir_pipeline

    for _ in range(RONDAS_REESTIMACION):
        pipeline = construir_pipeline(c_regularizacion).fit(df_train[COLUMNAS], df_train["etiqueta"])
        df_train = _reestimar_p_dominio_previo(df_train, pipeline)
    df_val = _reestimar_p_dominio_previo(df_val, pipeline)
    return df_train, df_val, pipeline


def _dividir_aprendices_estratificado(aprendices: list, rng: np.random.Generator):
    propension = {a.id: float(np.mean(list(a.dominio_latente.values()))) for a in aprendices}
    mediana = float(np.median(list(propension.values())))
    franja_baja = [a for a in aprendices if propension[a.id] < mediana]
    franja_alta = [a for a in aprendices if propension[a.id] >= mediana]

    def dividir(grupo):
        indices = rng.permutation(len(grupo))
        corte = int(len(grupo) * 0.8)
        entrenamiento = [grupo[i] for i in indices[:corte]]
        validacion = [grupo[i] for i in indices[corte:]]
        return entrenamiento, validacion

    train_baja, val_baja = dividir(franja_baja)
    train_alta, val_alta = dividir(franja_alta)
    return train_baja + train_alta, val_baja + val_alta


def simular_conjuntos(semilla: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Simula aprendices virtuales nuevos y devuelve los conjuntos de
    # entrenamiento y validación con aprendices disjuntos. `p_dominio_previo`
    # queda provisional hasta pasar por `ajustar_consistencia`.
    rng = np.random.default_rng(semilla)
    aprendices = [
        AprendizVirtual.generar(f"sim-{i:04d}", NUM_CONCEPTOS, rng) for i in range(NUM_APRENDICES)
    ]
    aprendices_train, aprendices_val = _dividir_aprendices_estratificado(aprendices, rng)

    columnas_finales = COLUMNAS + ["dominio_latente_real", "etiqueta", "aprendiz_id"]
    filas_train = [fila for aprendiz in aprendices_train for fila in _simular_aprendiz(aprendiz, rng)]
    filas_val = [fila for aprendiz in aprendices_val for fila in _simular_aprendiz(aprendiz, rng)]
    return pd.DataFrame(filas_train, columns=columnas_finales), pd.DataFrame(filas_val, columns=columnas_finales)


def guardar_conjuntos(df_train: pd.DataFrame, df_val: pd.DataFrame) -> dict:
    RUTA_ENTRENAMIENTO_CSV.parent.mkdir(parents=True, exist_ok=True)
    df_train.to_csv(RUTA_ENTRENAMIENTO_CSV, index=False)
    df_val.to_csv(RUTA_VALIDACION_CSV, index=False)
    return {
        "aprendices_entrenamiento": int(df_train["aprendiz_id"].nunique()),
        "aprendices_validacion": int(df_val["aprendiz_id"].nunique()),
        "filas_entrenamiento": len(df_train),
        "filas_validacion": len(df_val),
        "balance_etiqueta_entrenamiento": float(df_train["etiqueta"].mean()),
        "balance_etiqueta_validacion": float(df_val["etiqueta"].mean()),
    }


def generar(semilla: int = SEMILLA) -> dict:
    # Genera `entrenamiento.csv` y `validacion.csv` de forma independiente
    # del entrenamiento (con el C de referencia). `ml.entrenar` usa las
    # mismas piezas, pero además elige C por validación cruzada.
    from ml.entrenar import C_REFERENCIA

    df_train, df_val = simular_conjuntos(semilla)
    df_train, df_val, _ = ajustar_consistencia(df_train, df_val, C_REFERENCIA)
    return {"semilla": semilla, **guardar_conjuntos(df_train, df_val)}


if __name__ == "__main__":
    resumen = generar()
    print("Datos sintéticos generados:")
    for clave, valor in resumen.items():
        print(f"  {clave}: {valor}")
