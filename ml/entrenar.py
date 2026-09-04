
import json
import random

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
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.model_selection import GroupKFold, learning_curve

from config import (
    RUTA_COEFICIENTES,
    RUTA_ENTRENAMIENTO_CSV,
    RUTA_METRICAS,
    RUTA_MODELO,
    RUTA_VALIDACION_CSV,
    SEMILLA,
)
from ml.caracteristicas import COLUMNAS, COLUMNAS_CATEGORICAS, COLUMNAS_NUMERICAS

COLUMNA_ETIQUETA = "etiqueta"


def _fijar_semillas() -> None:
    random.seed(SEMILLA)
    np.random.seed(SEMILLA)



# Regularización deliberadamente fuerte (ver DECISIONES.md #8): dominio_latente
# evoluciona en pasos pequeños y monótonos, así que `p_dominio_previo` queda
# casi perfectamente correlacionado con la etiqueta (≈0.95). Sin regularizar
# con fuerza, la regresión logística explota ese casi-determinismo y produce
# un coeficiente enorme para esa única variable — probabilidades degeneradas
# (≈0 o ≈1) fuera del rango estrecho que vio en entrenamiento, en vez de una
# actualización de creencia suave. C=0.0001 se eligió empíricamente: produce
# una trayectoria de p_dominio suave y monótona ante rachas de aciertos o
# errores, mantiene los signos de todos los coeficientes coherentes con la
# intuición pedagógica, y conserva un AUC de validación alto (~0.98).
C_REGULARIZACION = 0.0001


def _construir_pipeline() -> Pipeline:
    preprocesador = ColumnTransformer(
        [
            ("numericas", StandardScaler(), COLUMNAS_NUMERICAS),
            ("categoricas", OneHotEncoder(handle_unknown="ignore"), COLUMNAS_CATEGORICAS),
        ]
    )
    modelo = LogisticRegression(
        random_state=SEMILLA, solver="lbfgs", max_iter=2000, C=C_REGULARIZACION
    )
    return Pipeline([("preprocesador", preprocesador), ("modelo", modelo)])


def _cargar_particion(ruta):
    df = pd.read_csv(ruta)
    return df[COLUMNAS], df[COLUMNA_ETIQUETA]


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


def _guardar_curva_aprendizaje(X_train, y_train, grupos_train, ruta) -> None:
    # Evalúa el mismo pipeline sobre CV interna, sin usar validacion.csv.
    #
    # Los pliegues se separan por aprendiz virtual para evitar que distintas
    # interacciones de una misma trayectoria aparezcan a ambos lados del fold.
    cv = GroupKFold(n_splits=3)
    tamanos, puntajes_train, puntajes_val = learning_curve(
        _construir_pipeline(), X_train, y_train, groups=grupos_train, cv=cv,
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


def entrenar() -> dict:
    # Implementa RNF-08 y RNF-09: entrena el estimador, lo persiste junto
    # con sus artefactos de interpretabilidad y devuelve un resumen.
    _fijar_semillas()

    X_train, y_train = _cargar_particion(RUTA_ENTRENAMIENTO_CSV)
    X_val, y_val = _cargar_particion(RUTA_VALIDACION_CSV)
    grupos_train = pd.read_csv(RUTA_ENTRENAMIENTO_CSV, usecols=["aprendiz_id"])["aprendiz_id"]

    pipeline = _construir_pipeline()
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_val)
    y_proba = pipeline.predict_proba(X_val)[:, 1]

    metricas = {
        "accuracy": float(accuracy_score(y_val, y_pred)),
        "precision": float(precision_score(y_val, y_pred, zero_division=0)),
        "recall": float(recall_score(y_val, y_pred, zero_division=0)),
        "f1": float(f1_score(y_val, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_val, y_proba)),
        "matriz_confusion": confusion_matrix(y_val, y_pred).tolist(),
        "tamano_train": int(len(X_train)),
        "tamano_test": int(len(X_val)),
    }

    RUTA_MODELO.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, RUTA_MODELO)
    RUTA_METRICAS.write_text(json.dumps(metricas, ensure_ascii=False, indent=2), encoding="utf-8")

    coeficientes = _extraer_coeficientes(pipeline)
    coeficientes.to_csv(RUTA_COEFICIENTES, index=False)

    distribucion_train = _distribucion_clases(y_train)
    distribucion_val = _distribucion_clases(y_val)
    metricas.update({
        "tamano_validacion": int(len(X_val)),
        "distribucion_clases": {"entrenamiento": distribucion_train, "validacion": distribucion_val},
        "intercepto": float(pipeline.named_steps["modelo"].intercept_[0]),
        "coeficientes": coeficientes.to_dict("records"),
    })
    RUTA_METRICAS.write_text(json.dumps(metricas, ensure_ascii=False, indent=2), encoding="utf-8")

    ruta_artefactos = RUTA_MODELO.parent
    _guardar_distribucion_clases(distribucion_train, distribucion_val, ruta_artefactos / "distribucion_clases.png")
    _guardar_grafica_coeficientes(coeficientes, ruta_artefactos / "coeficientes_modelo.png")
    _guardar_curva_aprendizaje(X_train, y_train, grupos_train, ruta_artefactos / "curva_aprendizaje.png")

    return {"metricas": metricas, "coeficientes": coeficientes}


if __name__ == "__main__":
    resultado = entrenar()
    print("Entrenamiento completo. Métricas sobre datos/sintetico/validacion.csv:")
    print(json.dumps(resultado["metricas"], indent=2, ensure_ascii=False))
    _imprimir_tabla_coeficientes(resultado["coeficientes"])
    print(f"\nModelo guardado en: {RUTA_MODELO}")
    print(f"Coeficientes guardados en: {RUTA_COEFICIENTES}")
    print(f"Métricas guardadas en: {RUTA_METRICAS}")
