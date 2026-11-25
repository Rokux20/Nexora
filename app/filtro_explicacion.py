# Filtro de las explicaciones generadas por el modelo de lenguaje local.
#
# El prompt pide al modelo que no dé la respuesta ni haga preguntas, pero un
# modelo pequeño no siempre lo cumple. Este filtro lo garantiza del lado del
# servidor: elimina las oraciones con preguntas, las que anuncian la respuesta
# y cualquier fragmento que contenga la solución del ítem en pantalla o que
# narre el ejercicio. La solución solo se usa aquí para comparar; nunca se
# envía al modelo. El resultado es un solo párrafo continuo: si al retirar una
# oración la siguiente queda aludiendo a ella ("Esto permite..."), también se
# retira, para que el texto no quede con saltos ni referencias sueltas.
import re
import unicodedata

# Longitud mínima de prosa útil tras filtrar; por debajo se reintenta.
LONGITUD_MINIMA = 180

_BLOQUE_CODIGO = re.compile(r"```.*?```", re.S)
_CORTE = "\0corte\0"
# Comienzos de oración que aluden a lo dicho justo antes.
_DEPENDE_DE_ANTERIOR = re.compile(
    r"(est[eoa]s?|es[eoa]s?|aquel|dich[oa]|ello|as[ií]|adem[aá]s|tambi[eé]n|asimismo|sin\s+embargo|aun\s+as[ií]|pero|y|o\s+sea"
    r"|en\s+su\s+lugar|en\s+resumen|entonces|luego|por\s+eso|de\s+(esta|esa)\s+(forma|manera)|para\s+(lograrlo|ello|esto)"
    r"|sin\s+(este|esta|esto|ese|esa|eso)|cada|ambos|ambas|el\s+resultado|lo\s+anterior|es\s+como|puedes\s+pensar\s+en\s+(él|ella|esto|eso))\b",
    re.I,
)
_RAZONAMIENTO = re.compile(r"<think>.*?</think>", re.S)
_ORACION = re.compile(r"(?<=[.!?…:])\s+(?=[A-ZÁÉÍÓÚÑ¿¡`(\"'])")

# Frases que anuncian la respuesta del ejercicio.
_REVELA_RESPUESTA = re.compile(
    r"\b(la\s+)?respuesta\b|\bsoluci[oó]n\b|\bopci[oó]n\s+(correcta|[a-d]\b)|\bla\s+correcta\b"
    r"|\bla\s+salida\s+(es|ser[aá]|ser[ií]a|ser[ií]an|son)\b|\bresultado(\s+final)?,?\s+(que\s+)?(es|ser[aá]|ser[ií]a)\b"
    r"|\bimprimir([aá]|[ií]a)n?\b|\bel\s+orden\s+(correcto|es|ser[ií]a)\b"
    # Una salida concreta: "se imprime 3, 2, 1", "imprime `[1, 2]`".
    r"|\b(se\s+)?(imprime|muestra)n?\s+[`\"'\[\d-]"
    # Predicciones sobre lo que hará un código: cualquier verbo en futuro
    # ("el bucle ejecutará...", "se obtendrá..."). Exige la tilde: sin ella
    # coincidiría con palabras como "para" u "otra".
    r"|\b\w+r(á|ás|án)\b",
    re.I,
)
# Comentarios sobre el estudiante, el ejercicio o las instrucciones, en lugar
# de explicar el concepto. "En este caso", "por lo tanto" y "el código
# debe/tiene..." aparecen cuando el modelo pasa a narrar el ejercicio.
_METACOMENTARIO = re.compile(
    r"\baprendiz\b|\bestudiante\b|\bla\s+explicaci[oó]n\b|\brequisito|\bejercicios?\b|\bresolver\b|\bresuelv"
    r"|\bejemplo\s+dado\b|\bc[oó]digo\s+(dado|del\s+ejercicio)\b|\bexplicar\s+esto\b|\bdesde\s+cero\b"
    r"|\banalog[ií]a\s+cotidiana\b|\bejemplo\s+m[ií]nimo\b|\bpara\s+explicar\b|\bdebes\s+enfatizar\b"
    r"|\b(que\s+debes|debemos)\s+explicar\b|\ben\s+(este|el)\s+(caso|ejemplo|c[oó]digo|contexto)\b|\bpor\s+lo\s+tanto\b"
    r"|\b(el|este|ese)\s+c[oó]digo\b"
    r"|\bordenar\s+las\s+l[ií]neas\b|\bdebes\s+(completar|ordenar)\b|\bparte\s+en\s+blanco\b|\best[aá]s\s+aprendiendo\b"
    r"|\b(la\s+parte|lo)\s+que\s+falta\b|\b(para|con)\s+el\s+(n[uú]mero|valor)\s+`?-?\d"
    # Ofrecimientos propios de un chat ("Si quieres, puedo explicarte...").
    r"|\bsi\s+(necesitas|quieres|deseas)\b|\bpuedo\s+(explicarte|ayudarte|darte)\b|\bencantad[oa]\b",
    re.I,
)
_VERBOS_COMPLETAR = re.compile(
    r"complet|espacio|blanco|falta|escrib|reemplaz|___|poner|colocar|va\s+|\bus(a|ar|as)\b|necesit|debes|operador|palabra\s+clave",
    re.I,
)
# Palabras clave y funciones de Python que se conservan al comparar la
# estructura de dos códigos (los demás nombres se consideran intercambiables).
_RESERVADAS = {
    "and", "as", "break", "class", "continue", "def", "del", "elif", "else", "except", "finally", "for", "from",
    "if", "import", "in", "is", "lambda", "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
    "True", "False", "None", "print", "range", "len", "int", "float", "str", "bool", "list", "dict", "set",
    "tuple", "input", "sum", "min", "max", "abs", "round", "sorted", "enumerate", "zip", "type", "isinstance",
}
# Nombres en español de los tipos de Python: en opción múltiple, decir
# "número flotante" cuando la respuesta es `float` también la revela.
_SINONIMOS_TIPOS = {
    "float": ["flotante", "punto flotante", "decimal"], "int": ["entero"], "str": ["cadena", "string"],
    "bool": ["booleano"], "list": ["lista"], "dict": ["diccionario"], "tuple": ["tupla"],
}
# Lo mismo con los operadores en los ítems de completar: "distinto de" es `!=`.
_SINONIMOS_OPERADORES = {
    "!=": ["distinto", "diferente"], "==": ["igual a", "igual que", "iguales"],
    "<=": ["menor o igual"], ">=": ["mayor o igual"], "<": ["menor que"], ">": ["mayor que"],
    "%": ["resto", "módulo"], "**": ["potencia"], "//": ["división entera"],
    "and": ["ambas", "ambos"], "or": ["alguna de", "alguno de"], "not": ["negación"],
}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFC", texto).replace("`", "")
    return re.sub(r"\s+", "", texto).lower()


def _contiene(texto: str, fragmento: str) -> bool:
    fragmento = _normalizar(fragmento)
    return bool(fragmento) and fragmento in _normalizar(texto)


def _menciona(texto: str, fragmento: str) -> bool:
    # Como `_contiene`, pero un fragmento corto (p. ej. "0" o "5") solo cuenta
    # como palabra completa, para no coincidir dentro de "10" o "50".
    fragmento = fragmento.strip()
    if len(fragmento) >= 3:
        return _contiene(texto, fragmento)
    return bool(fragmento) and re.search(rf"(?<![\w.]){re.escape(fragmento)}(?!\w|\.\d)", texto.replace("`", "")) is not None


def _lineas_completadas(item: dict) -> list[str]:
    # Líneas del código de un ítem de completar con el espacio ya resuelto.
    codigo = item.get("codigo") or ""
    lineas = []
    for solucion in item["solucion"]:
        for linea in codigo.splitlines():
            if "___" in linea:
                lineas.append(linea.replace("___", solucion))
    return lineas


def _entornos_completados(item: dict) -> list[str]:
    # La solución junto a lo que la rodea en el código (p. ej. "%2==0" o
    # "o.replace("): detecta la expresión completada aunque no se cite la
    # línea entera.
    entornos = []
    for solucion in item["solucion"]:
        for linea in (item.get("codigo") or "").splitlines():
            if "___" in linea:
                antes, despues = linea.split("___", 1)
                antes, despues = _normalizar(antes)[-2:], _normalizar(despues)[:2]
                solucion_n = _normalizar(solucion)
                if antes or despues:
                    entornos.append(antes + solucion_n + despues)
                # Con un solo lado también se reconoce ("*numeros" para "*").
                if len(antes) == 2:
                    entornos.append(antes + solucion_n)
                if len(despues) == 2:
                    entornos.append(solucion_n + despues)
    return entornos


def _lineas_parsons_en_orden(item: dict) -> list[str]:
    return [item["fragmentos"][i]["texto"] for i in item["solucion"]]


def _codigo_del_item(item: dict) -> str:
    # Código visible del ejercicio; en Parsons, las líneas a ordenar.
    if item["tipo"] == "parsons":
        return "\n".join(f["texto"] for f in item["fragmentos"])
    return item.get("codigo") or ""


def _nombres_del_item(item: dict) -> list[str]:
    # Variables y funciones que define el código del ejercicio. Usarlas en la
    # explicación es narrar el ejercicio en lugar de explicar el concepto.
    codigo = _codigo_del_item(item)
    nombres = re.findall(r"^\s*([A-Za-z_]\w*)\s*=(?!=)", codigo, re.M)
    nombres += re.findall(r"\bdef\s+([A-Za-z_]\w*)", codigo)
    nombres += re.findall(r"\bfor\s+([A-Za-z_]\w*)\s+in\b", codigo)
    for parametros in re.findall(r"\bdef\s+\w+\(([^)]*)\)", codigo):
        nombres += [p.replace("___", "").split("=")[0].strip(" *") for p in parametros.split(",")]
    return sorted({n for n in nombres if n and n not in _RESERVADAS})


def _usa_nombre_del_item(texto: str, item: dict, comunes: frozenset = frozenset()) -> bool:
    plano = texto.replace("`", "")
    for nombre in _nombres_del_item(item):
        if len(nombre) >= 3 and nombre.lower() not in comunes:
            if re.search(rf"(?<![\w.]){re.escape(nombre)}(?!\w)", plano):
                return True
        # Un nombre corto ("n", "x") o que también es palabra del concepto
        # ("entrada") solo cuenta escrito como código.
        elif re.search(rf"`{re.escape(nombre)}`", texto):
            return True
    return False


def _palabras_del_concepto(concepto: str) -> frozenset:
    return frozenset(re.findall(r"\w+", concepto.lower()))


def _menciona_palabra(texto: str, palabra: str) -> bool:
    # Mención de una palabra o símbolo completo, sin distinguir mayúsculas.
    plano = texto.replace("`", "")
    return re.search(rf"(?<![\w.]){re.escape(palabra)}(?!\w)", plano, re.I) is not None


def _palabras_de_solucion(item: dict) -> list[str]:
    # Nombres de función o palabras clave dentro de la solución de completar:
    # en "float(texto)" basta con decir "float" para dar la respuesta.
    palabras = set()
    for solucion in item["solucion"]:
        palabras |= {p for p in re.findall(r"[A-Za-z_]\w*", solucion) if len(p) >= 2}
    return sorted(palabras)


def _formas_de_opcion_correcta(item: dict) -> list[str]:
    # El texto de la opción correcta y, si es un tipo de Python ("float",
    # "<class 'bool'>"), también su nombre en español.
    correcta = next(o["texto"] for o in item["opciones"] if o["clave"] == item["solucion"])
    formas = [correcta]
    tipo = re.fullmatch(r"<class '(\w+)'>|(\w+)", correcta.strip())
    if tipo:
        formas += _SINONIMOS_TIPOS.get(tipo.group(1) or tipo.group(2), [])
    return formas


def _cita_codigo_del_item(oracion: str, item: dict, comunes: frozenset) -> bool:
    codigo = _codigo_del_item(item)
    lineas = [l.strip() for l in codigo.splitlines()]
    if any(len(_normalizar(l)) >= 5 and _contiene(oracion, l) for l in lineas):
        return True
    # Llamadas con argumentos del ejercicio, como `replace("o", "0")`.
    llamadas = re.findall(r"\w+\([^()]+\)", codigo)
    if any(len(_normalizar(l)) >= 6 and _contiene(oracion, l) for l in llamadas):
        return True
    if _usa_nombre_del_item(oracion, item, comunes):
        return True
    # Los valores del ejercicio (textos entre comillas y números de dos o más
    # cifras) permiten narrarlo o deducir la salida por descarte.
    textos = [t for t in re.findall(r"\"([^\"]*)\"|'([^']*)'", codigo) for t in t if len(t.strip()) >= 3]
    numeros = re.findall(r"\b\d+\.\d+\b|\b\d{2,}\b", codigo)
    return any(_menciona(oracion, literal) for literal in textos + numeros)


def _oracion_revela(oracion: str, item: dict | None, comunes: frozenset) -> bool:
    if "?" in oracion or "¿" in oracion:
        return True
    if _REVELA_RESPUESTA.search(oracion) or _METACOMENTARIO.search(oracion):
        return True
    if item is None:
        return False
    if _cita_codigo_del_item(oracion, item, comunes):
        # Citar el ejercicio en prosa es rastrearlo paso a paso.
        return True
    tipo = item["tipo"]
    if tipo in ("prediccion_salida", "opcion_multiple") and re.search(r"-?\d+(\s*,\s*-?\d+){2,}", oracion):
        # Una serie de valores ("son 1, 3, 5, 7, 9") es el rastreo del código.
        return True
    if tipo == "prediccion_salida":
        # Cualquier mención de la salida esperada la revela, aunque la oración
        # no use un verbo como "imprime" ("se convierte en [10, 20]").
        lineas = [l.strip() for l in item["solucion"].splitlines() if l.strip()]
        if any(_menciona(oracion, l) for l in lineas):
            return True
        # Una salida decimal larga también se revela truncada ("1.414").
        decimales = [l for l in lineas if re.fullmatch(r"-?\d+\.\d{3,}", l)]
        return any(_menciona(oracion, l[: l.index(".") + 3]) for l in decimales)
    if tipo == "opcion_multiple":
        # Mencionar la opción correcta ya es la respuesta ("float", "número
        # flotante", "[1, 2, 3, 4]"), con o sin palabras como "respuesta".
        correcta, *sinonimos = _formas_de_opcion_correcta(item)
        return _menciona(oracion, correcta) or any(_menciona_palabra(oracion, s) for s in sinonimos)
    if tipo == "completar_codigo":
        if any(_contiene(oracion, linea) for linea in _lineas_completadas(item)):
            return True
        if any(_contiene(oracion, e) for e in _entornos_completados(item)):
            return True
        # Nombrar lo que va en el espacio es dar la respuesta; un valor de un
        # solo carácter ("0") solo cuenta junto a un verbo de completar.
        for solucion in item["solucion"]:
            if len(solucion.strip()) >= 2 and _menciona(oracion, solucion):
                return True
        if any(
            _menciona_palabra(oracion, p) if p.lower() not in comunes else f"`{p}`" in oracion
            for p in _palabras_de_solucion(item)
        ):
            return True
        sinonimos = [s for sol in item["solucion"] for s in _SINONIMOS_OPERADORES.get(sol.strip(), [])]
        if any(_menciona_palabra(oracion, s) for s in sinonimos):
            return True
        return bool(_VERBOS_COMPLETAR.search(oracion)) and any(_menciona(oracion, s) for s in item["solucion"])
    if tipo == "parsons":
        return sum(_contiene(oracion, l) for l in _lineas_parsons_en_orden(item)) >= 2
    return False


def _oraciones(texto: str) -> list[str]:
    # Oraciones del texto en orden; un bloque de código o un título se marcan
    # con `_CORTE` porque interrumpen el hilo. Los párrafos se unen en uno.
    oraciones = []
    texto = _BLOQUE_CODIGO.sub(f"\n\n{_CORTE}\n\n", texto)
    for parrafo in re.split(r"\n\s*\n", texto):
        for linea in parrafo.splitlines():
            linea = re.sub(r"^\s*([-*•]|\d+[.)])\s+", "", linea).strip()
            if not linea:
                continue
            if linea.startswith("#") or linea == _CORTE:
                oraciones.append(_CORTE)
                continue
            for oracion in _ORACION.split(linea):
                oracion = oracion.strip()
                # Una viñeta sin punto final se une como oración completa.
                oraciones.append(oracion if re.search(r"[.!?…:]$", oracion) else f"{oracion}.")
    return oraciones


def filtrar_explicacion(texto: str, item: dict | None, concepto: str = "") -> str:
    # Devuelve la explicación como un solo párrafo continuo, sin razonamiento
    # interno, preguntas, bloques de código ni fragmentos que revelen la
    # respuesta del ítem. Las palabras de `concepto` se pueden usar en prosa
    # aunque coincidan con un nombre del ítem.
    comunes = _palabras_del_concepto(concepto)
    texto = _RAZONAMIENTO.sub("", texto)
    if "</think>" in texto:
        texto = texto.split("</think>", 1)[1]
    conservadas, vistas = [], set()
    # Al inicio no hay nada a qué referirse, igual que tras retirar algo.
    sin_antecedente = True
    for oracion in _oraciones(texto):
        if oracion == _CORTE:
            sin_antecedente = True
            continue
        clave = re.sub(r"[\"'«»“”]", "", _normalizar(oracion))
        # Menos de tres palabras es un resto de una oración cortada; una
        # presentación ("Por ejemplo:") ya no tiene nada que presentar.
        palabras = re.findall(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]{2,}", oracion)
        if len(palabras) < 3 or oracion.endswith(":") or clave in vistas or _oracion_revela(oracion, item, comunes):
            sin_antecedente = True
            continue
        if sin_antecedente and _DEPENDE_DE_ANTERIOR.match(oracion):
            # "Esto permite...", "En su lugar..." sin la oración a la que aluden.
            continue
        vistas.add(clave)
        conservadas.append(oracion)
        sin_antecedente = False
    return " ".join(conservadas)


def es_suficiente(texto: str) -> bool:
    return len(texto.strip()) >= LONGITUD_MINIMA
