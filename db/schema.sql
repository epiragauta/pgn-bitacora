-- ============================================================
-- BITÁCORA PGN 2025-I  —  Esquema de base de datos
-- Fuente: DNP / DPIP / SIIF Nación
-- Cifras en miles de millones de pesos corrientes (salvo donde se indique)
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- Tabla de control: metadatos por bitácora
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metadatos_bitacora (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_bitacora  TEXT    NOT NULL,          -- ej. "2"
    periodo          TEXT    NOT NULL,          -- ej. "2025-I"
    corte_fecha      DATE    NOT NULL,          -- ej. "2025-03-31"
    fuente_principal TEXT    DEFAULT 'SIIF Nación',
    elaborado_por    TEXT    DEFAULT 'DPIP - DNP',
    fecha_carga      DATETIME DEFAULT (datetime('now')),
    notas            TEXT
);

-- ------------------------------------------------------------
-- SECCIÓN 1 – Inversiones PND 2022-2026 (Transformaciones)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inversion_transformaciones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id     INTEGER REFERENCES metadatos_bitacora(id),
    vigencia        INTEGER NOT NULL,           -- año (2025)
    transformador   TEXT    NOT NULL,           -- ej. "SEGURIDAD HUMANA Y JUSTICIA SOCIAL"
    inversion_mmm   DECIMAL(12,3),             -- miles de millones de pesos
    peso_pct        DECIMAL(5,2)               -- porcentaje del total
);

CREATE TABLE IF NOT EXISTS inversion_componentes_pnd (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id     INTEGER REFERENCES metadatos_bitacora(id),
    vigencia        INTEGER NOT NULL,
    transformador   TEXT    NOT NULL,
    componente      TEXT    NOT NULL,
    vigente_mmm     DECIMAL(12,3),
    peso_pct        DECIMAL(5,2)
);

CREATE TABLE IF NOT EXISTS ejecucion_transformaciones (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id         INTEGER REFERENCES metadatos_bitacora(id),
    vigencia            INTEGER NOT NULL,
    transformador       TEXT    NOT NULL,
    apr_vigente_mmm     DECIMAL(12,3),
    compromisos_mmm     DECIMAL(12,3),
    obligaciones_mmm    DECIMAL(12,3),
    pagos_mmm           DECIMAL(12,3),
    pct_c_av            DECIMAL(5,2),
    pct_o_av            DECIMAL(5,2),
    pct_p_av            DECIMAL(5,2)
);

-- ------------------------------------------------------------
-- SECCIÓN 2 – Evolución presupuestal PGN 2022-2025
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS evolucion_presupuestal (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id     INTEGER REFERENCES metadatos_bitacora(id),
    vigencia        INTEGER NOT NULL,
    rubro           TEXT    NOT NULL,           -- ej. "Funcionamiento", "Inversión", "Servicio de la Deuda"
    sub_rubro       TEXT,
    vigente_mmm     DECIMAL(14,3),
    compromisos_mmm DECIMAL(14,3),
    obligaciones_mmm DECIMAL(14,3),
    pagos_mmm       DECIMAL(14,3),
    pct_pgn         DECIMAL(5,2),              -- % del total PGN
    UNIQUE(bitacora_id, vigencia, rubro, sub_rubro)
);

-- ------------------------------------------------------------
-- SECCIÓN 3 – Regionalización de la inversión
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS regionalizacion_resumen (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id     INTEGER REFERENCES metadatos_bitacora(id),
    vigencia        INTEGER NOT NULL,
    region          TEXT    NOT NULL,           -- ej. "AMAZONAS", "ANDINA", "CARIBE"...
    departamento    TEXT    NOT NULL,           -- nombre del dpto o igual a region si es total
    es_total_region BOOLEAN DEFAULT 0,
    apropiacion_mm  DECIMAL(14,3),             -- cifras en millones de pesos
    compromisos_mm  DECIMAL(14,3),
    obligaciones_mm DECIMAL(14,3),
    pagos_mm        DECIMAL(14,3)
);

CREATE TABLE IF NOT EXISTS regionalizacion_detalle_2025 (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id             INTEGER REFERENCES metadatos_bitacora(id),
    region                  TEXT    NOT NULL,
    departamento            TEXT    NOT NULL,
    vigente_mm              DECIMAL(14,3),
    compromisos_mm          DECIMAL(14,3),
    obligaciones_mm         DECIMAL(14,3),
    pagos_mm                DECIMAL(14,3),
    pct_ejec_compromisos    DECIMAL(5,2),
    pct_ejec_obligaciones   DECIMAL(5,2),
    pct_ejec_pagos          DECIMAL(5,2),
    pct_participacion       DECIMAL(5,2),
    principales_sectores    TEXT                -- JSON: [{"sector":"Transporte","pct":21}, ...]
);

-- ------------------------------------------------------------
-- SECCIÓN 4 – Ejecución de la inversión
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ejecucion_historica (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id         INTEGER REFERENCES metadatos_bitacora(id),
    vigencia            INTEGER NOT NULL,
    vigente_mmm         DECIMAL(12,3),
    compromisos_mmm     DECIMAL(12,3),
    obligaciones_mmm    DECIMAL(12,3),
    pagos_mmm           DECIMAL(12,3),
    pct_compromisos     DECIMAL(5,2),
    pct_obligaciones    DECIMAL(5,2),
    pct_pagos           DECIMAL(5,2),
    inv_pct_pib         DECIMAL(5,2),
    inv_pct_gasto_total DECIMAL(5,2),
    UNIQUE(bitacora_id, vigencia)
);

CREATE TABLE IF NOT EXISTS ejecucion_mensual_sectorial (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id     INTEGER REFERENCES metadatos_bitacora(id),
    vigencia        INTEGER NOT NULL,
    sector          TEXT    NOT NULL,
    mes             INTEGER NOT NULL,           -- 1=Ene, 2=Feb, 3=Mar
    pct_obligaciones DECIMAL(5,2)
);

CREATE TABLE IF NOT EXISTS apropiacion_por_sector (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id     INTEGER REFERENCES metadatos_bitacora(id),
    vigencia        INTEGER NOT NULL,
    sector          TEXT    NOT NULL,
    vigente_mmm     DECIMAL(12,3),
    UNIQUE(bitacora_id, vigencia, sector)
);

CREATE TABLE IF NOT EXISTS compromisos_pct_por_sector (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id     INTEGER REFERENCES metadatos_bitacora(id),
    vigencia        INTEGER NOT NULL,
    sector          TEXT    NOT NULL,
    pct_compromisos DECIMAL(5,2),
    UNIQUE(bitacora_id, vigencia, sector)
);

CREATE TABLE IF NOT EXISTS obligaciones_pct_por_sector (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id     INTEGER REFERENCES metadatos_bitacora(id),
    vigencia        INTEGER NOT NULL,
    sector          TEXT    NOT NULL,
    pct_obligaciones DECIMAL(5,2),
    UNIQUE(bitacora_id, vigencia, sector)
);

CREATE TABLE IF NOT EXISTS pagos_pct_por_sector (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id     INTEGER REFERENCES metadatos_bitacora(id),
    vigencia        INTEGER NOT NULL,
    sector          TEXT    NOT NULL,
    pct_pagos       DECIMAL(5,2),
    UNIQUE(bitacora_id, vigencia, sector)
);

-- ------------------------------------------------------------
-- SECCIÓN 5 – Vigencias Futuras
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vigencias_futuras (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id          INTEGER REFERENCES metadatos_bitacora(id),
    vigencia_exec        INTEGER NOT NULL,   -- año de ejecución
    sector               TEXT    NOT NULL,   -- sector individual (SIIF)
    valor_corriente_mmm  DECIMAL(14,3),      -- pesos corrientes / 1e9 (sin deflactar)
    UNIQUE(bitacora_id, vigencia_exec, sector)
);

-- ------------------------------------------------------------
-- SECCIÓN 5 – Deflactores PIB (base 2026)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS deflactores_pib (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id          INTEGER REFERENCES metadatos_bitacora(id),
    anio                 INTEGER NOT NULL,
    deflactor            DECIMAL(14,9),        -- DEFLACTOR PIB BASE 2026
    pib_corriente_mmm    DECIMAL(14,3),        -- PIB en pesos corrientes (miles de millones)
    pib_constante_mmm    DECIMAL(14,3),        -- PIB en pesos constantes 2026 (miles de millones)
    UNIQUE(bitacora_id, anio)
);

-- ------------------------------------------------------------
-- SECCIÓN 6 – Ejecución Sectorial (entidades)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ejecucion_sectorial_entidades (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id         INTEGER REFERENCES metadatos_bitacora(id),
    vigencia            INTEGER NOT NULL,
    sector              TEXT    NOT NULL,
    entidad             TEXT    NOT NULL,
    apr_vigente_mmm     DECIMAL(12,3),
    compromisos_mmm     DECIMAL(12,3),
    obligaciones_mmm    DECIMAL(12,3),
    pagos_mmm           DECIMAL(12,3),
    pct_c_av            DECIMAL(5,2),
    pct_o_av            DECIMAL(5,2),
    pct_p_av            DECIMAL(5,2),
    UNIQUE(bitacora_id, vigencia, entidad)
);

CREATE TABLE IF NOT EXISTS ejecucion_sectorial_mensual (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id         INTEGER REFERENCES metadatos_bitacora(id),
    vigencia            INTEGER NOT NULL,
    sector              TEXT    NOT NULL,
    mes                 INTEGER NOT NULL,
    pct_compromisos_2025  DECIMAL(5,2),
    pct_compromisos_2024  DECIMAL(5,2),
    pct_compromisos_prom  DECIMAL(5,2),
    pct_compromisos_mejor DECIMAL(5,2),
    pct_obligaciones_2025  DECIMAL(5,2),
    pct_obligaciones_2024  DECIMAL(5,2),
    pct_obligaciones_prom  DECIMAL(5,2),
    pct_obligaciones_mejor DECIMAL(5,2)
);

-- ------------------------------------------------------------
-- SECCIÓN 7 – Crédito Externo (SCCI)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS credito_portafolio (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id       INTEGER REFERENCES metadatos_bitacora(id),
    nombre            TEXT    NOT NULL,
    nombre_corto      TEXT,
    fuente            TEXT    NOT NULL,       -- BID, BM, CAF
    contrato          TEXT,
    sector            TEXT    NOT NULL,
    monto_usd         DECIMAL(16,2),
    desembolsado_usd  DECIMAL(16,2)
);

CREATE TABLE IF NOT EXISTS credito_ejecucion_entidad (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id         INTEGER REFERENCES metadatos_bitacora(id),
    entidad             TEXT    NOT NULL,
    sector              TEXT    NOT NULL,
    apr_inicial_mmm     DECIMAL(14,3),
    apr_vigente_mmm     DECIMAL(14,3),
    compromiso_mmm      DECIMAL(14,3),
    obligacion_mmm      DECIMAL(14,3),
    pago_mmm            DECIMAL(14,3),
    pct_com             DECIMAL(6,2),
    pct_ejec            DECIMAL(6,2),
    pct_pago            DECIMAL(6,2),
    UNIQUE(bitacora_id, entidad)
);

CREATE TABLE IF NOT EXISTS credito_ejecucion_historica (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id       INTEGER REFERENCES metadatos_bitacora(id),
    anio              INTEGER NOT NULL,
    pct_comprometido  DECIMAL(6,2),
    pct_ejecutado     DECIMAL(6,2),
    pct_pagado        DECIMAL(6,2),
    vigente_mmm       DECIMAL(14,3),
    comprometido_mmm  DECIMAL(14,3),
    ejecutado_mmm     DECIMAL(14,3),
    pagado_mmm        DECIMAL(14,3),
    UNIQUE(bitacora_id, anio)
);

-- ------------------------------------------------------------
-- SECCIÓN 8 – Sistema General de Participaciones (SGP)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sgp_historico_participacion (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id                 INTEGER REFERENCES metadatos_bitacora(id),
    vigencia                    INTEGER NOT NULL,
    educacion_mmm               DECIMAL(14,3),
    salud_mmm                   DECIMAL(14,3),
    agua_potable_mmm            DECIMAL(14,3),
    proposito_general_mmm       DECIMAL(14,3),
    alimentacion_escolar_mmm    DECIMAL(14,3),
    riberenos_mmm               DECIMAL(14,3),
    resguardos_indigenas_mmm    DECIMAL(14,3),
    fonpet_ae_mmm               DECIMAL(14,3),
    total_mmm                   DECIMAL(14,3),
    UNIQUE(bitacora_id, vigencia)
);

-- ------------------------------------------------------------
-- Índices para consultas frecuentes
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_ejecucion_historica_vigencia   ON ejecucion_historica(vigencia);
CREATE INDEX IF NOT EXISTS idx_regional_vigencia              ON regionalizacion_detalle_2025(region, departamento);
CREATE INDEX IF NOT EXISTS idx_sector_vigencia                ON apropiacion_por_sector(vigencia, sector);
CREATE INDEX IF NOT EXISTS idx_sectorial_entidad              ON ejecucion_sectorial_entidades(vigencia, sector, entidad);
CREATE INDEX IF NOT EXISTS idx_vigencias_futuras_año          ON vigencias_futuras(vigencia_exec);
CREATE INDEX IF NOT EXISTS idx_credito_entidad               ON credito_ejecucion_entidad(entidad);
CREATE INDEX IF NOT EXISTS idx_sgp_historico_vigencia        ON sgp_historico_participacion(vigencia);
