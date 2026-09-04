PRAGMA foreign_keys = ON;

-- ============================================================
-- Grupo catálogo
-- ============================================================

CREATE TABLE IF NOT EXISTS concepto (
    id     INTEGER PRIMARY KEY,
    orden  INTEGER NOT NULL CHECK (orden BETWEEN 1 AND 12),
    nombre TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categoria_error (
    id          INTEGER PRIMARY KEY,
    codigo      TEXT NOT NULL UNIQUE,
    nombre      TEXT NOT NULL,
    descripcion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS regla (
    id                 TEXT PRIMARY KEY,      -- 'R1'..'R9'
    nombre             TEXT NOT NULL,
    prioridad          INTEGER NOT NULL CHECK (prioridad BETWEEN 1 AND 9),
    condicion_textual  TEXT NOT NULL,
    accion             TEXT NOT NULL
);

-- ============================================================
-- Grupo transaccional
-- ============================================================

CREATE TABLE IF NOT EXISTS aprendiz (
    id               TEXT PRIMARY KEY,        -- UUID4 (RF-18)
    creado_en        TEXT NOT NULL,
    ultima_actividad TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sesion (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    aprendiz_id TEXT NOT NULL REFERENCES aprendiz(id),
    inicio      TEXT NOT NULL,
    fin         TEXT,
    estado      TEXT NOT NULL CHECK (estado IN ('activa', 'finalizada'))
);

CREATE TABLE IF NOT EXISTS intento (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id            INTEGER NOT NULL REFERENCES sesion(id),
    item_id              TEXT NOT NULL,
    concepto_id          INTEGER NOT NULL REFERENCES concepto(id),
    respuesta_cruda      TEXT NOT NULL,
    es_correcto          INTEGER NOT NULL CHECK (es_correcto IN (0, 1)),
    numero_intento       INTEGER NOT NULL CHECK (numero_intento BETWEEN 1 AND 3),
    tiempo_respuesta_ms  INTEGER NOT NULL,
    categoria_error_id   INTEGER REFERENCES categoria_error(id),
    creado_en            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pista (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    intento_id      INTEGER NOT NULL REFERENCES intento(id),
    nivel           INTEGER NOT NULL CHECK (nivel BETWEEN 1 AND 3),
    orden           INTEGER NOT NULL,
    texto_entregado TEXT NOT NULL,
    creado_en       TEXT NOT NULL
);

-- Estado acumulado del aprendiz por concepto. PK compuesta: un renglón por
-- (aprendiz, concepto). `bloqueado_avance` documentado en DECISIONES.md #2.
CREATE TABLE IF NOT EXISTS estado_aprendiz (
    aprendiz_id               TEXT NOT NULL REFERENCES aprendiz(id),
    concepto_id               INTEGER NOT NULL REFERENCES concepto(id),
    p_dominio_previo          REAL NOT NULL DEFAULT 0.25,
    racha_aciertos            INTEGER NOT NULL DEFAULT 0,
    racha_errores             INTEGER NOT NULL DEFAULT 0,
    total_intentos            INTEGER NOT NULL DEFAULT 0,
    total_aciertos            INTEGER NOT NULL DEFAULT 0,
    nivel_dificultad_actual   INTEGER NOT NULL DEFAULT 1 CHECK (nivel_dificultad_actual BETWEEN 1 AND 3),
    pistas_acumuladas         INTEGER NOT NULL DEFAULT 0,
    estado                    TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'en_curso', 'dominado')),
    bloqueado_avance          INTEGER NOT NULL DEFAULT 0 CHECK (bloqueado_avance IN (0, 1)),
    actualizado_en            TEXT NOT NULL,
    PRIMARY KEY (aprendiz_id, concepto_id)
);

CREATE TABLE IF NOT EXISTS estimacion_dominio (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    intento_id INTEGER NOT NULL REFERENCES intento(id),
    p_dominio  REAL NOT NULL,
    modo       TEXT NOT NULL CHECK (modo IN ('normal', 'degradado')),
    creado_en  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS traza_adaptacion (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    intento_id          INTEGER NOT NULL REFERENCES intento(id),
    regla_id            TEXT NOT NULL REFERENCES regla(id),
    accion              TEXT NOT NULL,
    factores_json       TEXT NOT NULL,   -- snapshot del estado evaluado
    explicacion_aprendiz TEXT NOT NULL,
    creado_en           TEXT NOT NULL
);

-- ============================================================
-- Índices (§3.2)
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_intento_sesion   ON intento(sesion_id);
CREATE INDEX IF NOT EXISTS idx_intento_concepto  ON intento(concepto_id);
CREATE INDEX IF NOT EXISTS idx_estado_aprendiz   ON estado_aprendiz(aprendiz_id);
