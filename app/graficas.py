import colorsys
from html import escape

PAPEL = "#F4F1E8"
TINTA = "#14213D"
TINTA_SUAVE = "#3B4458"
LINEA = "#B9B3A1"
REGLA = "#1B3BD6"
REGLA_CLARO = "#D6DDFA"
MODELO = "#7B2CBF"
MODELO_CLARO = "#EADCF7"
ACIERTO = "#0A6B3D"
ACIERTO_CLARO = "#CDEBDC"
ERROR = "#C81E3A"
ERROR_CLARO = "#F8D8DE"
ATENCION = "#E08C00"
ATENCION_CLARO = "#FCE7BF"
ATENCION_TEXTO = "#8A5300"  # el naranja de las barras no se lee como texto sobre el papel

FUENTE_MONO = "'JetBrains Mono', ui-monospace, monospace"
FUENTE_TEXTO = "'Public Sans', system-ui, sans-serif"

# Las gráficas se diseñan para uno de dos anchos de tarjeta: "completo"
# (ocupa toda la fila) o "medio" (dos por fila). El viewBox se ajusta a
# cada uno para que el texto se vea a ~15 px en pantalla de escritorio.
ANCHO_COMPLETO = 1000
ANCHO_MEDIO = 560
T_NOMBRE = 15
T_VALOR = 14
T_EJE = 13

COLORES_CATEGORIA = {
    # Cinco tonos derivados de la paleta, deliberadamente sin azul ni violeta
    # (reservados para regla/modelo, no se diluyen aquí).
    "sintaxis": "#C81E3A",
    "conceptual": "#8A4B12",
    "logica_algoritmo": "#E08C00",
    "flujo_ejecucion": "#A15843",
    "descuido": "#7A7566",
}

NOMBRES_CATEGORIA = {
    "sintaxis": "Sintaxis",
    "logica_algoritmo": "Lógica o algoritmo",
    "flujo_ejecucion": "Flujo de ejecución",
    "conceptual": "Conceptual",
    "descuido": "Descuido",
}

NOMBRES_ACCION = {
    "avanzar_concepto": "Avanzar de concepto",
    "subir_dificultad": "Subir dificultad",
    "consolidar_mismo_nivel": "Consolidar",
    "continuar_mismo_nivel": "Continuar",
    "apoyo_por_tiempo": "Apoyo por tiempo",
    "pista_progresiva": "Pista progresiva",
    "reforzar_bloqueando_avance": "Reforzar (bloqueado)",
    "reforzar_mismo_nivel": "Reforzar",
}


# ================================================================
# Utilidades de construcción SVG
# ================================================================


def _envolver(contenido: str, ancho: int, alto: int, titulo: str) -> str:
    return (
        f'<svg viewBox="0 0 {ancho} {alto}" preserveAspectRatio="xMidYMin meet" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" width="100%">'
        f"<title>{escape(titulo)}</title>"
        f'<rect x="0" y="0" width="{ancho}" height="{alto}" fill="{PAPEL}" />'
        f"{contenido}</svg>"
    )


def _texto(x, y, contenido, tamano=12, color=TINTA_SUAVE, ancla="start", peso="normal", fuente=FUENTE_TEXTO) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fuente}" font-size="{tamano}" '
        f'fill="{color}" text-anchor="{ancla}" font-weight="{peso}">{escape(str(contenido))}</text>'
    )


def _numero(x, y, contenido, tamano=12, color=TINTA, ancla="start", peso="700") -> str:
    # Los valores van en monoespaciada y en negrita para distinguirlos de los nombres.
    return _texto(x, y, contenido, tamano=tamano, color=color, ancla=ancla, peso=peso, fuente=FUENTE_MONO)


def _rect(x, y, ancho, alto, fill="none", stroke=None, stroke_width=1, opacidad=None, stroke_opacidad=None, radio=0) -> str:
    partes = [f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(0, ancho):.1f}" height="{max(0, alto):.1f}" fill="{fill}"']
    if radio:
        partes.append(f' rx="{radio}"')
    if stroke:
        partes.append(f' stroke="{stroke}" stroke-width="{stroke_width}"')
        if stroke_opacidad is not None:
            partes.append(f' stroke-opacity="{stroke_opacidad}"')
    if opacidad is not None:
        partes.append(f' fill-opacity="{opacidad}"')
    partes.append(" />")
    return "".join(partes)


def _linea(x1, y1, x2, y2, color=LINEA, ancho=1, punteada=False, opacidad=None) -> str:
    trazo = ' stroke-dasharray="4 3"' if punteada else ""
    op = f' stroke-opacity="{opacidad}"' if opacidad is not None else ""
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{color}" stroke-width="{ancho}" stroke-linecap="butt"{trazo}{op} />'
    )


def _polilinea(puntos, color, ancho=2) -> str:
    cadena = " ".join(f"{x:.1f},{y:.1f}" for x, y in puntos)
    return (
        f'<polyline points="{cadena}" fill="none" stroke="{color}" stroke-width="{ancho}" '
        f'stroke-linecap="round" stroke-linejoin="round" />'
    )


def _circulo(x, y, radio, fill, stroke=PAPEL, stroke_width=1.5) -> str:
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radio}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" />'


def _recortar(texto: str, maximo: int) -> str:
    texto = str(texto)
    return texto if len(texto) <= maximo else texto[: maximo - 1].rstrip() + "…"


def _partir(texto: str, maximo: int) -> list:
    # Parte un nombre en, como mucho, dos líneas de `maximo` caracteres.
    palabras, lineas, actual = str(texto).split(), [], ""
    for palabra in palabras:
        candidata = f"{actual} {palabra}".strip()
        if len(candidata) <= maximo or not actual:
            actual = candidata
        else:
            lineas.append(actual)
            actual = palabra
    lineas.append(actual)
    if len(lineas) > 2:
        lineas = [lineas[0], _recortar(" ".join(lineas[1:]), maximo)]
    return lineas


def _pct(valor: float) -> str:
    return f"{valor * 100:.0f}%"


def _separar_etiquetas(posiciones: list, minimo: float, tope: float) -> list:
    # Desplaza etiquetas verticales para que no se encimen (orden ascendente de y).
    orden = sorted(range(len(posiciones)), key=lambda i: posiciones[i])
    ajustadas = list(posiciones)
    previo = None
    for i in orden:
        if previo is not None and ajustadas[i] < previo + minimo:
            ajustadas[i] = previo + minimo
        previo = ajustadas[i]
    exceso = (previo or 0) - tope
    if exceso > 0:
        ajustadas = [y - exceso for y in ajustadas]
    return ajustadas


def _paleta_categorica(n: int) -> list:
    # Genera `n` colores planos distinguibles (evita azul y violeta,
    # reservados para regla/modelo).
    colores = []
    for i in range(n):
        matiz = (i / max(n, 1)) * 0.8  # evita dar la vuelta completa hacia el azul/violeta
        matiz = (matiz + 0.02) % 1.0
        r, g, b = colorsys.hls_to_rgb(matiz, 0.38, 0.55)
        colores.append(f"#{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}")
    return colores


def _grafica_vacia(titulo: str, mensaje: str, ancho: str = "medio") -> dict:
    return {"titulo": titulo, "subtitulo": "", "svg": None, "mensaje_vacio": mensaje, "leyenda": [], "columnas": [], "filas": [], "ancho": ancho}


def _barras_horizontales(filas: list, ancho=ANCHO_MEDIO, margen_izq=200, alto_fila=36, sufijo="") -> tuple:
    # filas: [(nombre, valor, color)]. Devuelve (partes, alto): nombre a la
    # izquierda, barra y valor al final de la barra.
    margen_der, margen_sup = 52, 8
    area_ancho = ancho - margen_izq - margen_der
    alto = margen_sup * 2 + len(filas) * alto_fila
    maximo = max((v for _, v, _ in filas), default=1) or 1
    partes = []
    for i, (nombre, valor, color) in enumerate(filas):
        y = margen_sup + i * alto_fila
        centro = y + alto_fila / 2 + 5
        ancho_barra = (valor / maximo) * area_ancho
        partes.append(_texto(margen_izq - 10, centro, _recortar(nombre, 24), tamano=T_NOMBRE, color=TINTA, ancla="end"))
        partes.append(_rect(margen_izq, y + 7, area_ancho, alto_fila - 14, fill=LINEA, opacidad=0.18, radio=3))
        partes.append(_rect(margen_izq, y + 7, ancho_barra, alto_fila - 14, fill=color, radio=3))
        partes.append(_numero(margen_izq + ancho_barra + 8, centro, f"{valor}{sufijo}", tamano=T_VALOR))
    return partes, alto


# ================================================================
# Vista de progreso (5 gráficas)
# ================================================================


def grafica_dominio_por_concepto(conceptos: list, estados: dict, umbrales: dict) -> dict:
    # 1. Dominio por concepto: barras horizontales, una por cada uno de
    # los 12 conceptos en orden de trayectoria, con el % al final de la barra.
    if not conceptos:
        return _grafica_vacia("Dominio por concepto", "Todavía no hay conceptos cargados.", "completo")

    margen_izq, margen_der, margen_sup, margen_inf = 270, 70, 30, 6
    alto_fila = 32
    ancho = ANCHO_COMPLETO
    area_ancho = ancho - margen_izq - margen_der
    alto = margen_sup + margen_inf + len(conceptos) * alto_fila

    partes = []
    for i in range(len(conceptos)):
        y = margen_sup + i * alto_fila
        partes.append(_rect(margen_izq, y + 7, area_ancho, alto_fila - 14, fill=LINEA, opacidad=0.18, radio=3))

    for umbral_nombre, etiqueta in (("dominio_bajo", "bajo"), ("dominio_alto", "alto")):
        x = margen_izq + umbrales[umbral_nombre] * area_ancho
        partes.append(_linea(x, margen_sup - 6, x, alto - margen_inf, color=TINTA_SUAVE, punteada=True, opacidad=0.7))
        partes.append(_texto(x, margen_sup - 12, f"{etiqueta} {_pct(umbrales[umbral_nombre])}", tamano=T_EJE, ancla="middle"))

    for i, c in enumerate(conceptos):
        y = margen_sup + i * alto_fila
        estado = estados.get(c["id"])
        centro = y + alto_fila / 2 + 5

        partes.append(_numero(14, centro, f"{c['orden']:02d}", tamano=T_EJE, color=TINTA_SUAVE, peso="normal"))
        partes.append(_texto(margen_izq - 12, centro, _recortar(c["nombre"], 30), tamano=T_NOMBRE, color=TINTA, ancla="end"))

        if estado is None:
            partes.append(_texto(margen_izq + 10, centro, "Pendiente", tamano=T_EJE, color=TINTA_SUAVE))
        else:
            color = ACIERTO if estado.estado == "dominado" else MODELO
            ancho_barra = estado.p_dominio_previo * area_ancho
            partes.append(_rect(margen_izq, y + 7, ancho_barra, alto_fila - 14, fill=color, radio=3))
            partes.append(_numero(margen_izq + ancho_barra + 8, centro, _pct(estado.p_dominio_previo), tamano=T_VALOR))

    svg = _envolver("".join(partes), ancho, alto, "Dominio estimado por concepto, con umbrales bajo y alto")

    dominados = sum(1 for e in estados.values() if e.estado == "dominado")
    return {
        "titulo": "Dominio por concepto",
        "subtitulo": f"{dominados} de {len(conceptos)} conceptos dominados.",
        "svg": svg,
        "ancho": "completo",
        "leyenda": [{"color": ACIERTO, "etiqueta": "Dominado"}, {"color": MODELO, "etiqueta": "En progreso"}],
        "columnas": ["Concepto", "Estado", "Dominio estimado"],
        "filas": [
            [c["nombre"], (estados[c["id"]].estado if c["id"] in estados else "pendiente"),
             f"{estados[c['id']].p_dominio_previo:.2f}" if c["id"] in estados else "—"]
            for c in conceptos
        ],
    }


def grafica_evolucion_dominio(series_por_concepto: dict, umbrales: dict) -> dict:
    # 2. Evolución del dominio: una línea por concepto trabajado, a lo
    # largo de todos los intentos históricos (entre sesiones, no solo la
    # actual — CU-05). Cada línea lleva su nombre y valor final al extremo.
    conceptos_con_datos = {k: v for k, v in series_por_concepto.items() if v}
    if not conceptos_con_datos:
        return _grafica_vacia("Evolución del dominio", "Aún no hay suficientes intentos para trazar una evolución.", "completo")

    margen_izq, margen_der, margen_sup, margen_inf = 56, 250, 16, 42
    ancho, alto = ANCHO_COMPLETO, 340
    area_ancho = ancho - margen_izq - margen_der
    area_alto = alto - margen_sup - margen_inf

    min_x = min(punto[0] for serie in conceptos_con_datos.values() for punto in serie)
    max_x = max(punto[0] for serie in conceptos_con_datos.values() for punto in serie)
    rango_x = max(max_x - min_x, 1)

    def coord(indice, valor):
        x = margen_izq + ((indice - min_x) / rango_x) * area_ancho
        y = margen_sup + (1 - valor) * area_alto
        return x, y

    partes = []
    _, y_de_0 = coord(min_x, 0)
    _, y_de_bajo = coord(min_x, umbrales["dominio_bajo"])
    _, y_de_alto = coord(min_x, umbrales["dominio_alto"])
    _, y_de_1 = coord(min_x, 1)
    partes.append(_rect(margen_izq, y_de_bajo, area_ancho, y_de_0 - y_de_bajo, fill=ERROR, opacidad=0.05))
    partes.append(_rect(margen_izq, y_de_alto, area_ancho, y_de_bajo - y_de_alto, fill=ATENCION, opacidad=0.06))
    partes.append(_rect(margen_izq, y_de_1, area_ancho, y_de_alto - y_de_1, fill=ACIERTO, opacidad=0.07))

    # Eje Y con porcentajes y líneas guía.
    for valor in (0, umbrales["dominio_bajo"], umbrales["dominio_alto"], 1):
        _, y = coord(min_x, valor)
        partes.append(_linea(margen_izq, y, margen_izq + area_ancho, y, color=LINEA, opacidad=0.6, punteada=valor not in (0, 1)))
        partes.append(_numero(margen_izq - 10, y + 5, _pct(valor), tamano=T_EJE, color=TINTA_SUAVE, ancla="end", peso="normal"))

    # Eje X: número de intento (1-based), con unas pocas marcas.
    pasos = min(8, rango_x)
    for k in range(pasos + 1):
        indice = min_x + round(k * rango_x / pasos)
        x, _ = coord(indice, 0)
        partes.append(_numero(x, alto - margen_inf + 20, indice + 1, tamano=T_EJE, color=TINTA_SUAVE, ancla="middle", peso="normal"))
    partes.append(_texto(margen_izq + area_ancho / 2, alto - 4, "N.º de intento", tamano=T_EJE, ancla="middle"))

    colores = _paleta_categorica(len(conceptos_con_datos))
    filas_tabla, finales = [], []
    for color, (concepto_nombre, serie) in zip(colores, sorted(conceptos_con_datos.items())):
        puntos = [coord(i, p) for i, p in serie]
        partes.append(_polilinea(puntos, color, ancho=2.5))
        for x, y in puntos:
            partes.append(_circulo(x, y, 3.5, color, stroke_width=1))
        finales.append((puntos[-1], serie[-1][1], concepto_nombre, color))
        for indice, p in serie:
            filas_tabla.append([concepto_nombre, indice + 1, f"{p:.2f}"])

    # Etiqueta al final de cada línea: dominio final y nombre del concepto.
    ys = _separar_etiquetas([y for (_, y), _, _, _ in finales], 19, alto - margen_inf)
    x_etiqueta = margen_izq + area_ancho + 16
    for ((x, y), valor, nombre, color), y_etiqueta in zip(finales, ys):
        partes.append(_linea(x + 5, y, x_etiqueta - 4, y_etiqueta - 5, color=color, punteada=True, opacidad=0.35))
        partes.append(_numero(x_etiqueta, y_etiqueta, _pct(valor), tamano=T_VALOR, color=color))
        partes.append(_texto(x_etiqueta + 46, y_etiqueta, _recortar(nombre, 24), tamano=T_EJE + 1, color=TINTA))

    svg = _envolver("".join(partes), ancho, alto, "Evolución histórica del dominio estimado por concepto")
    return {
        "titulo": "Evolución del dominio",
        "subtitulo": f"{len(conceptos_con_datos)} concepto(s) con historial, {sum(len(s) for s in conceptos_con_datos.values())} intentos en total. Franjas: dominio bajo, intermedio y alto.",
        "svg": svg,
        "ancho": "completo",
        "leyenda": [],
        "columnas": ["Concepto", "N.º de intento", "Dominio estimado"],
        "filas": filas_tabla,
    }


def grafica_errores_por_concepto_categoria(datos: dict) -> dict:
    # 3. Errores por concepto y categoría: barras horizontales apiladas, con
    # el conteo dentro de cada segmento y el total al final.
    conceptos_con_errores = {k: v for k, v in datos.items() if sum(v.values()) > 0}
    if not conceptos_con_errores:
        return _grafica_vacia("Errores por concepto y categoría", "No se han registrado errores todavía.")

    categorias = list(COLORES_CATEGORIA.keys())
    margen_izq, margen_der, margen_sup = 200, 52, 8
    alto_fila = 40
    ancho = ANCHO_MEDIO
    area_ancho = ancho - margen_izq - margen_der
    filas_orden = sorted(conceptos_con_errores.items(), key=lambda kv: sum(kv[1].values()), reverse=True)
    alto = margen_sup * 2 + len(filas_orden) * alto_fila
    maximo = sum(filas_orden[0][1].values()) or 1

    partes = []
    filas_tabla = []
    for i, (concepto_nombre, conteos) in enumerate(filas_orden):
        y = margen_sup + i * alto_fila
        centro = y + alto_fila / 2 + 5
        partes.append(_texto(margen_izq - 10, centro, _recortar(concepto_nombre, 24), tamano=T_NOMBRE, color=TINTA, ancla="end"))
        x = margen_izq
        for categoria in categorias:
            n_cat = conteos.get(categoria, 0)
            if n_cat == 0:
                continue
            ancho_segmento = (n_cat / maximo) * area_ancho
            partes.append(_rect(x, y + 6, ancho_segmento, alto_fila - 12, fill=COLORES_CATEGORIA[categoria], stroke=PAPEL, stroke_width=1))
            if ancho_segmento >= 20:
                color_numero = TINTA if categoria == "logica_algoritmo" else "#FFFFFF"
                partes.append(_numero(x + ancho_segmento / 2, centro, n_cat, tamano=T_EJE, color=color_numero, ancla="middle"))
            x += ancho_segmento
            filas_tabla.append([concepto_nombre, NOMBRES_CATEGORIA[categoria], n_cat])
        partes.append(_numero(x + 8, centro, sum(conteos.values()), tamano=T_VALOR))

    svg = _envolver("".join(partes), ancho, alto, "Errores por concepto y categoría")
    presentes = {c for v in conceptos_con_errores.values() for c, n in v.items() if n > 0}
    leyenda = [{"color": COLORES_CATEGORIA[c], "etiqueta": NOMBRES_CATEGORIA[c]} for c in categorias if c in presentes]
    return {
        "titulo": "Errores por concepto y categoría",
        "subtitulo": f"{sum(sum(v.values()) for v in conceptos_con_errores.values())} errores registrados en {len(filas_orden)} concepto(s). El número final es el total.",
        "svg": svg,
        "ancho": "medio",
        "leyenda": leyenda,
        "columnas": ["Concepto", "Categoría", "Errores"],
        "filas": filas_tabla,
    }


def grafica_acciones_pedagogicas(conteo_acciones: dict) -> dict:
    # 4. Acciones pedagógicas recibidas: barras horizontales, de mayor a menor.
    conteo_acciones = {k: v for k, v in conteo_acciones.items() if v > 0}
    if not conteo_acciones:
        return _grafica_vacia("Acciones pedagógicas recibidas", "Todavía no se ha registrado ninguna decisión del motor de reglas.")

    orden = list(NOMBRES_ACCION.keys())
    datos = sorted(((a, conteo_acciones[a]) for a in orden if a in conteo_acciones), key=lambda kv: kv[1], reverse=True)
    partes, alto = _barras_horizontales([(NOMBRES_ACCION[a], n, REGLA) for a, n in datos])

    svg = _envolver("".join(partes), ANCHO_MEDIO, alto, "Acciones pedagógicas recibidas")
    return {
        "titulo": "Acciones pedagógicas recibidas",
        "subtitulo": f"{sum(v for _, v in datos)} decisiones del motor de reglas en total.",
        "svg": svg,
        "ancho": "medio",
        "leyenda": [],
        "columnas": ["Acción", "Veces"],
        "filas": [[NOMBRES_ACCION[a], n] for a, n in datos],
    }


def grafica_rejilla_trayectoria(conceptos: list, estados: dict) -> dict:
    # 5. Rejilla de trayectoria: una tarjeta por concepto con su nombre y estado.
    if not conceptos:
        return _grafica_vacia("Rejilla de trayectoria", "Todavía no hay conceptos cargados.", "completo")

    columnas = 6
    espacio, margen = 10, 8
    ancho = ANCHO_COMPLETO
    ancho_celda = (ancho - margen * 2 - espacio * (columnas - 1)) / columnas
    alto_celda = 82
    filas_rejilla = -(-len(conceptos) // columnas)
    alto = margen * 2 + filas_rejilla * (alto_celda + espacio) - espacio

    estilos = {
        "dominado": (ACIERTO, ACIERTO, "#FFFFFF", "Dominado"),
        "en_curso": (REGLA_CLARO, REGLA, TINTA, "En progreso"),
        "pendiente": (PAPEL, LINEA, TINTA_SUAVE, "Pendiente"),
    }
    partes = []
    filas_tabla = []
    for i, c in enumerate(conceptos):
        estado = estados.get(c["id"])
        estado_texto = estado.estado if estado else "pendiente"
        relleno, borde, color_texto, etiqueta = estilos.get(estado_texto, estilos["pendiente"])
        x = margen + (i % columnas) * (ancho_celda + espacio)
        y = margen + (i // columnas) * (alto_celda + espacio)
        partes.append(_rect(x, y, ancho_celda, alto_celda, fill=relleno, stroke=borde, stroke_width=1.5, radio=4))
        partes.append(_numero(x + 12, y + 22, f"{c['orden']:02d}", tamano=T_VALOR, color=color_texto))
        detalle = etiqueta + (f" · {_pct(estado.p_dominio_previo)}" if estado else "")
        partes.append(_texto(x + ancho_celda - 12, y + 22, detalle, tamano=12, color=color_texto, ancla="end"))
        for j, linea in enumerate(_partir(c["nombre"], 18)):
            partes.append(_texto(x + 12, y + 48 + j * 18, linea, tamano=T_NOMBRE, color=color_texto, peso="600"))
        filas_tabla.append([c["nombre"], estado_texto])

    svg = _envolver("".join(partes), ancho, alto, "Rejilla de trayectoria de los 12 conceptos")
    dominados = sum(1 for e in estados.values() if e.estado == "dominado")
    return {
        "titulo": "Rejilla de trayectoria",
        "subtitulo": f"{dominados} de {len(conceptos)} conceptos dominados.",
        "svg": svg,
        "ancho": "completo",
        "leyenda": [
            {"color": LINEA, "etiqueta": "Pendiente"},
            {"color": REGLA, "etiqueta": "En progreso"},
            {"color": ACIERTO, "etiqueta": "Dominado"},
        ],
        "columnas": ["Concepto", "Estado"],
        "filas": filas_tabla,
    }


# ================================================================
# Resumen de sesión (4 gráficas)
# ================================================================


def grafica_trayectoria_sesion(puntos: list) -> dict:
    # 1. Trayectoria de la sesión: p_dominio intento a intento, con
    # marcadores por acierto/error, el % sobre cada punto y la regla debajo.
    if not puntos:
        return _grafica_vacia("Trayectoria de la sesión", "Todavía no has respondido ningún ítem en esta sesión.", "completo")

    margen_izq, margen_der, margen_sup, margen_inf = 64, 30, 30, 54
    ancho, alto = ANCHO_COMPLETO, 320
    area_ancho = ancho - margen_izq - margen_der
    area_alto = alto - margen_sup - margen_inf
    paso_x = area_ancho / max(1, len(puntos) - 1) if len(puntos) > 1 else 0

    def coord(i, valor):
        x = margen_izq + (i * paso_x if len(puntos) > 1 else area_ancho / 2)
        y = margen_sup + (1 - valor) * area_alto
        return x, y

    # Con muchos puntos solo se rotulan el primero, el último y los
    # extremos; la línea y todos los marcadores se dibujan igual.
    valores = [p["p_dominio"] for p in puntos]
    todos = len(puntos) <= 24
    if todos:
        indices_etiquetados = set(range(len(puntos)))
    else:
        indices_etiquetados = {0, len(puntos) - 1, valores.index(max(valores)), valores.index(min(valores))}

    partes = []
    for valor in (0, 0.5, 1):
        _, y = coord(0, valor)
        partes.append(_linea(margen_izq, y, margen_izq + area_ancho, y, color=LINEA, opacidad=0.6, punteada=valor == 0.5))
        partes.append(_numero(margen_izq - 10, y + 5, _pct(valor), tamano=T_EJE, color=TINTA_SUAVE, ancla="end", peso="normal"))

    coords = [coord(i, p["p_dominio"]) for i, p in enumerate(puntos)]
    partes.append(_polilinea(coords, MODELO, ancho=2.5))
    for i, (p, (x, y)) in enumerate(zip(puntos, coords)):
        color = ACIERTO if p["es_correcto"] else ERROR
        partes.append(_circulo(x, y, 6.5, color))
        if todos or i in indices_etiquetados or (i + 1) % 5 == 0:
            partes.append(_numero(x, alto - margen_inf + 22, i + 1, tamano=T_EJE, color=TINTA_SUAVE, ancla="middle", peso="normal"))
        if i in indices_etiquetados:
            partes.append(_numero(x, y - 13, _pct(p["p_dominio"]), tamano=T_EJE, ancla="middle"))
            partes.append(_numero(x, alto - margen_inf + 42, p["regla_id"], tamano=12, color=REGLA, ancla="middle", peso="normal"))
    partes.append(_texto(6, alto - margen_inf + 22, "Intento", tamano=12))
    partes.append(_texto(6, alto - margen_inf + 42, "Regla", tamano=12, color=REGLA))

    svg = _envolver("".join(partes), ancho, alto, "Trayectoria del dominio estimado a lo largo de la sesión")
    return {
        "titulo": "Trayectoria de la sesión",
        "subtitulo": f"{len(puntos)} intento(s). Dominio estimado tras cada respuesta y regla que se activó.",
        "svg": svg,
        "ancho": "completo",
        "leyenda": [
            {"color": ACIERTO, "etiqueta": "Acierto"},
            {"color": ERROR, "etiqueta": "Error"},
            {"color": MODELO, "etiqueta": "Dominio estimado"},
        ],
        "columnas": ["#", "Concepto", "Acierto", "p_dominio", "Regla"],
        "filas": [[i + 1, p["concepto_id"], "sí" if p["es_correcto"] else "no", f"{p['p_dominio']:.2f}", p["regla_id"]] for i, p in enumerate(puntos)],
    }


def grafica_aciertos_errores_por_concepto(datos: dict) -> dict:
    # 2. Aciertos y errores por concepto trabajado en la sesión: por cada
    # concepto, dos barras horizontales con su conteo al final.
    if not datos:
        return _grafica_vacia("Aciertos y errores por concepto", "Todavía no has respondido ningún ítem en esta sesión.")

    margen_izq, margen_der, margen_sup = 200, 44, 8
    alto_barra, alto_grupo = 16, 50
    ancho = ANCHO_MEDIO
    area_ancho = ancho - margen_izq - margen_der
    alto = margen_sup * 2 + len(datos) * alto_grupo
    maximo = max(max(v["aciertos"], v["errores"]) for v in datos.values()) or 1

    partes = []
    filas = []
    for i, (concepto_nombre, v) in enumerate(sorted(datos.items())):
        y = margen_sup + i * alto_grupo + 7
        partes.append(_texto(margen_izq - 10, y + alto_barra + 7, _recortar(concepto_nombre, 24), tamano=T_NOMBRE, color=TINTA, ancla="end"))
        for j, (clave, color) in enumerate((("aciertos", ACIERTO), ("errores", ERROR))):
            y_barra = y + j * (alto_barra + 4)
            ancho_barra = (v[clave] / maximo) * area_ancho
            partes.append(_rect(margen_izq, y_barra, ancho_barra, alto_barra, fill=color, radio=2))
            partes.append(_numero(margen_izq + ancho_barra + 7, y_barra + alto_barra - 3, v[clave], tamano=T_VALOR, color=color))
        filas.append([concepto_nombre, v["aciertos"], v["errores"]])

    svg = _envolver("".join(partes), ancho, alto, "Aciertos y errores por concepto en la sesión")
    return {
        "titulo": "Aciertos y errores por concepto",
        "subtitulo": f"{len(datos)} concepto(s) trabajados en esta sesión.",
        "svg": svg,
        "ancho": "medio",
        "leyenda": [{"color": ACIERTO, "etiqueta": "Aciertos"}, {"color": ERROR, "etiqueta": "Errores"}],
        "columnas": ["Concepto", "Aciertos", "Errores"],
        "filas": filas,
    }


def grafica_distribucion_categorias_error(conteo: dict) -> dict:
    # 3. Distribución de categorías de error: barras horizontales, de mayor
    # a menor, con el conteo y el porcentaje del total.
    conteo = {k: v for k, v in conteo.items() if v > 0}
    if not conteo:
        return _grafica_vacia("Distribución de categorías de error", "No se registraron errores en esta sesión.")

    filas_orden = sorted(conteo.items(), key=lambda kv: kv[1], reverse=True)
    total = sum(conteo.values())
    margen_izq, margen_der, margen_sup = 170, 96, 8
    alto_fila = 36
    ancho = ANCHO_MEDIO
    area_ancho = ancho - margen_izq - margen_der
    alto = margen_sup * 2 + len(filas_orden) * alto_fila
    maximo = filas_orden[0][1]

    partes = []
    for i, (categoria, n) in enumerate(filas_orden):
        y = margen_sup + i * alto_fila
        centro = y + alto_fila / 2 + 5
        ancho_barra = (n / maximo) * area_ancho
        partes.append(_texto(margen_izq - 10, centro, NOMBRES_CATEGORIA.get(categoria, categoria), tamano=T_NOMBRE, color=TINTA, ancla="end"))
        partes.append(_rect(margen_izq, y + 7, ancho_barra, alto_fila - 14, fill=COLORES_CATEGORIA.get(categoria, TINTA_SUAVE), radio=3))
        partes.append(_numero(margen_izq + ancho_barra + 8, centro, f"{n} ({n / total:.0%})", tamano=T_VALOR))

    svg = _envolver("".join(partes), ancho, alto, "Distribución de categorías de error en la sesión")
    return {
        "titulo": "Distribución de categorías de error",
        "subtitulo": f"{total} error(es) en total, de mayor a menor frecuencia.",
        "svg": svg,
        "ancho": "medio",
        "leyenda": [],
        "columnas": ["Categoría", "Errores"],
        "filas": [[NOMBRES_CATEGORIA.get(c, c), n] for c, n in filas_orden],
    }


def grafica_tiempo_vs_referencia(tiempos: list) -> dict:
    # 4. Tiempo de respuesta frente al tiempo de referencia: barras
    # verticales desde 1.0× (arriba = más lento, abajo = más rápido), con
    # umbrales en 0.5× y 1.5× y el valor de cada ítem.
    if not tiempos:
        return _grafica_vacia("Tiempo de respuesta frente al tiempo de referencia", "Todavía no has respondido ningún ítem en esta sesión.", "completo")

    margen_izq, margen_der, margen_sup, margen_inf = 60, 20, 24, 62
    ancho, alto = ANCHO_COMPLETO, 360
    area_ancho = ancho - margen_izq - margen_der
    area_alto = alto - margen_sup - margen_inf
    # Eje lineal desde 0× hasta el mayor tiempo (mínimo 2×): las barras
    # parten de 1.0×, así un valor atípico no aplasta al resto.
    tope = max(max(tiempos), 2.0)

    def y_de(t):
        return margen_sup + (1 - t / tope) * area_alto

    centro_y = y_de(1.0)

    partes = []
    for umbral in (0.5, 1.0, 1.5):
        y = y_de(umbral)
        partes.append(_linea(margen_izq, y, margen_izq + area_ancho, y, color=TINTA if umbral == 1.0 else TINTA_SUAVE,
                             punteada=umbral != 1.0, opacidad=0.7))
        partes.append(_numero(margen_izq - 8, y + 5, f"{umbral:.1f}×", tamano=T_EJE, color=TINTA_SUAVE, ancla="end", peso="normal"))

    paso = area_ancho / len(tiempos)
    ancho_barra = min(40, paso * 0.62)
    for i, t in enumerate(tiempos):
        x = margen_izq + i * paso + (paso - ancho_barra) / 2
        centro_x = x + ancho_barra / 2
        y = y_de(t)
        color = ACIERTO if t < 1.0 else (ERROR if t > 1.5 else ATENCION)
        arriba, abajo = min(y, centro_y), max(y, centro_y)
        partes.append(_rect(x, arriba, ancho_barra, max(abajo - arriba, 1.5), fill=color, radio=2))
        if len(tiempos) <= 30:
            y_valor = arriba - 6 if t > 1.0 else abajo + 15
            texto = f"{t:.2f}×" if paso >= 44 else f"{t:.1f}×"
            color_texto = ATENCION_TEXTO if color == ATENCION else color
            partes.append(_numero(centro_x, y_valor, texto, tamano=12 if paso >= 44 else 10.5, color=color_texto, ancla="middle"))
        partes.append(_numero(centro_x, alto - margen_inf + 38, i + 1, tamano=T_EJE, color=TINTA_SUAVE, ancla="middle", peso="normal"))
    partes.append(_texto(margen_izq + area_ancho / 2, alto - 6, "N.º de ítem", tamano=T_EJE, ancla="middle"))

    svg = _envolver("".join(partes), ancho, alto, "Tiempo de respuesta relativo al tiempo de referencia, por ítem")
    return {
        "titulo": "Tiempo de respuesta frente al tiempo de referencia",
        "subtitulo": "1.0× es el tiempo esperado: las barras hacia arriba son respuestas más lentas y hacia abajo más rápidas. Líneas punteadas: umbrales de 0.5× y 1.5×.",
        "svg": svg,
        "ancho": "completo",
        "leyenda": [
            {"color": ACIERTO, "etiqueta": "Más rápido que la referencia"},
            {"color": ATENCION, "etiqueta": "Dentro de lo esperado"},
            {"color": ERROR, "etiqueta": "Más lento que la referencia"},
        ],
        "columnas": ["Ítem #", "Tiempo relativo"],
        "filas": [[i + 1, f"{t:.2f}×"] for i, t in enumerate(tiempos)],
    }
