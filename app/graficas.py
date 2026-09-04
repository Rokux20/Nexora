import colorsys
from html import escape

PAPEL = "#F4F1E8"
TINTA = "#14213D"
TINTA_SUAVE = "#55607A"
LINEA = "#B9B3A1"
REGLA = "#1B3BD6"
REGLA_CLARO = "#D6DDFA"
MODELO = "#7B2CBF"
MODELO_CLARO = "#EADCF7"
ACIERTO = "#0E7C4A"
ACIERTO_CLARO = "#CDEBDC"
ERROR = "#C81E3A"
ERROR_CLARO = "#F8D8DE"
ATENCION = "#E08C00"
ATENCION_CLARO = "#FCE7BF"

FUENTE_MONO = "'JetBrains Mono', ui-monospace, monospace"

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


def _texto(x, y, contenido, tamano=10, color=TINTA_SUAVE, ancla="start", peso="normal") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FUENTE_MONO}" font-size="{tamano}" '
        f'fill="{color}" text-anchor="{ancla}" font-weight="{peso}">{escape(str(contenido))}</text>'
    )


def _rect(x, y, ancho, alto, fill="none", stroke=None, stroke_width=1, opacidad=None, stroke_opacidad=None) -> str:
    partes = [f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(0, ancho):.1f}" height="{max(0, alto):.1f}" fill="{fill}"']
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
        f'stroke-linecap="butt" stroke-linejoin="miter" />'
    )


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


def _grafica_vacia(titulo: str, mensaje: str) -> dict:
    return {"titulo": titulo, "subtitulo": "", "svg": None, "mensaje_vacio": mensaje, "leyenda": [], "columnas": [], "filas": []}


# ================================================================
# Vista de progreso (5 gráficas)
# ================================================================


def grafica_dominio_por_concepto(conceptos: list, estados: dict, umbrales: dict) -> dict:
    # 1. Dominio por concepto: barras horizontales, una por cada uno de
    # los 12 conceptos en orden de trayectoria.
    if not conceptos:
        return _grafica_vacia("Dominio por concepto", "Todavía no hay conceptos cargados.")

    margen_izq, margen_der, margen_sup = 168, 40, 10
    alto_fila = 18
    ancho = 560
    area_ancho = ancho - margen_izq - margen_der
    alto = margen_sup * 2 + len(conceptos) * alto_fila

    partes = []
    for i, c in enumerate(conceptos):
        y = margen_sup + i * alto_fila
        estado = estados.get(c["id"])
        p_dominio = estado.p_dominio_previo if estado else None
        etiqueta_y = y + alto_fila / 2 + 3

        partes.append(_texto(margen_izq - 8, etiqueta_y, f"{c['orden']:02d}. {c['nombre']}", tamano=10, ancla="end"))

        if estado is None:
            partes.append(_rect(margen_izq, y + 3, area_ancho, alto_fila - 6, stroke=LINEA, stroke_opacidad=0.5))
            partes.append(_texto(margen_izq + 6, etiqueta_y, "pendiente", tamano=10, color=TINTA_SUAVE))
        else:
            ancho_barra = p_dominio * area_ancho
            partes.append(_rect(margen_izq, y + 3, area_ancho, alto_fila - 6, stroke=LINEA, stroke_opacidad=0.5))
            partes.append(_rect(margen_izq, y + 3, ancho_barra, alto_fila - 6, fill=MODELO))
            partes.append(_texto(margen_izq + area_ancho + 6, etiqueta_y, f"{p_dominio:.2f}", tamano=10, color=TINTA))

    for umbral_nombre in ("dominio_bajo", "dominio_alto"):
        x = margen_izq + umbrales[umbral_nombre] * area_ancho
        partes.append(_linea(x, margen_sup - 3, x, alto - margen_sup + 3, color=TINTA_SUAVE, punteada=True, opacidad=0.6))

    svg = _envolver("".join(partes), ancho, alto, "Dominio estimado por concepto, con umbrales en 0.40 y 0.80")

    dominados = sum(1 for e in estados.values() if e.estado == "dominado")
    return {
        "titulo": "Dominio por concepto",
        "subtitulo": f"{dominados} de {len(conceptos)} conceptos dominados. Líneas punteadas: umbrales bajo (0.40) y alto (0.80).",
        "svg": svg,
        "leyenda": [{"color": MODELO, "etiqueta": "Dominio estimado (modelo)"}],
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
    # actual — CU-05).
    conceptos_con_datos = {k: v for k, v in series_por_concepto.items() if v}
    if not conceptos_con_datos:
        return _grafica_vacia("Evolución del dominio", "Aún no hay suficientes intentos para trazar una evolución.")

    margen_izq, margen_der, margen_sup, margen_inf = 34, 12, 10, 8
    ancho, alto = 560, 230
    area_ancho = ancho - margen_izq - margen_der
    area_alto = alto - margen_sup - margen_inf

    max_x = max(punto[0] for serie in conceptos_con_datos.values() for punto in serie)
    max_x = max(max_x, 1)

    def coord(indice, valor):
        x = margen_izq + (indice / max_x) * area_ancho
        y = margen_sup + (1 - valor) * area_alto
        return x, y

    partes = []
    banda_baja_y0, _ = coord(0, umbrales["dominio_bajo"])
    banda_alta_y0, _ = coord(0, umbrales["dominio_alto"])
    _, y_de_0 = coord(0, 0)
    _, y_de_bajo = coord(0, umbrales["dominio_bajo"])
    _, y_de_alto = coord(0, umbrales["dominio_alto"])
    _, y_de_1 = coord(0, 1)
    partes.append(_rect(margen_izq, y_de_bajo, area_ancho, y_de_0 - y_de_bajo, fill=ERROR, opacidad=0.06))
    partes.append(_rect(margen_izq, y_de_alto, area_ancho, y_de_bajo - y_de_alto, fill=ATENCION, opacidad=0.06))
    partes.append(_rect(margen_izq, y_de_1, area_ancho, y_de_alto - y_de_1, fill=ACIERTO, opacidad=0.06))
    partes.append(_rect(margen_izq, margen_sup, area_ancho, area_alto, stroke=LINEA, stroke_opacidad=0.5))

    colores = _paleta_categorica(len(conceptos_con_datos))
    leyenda = []
    filas_tabla = []
    for color, (concepto_nombre, serie) in zip(colores, sorted(conceptos_con_datos.items())):
        puntos = [coord(i, p) for i, p in serie]
        partes.append(_polilinea(puntos, color, ancho=1.5))
        leyenda.append({"color": color, "etiqueta": concepto_nombre})
        for indice, p in serie:
            filas_tabla.append([concepto_nombre, indice, f"{p:.2f}"])

    svg = _envolver("".join(partes), ancho, alto, "Evolución histórica del dominio estimado por concepto")
    return {
        "titulo": "Evolución del dominio",
        "subtitulo": f"{len(conceptos_con_datos)} concepto(s) con historial, {sum(len(s) for s in conceptos_con_datos.values())} intentos en total.",
        "svg": svg,
        "leyenda": leyenda,
        "columnas": ["Concepto", "N.º de intento", "Dominio estimado"],
        "filas": filas_tabla,
    }


def grafica_errores_por_concepto_categoria(datos: dict) -> dict:
    # 3. Errores por concepto y categoría: barras apiladas verticales.
    conceptos_con_errores = {k: v for k, v in datos.items() if sum(v.values()) > 0}
    if not conceptos_con_errores:
        return _grafica_vacia("Errores por concepto y categoría", "No se han registrado errores todavía.")

    categorias = list(COLORES_CATEGORIA.keys())
    ancho_barra, espacio = 30, 16
    margen_izq, margen_der, margen_sup, margen_inf = 24, 12, 10, 40
    n = len(conceptos_con_errores)
    ancho = margen_izq + margen_der + n * (ancho_barra + espacio)
    alto = 220
    area_alto = alto - margen_sup - margen_inf
    maximo = max(sum(v.values()) for v in conceptos_con_errores.values()) or 1

    partes = [_linea(margen_izq, alto - margen_inf, ancho - margen_der, alto - margen_inf, color=TINTA_SUAVE, opacidad=0.5)]
    filas_tabla = []
    for i, (concepto_nombre, conteos) in enumerate(sorted(conceptos_con_errores.items())):
        x = margen_izq + i * (ancho_barra + espacio) + espacio / 2
        y_acumulado = alto - margen_inf
        for categoria in categorias:
            n_cat = conteos.get(categoria, 0)
            if n_cat == 0:
                continue
            alto_segmento = (n_cat / maximo) * area_alto
            y_acumulado -= alto_segmento
            partes.append(_rect(x, y_acumulado, ancho_barra, alto_segmento, fill=COLORES_CATEGORIA[categoria]))
            filas_tabla.append([concepto_nombre, NOMBRES_CATEGORIA[categoria], n_cat])
        partes.append(_texto(x + ancho_barra / 2, alto - margen_inf + 14, concepto_nombre[:10], ancla="middle", tamano=9))

    svg = _envolver("".join(partes), ancho, alto, "Errores por concepto y categoría")
    leyenda = [{"color": COLORES_CATEGORIA[c], "etiqueta": NOMBRES_CATEGORIA[c]} for c in categorias]
    return {
        "titulo": "Errores por concepto y categoría",
        "subtitulo": f"{sum(sum(v.values()) for v in conceptos_con_errores.values())} errores registrados en {n} concepto(s).",
        "svg": svg,
        "leyenda": leyenda,
        "columnas": ["Concepto", "Categoría", "Errores"],
        "filas": filas_tabla,
    }


def grafica_acciones_pedagogicas(conteo_acciones: dict) -> dict:
    # 4. Acciones pedagógicas recibidas: barras verticales, conteo por acción.
    conteo_acciones = {k: v for k, v in conteo_acciones.items() if v > 0}
    if not conteo_acciones:
        return _grafica_vacia("Acciones pedagógicas recibidas", "Todavía no se ha registrado ninguna decisión del motor de reglas.")

    orden = list(NOMBRES_ACCION.keys())
    datos = [(a, conteo_acciones[a]) for a in orden if a in conteo_acciones]
    ancho_barra, espacio = 34, 14
    margen_izq, margen_der, margen_sup, margen_inf = 24, 12, 14, 54
    ancho = margen_izq + margen_der + len(datos) * (ancho_barra + espacio)
    alto = 220
    area_alto = alto - margen_sup - margen_inf
    maximo = max(v for _, v in datos)

    partes = [_linea(margen_izq, alto - margen_inf, ancho - margen_der, alto - margen_inf, color=TINTA_SUAVE, opacidad=0.5)]
    for i, (accion, n) in enumerate(datos):
        x = margen_izq + i * (ancho_barra + espacio) + espacio / 2
        alto_barra = (n / maximo) * area_alto
        y = alto - margen_inf - alto_barra
        partes.append(_rect(x, y, ancho_barra, alto_barra, fill=REGLA))
        partes.append(_texto(x + ancho_barra / 2, y - 5, n, ancla="middle", tamano=10, color=TINTA))
        for j, palabra in enumerate(NOMBRES_ACCION[accion].split()):
            partes.append(_texto(x + ancho_barra / 2, alto - margen_inf + 13 + j * 11, palabra, ancla="middle", tamano=9))

    svg = _envolver("".join(partes), ancho, alto, "Acciones pedagógicas recibidas")
    return {
        "titulo": "Acciones pedagógicas recibidas",
        "subtitulo": f"{sum(v for _, v in datos)} decisiones del motor de reglas en total.",
        "svg": svg,
        "leyenda": [{"color": REGLA, "etiqueta": "Decisión del motor de reglas"}],
        "columnas": ["Acción", "Veces"],
        "filas": [[NOMBRES_ACCION[a], n] for a, n in datos],
    }


def grafica_rejilla_trayectoria(conceptos: list, estados: dict) -> dict:
    # 5. Rejilla de trayectoria: 12 celdas, una por concepto.
    if not conceptos:
        return _grafica_vacia("Rejilla de trayectoria", "Todavía no hay conceptos cargados.")

    lado, espacio, margen = 40, 5, 8
    ancho = margen * 2 + len(conceptos) * (lado + espacio) - espacio
    alto = margen * 2 + lado + 16

    definiciones = (
        '<defs><pattern id="trama-en-curso" width="8" height="8" patternUnits="userSpaceOnUse" '
        f'patternTransform="rotate(45)"><rect width="8" height="8" fill="{PAPEL}" />'
        f'<line x1="0" y1="0" x2="0" y2="8" stroke="{LINEA}" stroke-width="4" /></pattern></defs>'
    )
    partes = [definiciones]
    filas_tabla = []
    for i, c in enumerate(conceptos):
        estado = estados.get(c["id"])
        estado_texto = estado.estado if estado else "pendiente"
        x = margen + i * (lado + espacio)
        y = margen
        if estado_texto == "dominado":
            relleno = REGLA
        elif estado_texto == "en_curso":
            relleno = "url(#trama-en-curso)"
        else:
            relleno = PAPEL
        partes.append(_rect(x, y, lado, lado, fill=relleno, stroke=TINTA, stroke_width=1))
        color_num = PAPEL if estado_texto == "dominado" else TINTA
        partes.append(_texto(x + lado / 2, y + lado / 2 + 4, c["orden"], ancla="middle", color=color_num, tamano=12))
        partes.append(_texto(x + lado / 2, y + lado + 12, estado_texto[:3], ancla="middle", tamano=8))
        filas_tabla.append([c["nombre"], estado_texto])

    svg = _envolver("".join(partes), ancho, alto, "Rejilla de trayectoria de los 12 conceptos")
    dominados = sum(1 for e in estados.values() if e.estado == "dominado")
    return {
        "titulo": "Rejilla de trayectoria",
        "subtitulo": f"{dominados} de {len(conceptos)} conceptos dominados.",
        "svg": svg,
        "leyenda": [
            {"color": PAPEL, "etiqueta": "Pendiente"},
            {"color": LINEA, "etiqueta": "En curso"},
            {"color": REGLA, "etiqueta": "Dominado"},
        ],
        "columnas": ["Concepto", "Estado"],
        "filas": filas_tabla,
    }


# ================================================================
# Resumen de sesión (4 gráficas)
# ================================================================


def grafica_trayectoria_sesion(puntos: list) -> dict:
    # 1. Trayectoria de la sesión: p_dominio intento a intento, con
    # marcadores por acierto/error y el ID de regla bajo cada punto.
    if not puntos:
        return _grafica_vacia("Trayectoria de la sesión", "Todavía no has respondido ningún ítem en esta sesión.")

    margen_izq, margen_der, margen_sup, margen_inf = 28, 12, 10, 26
    ancho = max(320, margen_izq + margen_der + (len(puntos) - 1) * 34 + 16)
    alto = 200
    area_ancho = ancho - margen_izq - margen_der
    area_alto = alto - margen_sup - margen_inf
    paso_x = area_ancho / max(1, len(puntos) - 1) if len(puntos) > 1 else 0

    def coord(i, valor):
        x = margen_izq + (i * paso_x if len(puntos) > 1 else area_ancho / 2)
        y = margen_sup + (1 - valor) * area_alto
        return x, y

    # Densidad de etiquetas: solo el primero, el último y los extremos de
    # p_dominio llevan el ID de regla debajo — el resto de los puntos y la
    # línea completa se dibujan igual, con todos los datos.
    indices_etiquetados = {0, len(puntos) - 1}
    valores = [p["p_dominio"] for p in puntos]
    indices_etiquetados.add(valores.index(max(valores)))
    indices_etiquetados.add(valores.index(min(valores)))

    partes = [_rect(margen_izq, margen_sup, area_ancho, area_alto, stroke=LINEA, stroke_opacidad=0.5)]
    coords = [coord(i, p["p_dominio"]) for i, p in enumerate(puntos)]
    partes.append(_polilinea(coords, MODELO, ancho=1.5))
    for i, (p, (x, y)) in enumerate(zip(puntos, coords)):
        color = ACIERTO if p["es_correcto"] else ERROR
        lado = 6
        partes.append(_rect(x - lado / 2, y - lado / 2, lado, lado, fill=color))
        if i in indices_etiquetados:
            partes.append(_texto(x, alto - margen_inf + 14, p["regla_id"], ancla="middle", tamano=9, color=REGLA))

    svg = _envolver("".join(partes), ancho, alto, "Trayectoria de p_dominio a lo largo de la sesión")
    return {
        "titulo": "Trayectoria de la sesión",
        "subtitulo": f"{len(puntos)} intento(s). Cuadros verdes: acierto; rojos: error. Etiquetas: regla activada.",
        "svg": svg,
        "leyenda": [
            {"color": ACIERTO, "etiqueta": "Acierto"},
            {"color": ERROR, "etiqueta": "Error"},
            {"color": MODELO, "etiqueta": "p_dominio estimado"},
        ],
        "columnas": ["#", "Concepto", "Acierto", "p_dominio", "Regla"],
        "filas": [[i + 1, p["concepto_id"], "sí" if p["es_correcto"] else "no", f"{p['p_dominio']:.2f}", p["regla_id"]] for i, p in enumerate(puntos)],
    }


def grafica_aciertos_errores_por_concepto(datos: dict) -> dict:
    # 2. Aciertos y errores por concepto trabajado en la sesión (barras agrupadas).
    if not datos:
        return _grafica_vacia("Aciertos y errores por concepto", "Todavía no has respondido ningún ítem en esta sesión.")

    ancho_barra, espacio_barras, espacio_grupo = 14, 3, 18
    margen_izq, margen_der, margen_sup, margen_inf = 24, 12, 14, 32
    n = len(datos)
    ancho = margen_izq + margen_der + n * (ancho_barra * 2 + espacio_barras + espacio_grupo)
    alto = 200
    area_alto = alto - margen_sup - margen_inf
    maximo = max(max(v["aciertos"], v["errores"]) for v in datos.values()) or 1

    partes = [_linea(margen_izq, alto - margen_inf, ancho - margen_der, alto - margen_inf, color=TINTA_SUAVE, opacidad=0.5)]
    filas = []
    for i, (concepto_nombre, v) in enumerate(sorted(datos.items())):
        x0 = margen_izq + i * (ancho_barra * 2 + espacio_barras + espacio_grupo) + espacio_grupo / 2
        alto_a = (v["aciertos"] / maximo) * area_alto
        alto_e = (v["errores"] / maximo) * area_alto
        partes.append(_rect(x0, alto - margen_inf - alto_a, ancho_barra, alto_a, fill=ACIERTO))
        partes.append(_rect(x0 + ancho_barra + espacio_barras, alto - margen_inf - alto_e, ancho_barra, alto_e, fill=ERROR))
        centro = x0 + ancho_barra + espacio_barras / 2
        partes.append(_texto(centro, alto - margen_inf + 13, concepto_nombre[:9], ancla="middle", tamano=9))
        filas.append([concepto_nombre, v["aciertos"], v["errores"]])

    svg = _envolver("".join(partes), ancho, alto, "Aciertos y errores por concepto en la sesión")
    return {
        "titulo": "Aciertos y errores por concepto",
        "subtitulo": f"{n} concepto(s) trabajados en esta sesión.",
        "svg": svg,
        "leyenda": [{"color": ACIERTO, "etiqueta": "Aciertos"}, {"color": ERROR, "etiqueta": "Errores"}],
        "columnas": ["Concepto", "Aciertos", "Errores"],
        "filas": filas,
    }


def grafica_distribucion_categorias_error(conteo: dict) -> dict:
    # 3. Distribución de categorías de error: barras horizontales, de mayor a menor.
    conteo = {k: v for k, v in conteo.items() if v > 0}
    if not conteo:
        return _grafica_vacia("Distribución de categorías de error", "No se registraron errores en esta sesión.")

    filas_orden = sorted(conteo.items(), key=lambda kv: kv[1], reverse=True)
    margen_izq, margen_der, margen_sup = 128, 34, 8
    alto_fila = 24
    ancho = 480
    area_ancho = ancho - margen_izq - margen_der
    alto = margen_sup * 2 + len(filas_orden) * alto_fila
    maximo = filas_orden[0][1]

    partes = []
    for i, (categoria, n) in enumerate(filas_orden):
        y = margen_sup + i * alto_fila
        ancho_barra = (n / maximo) * area_ancho
        partes.append(_texto(margen_izq - 8, y + alto_fila / 2 + 3, NOMBRES_CATEGORIA.get(categoria, categoria), tamano=10, ancla="end"))
        partes.append(_rect(margen_izq, y + 5, ancho_barra, alto_fila - 10, fill=COLORES_CATEGORIA.get(categoria, TINTA_SUAVE)))
        partes.append(_texto(margen_izq + ancho_barra + 6, y + alto_fila / 2 + 3, n, tamano=10, color=TINTA))

    svg = _envolver("".join(partes), ancho, alto, "Distribución de categorías de error en la sesión")
    return {
        "titulo": "Distribución de categorías de error",
        "subtitulo": f"{sum(conteo.values())} error(es) en total, de mayor a menor frecuencia.",
        "svg": svg,
        "leyenda": [],
        "columnas": ["Categoría", "Errores"],
        "filas": [[NOMBRES_CATEGORIA.get(c, c), n] for c, n in filas_orden],
    }


def grafica_tiempo_vs_referencia(tiempos: list) -> dict:
    # 4. Tiempo de respuesta frente al tiempo de referencia: barras
    # divergentes desde 1.0×, con umbrales en 0.5× y 1.5×.
    if not tiempos:
        return _grafica_vacia("Tiempo de respuesta frente al tiempo de referencia", "Todavía no has respondido ningún ítem en esta sesión.")

    margen_izq, margen_der, margen_sup, margen_inf = 12, 12, 8, 14
    alto_fila = 18
    ancho = 480
    centro_x = ancho / 2
    # Límite del eje: el mayor desvío absoluto respecto a 1.0, con un mínimo razonable.
    max_desvio = max(max(abs(t - 1.0) for t in tiempos), 1.0)
    area_medio_ancho = (ancho - margen_izq - margen_der) / 2 - 8
    alto = margen_sup * 2 + len(tiempos) * alto_fila

    def escala(valor):
        return (valor / max_desvio) * area_medio_ancho

    partes = [_linea(centro_x, margen_sup - 3, centro_x, alto - margen_inf + 3, color=TINTA, opacidad=0.7)]
    for umbral, factor in ((0.5, -1), (1.5, 1)):
        x = centro_x + factor * escala(abs(umbral - 1.0))
        partes.append(_linea(x, margen_sup - 3, x, alto - margen_inf + 3, color=TINTA_SUAVE, punteada=True, opacidad=0.6))

    for i, t in enumerate(tiempos):
        y = margen_sup + i * alto_fila
        desvio = escala(abs(t - 1.0))
        color = ACIERTO if t < 1.0 else (ERROR if t > 1.5 else ATENCION)
        if t <= 1.0:
            partes.append(_rect(centro_x - desvio, y + 4, desvio, alto_fila - 8, fill=color))
        else:
            partes.append(_rect(centro_x, y + 4, desvio, alto_fila - 8, fill=color))

    svg = _envolver("".join(partes), ancho, alto, "Tiempo de respuesta relativo al tiempo de referencia, por ítem")
    return {
        "titulo": "Tiempo de respuesta frente al tiempo de referencia",
        "subtitulo": "Línea central: 1.0×. Líneas punteadas: umbrales de tiempo corto (0.5×) y largo (1.5×) que usa el motor de reglas.",
        "svg": svg,
        "leyenda": [
            {"color": ACIERTO, "etiqueta": "Más rápido que la referencia"},
            {"color": ATENCION, "etiqueta": "Dentro de lo esperado"},
            {"color": ERROR, "etiqueta": "Más lento que la referencia"},
        ],
        "columnas": ["Ítem #", "Tiempo relativo"],
        "filas": [[i + 1, f"{t:.2f}×"] for i, t in enumerate(tiempos)],
    }
