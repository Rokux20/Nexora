
import argparse
import json
import os
import random
import secrets
from datetime import datetime

import joblib
import matplotlib
import numpy as np
import pandas as pd
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    log_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.model_selection import GroupKFold, cross_validate, learning_curve

from config import (
    RUTA_COEFICIENTES,
    RUTA_ENTRENAMIENTO_CSV,
    RUTA_METRICAS,
    RUTA_MODELO,
    RUTA_VALIDACION_CSV,
    SEMILLA,
)
from ml.caracteristicas import COLUMNAS, COLUMNAS_CATEGORICAS, COLUMNAS_NUMERICAS, aplicar_coherencia

COLUMNA_ETIQUETA = "etiqueta"


def _fijar_semillas() -> None:
    random.seed(SEMILLA)
    np.random.seed(SEMILLA)



# Control del sobreajuste. La fuerza de regularización C no se fija a mano:
# se elige por validación cruzada agrupada por aprendiz (GroupKFold, para que
# las interacciones de un mismo aprendiz nunca queden a ambos lados de un
# pliegue). La validación es en lazo cerrado: en cada pliegue de prueba se
# encadenan las predicciones del modelo a lo largo de cada trayectoria, como
# ocurre en ejecución, porque `p_dominio_previo` es la salida anterior del
# propio estimador. Una validación fila a fila con `p_dominio_previo` fijo
# premia modelos que la copian y que, realimentados, se vuelven insensibles a
# los errores. Se aplica la regla de un error estándar: entre los C cuya
# pérdida logarítmica media está a menos de un error estándar de la mejor,
# se toma el más pequeño (el modelo más regularizado que rinde igual).
C_CANDIDATOS = (1e-5, 1e-4, 1e-3, 1e-2, 1e-1)
# C con el que `simulador.generar_entrenamiento` construye los datos cuando se
# ejecuta por separado.
C_REFERENCIA = 1e-4
PLIEGUES_CV = 3
# Brecha máxima tolerada entre el AUC de entrenamiento y el de validación
# antes de marcar el modelo como sobreajustado.
BRECHA_AUC_SOBREAJUSTE = 0.02


def construir_pipeline(c_regularizacion: float = C_REFERENCIA) -> Pipeline:
    preprocesador = ColumnTransformer(
        [
            ("numericas", StandardScaler(), COLUMNAS_NUMERICAS),
            ("categoricas", OneHotEncoder(handle_unknown="ignore"), COLUMNAS_CATEGORICAS),
        ]
    )
    modelo = LogisticRegression(
        random_state=SEMILLA, solver="lbfgs", max_iter=2000, C=c_regularizacion
    )
    return Pipeline([("preprocesador", preprocesador), ("modelo", modelo)])


def seleccionar_c(df_train: pd.DataFrame) -> tuple[float, list[dict]]:
    # Devuelve el C elegido con la regla de un error estándar y la tabla de
    # validación cruzada (en lazo cerrado) que lo justifica.
    from simulador.generar_entrenamiento import ajustar_consistencia

    pliegues = list(GroupKFold(n_splits=PLIEGUES_CV).split(df_train, groups=df_train["aprendiz_id"]))
    tabla = []
    for c in C_CANDIDATOS:
        perdidas, aucs, aucs_train = [], [], []
        for idx_train, idx_prueba in pliegues:
            parte_train, parte_prueba, pipeline = ajustar_consistencia(
                df_train.iloc[idx_train], df_train.iloc[idx_prueba], c
            )
            p_prueba = _p_dominio(pipeline, parte_prueba[COLUMNAS])
            p_train = _p_dominio(pipeline, parte_train[COLUMNAS])
            perdidas.append(log_loss(parte_prueba[COLUMNA_ETIQUETA], np.clip(p_prueba, 1e-6, 1 - 1e-6)))
            aucs.append(roc_auc_score(parte_prueba[COLUMNA_ETIQUETA], p_prueba))
            aucs_train.append(roc_auc_score(parte_train[COLUMNA_ETIQUETA], p_train))
        tabla.append({
            "c": c,
            "log_loss_cv": float(np.mean(perdidas)),
            "error_estandar": float(np.std(perdidas, ddof=1) / np.sqrt(len(perdidas))),
            "roc_auc_cv": float(np.mean(aucs)),
            "roc_auc_entrenamiento": float(np.mean(aucs_train)),
        })
    mejor = min(tabla, key=lambda f: f["log_loss_cv"])
    limite = mejor["log_loss_cv"] + mejor["error_estandar"]
    elegido = min(f["c"] for f in tabla if f["log_loss_cv"] <= limite)
    return elegido, tabla


def _p_dominio(pipeline: Pipeline, X: pd.DataFrame):
    # `p_dominio` tal como lo produce el sistema en ejecución: la salida del
    # modelo tras la restricción de coherencia.
    return aplicar_coherencia(pipeline.predict_proba(X)[:, 1], X["p_dominio_previo"], X["es_correcto"])


def _preparar_datos(regenerar_datos: bool, semilla: int | None):
    # Con `regenerar_datos`, cada entrenamiento simula aprendices nuevos con
    # una semilla nueva (registrada en las métricas para poder reproducirlo
    # con `--semilla`), de modo que el modelo se actualiza con datos nuevos
    # en vez de reajustarse siempre sobre los mismos CSV.
    from simulador.generar_entrenamiento import ajustar_consistencia, guardar_conjuntos, simular_conjuntos

    if regenerar_datos:
        semilla = semilla if semilla is not None else secrets.randbelow(2**31)
        df_train, df_val = simular_conjuntos(semilla)
    else:
        semilla = None
        df_train = pd.read_csv(RUTA_ENTRENAMIENTO_CSV)
        df_val = pd.read_csv(RUTA_VALIDACION_CSV)

    c, tabla_cv = seleccionar_c(df_train)
    # `p_dominio_previo` depende del propio modelo: se construye con el C
    # elegido para que entrenamiento y ejecución sean coherentes.
    df_train, df_val, _ = ajustar_consistencia(df_train, df_val, c)
    guardar_conjuntos(df_train, df_val)
    return df_train, df_val, c, tabla_cv, semilla


def _extraer_coeficientes(pipeline: Pipeline) -> pd.DataFrame:
    modelo: LogisticRegression = pipeline.named_steps["modelo"]
    nombres = list(pipeline.named_steps["preprocesador"].get_feature_names_out())
    coefs = modelo.coef_[0]
    df = pd.DataFrame({"variable": nombres, "coeficiente": coefs, "odds_ratio": np.exp(coefs)})
    df["magnitud"] = df["coeficiente"].abs()
    df = df.sort_values("magnitud", ascending=False).drop(columns="magnitud").reset_index(drop=True)
    return df


def _imprimir_tabla_coeficientes(df: pd.DataFrame) -> None:
    print("\nCoeficientes del modelo (ordenados por magnitud, lectura en lenguaje natural):")
    for _, fila in df.iterrows():
        direccion = "aumenta" if fila["coeficiente"] > 0 else "reduce"
        print(
            f"  {fila['variable']:<38} coef={fila['coeficiente']:+.3f}  "
            f"odds_ratio={fila['odds_ratio']:.3f}  -> {direccion} la probabilidad estimada de dominio"
        )


def _distribucion_clases(etiquetas: pd.Series) -> dict:
    total = len(etiquetas)
    conteos = etiquetas.value_counts().reindex([0, 1], fill_value=0)
    return {
        str(clase): {
            "cantidad": int(conteos[clase]),
            "porcentaje": float(conteos[clase] / total * 100) if total else 0.0,
        }
        for clase in (0, 1)
    }


def _guardar_distribucion_clases(distribucion_train: dict, distribucion_val: dict, ruta) -> None:
    # Guarda una comparación de las clases reales de ambas particiones.
    fig, ax = plt.subplots(figsize=(7, 4.5))
    posiciones = np.arange(2)
    ancho = 0.36
    for desplazamiento, nombre, distribucion, color in (
        (-ancho / 2, "Entrenamiento", distribucion_train, "#2563EB"),
        (ancho / 2, "Validación", distribucion_val, "#7C3AED"),
    ):
        valores = [distribucion[str(clase)]["cantidad"] for clase in (0, 1)]
        barras = ax.bar(posiciones + desplazamiento, valores, ancho, label=nombre, color=color)
        for barra, clase in zip(barras, (0, 1)):
            porcentaje = distribucion[str(clase)]["porcentaje"]
            ax.annotate(f"{int(barra.get_height()):,}\n({porcentaje:.1f}%)", (barra.get_x() + barra.get_width() / 2, barra.get_height()), ha="center", va="bottom", fontsize=9)
    ax.set_xticks(posiciones, ["Clase 0", "Clase 1"])
    ax.set_ylabel("Cantidad de registros")
    ax.set_title("Distribución de clases en los conjuntos de entrenamiento y validación")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(ruta, dpi=160)
    plt.close(fig)


def _guardar_grafica_coeficientes(coeficientes: pd.DataFrame, ruta) -> None:
    top = coeficientes.head(15).sort_values("coeficiente")
    colores = np.where(top["coeficiente"] >= 0, "#2563EB", "#DC2626")
    fig, ax = plt.subplots(figsize=(9, max(5, len(top) * 0.42)))
    barras = ax.barh(top["variable"], top["coeficiente"], color=colores)
    ax.axvline(0, color="#334155", linewidth=1)
    ax.set_xlabel("Coeficiente de la regresión logística")
    ax.set_title("15 coeficientes de mayor magnitud absoluta")
    for barra, valor in zip(barras, top["coeficiente"]):
        ax.text(valor, barra.get_y() + barra.get_height() / 2, f" {valor:+.3f}", va="center", ha="left" if valor >= 0 else "right", fontsize=8)
    fig.tight_layout()
    fig.savefig(ruta, dpi=160)
    plt.close(fig)


def _guardar_curva_aprendizaje(X_train, y_train, grupos_train, c_regularizacion: float, ruta) -> None:
    # Evalúa el mismo pipeline sobre CV interna, sin usar validacion.csv.
    #
    # Los pliegues se separan por aprendiz virtual para evitar que distintas
    # interacciones de una misma trayectoria aparezcan a ambos lados del fold.
    cv = GroupKFold(n_splits=3)
    tamanos, puntajes_train, puntajes_val = learning_curve(
        construir_pipeline(c_regularizacion), X_train, y_train, groups=grupos_train, cv=cv,
        scoring="roc_auc", train_sizes=np.linspace(0.1, 1.0, 5), n_jobs=1,
    )
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    for puntajes, etiqueta, color in (
        (puntajes_train, "Entrenamiento", "#2563EB"),
        (puntajes_val, "Validación cruzada", "#7C3AED"),
    ):
        media, desviacion = puntajes.mean(axis=1), puntajes.std(axis=1)
        ax.plot(tamanos, media, marker="o", label=etiqueta, color=color)
        ax.fill_between(tamanos, media - desviacion, media + desviacion, alpha=0.16, color=color)
    ax.set_xlabel("Tamaño del conjunto de entrenamiento")
    ax.set_ylabel("ROC-AUC")
    ax.set_title("Curva de aprendizaje del estimador de dominio")
    ax.legend(frameon=False)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(ruta, dpi=160)
    plt.close(fig)


def entrenar(regenerar_datos: bool = True, semilla: int | None = None) -> dict:
    # Implementa RNF-08 y RNF-09: genera datos nuevos (por defecto), elige la
    # regularización por validación cruzada, entrena el estimador, lo
    # persiste junto con sus artefactos de interpretabilidad y devuelve un
    # resumen. El servidor recarga el modelo al detectar el archivo nuevo.
    _fijar_semillas()

    df_train, df_val, c_elegido, tabla_cv, semilla_datos = _preparar_datos(regenerar_datos, semilla)
    X_train, y_train = df_train[COLUMNAS], df_train[COLUMNA_ETIQUETA]
    X_val, y_val = df_val[COLUMNAS], df_val[COLUMNA_ETIQUETA]

    pipeline = construir_pipeline(c_elegido)
    pipeline.fit(X_train, y_train)

    y_proba = _p_dominio(pipeline, X_val)
    y_pred = (y_proba >= 0.5).astype(int)
    auc_train = float(roc_auc_score(y_train, _p_dominio(pipeline, X_train)))
    auc_val = float(roc_auc_score(y_val, y_proba))

    coeficientes = _extraer_coeficientes(pipeline)
    distribucion_train = _distribucion_clases(y_train)
    distribucion_val = _distribucion_clases(y_val)
    metricas = {
        "accuracy": float(accuracy_score(y_val, y_pred)),
        "precision": float(precision_score(y_val, y_pred, zero_division=0)),
        "recall": float(recall_score(y_val, y_pred, zero_division=0)),
        "f1": float(f1_score(y_val, y_pred, zero_division=0)),
        "roc_auc": auc_val,
        "log_loss": float(log_loss(y_val, np.clip(y_proba, 1e-6, 1 - 1e-6))),
        "matriz_confusion": confusion_matrix(y_val, y_pred).tolist(),
        "tamano_train": int(len(X_train)),
        "tamano_test": int(len(X_val)),
        "tamano_validacion": int(len(X_val)),
        "entrenado_en": datetime.now().isoformat(timespec="seconds"),
        "datos_regenerados": regenerar_datos,
        "semilla_datos": semilla_datos,
        "regularizacion": {
            "c_elegido": c_elegido,
            "criterio": f"GroupKFold({PLIEGUES_CV}) por aprendiz en lazo cerrado, log-loss, regla de un error estándar",
            "validacion_cruzada": tabla_cv,
        },
        "sobreajuste": {
            "roc_auc_entrenamiento": auc_train,
            "roc_auc_validacion": auc_val,
            "brecha": auc_train - auc_val,
            "umbral": BRECHA_AUC_SOBREAJUSTE,
            "detectado": (auc_train - auc_val) > BRECHA_AUC_SOBREAJUSTE,
        },
        "distribucion_clases": {"entrenamiento": distribucion_train, "validacion": distribucion_val},
        "intercepto": float(pipeline.named_steps["modelo"].intercept_[0]),
        "coeficientes": coeficientes.to_dict("records"),
    }

    # Escritura atómica: el servidor puede estar leyendo el modelo mientras
    # se reentrena y nunca debe ver un archivo a medio escribir.
    RUTA_MODELO.parent.mkdir(parents=True, exist_ok=True)
    temporal = RUTA_MODELO.with_suffix(".tmp")
    joblib.dump(pipeline, temporal)
    os.replace(temporal, RUTA_MODELO)
    coeficientes.to_csv(RUTA_COEFICIENTES, index=False)
    RUTA_METRICAS.write_text(json.dumps(metricas, ensure_ascii=False, indent=2), encoding="utf-8")

    ruta_artefactos = RUTA_MODELO.parent
    _guardar_distribucion_clases(distribucion_train, distribucion_val, ruta_artefactos / "distribucion_clases.png")
    _guardar_grafica_coeficientes(coeficientes, ruta_artefactos / "coeficientes_modelo.png")
    _guardar_curva_aprendizaje(X_train, y_train, df_train["aprendiz_id"], c_elegido, ruta_artefactos / "curva_aprendizaje.png")

    # Métricas frente al dominio latente, calibración y gráficas de validación
    # (se fusionan en metricas.json).
    from ml.evaluar import evaluar
    metricas.update(evaluar())

    return {"metricas": metricas, "coeficientes": coeficientes}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Entrena el estimador de dominio.")
    parser.add_argument("--semilla", type=int, default=None,
                        help="Semilla de la simulación; por defecto se usa una nueva en cada entrenamiento.")
    parser.add_argument("--sin-regenerar", action="store_true",
                        help="Reutiliza los CSV existentes en lugar de simular datos nuevos.")
    argumentos = parser.parse_args()
    resultado = entrenar(regenerar_datos=not argumentos.sin_regenerar, semilla=argumentos.semilla)
    resumen = {k: v for k, v in resultado["metricas"].items() if k != "coeficientes"}
    print("Entrenamiento completo. Métricas sobre datos/sintetico/validacion.csv:")
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    _imprimir_tabla_coeficientes(resultado["coeficientes"])
    print(f"\nModelo guardado en: {RUTA_MODELO}")
    print(f"Coeficientes guardados en: {RUTA_COEFICIENTES}")
    print(f"Métricas guardadas en: {RUTA_METRICAS}")
