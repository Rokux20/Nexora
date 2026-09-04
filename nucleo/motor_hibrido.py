# Motor híbrido: orquestador del ciclo de adaptación (RF-06 a RF-09).
#
# Implementa la secuencia fija de cuatro pasos, no reordenable:
# recolección, estimación, decisión, registro y retorno. Es el ÚNICO punto
# del sistema que conoce a los cuatro modelos del núcleo a la vez — ellos
# nunca se comunican entre sí directamente; toda la información pasa por
# aquí.
import dataclasses
from pathlib import Path

from config import INTENTOS_MAXIMOS_POR_ITEM, RUTA_MODELO
from nucleo import modelo_dominio, modelo_estudiante, modelo_pedagogico
from nucleo.esquemas import Decision, EstadoAprendiz
from persistencia import repositorio

ACCIONES_QUE_ENTREGAN_PISTA = {"apoyo_por_tiempo", "pista_progresiva"}
NUM_CONCEPTOS = 12


def ejecutar_ciclo(
    conexion,
    aprendiz_id: str,
    sesion_id: int,
    item_id: str,
    respuesta: str,
    tiempo_respuesta_ms: int,
    ruta_modelo: Path = RUTA_MODELO,
) -> Decision:
    # Implementa RF-06..RF-09: ejecuta el ciclo completo de adaptación
    # para una respuesta y devuelve la decisión pedagógica resultante.
    item = modelo_dominio.obtener_item(item_id)
    concepto_id = item["concepto_id"]

    # --- 1. Recolección ---
    numero_intento = repositorio.contar_intentos_item_en_sesion(conexion, sesion_id, item_id) + 1
    pistas_usadas = repositorio.contar_pistas_item_en_sesion(conexion, sesion_id, item_id)
    fallos_previos = repositorio.contar_fallos_concepto_en_sesion(conexion, sesion_id, concepto_id)
    estado = repositorio.obtener_estado_aprendiz(conexion, aprendiz_id, concepto_id)

    resultado_evaluacion = modelo_dominio.evaluar_respuesta(item, respuesta, fallos_previos)

    intento = {
        "es_correcto": resultado_evaluacion.es_correcto,
        "numero_intento": numero_intento,
        "tiempo_respuesta_ms": tiempo_respuesta_ms,
        "categoria_error": resultado_evaluacion.categoria_error,
    }

    # --- 2. Estimación ---
    p_dominio, modo_estimacion = modelo_estudiante.estimar_dominio(estado, intento, item, ruta_modelo)

    # --- 3. Decisión ---
    intentos_restantes = max(0, INTENTOS_MAXIMOS_POR_ITEM - numero_intento)
    tiempo_relativo = min(5.0, max(0.0, (tiempo_respuesta_ms / 1000) / item["tiempo_referencia_seg"]))

    variables = {
        "es_correcto": resultado_evaluacion.es_correcto,
        "p_dominio": p_dominio,
        "numero_intento": numero_intento,
        "intentos_restantes": intentos_restantes,
        "pistas_usadas": pistas_usadas,
        "categoria_error": resultado_evaluacion.categoria_error,
        "tiempo_relativo": tiempo_relativo,
        "racha_aciertos": estado.racha_aciertos,
        "racha_errores": estado.racha_errores,
        "nivel_dificultad_actual": estado.nivel_dificultad_actual,
        "modo_estimacion": modo_estimacion,
    }
    traza = modelo_pedagogico.decidir_accion(variables)

    # --- 4. Registro y retorno ---
    intento_id = repositorio.guardar_intento(
        conexion, sesion_id, item_id, concepto_id, respuesta,
        resultado_evaluacion.es_correcto, numero_intento, tiempo_respuesta_ms,
        resultado_evaluacion.categoria_error,
    )
    repositorio.guardar_estimacion_dominio(conexion, intento_id, p_dominio, modo_estimacion)
    repositorio.guardar_traza_adaptacion(
        conexion, intento_id, traza.regla_id, traza.accion, traza.factores, traza.explicacion_aprendiz
    )

    nuevo_estado = _aplicar_efecto(estado, resultado_evaluacion.es_correcto, p_dominio, traza.accion)
    repositorio.guardar_estado_aprendiz(conexion, nuevo_estado)

    if traza.accion == "avanzar_concepto" and concepto_id < NUM_CONCEPTOS:
        _iniciar_siguiente_concepto(conexion, aprendiz_id, concepto_id + 1)

    pista = None
    if traza.accion in ACCIONES_QUE_ENTREGAN_PISTA:
        pista = _entregar_pista(conexion, item, intento_id, pistas_usadas)

    siguiente_item_id = _seleccionar_siguiente_item(conexion, sesion_id, item, traza.accion, nuevo_estado)

    return Decision(
        intento_id=intento_id,
        es_correcto=resultado_evaluacion.es_correcto,
        categoria_error=resultado_evaluacion.categoria_error,
        p_dominio=p_dominio,
        p_dominio_previo=estado.p_dominio_previo,
        modo_estimacion=modo_estimacion,
        traza=traza,
        siguiente_item_id=siguiente_item_id,
        pista=pista,
        concepto_completado=(traza.accion == "avanzar_concepto"),
    )


def _aplicar_efecto(estado: EstadoAprendiz, es_correcto: bool, p_dominio: float, accion: str) -> EstadoAprendiz:
    # Implementa los efectos de cada acción sobre `estado_aprendiz`.
    cambios = {"p_dominio_previo": p_dominio, "total_intentos": estado.total_intentos + 1}
    if es_correcto:
        cambios["total_aciertos"] = estado.total_aciertos + 1
        cambios["racha_aciertos"] = estado.racha_aciertos + 1
        cambios["racha_errores"] = 0
    else:
        cambios["racha_errores"] = estado.racha_errores + 1
        cambios["racha_aciertos"] = 0

    nivel = estado.nivel_dificultad_actual
    estado_texto = estado.estado
    bloqueado = estado.bloqueado_avance

    if accion == "avanzar_concepto":
        estado_texto = "dominado"
        bloqueado = False
    elif accion == "subir_dificultad":
        nivel = min(3, nivel + 1)
        estado_texto = "en_curso"
    elif accion == "reforzar_bloqueando_avance":
        nivel = max(1, nivel - 1)
        bloqueado = True
        estado_texto = "en_curso"
    else:
        # consolidar_mismo_nivel, continuar_mismo_nivel, apoyo_por_tiempo,
        # pista_progresiva, reforzar_mismo_nivel: nivel sin cambios.
        if estado_texto == "pendiente":
            estado_texto = "en_curso"

    pistas_acumuladas = estado.pistas_acumuladas + 1 if accion in ACCIONES_QUE_ENTREGAN_PISTA else estado.pistas_acumuladas

    cambios.update(
        nivel_dificultad_actual=nivel,
        estado=estado_texto,
        bloqueado_avance=bloqueado,
        pistas_acumuladas=pistas_acumuladas,
    )
    return dataclasses.replace(estado, **cambios)


def _iniciar_siguiente_concepto(conexion, aprendiz_id: str, siguiente_concepto_id: int) -> None:
    estado_siguiente = repositorio.obtener_estado_aprendiz(conexion, aprendiz_id, siguiente_concepto_id)
    if estado_siguiente.estado == "pendiente":
        estado_siguiente = dataclasses.replace(estado_siguiente, estado="en_curso", nivel_dificultad_actual=1)
        repositorio.guardar_estado_aprendiz(conexion, estado_siguiente)


def _entregar_pista(conexion, item: dict, intento_id: int, pistas_usadas: int) -> dict:
    nivel_pista = min(3, pistas_usadas + 1)
    pistas_ordenadas = sorted(item["pistas"], key=lambda p: p["nivel"])
    pista = next((p for p in pistas_ordenadas if p["nivel"] == nivel_pista), pistas_ordenadas[-1])
    orden = pistas_usadas + 1
    repositorio.guardar_pista(conexion, intento_id, pista["nivel"], orden, pista["texto"])
    return {"nivel": pista["nivel"], "texto": pista["texto"]}


def _elegir_item(
    conexion,
    sesion_id: int,
    concepto_id: int,
    nivel: int,
    tipo_a_evitar: str | None = None,
    categoria_prioritaria: str | None = None,
    permitir_reutilizacion: bool = True,
) -> dict | None:
    # Implementa RF-13: prioriza ítems no vistos en la sesión; si
    # se agotan, reutiliza los más antiguos (priorizando los que necesitan
    # refuerzo); alterna tipos cuando hay alternativa disponible. Para
    # `consolidar_mismo_nivel`, prioriza — entre los candidatos — un ítem de
    # opción múltiple que incluya un distractor de la categoría de error más
    # frecuente: es la única forma de "dirigir" la selección a una
    # categoría, dado que los otros tres tipos de ítem no llevan una
    # categoría de error objetivo en su esquema.
    #
    # `permitir_reutilizacion=False` restringe la búsqueda a ítems que
    # todavía no se han visto en la sesión: devuelve `None` en vez de
    # reutilizar uno ya respondido, para que el llamador pueda intentar
    # ampliar la búsqueda antes de aceptar una repetición.
    candidatos = modelo_dominio.items_de_concepto_y_nivel(concepto_id, nivel)
    return _elegir_de_candidatos(
        conexion, sesion_id, candidatos, tipo_a_evitar, categoria_prioritaria, permitir_reutilizacion
    )


def _elegir_de_candidatos(
    conexion,
    sesion_id: int,
    candidatos: list,
    tipo_a_evitar: str | None = None,
    categoria_prioritaria: str | None = None,
    permitir_reutilizacion: bool = True,
) -> dict | None:
    if not candidatos:
        return None

    # Un ítem que ya agotó sus intentos máximos no puede volver a
    # servirse: hacerlo violaría la restricción de `numero_intento` en 1..3.
    agotados = repositorio.items_agotados_en_sesion(conexion, sesion_id, INTENTOS_MAXIMOS_POR_ITEM)
    disponibles = [it for it in candidatos if it["id"] not in agotados]
    if not disponibles:
        return None

    vistos = repositorio.items_vistos_en_sesion(conexion, sesion_id)
    no_vistos = [it for it in disponibles if it["id"] not in vistos]

    if no_vistos:
        pool = no_vistos
    elif not permitir_reutilizacion:
        return None
    else:
        # Sin ítems nuevos disponibles: se reutiliza, priorizando los que
        # todavía necesitan refuerzo (último intento incorrecto) sobre los
        # ya dominados; entre iguales, el visto hace más tiempo primero.
        ultima_vez = repositorio.ultima_vez_visto_en_sesion(conexion, sesion_id)
        ultimo_resultado = repositorio.ultimo_resultado_por_item_en_sesion(conexion, sesion_id)
        pool = sorted(
            disponibles,
            key=lambda it: (ultimo_resultado.get(it["id"], False), ultima_vez.get(it["id"], "")),
        )

    if categoria_prioritaria:
        dirigidos = [
            it for it in pool
            if it["tipo"] == "opcion_multiple"
            and any(o["categoria_error"] == categoria_prioritaria for o in it["opciones"])
        ]
        if dirigidos:
            pool = dirigidos

    if tipo_a_evitar:
        alternativos = [it for it in pool if it["tipo"] != tipo_a_evitar]
        if alternativos:
            pool = alternativos

    return pool[0]


def _elegir_item_en_concepto(
    conexion,
    sesion_id: int,
    concepto_id: int,
    nivel_preferido: int,
    tipo_a_evitar: str | None = None,
    categoria_prioritaria: str | None = None,
) -> dict | None:
    # Como `_elegir_item`, pero además de ampliar la búsqueda a otros
    # niveles del mismo concepto cuando el nivel preferido se agotó por
    # completo (todos sus ítems llegaron a 3 intentos), evita reutilizar un
    # ítem ya respondido mientras exista alguno sin ver en cualquier otro
    # nivel del concepto: primero intenta un ítem nuevo en el nivel
    # preferido (mantiene la dificultad vigente mientras hay información
    # nueva que ofrecer ahí); si no hay, busca en todo el concepto — lo que,
    # a través de `_elegir_de_candidatos`, primero agota los ítems sin ver
    # de cualquier nivel y solo si ninguno existe permite repetir uno ya
    # visto, priorizando entre esos el que todavía necesita refuerzo. La
    # prioridad de refuerzo debe poder cruzar niveles (un ítem que necesita
    # reforzarse no deja de necesitarlo por estar en otro nivel), así que
    # esta segunda búsqueda no se restringe al nivel preferido.
    item = _elegir_item(
        conexion, sesion_id, concepto_id, nivel_preferido, tipo_a_evitar, categoria_prioritaria,
        permitir_reutilizacion=False,
    )
    if item is not None:
        return item

    candidatos_concepto = modelo_dominio.items_de_concepto(concepto_id)
    return _elegir_de_candidatos(conexion, sesion_id, candidatos_concepto, tipo_a_evitar, categoria_prioritaria)


def _seleccionar_siguiente_item(
    conexion, sesion_id: int, item_actual: dict, accion: str, nuevo_estado: EstadoAprendiz
) -> str | None:
    if accion in ACCIONES_QUE_ENTREGAN_PISTA:
        return item_actual["id"]  # se mantiene el mismo ítem

    if accion == "avanzar_concepto":
        siguiente_concepto = item_actual["concepto_id"] + 1
        if siguiente_concepto > NUM_CONCEPTOS:
            return None  # no hay más conceptos: la interfaz redirige a CU-07
        item = _elegir_item_en_concepto(conexion, sesion_id, siguiente_concepto, 1)
        return item["id"] if item else None

    concepto_id = item_actual["concepto_id"]
    categoria_prioritaria = None
    if accion == "consolidar_mismo_nivel":
        categoria_prioritaria = repositorio.categoria_error_mas_frecuente_concepto_sesion(
            conexion, sesion_id, concepto_id
        )

    item = _elegir_item_en_concepto(
        conexion, sesion_id, concepto_id, nuevo_estado.nivel_dificultad_actual,
        tipo_a_evitar=item_actual["tipo"], categoria_prioritaria=categoria_prioritaria,
    )
    return item["id"] if item else None


def concepto_actual(conexion, aprendiz_id: str) -> int:
    # Primer concepto no dominado en la trayectoria fija; si los
    # 12 están dominados, devuelve 12 (el llamador debe redirigir a CU-07).
    estados = {e.concepto_id: e for e in repositorio.estados_de_aprendiz(conexion, aprendiz_id)}
    for concepto_id in range(1, NUM_CONCEPTOS + 1):
        estado = estados.get(concepto_id)
        if estado is None or estado.estado != "dominado":
            return concepto_id
    return NUM_CONCEPTOS


def trayectoria_completada(conexion, aprendiz_id: str) -> bool:
    estados = {e.concepto_id: e for e in repositorio.estados_de_aprendiz(conexion, aprendiz_id)}
    return len(estados) == NUM_CONCEPTOS and all(e.estado == "dominado" for e in estados.values())


def seleccionar_item_inicial(conexion, sesion_id: int, aprendiz_id: str) -> str | None:
    # Determina qué ítem mostrar en `GET /practica` cuando la interfaz no
    # trae ya un ítem en curso: el concepto actual del aprendiz, en su nivel
    # de dificultad vigente (o 1 si el concepto aún no tiene estado).
    if trayectoria_completada(conexion, aprendiz_id):
        return None
    concepto_id = concepto_actual(conexion, aprendiz_id)
    estado = repositorio.obtener_estado_aprendiz(conexion, aprendiz_id, concepto_id)
    item = _elegir_item_en_concepto(conexion, sesion_id, concepto_id, estado.nivel_dificultad_actual)
    return item["id"] if item else None
