# Dependencias de FastAPI: conexión a la base de datos por petición e
# identificación anónima del aprendiz por cookie (RF-18).
from fastapi import Request, Response

from config import COOKIE_MAX_AGE, COOKIE_NOMBRE, RUTA_BD
from persistencia import repositorio


def obtener_conexion_bd():
    conexion = repositorio.obtener_conexion(RUTA_BD)
    try:
        yield conexion
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def obtener_aprendiz_id(request: Request, conexion) -> str:
    cookie_previa = request.cookies.get(COOKIE_NOMBRE)
    aprendiz_id = repositorio.obtener_o_crear_aprendiz(conexion, cookie_previa)
    origen = "sesión existente" if cookie_previa else "nueva sesión"
    print(f"[APRENDIZ] Identificador: {aprendiz_id} ({origen})")
    return aprendiz_id


def imprimir_estado_aprendiz(conexion, aprendiz_id: str, concepto_id: int, p_dominio_previo: float) -> None:
    # Muestra en la consola el estado del aprendiz tal como quedó guardado en
    # SQLite tras responder un ítem.
    estado = repositorio.obtener_estado_aprendiz(conexion, aprendiz_id, concepto_id)
    concepto = conexion.execute("SELECT nombre FROM concepto WHERE id = ?", (concepto_id,)).fetchone()
    nombre = concepto["nombre"] if concepto else f"Concepto {concepto_id}"
    print(
        f"[ESTADO] Aprendiz {aprendiz_id} · {nombre}: "
        f"dominio {p_dominio_previo:.0%} → {estado.p_dominio_previo:.0%} · estado {estado.estado} · "
        f"nivel {estado.nivel_dificultad_actual} · aciertos {estado.total_aciertos}/{estado.total_intentos} · "
        f"racha +{estado.racha_aciertos}/-{estado.racha_errores}"
    )


def fijar_cookie_aprendiz(response: Response, aprendiz_id: str) -> None:
    response.set_cookie(
        key=COOKIE_NOMBRE,
        value=aprendiz_id,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
