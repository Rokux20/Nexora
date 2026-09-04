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


def probabilidad_acierto(aprendiz: AprendizVirtual, concepto_id: int, dificultad: int) -> float:
    efectivo = dominio_efectivo(aprendiz.dominio_latente[concepto_id], dificultad)
    return efectivo * (1 - aprendiz.descuido) + (1 - efectivo) * aprendiz.suerte


def simular_tiempo_respuesta_ms(
    aprendiz: AprendizVirtual,
    concepto_id: int,
    dificultad: int,
    tiempo_referencia_seg: int,
    rng: np.random.Generator,
) -> int:
    efectivo = dominio_efectivo(aprendiz.dominio_latente[concepto_id], dificultad)
    factor = np.exp(rng.normal(0, 0.4)) * (1.6 - efectivo)
    segundos = tiempo_referencia_seg * factor
    return max(500, int(segundos * 1000))


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
