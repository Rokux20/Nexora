import yaml

from config import RUTA_CATEGORIAS_ERROR
from nucleo.modelo_pedagogico import cargar_reglas, variables_relevantes_de_regla

_NOMBRES_CATEGORIA = None


def nombres_categoria_error() -> dict:
    global _NOMBRES_CATEGORIA
    if _NOMBRES_CATEGORIA is None:
        datos = yaml.safe_load(RUTA_CATEGORIAS_ERROR.read_text(encoding="utf-8"))
        _NOMBRES_CATEGORIA = {c["codigo"]: c["nombre"] for c in datos["categorias"]}
    return _NOMBRES_CATEGORIA


def _banda_dominio(p_dominio: float, umbrales: dict) -> str:
    if p_dominio >= umbrales["dominio_alto"]:
        return "alto"
    if p_dominio >= umbrales["dominio_bajo"]:
        return "intermedio"
    return "bajo"


def _banda_tiempo(tiempo_relativo: float, umbrales: dict) -> str:
    if tiempo_relativo < umbrales["factor_tiempo_corto"]:
        return "más rápido de lo esperado"
    if tiempo_relativo > umbrales["factor_tiempo_largo"]:
        return "más lento de lo esperado"
    return "dentro de lo esperado"


def _etiquetas_factores(factores: dict, umbrales: dict) -> dict:
    p_dominio = factores["p_dominio"]
    tiempo_relativo = factores["tiempo_relativo"]
    categoria = factores["categoria_error"]
    nombres_categoria = nombres_categoria_error()

    return {
        "es_correcto": ("Tu respuesta", "correcta" if factores["es_correcto"] else "incorrecta"),
        "p_dominio": (
            "Tu dominio estimado de este tema",
            f"{p_dominio:.0%} ({_banda_dominio(p_dominio, umbrales)})",
        ),
        "numero_intento": ("Número de intento en este ítem", f"{factores['numero_intento']} de 3"),
        "intentos_restantes": ("Intentos que te quedaban", str(factores["intentos_restantes"])),
        "pistas_usadas": ("Pistas que ya habías pedido para este ítem", str(factores["pistas_usadas"])),
        "categoria_error": (
            "Tipo de error",
            nombres_categoria.get(categoria, "—") if categoria else "no aplica (respuesta correcta)",
        ),
        "tiempo_relativo": (
            "Tiempo que tardaste en responder",
            f"{tiempo_relativo:.1f}× el tiempo de referencia ({_banda_tiempo(tiempo_relativo, umbrales)})",
        ),
        "racha_aciertos": ("Respuestas correctas seguidas", str(factores["racha_aciertos"])),
        "racha_errores": ("Respuestas incorrectas seguidas", str(factores["racha_errores"])),
        "nivel_dificultad_actual": ("Nivel de dificultad", f"{factores['nivel_dificultad_actual']} de 3"),
        "modo_estimacion": (
            "Modo del estimador",
            "normal" if factores["modo_estimacion"] == "normal" else "degradado (sin modelo entrenado)",
        ),
    }


def traducir_factores(factores: dict, regla_id: str) -> list:
    # Devuelve una lista de filas `{etiqueta, valor, contribuyo}` lista
    # para la tabla de la vista de explicación, en el orden fijo.
    config = cargar_reglas()
    umbrales = config["umbrales"]
    relevantes = variables_relevantes_de_regla(regla_id)
    etiquetas = _etiquetas_factores(factores, umbrales)

    orden = [
        "es_correcto", "p_dominio", "numero_intento", "intentos_restantes",
        "pistas_usadas", "categoria_error", "tiempo_relativo",
        "racha_aciertos", "racha_errores", "nivel_dificultad_actual", "modo_estimacion",
    ]
    filas = []
    for variable in orden:
        etiqueta, valor = etiquetas[variable]
        filas.append({"etiqueta": etiqueta, "valor": valor, "contribuyo": variable in relevantes})
    return filas
