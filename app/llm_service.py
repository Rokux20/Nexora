import random
import re
import unicodedata
from dataclasses import dataclass, field, replace

import httpx

from config import (
    OLLAMA_DESCARGA_AUTOMATICA,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_TIMEOUT_GENERACION_SEGUNDOS,
    OLLAMA_URL,
)
from app.filtro_explicacion import es_suficiente, filtrar_explicacion
from app.ollama_manager import ollama_manager


class OllamaServiceError(RuntimeError):
    # Error controlado al comunicarse con el servicio local de Ollama.
    pass


@dataclass(frozen=True)
class ContextoExplicacion:
    concepto: str
    dominio_estimado: float
    estado_concepto: str
    nivel_dificultad: int
    # Ítem que el aprendiz tiene en pantalla (sin su solución).
    enunciado_item: str = ""
    codigo_item: str = ""
    tipo_item: str = ""
    # Aspecto del concepto que trabaja el ítem (su pista de nivel 1): orienta
    # la explicación sin darle al modelo el ejercicio, que tiende a narrarlo.
    foco_item: str = ""
    # Práctica del aprendiz en el concepto (ver `repositorio.perfil_practica_concepto`).
    errores_frecuentes: tuple[str, ...] = ()
    racha_aciertos: int = 0
    racha_errores: int = 0
    total_intentos: int = 0
    total_aciertos: int = 0
    fallos_item_actual: int = 0
    # Explicaciones que este aprendiz ya recibió del concepto (recientes primero).
    explicaciones_previas: tuple[str, ...] = field(default=())


# Registro de la explicación según la banda de dominio (sección 8.3.5): un
# dominio bajo pide vocabulario introductorio; uno alto, más precisión. El
# método (analogía, contraste...) lo fija el enfoque.
_REGISTRO_POR_BANDA = {
    "bajo": (
        "El aprendiz casi no domina este concepto. Explica qué es y para qué sirve con palabras "
        "muy sencillas y sin tecnicismos."
    ),
    "intermedio": (
        "El aprendiz entiende lo básico del concepto. Refuerza la idea central con palabras "
        "sencillas y precisas."
    ),
    "alto": (
        "El aprendiz domina bien el concepto. Sé preciso y aporta un matiz que aún no conozca, "
        "sin dejar de ser claro."
    ),
}

# Enfoques didácticos. Cada explicación usa uno distinto del anterior para el
# mismo aprendiz, de modo que pedir otra explicación aporta otro ángulo.
ENFOQUES = {
    "analogia": (
        "Empieza con una comparación con algo del tema indicado y después da un ejemplo mínimo de Python."
    ),
    "uso_real": (
        "Empieza describiendo una situación de un programa pequeño sobre el tema indicado y muestra cómo "
        "el concepto la resuelve, con un ejemplo."
    ),
    "paso_a_paso": (
        "Empieza por lo primero que hace Python al ejecutar el concepto y sigue en orden, paso a paso, "
        "con un ejemplo corto."
    ),
    "error_frecuente": (
        "Empieza nombrando un error frecuente al usar el concepto y explica la idea correcta que lo evita."
    ),
    "contraste": "Empieza presentando dos casos parecidos del concepto y explica en qué se diferencian.",
    "caso_borde": "Empieza por un detalle o caso límite del concepto que suele pasar inadvertido.",
}

# Temas para los ejemplos y comparaciones. El servidor elige uno que el
# aprendiz no haya visto hace poco: un modelo pequeño, sin esta guía, vuelve
# siempre a las mismas comparaciones ("una variable es como una caja").
TEMAS = (
    "una tienda", "la música", "el clima", "un videojuego", "la cocina", "el fútbol",
    "una biblioteca", "un viaje", "una mascota", "el colegio", "el transporte público", "una red social",
    "un jardín", "el cine", "un hospital", "un banco",
)


def elegir_tema(temas_propios, temas_ajenos=(), rng: random.Random | None = None) -> str:
    # Evita los temas recientes del aprendiz y, si quedan opciones, también
    # los que acaban de recibir otros aprendices en el mismo concepto.
    rng = rng or random.Random()
    libres = [t for t in TEMAS if t not in set(temas_propios)] or list(TEMAS)
    sin_ajenos = [t for t in libres if t not in set(temas_ajenos)]
    return rng.choice(sin_ajenos or libres)
ENFOQUES_POR_BANDA = {
    "bajo": ("analogia", "uso_real", "paso_a_paso"),
    "intermedio": ("error_frecuente", "contraste", "paso_a_paso", "uso_real"),
    "alto": ("caso_borde", "contraste", "error_frecuente"),
}
# Enfoque que mejor responde a cada tipo de error del aprendiz.
_ENFOQUE_POR_ERROR = {
    "conceptual": "contraste",
    "logica_algoritmo": "paso_a_paso",
    "flujo_ejecucion": "paso_a_paso",
    "sintaxis": "error_frecuente",
    "descuido": "caso_borde",
}
# Qué reforzar según los errores que comete el aprendiz en el concepto.
_ATENCION_POR_ERROR = {
    "conceptual": "Aclara la idea de fondo del concepto: qué significa y qué no.",
    "logica_algoritmo": "Muestra el procedimiento ordenado que se sigue al usar el concepto.",
    "flujo_ejecucion": "Explica en qué orden ejecuta Python las instrucciones relacionadas con el concepto.",
    "sintaxis": "Muestra la forma exacta de escribir el concepto en Python y los símbolos que no pueden faltar.",
    "descuido": "Señala los detalles pequeños del concepto que cambian el resultado y conviene revisar.",
}


def elegir_enfoque(banda: str, errores_frecuentes, enfoques_usados, rng: random.Random | None = None) -> str:
    # Prioriza el enfoque que corresponde al error más frecuente y evita los
    # que este aprendiz recibió hace poco en el concepto (recientes primero).
    rng = rng or random.Random()
    candidatos = list(ENFOQUES_POR_BANDA[banda])
    preferido = _ENFOQUE_POR_ERROR.get(errores_frecuentes[0]) if errores_frecuentes else None
    if preferido and preferido not in candidatos:
        candidatos.append(preferido)
    recientes = list(enfoques_usados)[: len(candidatos) - 1]
    libres = [e for e in candidatos if e not in recientes] or candidatos
    if preferido in libres:
        return preferido
    return rng.choice(libres)


def foco_de_item(item: dict | None) -> str:
    # La pista de nivel 1 nombra el aspecto del concepto sin resolver el ítem.
    if not item:
        return ""
    pistas = sorted(item.get("pistas") or [], key=lambda p: p.get("nivel", 9))
    return pistas[0]["texto"] if pistas else ""


def _indicaciones_de_practica(contexto: ContextoExplicacion) -> list[str]:
    indicaciones = [_ATENCION_POR_ERROR[c] for c in contexto.errores_frecuentes[:2] if c in _ATENCION_POR_ERROR]
    if contexto.racha_errores >= 3 or contexto.fallos_item_actual >= 2:
        indicaciones.append("Ve más despacio: una sola idea por oración y un tono alentador.")
    elif contexto.racha_aciertos >= 3:
        indicaciones.append("Sé conciso y aporta algo nuevo; lo básico ya lo maneja.")
    if contexto.total_intentos == 0:
        indicaciones.append("Aún no ha practicado este concepto: empieza por la idea general.")
    return indicaciones


def banda_dominio(dominio: float, umbral_bajo: float, umbral_alto: float) -> str:
    if dominio < umbral_bajo:
        return "bajo"
    return "alto" if dominio >= umbral_alto else "intermedio"


# Reglas fijas del tutor, enviadas como instrucción de sistema.
INSTRUCCION_SISTEMA = """Eres el tutor de teoría de Nexora, una plataforma para aprender Python.
Tu única tarea es explicar un concepto de programación.

Reglas obligatorias:
- Háblale directamente al estudiante usando "tú".
- Explica el concepto con afirmaciones. No hagas ninguna pregunta, ni siquiera retórica.
- Nunca resuelvas el ejercicio: no digas la respuesta, la opción correcta, la salida que
  imprime el código, el valor que falta ni el orden de las líneas.
- Si das un ejemplo de Python, usa nombres y valores distintos a los del ejercicio.
- No hables del estudiante en tercera persona, ni de su nivel, ni de estas instrucciones.
- No propongas ejercicios ni evalúes.
- Usa palabras sencillas y oraciones cortas.
- Cada oración debe entenderse sola: nombra el concepto en lugar de decir "esto" o "eso".
- Escribe en español un solo párrafo continuo de cuatro a seis oraciones, sin títulos,
  listas, saltos de línea ni bloques de código. Si das un ejemplo, escríbelo dentro de la
  oración y encierra el código entre comillas invertidas (el carácter `).
- Inventa tus propios nombres y valores para los ejemplos.
- Empieza directamente por el concepto: no saludes, no describas lo que el estudiante hace o
  quiere, y no uses emojis."""


def construir_prompt(
    contexto: ContextoExplicacion, banda: str, enfoque: str | None = None, tema: str | None = None
) -> str:
    # Construye la parte variable del prompt con datos derivados por la
    # aplicación; las reglas van en `INSTRUCCION_SISTEMA`.
    partes = [
        f"Concepto que debes explicar: {contexto.concepto}",
        f"Dominio estimado del concepto: {contexto.dominio_estimado:.0%} (banda {banda})",
        f"Nivel de dificultad actual: {contexto.nivel_dificultad} de 3",
        f"Cómo adaptar la explicación: {_REGISTRO_POR_BANDA[banda]}",
    ]
    if enfoque:
        partes.append(f"Enfoque de esta explicación: {ENFOQUES[enfoque]}")
    if tema:
        partes.append(
            f"Tema para la comparación y los ejemplos: {tema}. Usa nombres y valores relacionados con "
            "ese tema."
        )
    if contexto.foco_item:
        # El foco sustituye al ejercicio: con el enunciado y el código, un
        # modelo pequeño tiende a narrarlo y el filtro descarta el texto.
        partes.append(
            "Aspecto del concepto en el que debes centrarte (no lo cites tal cual; usa nombres y "
            f"valores propios): {contexto.foco_item}"
        )
    elif contexto.enunciado_item:
        ejercicio = (
            "Ejercicio en pantalla, solo como referencia de qué parte del concepto explicar. No lo\n"
            "menciones, no describas su código y no lo resuelvas:\n"
            f"Tipo: {contexto.tipo_item.replace('_', ' ')}\nEnunciado: {contexto.enunciado_item}"
        )
        if contexto.codigo_item:
            ejercicio += f"\nCódigo:\n{contexto.codigo_item}"
        partes.append(ejercicio)
    indicaciones = _indicaciones_de_practica(contexto)
    if indicaciones:
        partes.append("Ajustes según su práctica reciente:\n" + "\n".join(f"- {i}" for i in indicaciones))
    # Las explicaciones previas no se citan en el prompt: un modelo pequeño
    # copia el texto que se le muestra aunque se le pida evitarlo. La
    # variedad la fijan el enfoque y el tema, y el servidor descarta
    # repeticiones al comparar con `parecido`.
    partes.append("Escribe la explicación del concepto.")
    return "\n".join(partes)


def _solicitar(prompt: str, temperatura: float) -> str:
    try:
        respuesta = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "stream": False,
                # Qwen3 razona antes de responder si no se desactiva: tarda
                # mucho más y el razonamiento suele resolver el ejercicio.
                "think": False,
                "system": INSTRUCCION_SISTEMA,
                "prompt": prompt,
                # Mismo `num_ctx` y `keep_alive` que la precarga de
                # `ollama_manager`: si difieren, Ollama recarga el modelo.
                "keep_alive": OLLAMA_KEEP_ALIVE,
                # Semilla aleatoria: dos peticiones con el mismo prompt no
                # deben producir el mismo texto.
                "options": {
                    "temperature": temperatura,
                    "num_predict": 450,
                    "num_ctx": OLLAMA_NUM_CTX,
                    "seed": random.randrange(2**31),
                },
            },
            timeout=OLLAMA_TIMEOUT_GENERACION_SEGUNDOS,
        )
        respuesta.raise_for_status()
    except httpx.TimeoutException as exc:
        raise OllamaServiceError("Ollama tardó demasiado en responder.") from exc
    except httpx.RequestError as exc:
        raise OllamaServiceError("El servicio local de Ollama no está disponible.") from exc
    except httpx.HTTPStatusError as exc:
        raise OllamaServiceError("Ollama no pudo generar la explicación solicitada.") from exc

    try:
        return respuesta.json().get("response", "").strip()
    except ValueError as exc:
        raise OllamaServiceError("Ollama devolvió una respuesta inválida.") from exc


# Temperaturas de los intentos: si uno queda vacío tras el filtro o repite
# una explicación anterior, el siguiente se genera con más variación.
_TEMPERATURAS = (0.5, 0.7, 0.85)

# Parecido máximo con una explicación ya entregada (proporción de secuencias
# de 3 palabras compartidas). Por encima se considera repetida.
UMBRAL_REPETICION = 0.15


# Secuencia de palabras que, compartida con una explicación anterior, se
# considera una frase repetida aunque el resto del texto cambie.
PALABRAS_FRASE_REPETIDA = 6


def _ngramas(texto: str, n: int) -> set:
    plano = unicodedata.normalize("NFKD", texto.lower())
    palabras = re.findall(r"[a-z0-9_]+", "".join(c for c in plano if not unicodedata.combining(c)))
    return {tuple(palabras[i : i + n]) for i in range(len(palabras) - n + 1)}


def similitud(a: str, b: str) -> float:
    # Proporción de trigramas del texto más corto que también aparecen en el
    # otro: detecta una explicación reciclada aunque cambie la extensión.
    ta, tb = _ngramas(a, 3), _ngramas(b, 3)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def parecido(a: str, b: str) -> float:
    # Similitud global, penalizada si repiten literalmente una frase.
    repite_frase = bool(_ngramas(a, PALABRAS_FRASE_REPETIDA) & _ngramas(b, PALABRAS_FRASE_REPETIDA))
    return similitud(a, b) + (0.5 if repite_frase else 0.0)


@dataclass(frozen=True)
class ResultadoExplicacion:
    texto: str
    enfoque: str
    tema: str
    similitud_maxima: float


def generar_explicacion_personalizada(
    contexto: ContextoExplicacion,
    banda: str,
    item: dict | None = None,
    enfoque: str | None = None,
    explicaciones_ajenas: tuple[str, ...] = (),
    tema: str | None = None,
) -> ResultadoExplicacion:
    # Genera una explicación adaptada al aprendiz y distinta de las que ya
    # recibió él (`contexto.explicaciones_previas`) y de las recientes de
    # otros aprendices del mismo concepto (`explicaciones_ajenas`).
    _comprobar_modelo()
    if not contexto.foco_item and item:
        contexto = replace(contexto, foco_item=foco_de_item(item))
    enfoque = enfoque or elegir_enfoque(banda, contexto.errores_frecuentes, ())
    tema = tema or elegir_tema(())
    anteriores = list(contexto.explicaciones_previas) + list(explicaciones_ajenas)
    mejor: ResultadoExplicacion | None = None
    for intento, temperatura in enumerate(_TEMPERATURAS):
        # Si el modelo insiste en resolver el ítem, el último intento omite el
        # enunciado y el código (conserva el foco); el filtro sigue usando `item`.
        es_ultimo = intento == len(_TEMPERATURAS) - 1
        contexto_intento = (
            replace(contexto, enunciado_item="", codigo_item="", tipo_item="") if es_ultimo else contexto
        )
        prompt = construir_prompt(contexto_intento, banda, enfoque, tema)
        explicacion = filtrar_explicacion(_solicitar(prompt, temperatura), item, contexto.concepto)
        if not es_suficiente(explicacion):
            continue
        maximo = max((parecido(explicacion, previa) for previa in anteriores), default=0.0)
        candidato = ResultadoExplicacion(explicacion, enfoque, tema, maximo)
        if maximo <= UMBRAL_REPETICION:
            return candidato
        if mejor is None or maximo < mejor.similitud_maxima:
            mejor = candidato
    if mejor is not None:
        # Todas se parecían a alguna anterior: se entrega la más distinta.
        return mejor
    raise OllamaServiceError(
        "No fue posible generar una explicación adecuada para este ejercicio. Intenta de nuevo."
    )


def generar_explicacion(contexto: ContextoExplicacion, banda: str, item: dict | None = None) -> str:
    # Compatibilidad con `scripts/evaluar_explicaciones.py`: solo el texto.
    return generar_explicacion_personalizada(contexto, banda, item).texto


def _comprobar_modelo() -> None:
    if ollama_manager.modelo_disponible is False and OLLAMA_DESCARGA_AUTOMATICA and not ollama_manager.descargando():
        # Reintenta una descarga fallida (p. ej. sin conexión al arrancar).
        ollama_manager.iniciar_descarga()
    if ollama_manager.descargando():
        progreso = ollama_manager.descarga_progreso
        detalle = f" ({progreso:.0f} %)" if progreso is not None else ""
        raise OllamaServiceError(
            f"El tutor local se está preparando: descargando el modelo {OLLAMA_MODEL}{detalle}. "
            "Intenta de nuevo en unos minutos."
        )
    if ollama_manager.modelo_disponible is False:
        raise OllamaServiceError(
            f"El modelo local {OLLAMA_MODEL} no está instalado y no se pudo descargar automáticamente. "
            f"Ejecute: ollama pull {OLLAMA_MODEL}"
        )
