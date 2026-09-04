# Estructuras de datos compartidas entre los modelos del núcleo y el
# orquestador.
from dataclasses import dataclass


@dataclass(frozen=True)
class Traza:
    # Resultado del modelo pedagógico (RF-08): la regla activada, la
    # acción resultante y los factores que se evaluaron para decidirla.

    regla_id: str
    nombre: str
    accion: str
    condicion_textual: str
    explicacion_aprendiz: str
    factores: dict


@dataclass
class EstadoAprendiz:
    # Estado acumulado de un aprendiz para un concepto (tabla
    # `estado_aprendiz`). `bloqueado_avance` es una extensión sobre el
    # esquema mínimo de la especificación — ver DECISIONES.md #2.

    aprendiz_id: str
    concepto_id: int
    p_dominio_previo: float = 0.25
    racha_aciertos: int = 0
    racha_errores: int = 0
    total_intentos: int = 0
    total_aciertos: int = 0
    nivel_dificultad_actual: int = 1
    pistas_acumuladas: int = 0
    estado: str = "pendiente"
    bloqueado_avance: bool = False


@dataclass(frozen=True)
class Decision:
    # Resultado devuelto por `motor_hibrido.ejecutar_ciclo` (RF-06 a
    # RF-09) a la capa de interfaz.

    intento_id: int
    es_correcto: bool
    categoria_error: str | None
    p_dominio: float
    p_dominio_previo: float
    modo_estimacion: str
    traza: Traza
    siguiente_item_id: str | None
    pista: dict | None
    concepto_completado: bool
