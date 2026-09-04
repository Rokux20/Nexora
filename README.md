# Prototipo de plataforma de aprendizaje adaptativo para programación

## 1. Qué es

Un prototipo académico que demuestra un **motor de adaptación híbrido**:
cada respuesta de un aprendiz se convierte en una estimación probabilística
de dominio (un modelo de aprendizaje automático interpretable) y en una
decisión pedagógica (un motor de reglas declarativo) que consume esa
estimación. La decisión siempre es explicable: se registra la regla
activada y los factores que la sustentaron. Este prototipo acompaña la
monografía *"Prototipo de plataforma de aprendizaje adaptativo para
programación con un motor de adaptación híbrido basado en reglas y
aprendizaje automático"* (Edwin Steven Herrera Delgado, Universidad de
Cundinamarca — Extensión Chía, 2026). No es una plataforma educativa de
producción: no hay registro de usuarios, autenticación real ni pagos.

## 2. Requisitos previos

- **Python 3.11 o superior.** Verifica tu versión con:
  ```bash
  python --version
  ```
  Si el resultado es menor a `3.11`, instala una versión más reciente
  desde [python.org](https://www.python.org/downloads/) antes de continuar.
- `pip` (incluido con Python).
- ~200 MB de espacio libre en disco (dependencias + artefactos del modelo).
- No necesitas conexión a internet una vez instaladas las dependencias:
  el prototipo funciona completamente en local.

## 3. Instalación paso a paso

**Linux / macOS:**
```bash
git clone <repo> && cd prototipo-adaptativo
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**
```powershell
git clone <repo>; cd prototipo-adaptativo
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Si ya tienes el código descargado (sin `git clone`), simplemente sitúate
en la carpeta del proyecto y ejecuta desde ahí los comandos de `venv` en
adelante.

## 4. Preparación de datos y modelo

Un solo comando hace los cuatro pasos siguientes, en orden:

```bash
python scripts/preparar.py
```

Desglose por si quieres ejecutar los pasos por separado (por ejemplo, para
inspeccionar la salida de cada uno):

```bash
python -m persistencia.inicializar          # 1. crea SQLite y carga catálogos       (~1 s)
python -m simulador.generar_entrenamiento   # 2. genera CSV sintéticos               (~1-2 min)
python -m ml.entrenar                       # 3. entrena y guarda el .joblib         (~3 s)
python -m simulador.validar_motor           # 4. valida el motor híbrido             (~20 s)
```

**Salida esperada de cada paso:**

1. *Inicializar*: imprime cuántos conceptos (12), categorías de error (5)
   y reglas (9) se cargaron.
2. *Generar entrenamiento*: imprime cuántos aprendices virtuales y filas
   se generaron para `datos/sintetico/entrenamiento.csv` y `validacion.csv`.
3. *Entrenar*: imprime las métricas de validación (accuracy, precision,
   recall, F1, ROC-AUC) y la tabla de coeficientes del modelo, cada uno
   con su lectura en lenguaje natural.
4. *Validar motor*: imprime la correlación entre `p_dominio` estimada y el
   dominio latente simulado (debe ser positiva), y qué proporción de
   aprendices con dominio alto/bajo recibieron la acción esperada.

## 5. Ejecución

```bash
uvicorn app.main:app --reload --port 8000
```

Abre `http://127.0.0.1:8000` en el navegador — redirige automáticamente a
la vista de práctica. La documentación interactiva de la API (generada
automáticamente por FastAPI) está en `http://127.0.0.1:8000/docs`.

### Tutor teórico local (Ollama)

La aplicación comprueba e inicia automáticamente `ollama serve` al arrancar,
si Ollama está instalado localmente. Solo necesitas descargar el modelo una
vez:

```bash
ollama pull qwen3:0.6b
```

Si el ejecutable o el modelo no están disponibles, la plataforma sigue
funcionando y el botón de explicación muestra un aviso comprensible.

## 6. Recorrido de 2 minutos

Para ver el comportamiento adaptativo en acción:

1. Entra a `http://127.0.0.1:8000/` — se crea tu identificador anónimo
   (cookie) y empiezas en el primer concepto.
2. **Responde 3 ítems seguidos correctamente**, rápido y sin pedir pistas:
   deberías ver activarse **R2** (sube la dificultad) y, si tu dominio
   estimado ya es alto, **R1** (avanza de concepto). La barra de decisión
   en la pantalla de resultado muestra el valor de `p_dominio` y la regla
   activada.
3. **Falla el mismo ítem 3 veces seguidas**: al tercer intento debería
   activarse **R7** (refuerzo con bloqueo de avance) o **R8**, según tu
   dominio estimado y tu racha de errores.
4. Haz clic en **"¿Por qué esto?"** en cualquier resultado para ver la
   explicación completa (CU-04): la condición de la regla, los factores
   evaluados y los tres coeficientes de mayor peso del modelo.
5. Visita `/progreso` para ver las 5 gráficas de tu trayectoria completa
   (incluye conceptos de sesiones anteriores, si las hubo).
6. Finaliza la práctica para ver el resumen de la sesión (4 gráficas más).

## 7. Pruebas

```bash
pytest -q                          # toda la suite
pytest --cov=nucleo                # cobertura del núcleo (mínimo 85%, actual ~92%)
python -m scripts.verificar_estilo # restricciones de diseño (§10.1)
```

Para leer `ml/artefactos/metricas.json`: `accuracy`/`precision`/`recall`/`f1`
son sobre el conjunto de validación sintético; `roc_auc` es el área bajo la
curva ROC (más cerca de 1.0 es mejor); `matriz_confusion` es
`[[VN, FP], [FN, VP]]`; `tamano_train`/`tamano_test` son los tamaños de
cada partición. `ml/artefactos/validacion_motor.json` compara `p_dominio`
contra el dominio latente simulado a través del ciclo híbrido completo.

## 8. Estructura del proyecto

```
prototipo2/
├── config.py              # rutas, semilla aleatoria, constantes globales
├── app/                    # FastAPI: rutas HTML/JSON, gráficas SVG, dependencias
├── nucleo/                 # los 4 modelos del sistema + el orquestador (motor_hibrido)
├── ml/                     # características, entrenamiento y evaluación del estimador
├── simulador/               # aprendices virtuales, generación de datos, validación del motor
├── datos/                   # banco de ítems, reglas, catálogos YAML, SQLite (generado)
├── persistencia/            # esquema SQL y repositorio de acceso a datos
├── plantillas/               # vistas Jinja2 y parciales reutilizables
├── estatico/                 # CSS, JS mínimo, fuentes autohospedadas
├── scripts/                  # preparar.py (setup) y verificar_estilo.py
└── pruebas/                  # suite de pytest
```

## 9. Cómo modificar el comportamiento sin tocar código

- **Umbrales y reglas pedagógicas**: edita `datos/reglas.yaml`. Ejemplo:
  para que sea más fácil alcanzar dominio alto, baja `dominio_alto` de
  `0.80` a `0.70` y reinicia el servidor (no hace falta reentrenar nada).
- **Contenido de los ítems**: edita `datos/banco_items.json` (respeta el
  esquema descrito en la especificación: `id`, `concepto_id`, `tipo`,
  `dificultad`, `enunciado`, `solucion`, `pistas`, y los campos propios de
  cada tipo).
- Ambos archivos se leen en cada arranque del servidor (o en caliente en
  el caso de `reglas.yaml`, que se cachea por ruta); no requieren
  reentrenar el modelo.

## 10. Reentrenar el modelo

Reentrena cuando cambies `ml/caracteristicas.py`, la lógica del simulador,
o quieras variar la semilla o el volumen de datos sintéticos:

```bash
python -m simulador.generar_entrenamiento
python -m ml.entrenar
python -m ml.evaluar             # curva ROC + comparación con dominio latente
python -m simulador.validar_motor
```

## 11. Solución de problemas

| Problema | Causa probable | Solución |
|---|---|---|
| `Address already in use` / puerto ocupado | Ya hay algo corriendo en el puerto 8000 | Usa otro puerto: `uvicorn app.main:app --port 8001` |
| El sistema muestra un aviso de "modo degradado" | Falta `ml/artefactos/estimador_dominio.joblib` (no se entrenó) | Es esperado y no rompe nada (RNF-12): ejecuta `python -m ml.entrenar` para volver a modo normal |
| `sqlite3.DatabaseError` o comportamiento extraño de la base de datos | `datos/prototipo.db` corrupta o de un esquema anterior | Bórrala y reinicialízala: elimina `datos/prototipo.db` y ejecuta `python -m persistencia.inicializar` |
| El texto se ve con una tipografía genérica, no IBM Plex | No se incluyeron los binarios `.woff2` (ver DECISIONES.md #7) | Coloca los archivos reales de IBM Plex en `estatico/fonts/` con los nombres que ya referencia `estatico/css/estilo.css`; el prototipo funciona igual sin ellos |
| `.venv\Scripts\Activate.ps1` falla con "no se puede cargar... deshabilitado" | La política de ejecución de PowerShell bloquea scripts | Ejecuta una vez: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, luego reintenta activar el entorno |
| `pip install` falla compilando alguna dependencia en Windows | Falta el Build Tools de Visual C++ para paquetes con extensiones nativas | Instala "Microsoft C++ Build Tools" o actualiza `pip` (`python -m pip install --upgrade pip`) antes de reintentar |
| `python scripts/preparar.py` falla en el paso 2 (datos sintéticos) por memoria o lentitud extrema | Máquina con pocos recursos | Reduce `NUM_APRENDICES` en `simulador/generar_entrenamiento.py` antes de ejecutar |

## 12. Limitaciones conocidas

- Es un **prototipo académico**, no una plataforma lista para producción:
  sin autenticación real, sin gestión de usuarios, sin persistencia
  distribuida.
- La validación es únicamente **técnica y funcional** (pruebas
  automatizadas, simulación estadística); no se hizo evaluación de
  impacto pedagógico real ni pruebas con usuarios.
- Los datos de entrenamiento son **enteramente sintéticos**, generados
  por un simulador con supuestos explícitos (§8 de la especificación); no
  provienen de aprendices reales.
- El banco de ítems (180) cubre 12 conceptos introductorios de Python;
  no es un currículo completo.
- Las fuentes tipográficas IBM Plex no se incluyen como binarios (ver
  DECISIONES.md #7); el sistema usa la pila de reemplazo declarada.

## 13. Licencia y crédito académico

Proyecto académico desarrollado como parte de la monografía de pregrado
citada en la sección 1, Universidad de Cundinamarca — Extensión Chía,
2026. Uso educativo y de investigación.
