
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

PASOS = [
    ("Inicializando base de datos y catálogos", [sys.executable, "-m", "persistencia.inicializar"]),
    ("Generando datos sintéticos de entrenamiento (puede tardar 1-2 min)",
     [sys.executable, "-m", "simulador.generar_entrenamiento"]),
    ("Entrenando el estimador de dominio", [sys.executable, "-m", "ml.entrenar"]),
    ("Validando el motor híbrido (puede tardar unos segundos)",
     [sys.executable, "-m", "simulador.validar_motor"]),
]


def main() -> None:
    for i, (descripcion, comando) in enumerate(PASOS, start=1):
        print(f"\n[{i}/{len(PASOS)}] {descripcion}...")
        inicio = time.time()
        resultado = subprocess.run(comando, cwd=RAIZ)
        duracion = time.time() - inicio
        if resultado.returncode != 0:
            print(f"\nFalló el paso {i} ({descripcion}). Revisa el error de arriba.")
            sys.exit(resultado.returncode)
        print(f"    completado en {duracion:.1f}s")

    print("\nListo. Ahora puedes arrancar el servidor con:")
    print("    uvicorn app.main:app --reload --port 8000")
    print("\nY abrir http://127.0.0.1:8000 en el navegador.")


if __name__ == "__main__":
    main()
