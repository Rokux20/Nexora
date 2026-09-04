# Modelo de dominio: banco de ítems, evaluación de respuestas y
# clasificación de errores.
#
# Implementa RF-02 (presentar ítem), RF-04 (evaluar acierto/error de forma
# determinista y binaria) y RF-05 (clasificar el error en una de las cinco
# categorías). Nunca ejecuta código escrito por el aprendiz con `exec`/`eval`;
# la validación de sintaxis usa exclusivamente `ast.parse`, que no ejecuta
# nada.
import ast
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from config import RUTA_BANCO_ITEMS

TIPOS_VALIDOS = {"opcion_multiple", "prediccion_salida", "completar_codigo", "parsons"}


@dataclass(frozen=True)
class ResultadoEvaluacion:
    # Resultado de evaluar una respuesta (RF-04, RF-05).

    es_correcto: bool
    categoria_error: str | None


# ================================================================
# Carga del banco de ítems
# ================================================================


@lru_cache(maxsize=1)
def _cargar_banco() -> dict:
    datos = json.loads(RUTA_BANCO_ITEMS.read_text(encoding="utf-8"))
    return {item["id"]: item for item in datos["items"]}


def obtener_item(item_id: str) -> dict:
    # Implementa RF-02: recupera un ítem del banco por su identificador.
    banco = _cargar_banco()
    if item_id not in banco:
        raise KeyError(f"Ítem no encontrado en el banco: {item_id}")
    return banco[item_id]


def items_de_concepto(concepto_id: int) -> list[dict]:
    return [it for it in _cargar_banco().values() if it["concepto_id"] == concepto_id]


def items_de_concepto_y_nivel(concepto_id: int, nivel: int) -> list[dict]:
    return [it for it in items_de_concepto(concepto_id) if it["dificultad"] == nivel]


# ================================================================
# Normalización de respuestas
# ================================================================


def _normalizar_espacios(texto: str) -> str:
    return " ".join(texto.split())


def _normalizar_comillas(texto: str) -> str:
    return texto.replace("'", '"')


def _normalizar_expresion(texto: str) -> str:
    # Normalización para `completar_codigo`: sin espacios extra, sin
    # comillas alternadas (RF-04).
    return _normalizar_comillas(_normalizar_espacios(texto))


def _normalizar_salida(texto: str) -> str:
    # Normalización para `prediccion_salida`: strip() por línea y colapso
    # de espacios finales.
    lineas = [linea.rstrip() for linea in texto.split("\n")]
    return "\n".join(lineas).strip()


def _es_python_valido(fragmento: str) -> bool:
    try:
        ast.parse(fragmento)
        return True
    except SyntaxError:
        return False


def _reconstruir_parsons(fragmentos: list[dict], orden: list[int]) -> str:
    lineas = ["    " * fragmentos[i]["indentacion"] + fragmentos[i]["texto"] for i in orden]
    return "\n".join(lineas)


def _decodificar_orden_parsons(respuesta_cruda: str) -> list[int] | None:
    # La respuesta de un ítem parsons viaja como una lista JSON de índices
    # de fragmentos, p. ej. "[1, 2, 0]".
    try:
        orden = json.loads(respuesta_cruda)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(orden, list) or not all(isinstance(x, int) for x in orden):
        return None
    return orden


def _distancia_edicion(a: str, b: str) -> int:
    # Distancia de Levenshtein clásica, usada solo para el paso 1 de la
    # cascada de clasificación de error (umbral: distancia == 1).
    if a == b:
        return 0
    filas, columnas = len(a) + 1, len(b) + 1
    dp = [[0] * columnas for _ in range(filas)]
    for i in range(filas):
        dp[i][0] = i
    for j in range(columnas):
        dp[0][j] = j
    for i in range(1, filas):
        for j in range(1, columnas):
            costo = 0 if a[i - 1] == b[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + costo)
    return dp[-1][-1]


def _es_descuido(respuesta_norm: str, referencias_norm: list[str]) -> bool:
    for referencia in referencias_norm:
        if respuesta_norm.lower() == referencia.lower():
            return True
        if _distancia_edicion(respuesta_norm, referencia) == 1:
            return True
    return False


# ================================================================
# Corrección por tipo de ítem (RF-04)
# ================================================================


def _es_correcta_opcion_multiple(item: dict, respuesta_cruda: str) -> bool:
    return respuesta_cruda == item["solucion"]


def _categoria_de_opcion(item: dict, clave_seleccionada: str) -> str | None:
    opciones_por_clave = {o["clave"]: o["categoria_error"] for o in item["opciones"]}
    return opciones_por_clave[clave_seleccionada]


def _es_correcta_prediccion_salida(item: dict, respuesta_cruda: str) -> bool:
    return _normalizar_salida(respuesta_cruda) == _normalizar_salida(item["solucion"])


def _es_correcta_completar_codigo(item: dict, respuesta_cruda: str) -> bool:
    candidata = _normalizar_expresion(respuesta_cruda)
    aceptadas = {_normalizar_expresion(s) for s in item["solucion"]}
    return candidata in aceptadas


def _es_correcta_parsons(item: dict, respuesta_cruda: str) -> bool:
    orden = _decodificar_orden_parsons(respuesta_cruda)
    return orden == item["solucion"]


# ================================================================
# RF-05: cascada de clasificación de error
# ================================================================


def clasificar_error(item: dict, respuesta_cruda: str, fallos_previos_concepto_sesion: int) -> str:
    # Implementa RF-05: clasifica el error de una respuesta ya sabida
    # incorrecta, para los tres tipos de ítem que no traen la categoría
    # embebida en la propia opción elegida (`prediccion_salida`,
    # `completar_codigo` y `parsons`; `opcion_multiple` se resuelve aparte,
    # tomando la categoría directamente del distractor seleccionado —
    # ver `_categoria_de_opcion`).
    #
    # Cascada, en este orden estricto; se detiene en el primer caso que
    # aplica:
    #
    #   1. DESCUIDO — la respuesta difiere de la solución de referencia solo
    #      en mayúsculas/minúsculas o en un único carácter (una sustitución,
    #      inserción o eliminación: distancia de edición == 1). Indica que
    #      el concepto se domina pese al tropiezo puntual. Para
    #      `completar_codigo`, si hay varias soluciones aceptadas, basta con
    #      que la respuesta esté a un carácter de CUALQUIERA de ellas.
    #
    #   2. SINTAXIS — la respuesta, interpretada como código Python (sin
    #      ejecutarla en ningún momento, solo con `ast.parse`), no es
    #      válida. Para `completar_codigo` se reconstruye el fragmento
    #      completo (el `codigo` del ítem con `___` sustituido por la
    #      respuesta) antes de analizarlo, porque una respuesta aislada como
    #      `else` o `==` no es un programa válido por sí sola, pero sí lo es
    #      una vez insertada en su contexto. Para `parsons`, además, si la
    #      respuesta no usa exactamente el mismo conjunto de fragmentos que
    #      el ítem (por índices repetidos, faltantes o fuera de rango) se
    #      clasifica también como `sintaxis`, antes de intentar reconstruir
    #      nada.
    #
    #   3. FLUJO_EJECUCION — exclusivo de `parsons`: una vez descartados los
    #      casos 1 y 2, cualquier `parsons` incorrecto que llegue aquí usa
    #      las líneas correctas (mismo conjunto de fragmentos, ya
    #      verificado en el paso 2) en un orden distinto al esperado — no
    #      anticipó bien el orden o las condiciones de ejecución.
    #
    #   4. CONCEPTUAL — el aprendiz ya había fallado 2 o más ítems de este
    #      mismo concepto en la sesión actual: patrón de error repetido, no
    #      un tropiezo aislado.
    #
    #   5. LOGICA_ALGORITMO — cualquier otro caso; es el valor por defecto
    #      de la cascada.
    tipo = item["tipo"]
    orden: list[int] | None = None

    if tipo == "parsons":
        orden = _decodificar_orden_parsons(respuesta_cruda)
        texto_respuesta = ",".join(str(i) for i in orden) if orden is not None else respuesta_cruda
        referencias_norm = [_normalizar_espacios(",".join(str(i) for i in item["solucion"]))]
    elif tipo == "prediccion_salida":
        texto_respuesta = respuesta_cruda
        referencias_norm = [_normalizar_espacios(item["solucion"])]
    else:  # completar_codigo
        texto_respuesta = respuesta_cruda
        referencias_norm = [_normalizar_espacios(s) for s in item["solucion"]]

    respuesta_norm = _normalizar_espacios(texto_respuesta)

    # Paso 1: descuido
    if _es_descuido(respuesta_norm, referencias_norm):
        return "descuido"

    # Paso 2: sintaxis
    if tipo == "completar_codigo":
        reconstruido = item["codigo"].replace("___", respuesta_cruda, 1)
        valido = _es_python_valido(reconstruido)
    elif tipo == "prediccion_salida":
        valido = _es_python_valido(respuesta_cruda)
    else:  # parsons
        conjunto_esperado = set(range(len(item["fragmentos"])))
        if orden is None or set(orden) != conjunto_esperado or len(orden) != len(conjunto_esperado):
            valido = False
        else:
            valido = _es_python_valido(_reconstruir_parsons(item["fragmentos"], orden))
    if not valido:
        return "sintaxis"

    # Paso 3: flujo_ejecucion (exclusivo de parsons)
    if tipo == "parsons":
        return "flujo_ejecucion"

    # Paso 4: conceptual
    if fallos_previos_concepto_sesion >= 2:
        return "conceptual"

    # Paso 5: por defecto
    return "logica_algoritmo"


# ================================================================
# Punto de entrada público
# ================================================================


def evaluar_respuesta(
    item: dict, respuesta_cruda: str, fallos_previos_concepto_sesion: int = 0
) -> ResultadoEvaluacion:
    # Implementa RF-04 y RF-05: evalúa una respuesta de forma determinista
    # y binaria (nunca parcial) para cualquiera de los cuatro tipos de ítem.
    tipo = item["tipo"]

    if tipo == "opcion_multiple":
        es_correcto = _es_correcta_opcion_multiple(item, respuesta_cruda)
        categoria = None if es_correcto else _categoria_de_opcion(item, respuesta_cruda)
        return ResultadoEvaluacion(es_correcto, categoria)

    if tipo == "prediccion_salida":
        es_correcto = _es_correcta_prediccion_salida(item, respuesta_cruda)
    elif tipo == "completar_codigo":
        es_correcto = _es_correcta_completar_codigo(item, respuesta_cruda)
    elif tipo == "parsons":
        es_correcto = _es_correcta_parsons(item, respuesta_cruda)
    else:
        raise ValueError(f"Tipo de ítem desconocido: {tipo}")

    if es_correcto:
        return ResultadoEvaluacion(True, None)

    categoria = clasificar_error(item, respuesta_cruda, fallos_previos_concepto_sesion)
    return ResultadoEvaluacion(False, categoria)
