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
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:0.6b")
OLLAMA_TIMEOUT_SEGUNDOS = float(os.getenv("OLLAMA_TIMEOUT_SEGUNDOS", "20"))
OLLAMA_ESPERA_INICIO_SEGUNDOS = float(os.getenv("OLLAMA_ESPERA_INICIO_SEGUNDOS", "30"))
OLLAMA_INTERVALO_COMPROBACION_SEGUNDOS = float(os.getenv("OLLAMA_INTERVALO_COMPROBACION_SEGUNDOS", "0.5"))
