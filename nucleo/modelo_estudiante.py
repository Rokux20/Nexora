# Modelo del estudiante: estimación de dominio con degradación
# controlada (RNF-08, RNF-12).
#
# El estimador es el `Pipeline` de scikit-learn entrenado por
# `ml/entrenar.py` y persistido en `ml/artefactos/estimador_dominio.joblib`.
# Si el artefacto no existe, no carga, o `predict_proba` lanza una
# excepción, el sistema entra en modo degradado: usa `p_dominio_previo` si
# existe, o 0.5 en su defecto. El motor de reglas sigue operando con
# normalidad en cualquiera de los dos modos — el aprendiz no percibe
# interrupción.
from functools import lru_cache
from pathlib import Path

import joblib

from config import RUTA_MODELO
from ml.caracteristicas import construir_vector


@lru_cache(maxsize=4)
def _cargar_pipeline(ruta_modelo: Path):
    try:
        return joblib.load(ruta_modelo)
    except Exception:  # noqa: BLE001 - RNF-12 exige degradar ante CUALQUIER fallo de carga
        return None


def estimar_dominio(estado, intento: dict, item: dict, ruta_modelo: Path = RUTA_MODELO) -> tuple[float, str]:
    # Implementa RNF-12: intenta estimar `p_dominio` con el pipeline
    # entrenado; si algo falla en cualquier punto, degrada con seguridad.
    pipeline = _cargar_pipeline(ruta_modelo)
    if pipeline is not None:
        try:
            estado_dict = {
                "p_dominio_previo": estado.p_dominio_previo,
                "racha_aciertos": estado.racha_aciertos,
                "racha_errores": estado.racha_errores,
                "total_intentos": estado.total_intentos,
                "total_aciertos": estado.total_aciertos,
            }
            vector = construir_vector(estado_dict, intento, item)
            p_dominio = float(pipeline.predict_proba(vector)[0, 1])
            return p_dominio, "normal"
        except Exception:  # noqa: BLE001 - idem: cualquier fallo de inferencia degrada, no propaga
            pass
    p_dominio_previo = estado.p_dominio_previo
    p_dominio = p_dominio_previo if p_dominio_previo is not None else 0.5
    return p_dominio, "degradado"
