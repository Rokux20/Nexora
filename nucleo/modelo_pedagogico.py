# Modelo pedagógico: carga y evaluación del motor de reglas declarativo.
#
# Implementa RF-08: decide la acción pedagógica evaluando `datos/reglas.yaml`
# en orden de prioridad ascendente y devuelve la primera acción cuya
# condición se cumple, junto con la traza de la decisión (regla activada y
# factores evaluados). La gramática de condiciones (combinadores `todas`/
# `alguna`, operadores de comparación) se interpreta de forma explícita con
# un intérprete propio — **no se usa `eval()` ni `exec()`** en ningún punto,
# para que el motor sea auditable y no ejecute contenido arbitrario.
#
# RNF-03: los umbrales y las condiciones viven únicamente en el YAML; este
# módulo no contiene ningún literal de negocio (0.40, 0.80, etc.).
from functools import lru_cache
from pathlib import Path

import yaml

from config import RUTA_REGLAS
from nucleo.esquemas import Traza

_OPERADORES = {
    "es": lambda izq, der: izq == der,
    "igual": lambda izq, der: izq == der,
    "distinto": lambda izq, der: izq != der,
    "mayor": lambda izq, der: izq > der,
    "mayor_igual": lambda izq, der: izq >= der,
    "menor": lambda izq, der: izq < der,
    "menor_igual": lambda izq, der: izq <= der,
    "en": lambda izq, der: izq in der,
}


@lru_cache(maxsize=8)
def cargar_reglas(ruta: Path = RUTA_REGLAS) -> dict:
    # Carga `reglas.yaml` y devuelve `{"umbrales": {...}, "reglas": [...]}`
    # con las reglas ya ordenadas por prioridad ascendente. Cacheado por
    # ruta: pasar una ruta distinta (p. ej. en una prueba) evita cualquier
    # caché cruzada entre archivos.
    datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    reglas_ordenadas = sorted(datos["reglas"], key=lambda r: r["prioridad"])
    return {"umbrales": datos["umbrales"], "reglas": reglas_ordenadas}


def _evaluar_condicion(condicion: dict, variables: dict, umbrales: dict) -> bool:
    # Intérprete explícito de la gramática de condiciones: sin
    # `eval()`/`exec()`, recorre combinadores `todas` (AND) / `alguna` (OR),
    # anidables, hasta llegar a condiciones simples de hoja.
    if "todas" in condicion:
        return all(_evaluar_condicion(c, variables, umbrales) for c in condicion["todas"])
    if "alguna" in condicion:
        return any(_evaluar_condicion(c, variables, umbrales) for c in condicion["alguna"])

    variable = condicion["variable"]
    operador = condicion["operador"]
    valor_izquierdo = variables[variable]
    valor_derecho = condicion["valor"] if "valor" in condicion else umbrales[condicion["umbral"]]
    return _OPERADORES[operador](valor_izquierdo, valor_derecho)


def decidir_accion(variables: dict, ruta_reglas: Path = RUTA_REGLAS) -> Traza:
    # Implementa RF-08: recorre las reglas en orden de prioridad
    # ascendente y devuelve la traza de la primera cuya condición se cumple.
    # R9 (regla por defecto) tiene condición vacuamente verdadera
    # (`todas: []`), así que la función siempre devuelve exactamente una
    # traza — nunca hay decisión vacía.
    config = cargar_reglas(ruta_reglas)
    for regla in config["reglas"]:
        if _evaluar_condicion(regla["condicion"], variables, config["umbrales"]):
            return Traza(
                regla_id=regla["id"],
                nombre=regla["nombre"],
                accion=regla["accion"],
                condicion_textual=regla["condicion_textual"],
                explicacion_aprendiz=regla["explicacion"],
                factores=dict(variables),
            )
    raise RuntimeError(
        "Ninguna regla se activó: revisa que R9 (regla por defecto, condición vacía) "
        "exista en reglas.yaml."
    )


def _recolectar_variables(condicion: dict) -> set:
    if "todas" in condicion:
        variables = set()
        for c in condicion["todas"]:
            variables |= _recolectar_variables(c)
        return variables
    if "alguna" in condicion:
        variables = set()
        for c in condicion["alguna"]:
            variables |= _recolectar_variables(c)
        return variables
    return {condicion["variable"]}


def variables_relevantes_de_regla(regla_id: str, ruta_reglas: Path = RUTA_REGLAS) -> set:
    # Usado por la vista de explicación (CU-04, RF-11): qué variables
    # referencia realmente la condición de una regla, para distinguir en la
    # tabla de factores cuáles pesaron en la decisión de cuáles son solo
    # contexto.
    config = cargar_reglas(ruta_reglas)
    regla = next(r for r in config["reglas"] if r["id"] == regla_id)
    return _recolectar_variables(regla["condicion"])
