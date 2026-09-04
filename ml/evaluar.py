
import json

import joblib
import matplotlib
import numpy as np
import pandas as pd
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
    brier_score_loss,
)

from config import RUTA_METRICAS, RUTA_MODELO, RUTA_ROC_SVG, RUTA_VALIDACION_CSV
from ml.caracteristicas import COLUMNAS

# Paleta consistente con estatico/css/estilo.css: violeta = componente probabilístico.
_COLOR_LINEA = "#C9CCD1"
_COLOR_CURVA = "#6D28D9"
_COLOR_TEXTO = "#5A6169"
_COLOR_FONDO = "#FBFAF7"


def _cargar_validacion():
    df = pd.read_csv(RUTA_VALIDACION_CSV)
    return df[COLUMNAS], df["etiqueta"], df["dominio_latente_real"]


def _construir_svg_roc(fpr, tpr, auc: float) -> str:
    # Curva ROC como SVG inline, sin esquinas redondeadas ni desenfoques:
    # coherente con el resto de gráficas del prototipo aunque
    # este archivo se genere fuera de la aplicación web.
    ancho, alto = 380, 380
    margen = 46
    lado = ancho - 2 * margen

    def coord(x: float, y: float) -> tuple[float, float]:
        return margen + x * lado, (alto - margen) - y * lado

    puntos = " ".join(f"{px:.1f},{py:.1f}" for px, py in (coord(x, y) for x, y in zip(fpr, tpr)))
    ix, iy = coord(0, 0)
    fx, fy = coord(1, 1)

    return f'''<svg viewBox="0 0 {ancho} {alto}" preserveAspectRatio="xMidYMin meet"
     xmlns="http://www.w3.org/2000/svg" role="img" width="100%">
  <title>Curva ROC del estimador de dominio (AUC = {auc:.3f})</title>
  <rect x="0" y="0" width="{ancho}" height="{alto}" fill="{_COLOR_FONDO}" />
  <line x1="{margen}" y1="{alto - margen}" x2="{ancho - margen}" y2="{alto - margen}"
        stroke="{_COLOR_LINEA}" stroke-width="1" stroke-linecap="butt" />
  <line x1="{margen}" y1="{margen}" x2="{margen}" y2="{alto - margen}"
        stroke="{_COLOR_LINEA}" stroke-width="1" stroke-linecap="butt" />
  <line x1="{ix:.1f}" y1="{iy:.1f}" x2="{fx:.1f}" y2="{fy:.1f}"
        stroke="{_COLOR_LINEA}" stroke-width="1" stroke-dasharray="4 4" stroke-linecap="butt" />
  <polyline points="{puntos}" fill="none" stroke="{_COLOR_CURVA}" stroke-width="2"
            stroke-linecap="butt" stroke-linejoin="miter" />
  <text x="{margen}" y="{alto - margen + 22}" font-family="monospace" font-size="11" fill="{_COLOR_TEXTO}">tasa de falsos positivos</text>
  <text x="{margen - 34}" y="{margen - 12}" font-family="monospace" font-size="11" fill="{_COLOR_TEXTO}">tasa de verdaderos positivos</text>
  <text x="{ancho - margen}" y="{margen + 14}" font-family="monospace" font-size="12" fill="{_COLOR_CURVA}" text-anchor="end">AUC = {auc:.3f}</text>
</svg>'''


def _guardar_curva_calibracion(y, y_proba, brier: float, ruta) -> None:
    frecuencia_observada, probabilidad_predicha = calibration_curve(y, y_proba, n_bins=10, strategy="uniform")
    fig, ax = plt.subplots(figsize=(6.5, 5.2))
    ax.plot([0, 1], [0, 1], "--", color="#64748B", label="Calibración perfecta")
    ax.plot(probabilidad_predicha, frecuencia_observada, marker="o", color="#7C3AED", label="Estimador")
    ax.set(xlabel="Probabilidad predicha (p_dominio)", ylabel="Frecuencia observada", xlim=(0, 1), ylim=(0, 1), title=f"Curva de calibración (Brier = {brier:.4f})")
    ax.grid(alpha=0.2)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(ruta, dpi=160)
    plt.close(fig)


def _guardar_comparacion_dominio(y_proba, dominio_real, mae: float, correlacion: float, ruta) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 5.2))
    ax.scatter(y_proba, dominio_real, s=11, alpha=0.24, color="#2563EB", edgecolors="none")
    ax.plot([0, 1], [0, 1], "--", color="#DC2626", label="Referencia y=x")
    ax.set(xlabel="p_dominio estimado", ylabel="dominio_latente_real", xlim=(0, 1), ylim=(0, 1), title="Comparación entre p_dominio y dominio latente real")
    ax.text(0.04, 0.95, f"MAE: {mae:.4f}\nPearson: {correlacion:.4f}", transform=ax.transAxes, va="top", bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.9, "edgecolor": "#CBD5E1"})
    ax.grid(alpha=0.2)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(ruta, dpi=160)
    plt.close(fig)


def _guardar_matriz_confusion(y_true, y_pred, ruta) -> None:
    # Visualiza la matriz calculada a partir de las etiquetas y predicciones reales.
    matriz = confusion_matrix(y_true, y_pred)
    etiquetas = ["No Domina", "Domina"]
    fig, ax = plt.subplots(figsize=(6.4, 5.4))
    imagen = ax.imshow(matriz, interpolation="nearest", cmap="Blues")
    fig.colorbar(imagen, ax=ax, label="Cantidad de registros")
    ax.set(
        xticks=np.arange(len(etiquetas)),
        yticks=np.arange(len(etiquetas)),
        xticklabels=etiquetas,
        yticklabels=etiquetas,
        xlabel="Clase predicha",
        ylabel="Clase real",
        title="Matriz de confusión del modelo de regresión logística",
    )
    ax.xaxis.set_label_position("top")
    ax.xaxis.tick_top()
    umbral_color = matriz.max() / 2
    for fila, columna in np.ndindex(matriz.shape):
        ax.text(
            columna, fila, f"{matriz[fila, columna]:,}", ha="center", va="center",
            color="white" if matriz[fila, columna] > umbral_color else "#102A43", fontsize=13, fontweight="bold",
        )
    ax.set_ylim(len(etiquetas) - 0.5, -0.5)
    fig.tight_layout()
    fig.savefig(ruta, dpi=160)
    plt.close(fig)


def evaluar() -> dict:
    pipeline = joblib.load(RUTA_MODELO)
    X, y, dominio_real = _cargar_validacion()

    y_proba = pipeline.predict_proba(X)[:, 1]
    y_pred = (y_proba >= 0.5).astype(int)

    fpr, tpr, _ = roc_curve(y, y_proba)
    auc = roc_auc_score(y, y_proba)

    error_absoluto = np.abs(y_proba - dominio_real.to_numpy())
    mae = float(error_absoluto.mean())
    correlacion = float(np.corrcoef(y_proba, dominio_real.to_numpy())[0, 1])
    brier = float(brier_score_loss(y, y_proba))

    resultado = {
        "accuracy": float(accuracy_score(y, y_pred)),
        "precision": float(precision_score(y, y_pred, zero_division=0)),
        "recall": float(recall_score(y, y_pred, zero_division=0)),
        "f1": float(f1_score(y, y_pred, zero_division=0)),
        "roc_auc": float(auc),
        "matriz_confusion": confusion_matrix(y, y_pred).tolist(),
        "mae_vs_dominio_latente": mae,
        "correlacion_pearson_vs_dominio_latente": correlacion,
        "brier_score": brier,
    }

    RUTA_ROC_SVG.parent.mkdir(parents=True, exist_ok=True)
    RUTA_ROC_SVG.write_text(_construir_svg_roc(fpr, tpr, auc), encoding="utf-8")
    ruta_artefactos = RUTA_MODELO.parent
    _guardar_curva_calibracion(y, y_proba, brier, ruta_artefactos / "curva_calibracion.png")
    _guardar_comparacion_dominio(y_proba, dominio_real.to_numpy(), mae, correlacion, ruta_artefactos / "p_dominio_vs_dominio_latente.png")
    _guardar_matriz_confusion(y, y_pred, ruta_artefactos / "matriz_confusion.png")

    metricas_existentes = json.loads(RUTA_METRICAS.read_text(encoding="utf-8")) if RUTA_METRICAS.exists() else {}
    metricas_existentes.update(resultado)
    RUTA_METRICAS.write_text(json.dumps(metricas_existentes, ensure_ascii=False, indent=2), encoding="utf-8")

    return resultado


if __name__ == "__main__":
    resultado = evaluar()
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    print(f"\nCurva ROC guardada en: {RUTA_ROC_SVG}")
