import re
import sys
from pathlib import Path

from config import RAIZ

RUTA_CSS = RAIZ / "estatico" / "css"


def verificar_sintaxis_balanceada(ruta: Path) -> list:
    texto = ruta.read_text(encoding="utf-8")
    problemas = []

    abiertas, cerradas = texto.count("{"), texto.count("}")
    if abiertas != cerradas:
        problemas.append(
            f"{ruta}: llaves desbalanceadas ({{={abiertas}, }}={cerradas}) — "
            "probablemente hay un bloque sin cerrar que descarta el resto del archivo."
        )

    apertura_comentarios = len(re.findall(r"/\*", texto))
    cierre_comentarios = len(re.findall(r"\*/", texto))
    if apertura_comentarios != cierre_comentarios:
        problemas.append(
            f"{ruta}: comentarios /* */ desbalanceados "
            f"(/*={apertura_comentarios}, */={cierre_comentarios})."
        )

    return problemas


def verificar_tokens_de_tema(ruta: Path) -> list:
   
    texto = ruta.read_text(encoding="utf-8")
    problemas = []
    if ":root" not in texto:
        problemas.append(f"{ruta}: no se encontró un bloque :root con los tokens del tema claro.")
    if 'data-theme="dark"' not in texto and "prefers-color-scheme: dark" not in texto:
        problemas.append(f"{ruta}: no se encontró un bloque de tokens para el tema oscuro.")
    return problemas


def verificar() -> list:
    problemas = []
    for ruta in sorted(RUTA_CSS.rglob("*.css")):
        problemas.extend(verificar_sintaxis_balanceada(ruta))
        problemas.extend(verificar_tokens_de_tema(ruta))
    return problemas


if __name__ == "__main__":
    problemas = verificar()
    if problemas:
        print(f"{len(problemas)} PROBLEMA(S) ENCONTRADO(S):")
        for p in problemas:
            print(" -", p)
        sys.exit(1)
    print("Verificación de estilo: CSS bien formado, con tokens de tema claro y oscuro definidos.")
