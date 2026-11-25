# Evaluación de las explicaciones del tutor teórico (LLM local vía Ollama).
# Reutiliza el mismo flujo de POST /api/explicacion: ContextoExplicacion ->
# banda_dominio -> generar_explicacion (prompt + Ollama + filtro). El estado
# del aprendiz se construye en memoria; no se lee ni escribe en SQLite.
#
# Uso (desde la raíz del proyecto):
#   python scripts/evaluar_explicaciones.py              genera las 12 explicaciones
#   python scripts/evaluar_explicaciones.py --desde-csv  rehace el anexo .md/.xlsx
#                                                        desde el CSV ya generado
import argparse
import csv
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import yaml  # noqa: E402
from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

from app import llm_service  # noqa: E402
from app.ollama_manager import ollama_manager  # noqa: E402
from config import OLLAMA_MODEL, RUTA_CONCEPTOS  # noqa: E402
from nucleo import modelo_pedagogico  # noqa: E402
from nucleo.modelo_dominio import items_de_concepto_y_nivel  # noqa: E402

CARPETA_SALIDA = RAIZ / "resultados" / "evaluacion_llm"

# Conceptos de la muestra (nombres tal como están en datos/conceptos.yaml).
CONCEPTOS_MUESTRA = (
    "Variables y tipos de datos",
    "Entrada y salida básica",
    "Estructuras condicionales",
    "Bucle for",
)

# Nivel de dominio -> (p_dominio fijo, dificultad del ítem en pantalla).
NIVELES = {"bajo": (0.25, 1), "medio": (0.60, 2), "alto": (0.90, 3)}

COLUMNAS = [
    "id", "concepto", "nivel_dominio", "p_dominio", "modelo", "tiempo_respuesta_s",
    "num_palabras", "explicacion", "correccion_tecnica", "pertinencia",
    "adecuacion_dominio", "claridad", "observaciones",
]

# Criterios de la rúbrica: columna del CSV -> (título, qué se verifica).
CRITERIOS = {
    "correccion_tecnica": ("Corrección técnica", "Lo que afirma sobre Python es correcto y no contiene errores conceptuales."),
    "pertinencia": ("Pertinencia", "Explica el concepto y la parte del ítem en pantalla, sin revelar la respuesta."),
    "adecuacion_dominio": ("Adecuación al dominio", "El registro corresponde al nivel: introductorio (bajo), de refuerzo (medio) o técnico (alto)."),
    "claridad": ("Claridad", "El texto es comprensible, coherente y se lee sin fragmentos sueltos."),
}
ESCALA = ("cumple", "parcial", "no cumple")

_THINK = re.compile(r"<think>.*?</think>", re.S)


def conceptos_por_nombre() -> dict[str, int]:
    datos = yaml.safe_load(RUTA_CONCEPTOS.read_text(encoding="utf-8"))
    return {c["nombre"]: c["id"] for c in datos["conceptos"]}


def verificar_ollama() -> None:
    # Termina con un mensaje claro si Ollama o el modelo no están disponibles.
    if not ollama_manager.comprobar_modelo():
        if not ollama_manager.disponible:
            sys.exit(f"[ERROR] Ollama no está corriendo en {ollama_manager.url}. Inícielo con: ollama serve")
        sys.exit(f"[ERROR] El modelo {OLLAMA_MODEL} no está instalado. Ejecute: ollama pull {OLLAMA_MODEL}")


def calentar_modelo() -> None:
    # Llamada inicial no registrada para cargar el modelo en memoria.
    print(f"Calentando {OLLAMA_MODEL}...")
    try:
        llm_service._solicitar("Responde solo: listo", 0.3)
    except llm_service.OllamaServiceError as exc:
        print(f"[AVISO] El calentamiento falló ({exc}); se continúa con la evaluación.")


def item_en_pantalla(concepto_id: int, dificultad: int) -> dict:
    # Primer ítem del banco del concepto con la dificultad del nivel.
    return items_de_concepto_y_nivel(concepto_id, dificultad)[0]


def generar(concepto: str, concepto_id: int, p_dominio: float, dificultad: int, umbrales: dict) -> tuple[dict, str, float]:
    # Mismo contexto que arma el endpoint, con el ítem en pantalla del nivel.
    item = item_en_pantalla(concepto_id, dificultad)
    contexto = llm_service.ContextoExplicacion(
        concepto=concepto,
        dominio_estimado=p_dominio,
        estado_concepto="en_curso",
        nivel_dificultad=dificultad,
        enunciado_item=item["enunciado"],
        codigo_item=item.get("codigo") or "",
        tipo_item=item["tipo"],
    )
    banda = llm_service.banda_dominio(p_dominio, umbrales["dominio_bajo"], umbrales["dominio_alto"])
    inicio = time.perf_counter()
    try:
        texto = llm_service.generar_explicacion(contexto, banda, item)
        texto = _THINK.sub("", texto).strip()
    except llm_service.OllamaServiceError as exc:
        texto = f"[ERROR] {exc}"
    return item, texto, round(time.perf_counter() - inicio, 2)


def escribir_markdown(filas: list[dict], items: dict[str, dict]) -> None:
    lineas = [f"# Evaluación de explicaciones del tutor teórico ({OLLAMA_MODEL})", ""]
    for concepto in CONCEPTOS_MUESTRA:
        lineas += [f"## {concepto}", ""]
        for fila in (f for f in filas if f["concepto"] == concepto):
            item = items[fila["id"]]
            lineas += [
                f"### {fila['id']} · Dominio {fila['nivel_dominio']} (p_dominio = {fila['p_dominio']:.2f})",
                "",
                f"- Tiempo de respuesta: {fila['tiempo_respuesta_s']:.2f} s · Palabras: {fila['num_palabras']}",
                f"- Ítem en pantalla: {item['id']} ({item['tipo'].replace('_', ' ')}, dificultad {item['dificultad']})",
                "",
                fila["explicacion"],
                "",
            ]
    (CARPETA_SALIDA / "explicaciones.md").write_text("\n".join(lineas), encoding="utf-8")


def escribir_excel(filas: list[dict], items: dict[str, dict]) -> None:
    # Anexo legible: hoja de explicaciones calificables, resumen y método.
    libro = Workbook()
    negrita = Font(bold=True)
    titulo = Font(bold=True, size=14)
    blanco = Font(bold=True, color="FFFFFF")
    fondo_encabezado = PatternFill("solid", fgColor="1F3864")
    fondos_concepto = (PatternFill("solid", fgColor="FFFFFF"), PatternFill("solid", fgColor="EEF3FA"))
    borde = Border(*(Side(style="thin", color="B4BCC8"),) * 4)
    ajustar = Alignment(wrap_text=True, vertical="top")

    def encabezado(hoja, fila: int, textos: list[str]) -> None:
        for col, texto in enumerate(textos, 1):
            celda = hoja.cell(fila, col, texto)
            celda.font, celda.fill, celda.border = blanco, fondo_encabezado, borde
            celda.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")

    # Hoja 1: una fila por explicación, con la rúbrica para calificar.
    hoja = libro.active
    hoja.title = "Explicaciones"
    hoja["A1"] = f"Evaluación de las explicaciones del tutor teórico de Nexora ({OLLAMA_MODEL})"
    hoja["A1"].font = titulo
    hoja["A2"] = "Calificar cada criterio con: cumple / parcial / no cumple (lista desplegable)."
    columnas = [
        ("ID", 8), ("Concepto", 16), ("Nivel de dominio", 10), ("p_dominio", 9), ("Ítem en pantalla", 26),
        ("Tiempo (s)", 9), ("Palabras", 9), ("Explicación generada", 70),
        *[(t, 13) for t, _ in CRITERIOS.values()], ("Observaciones", 30),
    ]
    encabezado(hoja, 4, [c for c, _ in columnas])
    for col, (_, ancho) in enumerate(columnas, 1):
        hoja.column_dimensions[hoja.cell(4, col).column_letter].width = ancho
    lista = DataValidation(type="list", formula1=f'"{",".join(ESCALA)}"', allow_blank=True)
    hoja.add_data_validation(lista)

    for n, fila in enumerate(filas):
        item = items[fila["id"]]
        r = 5 + n
        valores = [
            fila["id"], fila["concepto"], fila["nivel_dominio"], fila["p_dominio"],
            f"{item['id']} ({item['tipo'].replace('_', ' ')}, dificultad {item['dificultad']})\n{item['enunciado']}",
            fila["tiempo_respuesta_s"], fila["num_palabras"], fila["explicacion"],
            *[fila[c] for c in CRITERIOS], fila["observaciones"],
        ]
        fondo = fondos_concepto[CONCEPTOS_MUESTRA.index(fila["concepto"]) % 2]
        for col, valor in enumerate(valores, 1):
            celda = hoja.cell(r, col, valor)
            celda.alignment, celda.border, celda.fill = ajustar, borde, fondo
        hoja.cell(r, 4).number_format = "0.00"
        hoja.cell(r, 6).number_format = "0.00"
        lista.add(f"I{r}:L{r}")
        # Alto aproximado para que la explicación se vea completa.
        hoja.row_dimensions[r].height = max(60, 15 * (len(fila["explicacion"]) // 75 + fila["explicacion"].count("\n") + 1))
    hoja.freeze_panes = "B5"
    hoja.page_setup.orientation = "landscape"
    hoja.page_setup.fitToWidth, hoja.page_setup.fitToHeight = 1, 0
    hoja.sheet_properties.pageSetUpPr.fitToPage = True
    hoja.print_title_rows = "4:4"
    ultima = 4 + len(filas)

    # Hoja 2: tiempos y conteo de la rúbrica (fórmulas: se actualiza al calificar).
    resumen = libro.create_sheet("Resumen")
    resumen["A1"] = "Resumen de la evaluación"
    resumen["A1"].font = titulo
    validas = [f for f in filas if not f["explicacion"].startswith("[ERROR]")]
    tiempos = [f["tiempo_respuesta_s"] for f in validas]
    datos = [
        ("Modelo", OLLAMA_MODEL),
        ("Explicaciones generadas", f"{len(validas)} de {len(filas)}"),
        ("Errores", len(filas) - len(validas)),
        ("Tiempo promedio (s)", round(sum(tiempos) / len(tiempos), 2) if tiempos else "-"),
        ("Tiempo mínimo (s)", min(tiempos, default="-")),
        ("Tiempo máximo (s)", max(tiempos, default="-")),
    ]
    for r, (nombre, valor) in enumerate(datos, 3):
        resumen.cell(r, 1, nombre).font = negrita
        resumen.cell(r, 2, valor)

    r = 4 + len(datos)
    encabezado(resumen, r, ["Nivel de dominio", "p_dominio", "Explicaciones", "Tiempo promedio (s)", "Palabras promedio"])
    for nivel, (p_dominio, _) in NIVELES.items():
        r += 1
        grupo = [f for f in validas if f["nivel_dominio"] == nivel]
        promedio = lambda clave: round(sum(f[clave] for f in grupo) / len(grupo), 2) if grupo else "-"  # noqa: E731
        for col, valor in enumerate([nivel, p_dominio, len(grupo), promedio("tiempo_respuesta_s"), promedio("num_palabras")], 1):
            resumen.cell(r, col, valor).border = borde

    r += 2
    encabezado(resumen, r, ["Criterio", *[e.capitalize() for e in ESCALA], "Sin calificar"])
    for n, (titulo_criterio, _) in enumerate(CRITERIOS.values()):
        r += 1
        letra = "IJKL"[n]
        rango = f"Explicaciones!{letra}5:{letra}{ultima}"
        formulas = [f'=COUNTIF({rango},"{e}")' for e in ESCALA] + [f"=COUNTBLANK({rango})"]
        for col, valor in enumerate([titulo_criterio, *formulas], 1):
            resumen.cell(r, col, valor).border = borde
    for col, ancho in zip("ABCDE", (26, 14, 14, 20, 18)):
        resumen.column_dimensions[col].width = ancho

    # Hoja 3: cómo se generó la muestra y qué mide cada criterio.
    metodo = libro.create_sheet("Método")
    metodo["A1"] = "Método de generación y rúbrica"
    metodo["A1"].font = titulo
    texto_metodo = [
        "Las explicaciones se generaron con el mismo flujo de POST /api/explicacion: contexto del aprendiz, "
        "banda de dominio según los umbrales del modelo pedagógico (0.40 y 0.80), prompt, Ollama y filtro "
        "de explicaciones (retira preguntas y lo que revele la respuesta; reintenta con temperatura 0.6 y 0.8).",
        "El estado del aprendiz se construyó en memoria con p_dominio fijo y estado 'en curso'; no se usó la base de datos.",
        "Ítem en pantalla: el primero del banco del concepto con dificultad 1 (bajo), 2 (medio) o 3 (alto).",
        "Antes de medir se hizo una llamada de calentamiento no registrada. El tiempo se midió con "
        "time.perf_counter() e incluye los reintentos del filtro.",
    ]
    for r, linea in enumerate(texto_metodo, 3):
        metodo.cell(r, 1, linea).alignment = ajustar
        metodo.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
        metodo.row_dimensions[r].height = 45
    r = 4 + len(texto_metodo)
    encabezado(metodo, r, ["Criterio", "Qué se verifica"])
    for titulo_criterio, descripcion in CRITERIOS.values():
        r += 1
        metodo.cell(r, 1, titulo_criterio).border = borde
        celda = metodo.cell(r, 2, descripcion)
        celda.alignment, celda.border = ajustar, borde
        metodo.row_dimensions[r].height = 30
    r += 2
    metodo.cell(r, 1, "Escala").font = negrita
    metodo.cell(r, 2, "cumple: satisface el criterio · parcial: lo satisface con fallas menores · no cumple: no lo satisface")
    metodo.column_dimensions["A"].width = 24
    metodo.column_dimensions["B"].width = 100

    libro.save(CARPETA_SALIDA / "anexo_evaluacion_llm.xlsx")


def leer_csv() -> list[dict]:
    # Recupera las filas ya generadas (incluidas las calificaciones hechas).
    with open(CARPETA_SALIDA / "explicaciones.csv", encoding="utf-8-sig", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    for fila in filas:
        fila["p_dominio"] = float(fila["p_dominio"])
        fila["tiempo_respuesta_s"] = float(fila["tiempo_respuesta_s"])
        fila["num_palabras"] = int(fila["num_palabras"])
    return filas


def imprimir_resumen(filas: list[dict]) -> None:
    validas = [f for f in filas if not f["explicacion"].startswith("[ERROR]")]
    tiempos = [f["tiempo_respuesta_s"] for f in validas]
    print("\n===== Resumen =====")
    print(f"Total generado: {len(validas)} de {len(filas)}")
    print(f"Errores: {len(filas) - len(validas)}")
    if tiempos:
        print(f"Tiempo promedio: {sum(tiempos) / len(tiempos):.2f} s")
        print(f"Tiempo mínimo:   {min(tiempos):.2f} s")
        print(f"Tiempo máximo:   {max(tiempos):.2f} s")
    print("Tiempo promedio por nivel de dominio:")
    for nivel in NIVELES:
        t = [f["tiempo_respuesta_s"] for f in validas if f["nivel_dominio"] == nivel]
        print(f"  {nivel:<6} {sum(t) / len(t):.2f} s ({len(t)} explicaciones)" if t else f"  {nivel:<6} sin datos")
    print(f"\nResultados en: {CARPETA_SALIDA}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evalúa las explicaciones del tutor teórico.")
    parser.add_argument("--desde-csv", action="store_true",
                        help="No llama a Ollama: rehace el anexo desde resultados/evaluacion_llm/explicaciones.csv")
    if parser.parse_args().desde_csv:
        ids = conceptos_por_nombre()
        filas = leer_csv()
        items = {f["id"]: item_en_pantalla(ids[f["concepto"]], NIVELES[f["nivel_dominio"]][1]) for f in filas}
        escribir_markdown(filas, items)
        escribir_excel(filas, items)
        imprimir_resumen(filas)
        return

    verificar_ollama()
    ids = conceptos_por_nombre()
    umbrales = modelo_pedagogico.cargar_reglas()["umbrales"]
    calentar_modelo()

    filas, items = [], {}
    for concepto in CONCEPTOS_MUESTRA:
        for nivel, (p_dominio, dificultad) in NIVELES.items():
            id_fila = f"EX-{len(filas) + 1:02d}"
            item, texto, segundos = generar(concepto, ids[concepto], p_dominio, dificultad, umbrales)
            items[id_fila] = item
            error = texto.startswith("[ERROR]")
            filas.append({
                "id": id_fila, "concepto": concepto, "nivel_dominio": nivel, "p_dominio": p_dominio,
                "modelo": OLLAMA_MODEL, "tiempo_respuesta_s": segundos,
                "num_palabras": 0 if error else len(texto.split()), "explicacion": texto,
                "correccion_tecnica": "", "pertinencia": "", "adecuacion_dominio": "",
                "claridad": "", "observaciones": "",
            })
            print(f"{id_fila} {concepto} · {nivel} ({p_dominio:.2f}): {segundos:.2f} s{' [ERROR]' if error else ''}")

    CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)
    with open(CARPETA_SALIDA / "explicaciones.csv", "w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(filas)
    escribir_markdown(filas, items)
    escribir_excel(filas, items)
    imprimir_resumen(filas)


if __name__ == "__main__":
    main()
