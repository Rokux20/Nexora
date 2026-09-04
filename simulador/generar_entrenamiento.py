
import numpy as np
import pandas as pd

from config import RUTA_ENTRENAMIENTO_CSV, RUTA_VALIDACION_CSV, SEMILLA
from ml.caracteristicas import construir_vector
from nucleo.modelo_dominio import items_de_concepto_y_nivel
from simulador.aprendiz_virtual import (
    AprendizVirtual,
    actualizar_dominio_tras_interaccion,
    dominio_efectivo,
    muestrear_categoria_error,
    probabilidad_acierto,
    simular_tiempo_respuesta_ms,
)

NUM_APRENDICES = 500
NUM_CONCEPTOS = 12
INTERACCIONES_POR_CONCEPTO = 20
RACHA_PARA_SUBIR_NIVEL = 3
RACHA_PARA_BAJAR_NIVEL = 3
TIPOS_EN_CICLO = ["opcion_multiple", "prediccion_salida", "completar_codigo", "parsons"]

COLUMNAS_FINALES = None  # se calcula en generar(), a partir de construir_vector


def _simular_aprendiz(aprendiz: AprendizVirtual, rng: np.random.Generator) -> list[dict]:
    filas = []
    for concepto_id in range(1, NUM_CONCEPTOS + 1):
        estado = {
            "p_dominio_previo": 0.25,
            "racha_aciertos": 0,
            "racha_errores": 0,
            "total_intentos": 0,
            "total_aciertos": 0,
        }
        nivel = 1

        for i in range(INTERACCIONES_POR_CONCEPTO):
            items_nivel = items_de_concepto_y_nivel(concepto_id, nivel)
            tipo_preferido = TIPOS_EN_CICLO[i % len(TIPOS_EN_CICLO)]
            candidatos = [it for it in items_nivel if it["tipo"] == tipo_preferido] or items_nivel
            item = candidatos[int(rng.integers(0, len(candidatos)))]

            p_acierto = probabilidad_acierto(aprendiz, concepto_id, nivel)
            es_correcto = bool(rng.uniform() < p_acierto)
            efectivo = dominio_efectivo(aprendiz.dominio_latente[concepto_id], nivel)
            tiempo_ms = simular_tiempo_respuesta_ms(
                aprendiz, concepto_id, nivel, item["tiempo_referencia_seg"], rng
            )
            categoria_error = None if es_correcto else muestrear_categoria_error(efectivo, rng)

            intento = {
                "es_correcto": es_correcto,
                "numero_intento": 1,
                "tiempo_respuesta_ms": tiempo_ms,
                "categoria_error": categoria_error,
            }


            fila = construir_vector(estado, intento, item).iloc[0].to_dict()
            fila["aprendiz_id"] = aprendiz.id

            estado["total_intentos"] += 1
            if es_correcto:
                estado["total_aciertos"] += 1
                estado["racha_aciertos"] += 1
                estado["racha_errores"] = 0
            else:
                estado["racha_errores"] += 1
                estado["racha_aciertos"] = 0

            if estado["racha_aciertos"] >= RACHA_PARA_SUBIR_NIVEL:
                nivel = min(3, nivel + 1)
                estado["racha_aciertos"] = 0
            elif estado["racha_errores"] >= RACHA_PARA_BAJAR_NIVEL:
                nivel = max(1, nivel - 1)
                estado["racha_errores"] = 0

            actualizar_dominio_tras_interaccion(aprendiz, concepto_id, es_correcto)
            estado["p_dominio_previo"] = aprendiz.dominio_latente[concepto_id]


            fila["dominio_latente_real"] = aprendiz.dominio_latente[concepto_id]
            fila["etiqueta"] = int(aprendiz.dominio_latente[concepto_id] >= 0.5)
            filas.append(fila)

    return filas


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


def generar() -> dict:
    # Genera `entrenamiento.csv` y `validacion.csv` con
    # aprendices disjuntos entre ambos conjuntos.
    rng = np.random.default_rng(SEMILLA)
    aprendices = [
        AprendizVirtual.generar(f"sim-{i:04d}", NUM_CONCEPTOS, rng) for i in range(NUM_APRENDICES)
    ]

    aprendices_train, aprendices_val = _dividir_aprendices_estratificado(aprendices, rng)

    item_referencia = items_de_concepto_y_nivel(1, 1)[0]
    columnas_finales = list(
        construir_vector(
            {"p_dominio_previo": 0.5, "racha_aciertos": 0, "racha_errores": 0, "total_intentos": 0, "total_aciertos": 0},
            {"es_correcto": True, "numero_intento": 1, "tiempo_respuesta_ms": 1000, "categoria_error": None},
            item_referencia,
        ).columns
    ) + ["dominio_latente_real", "etiqueta", "aprendiz_id"]

    filas_train = [fila for aprendiz in aprendices_train for fila in _simular_aprendiz(aprendiz, rng)]
    filas_val = [fila for aprendiz in aprendices_val for fila in _simular_aprendiz(aprendiz, rng)]

    df_train = pd.DataFrame(filas_train, columns=columnas_finales)
    df_val = pd.DataFrame(filas_val, columns=columnas_finales)

    RUTA_ENTRENAMIENTO_CSV.parent.mkdir(parents=True, exist_ok=True)
    df_train.to_csv(RUTA_ENTRENAMIENTO_CSV, index=False)
    df_val.to_csv(RUTA_VALIDACION_CSV, index=False)

    return {
        "aprendices_entrenamiento": len(aprendices_train),
        "aprendices_validacion": len(aprendices_val),
        "filas_entrenamiento": len(df_train),
        "filas_validacion": len(df_val),
        "balance_etiqueta_entrenamiento": float(df_train["etiqueta"].mean()),
        "balance_etiqueta_validacion": float(df_val["etiqueta"].mean()),
    }


if __name__ == "__main__":
    resumen = generar()
    print("Datos sintéticos generados:")
    for clave, valor in resumen.items():
        print(f"  {clave}: {valor}")
