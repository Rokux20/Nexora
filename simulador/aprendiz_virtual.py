from dataclasses import dataclass

import numpy as np


@dataclass
class AprendizVirtual:
    id: str
    tasa_aprendizaje: float
    descuido: float
    suerte: float
    dominio_latente: dict  # {concepto_id: valor en [0, 1]}

    @classmethod
    def generar(cls, id_aprendiz: str, num_conceptos: int, rng: np.random.Generator) -> "AprendizVirtual":
        return cls(
            id=id_aprendiz,
            tasa_aprendizaje=float(rng.uniform(0.02, 0.15)),
            descuido=float(rng.uniform(0.00, 0.20)),
            suerte=float(rng.uniform(0.00, 0.25)),
            dominio_latente={c: float(rng.uniform(0.05, 0.45)) for c in range(1, num_conceptos + 1)},
        )


def dominio_efectivo(dominio_latente: float, dificultad: int) -> float:
    # Ajusta el dominio latente por la dificultad del ítem.
    valor = dominio_latente - 0.15 * (dificultad - 1)
    return max(0.0, min(1.0, valor))


# Ayuda que aporta cada pista ya recibida sobre el mismo ítem: la pista de
# nivel 3 casi entrega la respuesta y, en opción múltiple, los intentos
# fallidos descartan opciones. Tras 1 pista la probabilidad de acertar sin
# saber sube ≈35 %, tras 2 ≈58 %, así que un acierto en el tercer intento es
# poca evidencia de dominio.
AYUDA_POR_PISTA = 0.35

# Tiempo de respuesta relativo al de referencia del ítem.
# - Quien sabe responde con fluidez: el tiempo decrece con el dominio
#   efectivo (≈0.48× con dominio 0.5, ≈0.15× con dominio pleno), lo que
#   produce los tiempos cortos (< 0.5×) que exige R2. Un error por descuido
#   también es rápido.
# - Quien no sabe adivina rápido o se atasca (≈1.6×, tiempos largos de R5).
#   Por eso un error rápido no es señal de dominio.
TIEMPO_RELATIVO_SIN_DOMINIO = 1.6
PENDIENTE_TIEMPO_DOMINIO = 2.4
TIEMPO_RELATIVO_ADIVINANZA = 0.35
PROBABILIDAD_ADIVINAR_RAPIDO = 0.5
DISPERSION_TIEMPO = 0.35


def _ayuda_por_pistas(pistas_recibidas: int) -> float:
    return 1 - (1 - AYUDA_POR_PISTA) ** pistas_recibidas


def simular_respuesta(
    aprendiz: AprendizVirtual,
    concepto_id: int,
    dificultad: int,
    tiempo_referencia_seg: int,
    rng: np.random.Generator,
    pistas_recibidas: int = 0,
) -> tuple[bool, int]:
    # Devuelve (es_correcto, tiempo_respuesta_ms). Primero se decide si el
    # aprendiz sabe resolver el ítem (con probabilidad igual a su dominio
    # efectivo); el resultado y el tiempo dependen de ese camino.
    efectivo = dominio_efectivo(aprendiz.dominio_latente[concepto_id], dificultad)
    ruido = np.exp(rng.normal(0, DISPERSION_TIEMPO))
    if rng.uniform() < efectivo:
        es_correcto = bool(rng.uniform() >= aprendiz.descuido)
        factor = TIEMPO_RELATIVO_SIN_DOMINIO * np.exp(-PENDIENTE_TIEMPO_DOMINIO * efectivo) * ruido
    else:
        acierto_sin_saber = aprendiz.suerte + (1 - aprendiz.suerte) * _ayuda_por_pistas(pistas_recibidas)
        es_correcto = bool(rng.uniform() < acierto_sin_saber)
        rapido = rng.uniform() < PROBABILIDAD_ADIVINAR_RAPIDO
        factor = (TIEMPO_RELATIVO_ADIVINANZA if rapido else TIEMPO_RELATIVO_SIN_DOMINIO) * ruido
    return es_correcto, max(500, int(tiempo_referencia_seg * factor * 1000))


def actualizar_dominio_tras_interaccion(aprendiz: AprendizVirtual, concepto_id: int, acerto: bool) -> None:
    # Evolución del dominio latente tras una interacción: crece
    # más si acertó, y algo menos si falló (también se aprende del error).
    actual = aprendiz.dominio_latente[concepto_id]
    incremento = aprendiz.tasa_aprendizaje * (1 - actual)
    if not acerto:
        incremento *= 0.3
    aprendiz.dominio_latente[concepto_id] = min(1.0, actual + incremento)


def muestrear_categoria_error(dominio_efectivo_valor: float, rng: np.random.Generator) -> str:
    # Muestreo ponderado de categoría de error según el dominio efectivo:
    # dominio alto favorece 'descuido'; dominio bajo favorece
    # 'conceptual' y 'logica_algoritmo'.
    pesos = {
        "descuido": 0.15 + 0.6 * dominio_efectivo_valor,
        "conceptual": 0.10 + 0.5 * (1 - dominio_efectivo_valor),
        "logica_algoritmo": 0.10 + 0.5 * (1 - dominio_efectivo_valor),
        "flujo_ejecucion": 0.15,
        "sintaxis": 0.10,
    }
    categorias = list(pesos.keys())
    valores = np.array(list(pesos.values()))
    valores = valores / valores.sum()
    return str(rng.choice(categorias, p=valores))
