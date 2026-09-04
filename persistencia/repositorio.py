import dataclasses
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config import RUTA_BD
from nucleo.esquemas import EstadoAprendiz


def obtener_conexion(ruta_bd=RUTA_BD) -> sqlite3.Connection:
    # Abre una conexión con claves foráneas activas y filas tipo mapping.
    if str(ruta_bd) != ":memory:":
        Path(ruta_bd).parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(ruta_bd)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


# ================================================================
# Aprendiz (RF-18)
# ================================================================


def obtener_o_crear_aprendiz(conexion: sqlite3.Connection, aprendiz_id: str | None) -> str:
    # Si `aprendiz_id` es `None` o no existe en la base de datos, crea un
    # aprendiz nuevo (UUID4) y lo devuelve; si ya existe, actualiza su
    # `ultima_actividad` y lo devuelve tal cual.
    if aprendiz_id:
        fila = conexion.execute("SELECT id FROM aprendiz WHERE id = ?", (aprendiz_id,)).fetchone()
        if fila:
            conexion.execute(
                "UPDATE aprendiz SET ultima_actividad = ? WHERE id = ?", (_ahora(), aprendiz_id)
            )
            return aprendiz_id
    nuevo_id = str(uuid.uuid4())
    ahora = _ahora()
    conexion.execute(
        "INSERT INTO aprendiz (id, creado_en, ultima_actividad) VALUES (?, ?, ?)",
        (nuevo_id, ahora, ahora),
    )
    return nuevo_id


# ================================================================
# Sesión
# ================================================================


def crear_sesion(conexion: sqlite3.Connection, aprendiz_id: str) -> int:
    cursor = conexion.execute(
        "INSERT INTO sesion (aprendiz_id, inicio, estado) VALUES (?, ?, 'activa')",
        (aprendiz_id, _ahora()),
    )
    return cursor.lastrowid


def obtener_sesion_activa(conexion: sqlite3.Connection, aprendiz_id: str):
    return conexion.execute(
        "SELECT * FROM sesion WHERE aprendiz_id = ? AND estado = 'activa' ORDER BY id DESC LIMIT 1",
        (aprendiz_id,),
    ).fetchone()


def obtener_sesion(conexion: sqlite3.Connection, sesion_id: int):
    return conexion.execute("SELECT * FROM sesion WHERE id = ?", (sesion_id,)).fetchone()


def finalizar_sesion(conexion: sqlite3.Connection, sesion_id: int) -> None:
    conexion.execute(
        "UPDATE sesion SET estado = 'finalizada', fin = ? WHERE id = ?", (_ahora(), sesion_id)
    )


def sesiones_de_aprendiz(conexion: sqlite3.Connection, aprendiz_id: str) -> list[sqlite3.Row]:
    return conexion.execute(
        "SELECT * FROM sesion WHERE aprendiz_id = ? ORDER BY id", (aprendiz_id,)
    ).fetchall()


# ================================================================
# Estado del aprendiz
# ================================================================


def obtener_estado_aprendiz(conexion: sqlite3.Connection, aprendiz_id: str, concepto_id: int) -> EstadoAprendiz:
    fila = conexion.execute(
        "SELECT * FROM estado_aprendiz WHERE aprendiz_id = ? AND concepto_id = ?",
        (aprendiz_id, concepto_id),
    ).fetchone()
    if fila is None:
        return EstadoAprendiz(aprendiz_id=aprendiz_id, concepto_id=concepto_id)
    datos = dict(fila)
    datos.pop("actualizado_en", None)
    datos["bloqueado_avance"] = bool(datos["bloqueado_avance"])
    return EstadoAprendiz(**datos)


def guardar_estado_aprendiz(conexion: sqlite3.Connection, estado: EstadoAprendiz) -> None:
    datos = dataclasses.asdict(estado)
    datos["bloqueado_avance"] = int(datos["bloqueado_avance"])
    datos["actualizado_en"] = _ahora()
    conexion.execute(
        """
        INSERT INTO estado_aprendiz (
            aprendiz_id, concepto_id, p_dominio_previo, racha_aciertos, racha_errores,
            total_intentos, total_aciertos, nivel_dificultad_actual, pistas_acumuladas,
            estado, bloqueado_avance, actualizado_en
        ) VALUES (
            :aprendiz_id, :concepto_id, :p_dominio_previo, :racha_aciertos, :racha_errores,
            :total_intentos, :total_aciertos, :nivel_dificultad_actual, :pistas_acumuladas,
            :estado, :bloqueado_avance, :actualizado_en
        )
        ON CONFLICT (aprendiz_id, concepto_id) DO UPDATE SET
            p_dominio_previo = excluded.p_dominio_previo,
            racha_aciertos = excluded.racha_aciertos,
            racha_errores = excluded.racha_errores,
            total_intentos = excluded.total_intentos,
            total_aciertos = excluded.total_aciertos,
            nivel_dificultad_actual = excluded.nivel_dificultad_actual,
            pistas_acumuladas = excluded.pistas_acumuladas,
            estado = excluded.estado,
            bloqueado_avance = excluded.bloqueado_avance,
            actualizado_en = excluded.actualizado_en
        """,
        datos,
    )


def estados_de_aprendiz(conexion: sqlite3.Connection, aprendiz_id: str) -> list[EstadoAprendiz]:
    filas = conexion.execute(
        "SELECT * FROM estado_aprendiz WHERE aprendiz_id = ?", (aprendiz_id,)
    ).fetchall()
    resultado = []
    for fila in filas:
        datos = dict(fila)
        datos.pop("actualizado_en", None)
        datos["bloqueado_avance"] = bool(datos["bloqueado_avance"])
        resultado.append(EstadoAprendiz(**datos))
    return resultado


# ================================================================
# Intento, pista, estimación, traza
# ================================================================


def contar_intentos_item_en_sesion(conexion: sqlite3.Connection, sesion_id: int, item_id: str) -> int:
    fila = conexion.execute(
        "SELECT COUNT(*) AS n FROM intento WHERE sesion_id = ? AND item_id = ?",
        (sesion_id, item_id),
    ).fetchone()
    return fila["n"]


def contar_pistas_item_en_sesion(conexion: sqlite3.Connection, sesion_id: int, item_id: str) -> int:
    fila = conexion.execute(
        """
        SELECT COUNT(*) AS n FROM pista
        JOIN intento ON pista.intento_id = intento.id
        WHERE intento.sesion_id = ? AND intento.item_id = ?
        """,
        (sesion_id, item_id),
    ).fetchone()
    return fila["n"]


def contar_fallos_concepto_en_sesion(conexion: sqlite3.Connection, sesion_id: int, concepto_id: int) -> int:
    fila = conexion.execute(
        "SELECT COUNT(*) AS n FROM intento WHERE sesion_id = ? AND concepto_id = ? AND es_correcto = 0",
        (sesion_id, concepto_id),
    ).fetchone()
    return fila["n"]


def items_vistos_en_sesion(conexion: sqlite3.Connection, sesion_id: int) -> set:
    filas = conexion.execute(
        "SELECT DISTINCT item_id FROM intento WHERE sesion_id = ?", (sesion_id,)
    ).fetchall()
    return {f["item_id"] for f in filas}


def pistas_de_item_en_sesion(conexion: sqlite3.Connection, sesion_id: int, item_id: str) -> list:
    return conexion.execute(
        """
        SELECT pista.* FROM pista
        JOIN intento ON pista.intento_id = intento.id
        WHERE intento.sesion_id = ? AND intento.item_id = ?
        ORDER BY pista.orden
        """,
        (sesion_id, item_id),
    ).fetchall()


def listar_conceptos(conexion: sqlite3.Connection) -> list:
    return conexion.execute("SELECT * FROM concepto ORDER BY orden").fetchall()


def obtener_regla(conexion: sqlite3.Connection, regla_id: str):
    return conexion.execute("SELECT * FROM regla WHERE id = ?", (regla_id,)).fetchone()


def items_agotados_en_sesion(conexion: sqlite3.Connection, sesion_id: int, intentos_maximos: int) -> set:
    # Ítems que ya alcanzaron el máximo de intentos permitidos en esta
    # sesión (`intentos_maximos`) y por lo tanto no deben volver a
    # servirse — evita violar el CHECK(numero_intento BETWEEN 1 AND 3).
    filas = conexion.execute(
        "SELECT item_id FROM intento WHERE sesion_id = ? GROUP BY item_id HAVING COUNT(*) >= ?",
        (sesion_id, intentos_maximos),
    ).fetchall()
    return {f["item_id"] for f in filas}


def ultima_vez_visto_en_sesion(conexion: sqlite3.Connection, sesion_id: int) -> dict:
    filas = conexion.execute(
        "SELECT item_id, MAX(creado_en) AS ultima FROM intento WHERE sesion_id = ? GROUP BY item_id",
        (sesion_id,),
    ).fetchall()
    return {f["item_id"]: f["ultima"] for f in filas}


def ultimo_resultado_por_item_en_sesion(conexion: sqlite3.Connection, sesion_id: int) -> dict:
    # Para cada ítem ya intentado en la sesión, si su intento más reciente
    # fue correcto. Usado para priorizar, cuando la selección del siguiente
    # ítem no tiene alternativa sin ver y debe reutilizar uno ya visto,
    # los que todavía necesitan refuerzo sobre los ya dominados.
    filas = conexion.execute(
        """
        SELECT item_id, es_correcto FROM intento
        WHERE sesion_id = ? AND id IN (
            SELECT MAX(id) FROM intento WHERE sesion_id = ? GROUP BY item_id
        )
        """,
        (sesion_id, sesion_id),
    ).fetchall()
    return {f["item_id"]: bool(f["es_correcto"]) for f in filas}


def categoria_error_mas_frecuente_concepto_sesion(
    conexion: sqlite3.Connection, sesion_id: int, concepto_id: int
) -> str | None:
    fila = conexion.execute(
        """
        SELECT categoria_error.codigo AS codigo, COUNT(*) AS n
        FROM intento
        JOIN categoria_error ON intento.categoria_error_id = categoria_error.id
        WHERE intento.sesion_id = ? AND intento.concepto_id = ? AND intento.es_correcto = 0
        GROUP BY categoria_error.codigo
        ORDER BY n DESC
        LIMIT 1
        """,
        (sesion_id, concepto_id),
    ).fetchone()
    return fila["codigo"] if fila else None


def guardar_intento(
    conexion: sqlite3.Connection,
    sesion_id: int,
    item_id: str,
    concepto_id: int,
    respuesta_cruda: str,
    es_correcto: bool,
    numero_intento: int,
    tiempo_respuesta_ms: int,
    categoria_error: str | None,
) -> int:
    categoria_error_id = None
    if categoria_error:
        fila = conexion.execute(
            "SELECT id FROM categoria_error WHERE codigo = ?", (categoria_error,)
        ).fetchone()
        categoria_error_id = fila["id"] if fila else None
    cursor = conexion.execute(
        """
        INSERT INTO intento (
            sesion_id, item_id, concepto_id, respuesta_cruda, es_correcto,
            numero_intento, tiempo_respuesta_ms, categoria_error_id, creado_en
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sesion_id, item_id, concepto_id, respuesta_cruda, int(es_correcto),
            numero_intento, tiempo_respuesta_ms, categoria_error_id, _ahora(),
        ),
    )
    return cursor.lastrowid


def guardar_pista(conexion: sqlite3.Connection, intento_id: int, nivel: int, orden: int, texto: str) -> int:
    cursor = conexion.execute(
        "INSERT INTO pista (intento_id, nivel, orden, texto_entregado, creado_en) VALUES (?, ?, ?, ?, ?)",
        (intento_id, nivel, orden, texto, _ahora()),
    )
    return cursor.lastrowid


def guardar_estimacion_dominio(conexion: sqlite3.Connection, intento_id: int, p_dominio: float, modo: str) -> int:
    cursor = conexion.execute(
        "INSERT INTO estimacion_dominio (intento_id, p_dominio, modo, creado_en) VALUES (?, ?, ?, ?)",
        (intento_id, p_dominio, modo, _ahora()),
    )
    return cursor.lastrowid


def guardar_traza_adaptacion(
    conexion: sqlite3.Connection,
    intento_id: int,
    regla_id: str,
    accion: str,
    factores: dict,
    explicacion_aprendiz: str,
) -> int:
    cursor = conexion.execute(
        """
        INSERT INTO traza_adaptacion (intento_id, regla_id, accion, factores_json, explicacion_aprendiz, creado_en)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (intento_id, regla_id, accion, json.dumps(factores, ensure_ascii=False), explicacion_aprendiz, _ahora()),
    )
    return cursor.lastrowid


def obtener_traza_de_intento(conexion: sqlite3.Connection, intento_id: int):
    return conexion.execute(
        "SELECT * FROM traza_adaptacion WHERE intento_id = ?", (intento_id,)
    ).fetchone()


def obtener_estimacion_de_intento(conexion: sqlite3.Connection, intento_id: int):
    return conexion.execute(
        "SELECT * FROM estimacion_dominio WHERE intento_id = ?", (intento_id,)
    ).fetchone()


def obtener_intento(conexion: sqlite3.Connection, intento_id: int):
    return conexion.execute("SELECT * FROM intento WHERE id = ?", (intento_id,)).fetchone()


def ultimo_intento_de_item_en_sesion(conexion: sqlite3.Connection, sesion_id: int, item_id: str):
    return conexion.execute(
        "SELECT * FROM intento WHERE sesion_id = ? AND item_id = ? ORDER BY id DESC LIMIT 1",
        (sesion_id, item_id),
    ).fetchone()


def intentos_de_sesion(conexion: sqlite3.Connection, sesion_id: int) -> list[sqlite3.Row]:
    return conexion.execute(
        "SELECT * FROM intento WHERE sesion_id = ? ORDER BY id", (sesion_id,)
    ).fetchall()


def trazas_de_sesion(conexion: sqlite3.Connection, sesion_id: int) -> list[sqlite3.Row]:
    return conexion.execute(
        """
        SELECT traza_adaptacion.*, intento.concepto_id AS intento_concepto_id,
               intento.es_correcto AS intento_es_correcto, intento.creado_en AS intento_creado_en
        FROM traza_adaptacion
        JOIN intento ON traza_adaptacion.intento_id = intento.id
        WHERE intento.sesion_id = ?
        ORDER BY traza_adaptacion.id
        """,
        (sesion_id,),
    ).fetchall()


def estimaciones_de_sesion(conexion: sqlite3.Connection, sesion_id: int) -> list[sqlite3.Row]:
    return conexion.execute(
        """
        SELECT estimacion_dominio.*, intento.concepto_id AS intento_concepto_id,
               intento.es_correcto AS intento_es_correcto
        FROM estimacion_dominio
        JOIN intento ON estimacion_dominio.intento_id = intento.id
        WHERE intento.sesion_id = ?
        ORDER BY estimacion_dominio.id
        """,
        (sesion_id,),
    ).fetchall()


def contar_pistas_de_sesion(conexion: sqlite3.Connection, sesion_id: int) -> int:
    fila = conexion.execute(
        """
        SELECT COUNT(*) AS n FROM pista
        JOIN intento ON pista.intento_id = intento.id
        WHERE intento.sesion_id = ?
        """,
        (sesion_id,),
    ).fetchone()
    return fila["n"]


def detalle_intentos_sesion(conexion: sqlite3.Connection, sesion_id: int) -> list[sqlite3.Row]:
    # Todo lo necesario para las 4 gráficas de resumen de sesión
    # en una sola consulta: intento + su estimación + su traza + su
    # categoría de error, en orden cronológico.
    return conexion.execute(
        """
        SELECT intento.id AS intento_id, intento.concepto_id AS concepto_id,
               intento.es_correcto AS es_correcto, intento.tiempo_respuesta_ms AS tiempo_respuesta_ms,
               intento.item_id AS item_id,
               categoria_error.codigo AS categoria_codigo,
               estimacion_dominio.p_dominio AS p_dominio,
               traza_adaptacion.regla_id AS regla_id, traza_adaptacion.accion AS accion
        FROM intento
        LEFT JOIN categoria_error ON intento.categoria_error_id = categoria_error.id
        JOIN estimacion_dominio ON estimacion_dominio.intento_id = intento.id
        JOIN traza_adaptacion ON traza_adaptacion.intento_id = intento.id
        WHERE intento.sesion_id = ?
        ORDER BY intento.id
        """,
        (sesion_id,),
    ).fetchall()


def errores_de_aprendiz_por_concepto_categoria(conexion: sqlite3.Connection, aprendiz_id: str) -> list[sqlite3.Row]:
    return conexion.execute(
        """
        SELECT intento.concepto_id AS concepto_id, categoria_error.codigo AS categoria_codigo
        FROM intento
        JOIN sesion ON intento.sesion_id = sesion.id
        JOIN categoria_error ON intento.categoria_error_id = categoria_error.id
        WHERE sesion.aprendiz_id = ? AND intento.es_correcto = 0
        """,
        (aprendiz_id,),
    ).fetchall()


def acciones_de_aprendiz(conexion: sqlite3.Connection, aprendiz_id: str) -> list[sqlite3.Row]:
    return conexion.execute(
        """
        SELECT traza_adaptacion.accion AS accion
        FROM traza_adaptacion
        JOIN intento ON traza_adaptacion.intento_id = intento.id
        JOIN sesion ON intento.sesion_id = sesion.id
        WHERE sesion.aprendiz_id = ?
        """,
        (aprendiz_id,),
    ).fetchall()


def intentos_de_aprendiz(conexion: sqlite3.Connection, aprendiz_id: str) -> list[sqlite3.Row]:
    # Todos los intentos de un aprendiz, a través de todas sus sesiones
    # (histórico completo — usado por CU-05, que debe mostrar continuidad
    # entre sesiones, no solo la actual).
    return conexion.execute(
        """
        SELECT intento.*, estimacion_dominio.p_dominio AS p_dominio,
               estimacion_dominio.modo AS modo_estimacion
        FROM intento
        JOIN sesion ON intento.sesion_id = sesion.id
        LEFT JOIN estimacion_dominio ON estimacion_dominio.intento_id = intento.id
        WHERE sesion.aprendiz_id = ?
        ORDER BY intento.id
        """,
        (aprendiz_id,),
    ).fetchall()
