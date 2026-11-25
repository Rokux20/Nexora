from pathlib import Path
import os

RAIZ = Path(__file__).resolve().parent

# --- Base de datos y esquema ---
RUTA_BD = RAIZ / "datos" / "prototipo.db"
RUTA_ESQUEMA_SQL = RAIZ / "persistencia" / "esquema.sql"

# --- Catálogos y contenido declarativo ---
RUTA_BANCO_ITEMS = RAIZ / "datos" / "banco_items.json"
RUTA_REGLAS = RAIZ / "datos" / "reglas.yaml"
RUTA_CATEGORIAS_ERROR = RAIZ / "datos" / "categorias_error.yaml"
RUTA_CONCEPTOS = RAIZ / "datos" / "conceptos.yaml"

# --- Datos sintéticos del simulador ---
RUTA_ENTRENAMIENTO_CSV = RAIZ / "datos" / "sintetico" / "entrenamiento.csv"
RUTA_VALIDACION_CSV = RAIZ / "datos" / "sintetico" / "validacion.csv"

# --- Artefactos del modelo de aprendizaje automático ---
RUTA_MODELO = RAIZ / "ml" / "artefactos" / "estimador_dominio.joblib"
RUTA_COEFICIENTES = RAIZ / "ml" / "artefactos" / "coeficientes.csv"
RUTA_METRICAS = RAIZ / "ml" / "artefactos" / "metricas.json"
RUTA_ROC_SVG = RAIZ / "ml" / "artefactos" / "roc.svg"
RUTA_VALIDACION_MOTOR = RAIZ / "ml" / "artefactos" / "validacion_motor.json"

# --- Modelo del aprendiz ---
# Dominio con el que empieza todo aprendiz nuevo en cada concepto; a partir
# de ahí solo lo mueve el estimador.
P_DOMINIO_INICIAL = 0.0

# --- Reproducibilidad (RNF-09) ---
SEMILLA = 42

# --- Validación de entrada (RNF-10) ---
MAX_LONGITUD_RESPUESTA = 2000
INTENTOS_MAXIMOS_POR_ITEM = 3

# --- Identificación anónima (RF-18) ---
COOKIE_NOMBRE = "aprendiz_id"
COOKIE_MAX_AGE = 31536000

# --- Tutor teórico local (Ollama) ---
# Esta integración no interviene en la estimación de dominio ni en el motor
# pedagógico; solo genera explicaciones bajo demanda.
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
OLLAMA_TIMEOUT_SEGUNDOS = float(os.getenv("OLLAMA_TIMEOUT_SEGUNDOS", "20"))
# Límite para generar (y precargar) el modelo. Debe cubrir una carga en frío:
# si el cliente corta antes, Ollama aborta la carga y nunca llega a quedar listo.
OLLAMA_TIMEOUT_GENERACION_SEGUNDOS = float(os.getenv("OLLAMA_TIMEOUT_GENERACION_SEGUNDOS", "120"))
# Contexto fijo para el tutor. Las explicaciones usan < 1000 tokens; un
# contexto mayor (p. ej. 16k fijado desde la app de Ollama) reserva ~1,2 GB de
# VRAM y en GPU de 4 GB deja capas en CPU: la carga pasa de ~4 s a > 80 s.
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "4096"))
# Tiempo que Ollama mantiene el modelo en memoria. -1 = mientras dure la
# sesión de la aplicación (se libera al cerrarla); acepta también "30m", "1h".
_keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "-1").strip()
OLLAMA_KEEP_ALIVE: int | str = int(_keep_alive) if _keep_alive.lstrip("-").isdigit() else _keep_alive
OLLAMA_ESPERA_INICIO_SEGUNDOS = float(os.getenv("OLLAMA_ESPERA_INICIO_SEGUNDOS", "30"))
OLLAMA_INTERVALO_COMPROBACION_SEGUNDOS = float(os.getenv("OLLAMA_INTERVALO_COMPROBACION_SEGUNDOS", "0.5"))
# Si el modelo no está instalado, se descarga en segundo plano al arrancar
# (OLLAMA_DESCARGA_AUTOMATICA=0 lo desactiva).
OLLAMA_DESCARGA_AUTOMATICA = os.getenv("OLLAMA_DESCARGA_AUTOMATICA", "1").strip().lower() not in ("0", "false", "no")
