import sqlite3
from datetime import datetime, timezone

import yaml

from config import RUTA_BD, RUTA_CATEGORIAS_ERROR, RUTA_CONCEPTOS, RUTA_ESQUEMA_SQL, RUTA_REGLAS
from persistencia.repositorio import obtener_conexion


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def crear_esquema(conexion: sqlite3.Connection) -> None:
    sql = RUTA_ESQUEMA_SQL.read_text(encoding="utf-8")
    conexion.executescript(sql)


def cargar_conceptos(conexion: sqlite3.Connection, ruta=RUTA_CONCEPTOS) -> int:
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    conceptos = datos["conceptos"]
    conexion.executemany(
        "INSERT OR REPLACE INTO concepto (id, orden, nombre) VALUES (:id, :orden, :nombre)",
        conceptos,
    )
    return len(conceptos)


def cargar_categorias_error(conexion: sqlite3.Connection, ruta=RUTA_CATEGORIAS_ERROR) -> int:
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    categorias = datos["categorias"]
    filas = [
        {"id": indice, "codigo": c["codigo"], "nombre": c["nombre"], "descripcion": c["descripcion"]}
        for indice, c in enumerate(categorias, start=1)
    ]
    conexion.executemany(
        "INSERT OR REPLACE INTO categoria_error (id, codigo, nombre, descripcion) "
        "VALUES (:id, :codigo, :nombre, :descripcion)",
        filas,
    )
    return len(filas)


def cargar_reglas(conexion: sqlite3.Connection, ruta=RUTA_REGLAS) -> int:
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    reglas = datos["reglas"]
    filas = [
        {
            "id": r["id"],
            "nombre": r["nombre"],
            "prioridad": r["prioridad"],
            "condicion_textual": r["condicion_textual"],
            "accion": r["accion"],
        }
        for r in reglas
    ]
    conexion.executemany(
        "INSERT OR REPLACE INTO regla (id, nombre, prioridad, condicion_textual, accion) "
        "VALUES (:id, :nombre, :prioridad, :condicion_textual, :accion)",
        filas,
    )
    return len(filas)


def inicializar(ruta_bd=RUTA_BD) -> dict:
    # Crea el esquema (si no existe) y carga los tres catálogos. Devuelve
    # un resumen con los conteos cargados, usado para validar la fase 1.
    conexion = obtener_conexion(ruta_bd)
    try:
        crear_esquema(conexion)
        resumen = {
            "conceptos": cargar_conceptos(conexion),
            "categorias_error": cargar_categorias_error(conexion),
            "reglas": cargar_reglas(conexion),
        }
        conexion.commit()
        return resumen
    finally:
        conexion.close()


if __name__ == "__main__":
    resumen = inicializar()
    print(f"Base de datos inicializada en: {RUTA_BD}")
    print(f"  conceptos cargados:        {resumen['conceptos']}")
    print(f"  categorías de error cargadas: {resumen['categorias_error']}")
    print(f"  reglas cargadas:            {resumen['reglas']}")
