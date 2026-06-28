-- ============================================================
-- schema_pgn.sql — Sección 2: Evolución Presupuestal PGN
-- DNP / DPIP — datos acumulados a marzo, 2022-2026
-- Reemplaza las tablas evolucion_presupuestal y ejecucion_historica
-- Solo afecta tablas con prefijo pgn_; el resto del schema queda intacto.
-- ============================================================

PRAGMA foreign_keys = OFF;

-- Orden importa: primero hechos, luego dimensión (por FK)
DROP TABLE IF EXISTS pgn_ejecucion;
DROP TABLE IF EXISTS pgn_concepto;
DROP VIEW  IF EXISTS pgn_vista_crosstab;

-- ------------------------------------------------------------
-- Dimensión: jerarquía de conceptos presupuestales
-- ------------------------------------------------------------
CREATE TABLE pgn_concepto (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre   TEXT    NOT NULL UNIQUE,
    padre_id INTEGER REFERENCES pgn_concepto(id) ON DELETE SET NULL,
    nivel    INTEGER NOT NULL CHECK(nivel BETWEEN 1 AND 4),
    unidad   TEXT    NOT NULL CHECK(unidad IN ('Miles mm COP', '% PIB')),
    orden    INTEGER NOT NULL   -- posición de primera aparición en el CSV; governa display
);

-- ------------------------------------------------------------
-- Hechos: valor por (año, fase, concepto)
-- ------------------------------------------------------------
CREATE TABLE pgn_ejecucion (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    anio        INTEGER NOT NULL CHECK(anio BETWEEN 2022 AND 2030),
    fase        TEXT    NOT NULL CHECK(fase IN ('Vigente','Comprometido','Obligado','Pagado')),
    concepto_id INTEGER NOT NULL REFERENCES pgn_concepto(id),
    valor       REAL    NOT NULL,
    UNIQUE(anio, fase, concepto_id)
);

-- ------------------------------------------------------------
-- Índices para las consultas frecuentes de la app
-- ------------------------------------------------------------
CREATE INDEX idx_pgn_ej_anio_fase ON pgn_ejecucion(anio, fase);
CREATE INDEX idx_pgn_ej_concepto  ON pgn_ejecucion(concepto_id);
CREATE INDEX idx_pgn_co_padre     ON pgn_concepto(padre_id);

-- ------------------------------------------------------------
-- Vista de compatibilidad: formato ancho (año×fase como columnas)
-- Útil para partes de la app que consuman el formato tabular anterior.
-- Agregar años futuros: replicar el bloque MAX(CASE WHEN ...) para anio=N
-- ------------------------------------------------------------
CREATE VIEW pgn_vista_crosstab AS
SELECT
    c.id,
    c.nombre,
    c.nivel,
    c.unidad,
    c.orden,
    MAX(CASE WHEN e.anio=2022 AND e.fase='Vigente'       THEN e.valor END) AS vigente_2022,
    MAX(CASE WHEN e.anio=2022 AND e.fase='Comprometido'  THEN e.valor END) AS comprometido_2022,
    MAX(CASE WHEN e.anio=2022 AND e.fase='Obligado'      THEN e.valor END) AS obligado_2022,
    MAX(CASE WHEN e.anio=2022 AND e.fase='Pagado'        THEN e.valor END) AS pagado_2022,
    MAX(CASE WHEN e.anio=2023 AND e.fase='Vigente'       THEN e.valor END) AS vigente_2023,
    MAX(CASE WHEN e.anio=2023 AND e.fase='Comprometido'  THEN e.valor END) AS comprometido_2023,
    MAX(CASE WHEN e.anio=2023 AND e.fase='Obligado'      THEN e.valor END) AS obligado_2023,
    MAX(CASE WHEN e.anio=2023 AND e.fase='Pagado'        THEN e.valor END) AS pagado_2023,
    MAX(CASE WHEN e.anio=2024 AND e.fase='Vigente'       THEN e.valor END) AS vigente_2024,
    MAX(CASE WHEN e.anio=2024 AND e.fase='Comprometido'  THEN e.valor END) AS comprometido_2024,
    MAX(CASE WHEN e.anio=2024 AND e.fase='Obligado'      THEN e.valor END) AS obligado_2024,
    MAX(CASE WHEN e.anio=2024 AND e.fase='Pagado'        THEN e.valor END) AS pagado_2024,
    MAX(CASE WHEN e.anio=2025 AND e.fase='Vigente'       THEN e.valor END) AS vigente_2025,
    MAX(CASE WHEN e.anio=2025 AND e.fase='Comprometido'  THEN e.valor END) AS comprometido_2025,
    MAX(CASE WHEN e.anio=2025 AND e.fase='Obligado'      THEN e.valor END) AS obligado_2025,
    MAX(CASE WHEN e.anio=2025 AND e.fase='Pagado'        THEN e.valor END) AS pagado_2025,
    MAX(CASE WHEN e.anio=2026 AND e.fase='Vigente'       THEN e.valor END) AS vigente_2026,
    MAX(CASE WHEN e.anio=2026 AND e.fase='Comprometido'  THEN e.valor END) AS comprometido_2026,
    MAX(CASE WHEN e.anio=2026 AND e.fase='Obligado'      THEN e.valor END) AS obligado_2026,
    MAX(CASE WHEN e.anio=2026 AND e.fase='Pagado'        THEN e.valor END) AS pagado_2026
FROM pgn_concepto c
LEFT JOIN pgn_ejecucion e ON e.concepto_id = c.id
GROUP BY c.id
ORDER BY c.orden;

PRAGMA foreign_keys = ON;
