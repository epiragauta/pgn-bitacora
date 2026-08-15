-- ============================================================
-- 002_views.sql — Vistas (base dnp_dpip)
--
-- pgn_vista_crosstab: formato ancho (año × fase como columnas).
-- La consume /api/evolucion/tabla_completa.
--
-- Dos correcciones respecto del original SQLite:
--   1. SQLite permite GROUP BY c.id dejando el resto de columnas
--      sin agregar; SQL Server exige listarlas todas.
--   2. SQL Server no admite ORDER BY dentro de una vista sin TOP.
--      Se elimina: el endpoint ya ordena por `orden`.
--
-- Para añadir un año futuro: replicar el bloque MAX(CASE WHEN ...)
-- con el nuevo valor de anio.
-- ============================================================

SET NOCOUNT ON;
GO

CREATE OR ALTER VIEW dbo.pgn_vista_crosstab AS
SELECT
    c.id,
    c.nombre,
    c.nivel,
    c.unidad,
    c.orden,
    MAX(CASE WHEN e.anio = 2022 AND e.fase = 'Vigente'      THEN e.valor END) AS vigente_2022,
    MAX(CASE WHEN e.anio = 2022 AND e.fase = 'Comprometido' THEN e.valor END) AS comprometido_2022,
    MAX(CASE WHEN e.anio = 2022 AND e.fase = 'Obligado'     THEN e.valor END) AS obligado_2022,
    MAX(CASE WHEN e.anio = 2022 AND e.fase = 'Pagado'       THEN e.valor END) AS pagado_2022,
    MAX(CASE WHEN e.anio = 2023 AND e.fase = 'Vigente'      THEN e.valor END) AS vigente_2023,
    MAX(CASE WHEN e.anio = 2023 AND e.fase = 'Comprometido' THEN e.valor END) AS comprometido_2023,
    MAX(CASE WHEN e.anio = 2023 AND e.fase = 'Obligado'     THEN e.valor END) AS obligado_2023,
    MAX(CASE WHEN e.anio = 2023 AND e.fase = 'Pagado'       THEN e.valor END) AS pagado_2023,
    MAX(CASE WHEN e.anio = 2024 AND e.fase = 'Vigente'      THEN e.valor END) AS vigente_2024,
    MAX(CASE WHEN e.anio = 2024 AND e.fase = 'Comprometido' THEN e.valor END) AS comprometido_2024,
    MAX(CASE WHEN e.anio = 2024 AND e.fase = 'Obligado'     THEN e.valor END) AS obligado_2024,
    MAX(CASE WHEN e.anio = 2024 AND e.fase = 'Pagado'       THEN e.valor END) AS pagado_2024,
    MAX(CASE WHEN e.anio = 2025 AND e.fase = 'Vigente'      THEN e.valor END) AS vigente_2025,
    MAX(CASE WHEN e.anio = 2025 AND e.fase = 'Comprometido' THEN e.valor END) AS comprometido_2025,
    MAX(CASE WHEN e.anio = 2025 AND e.fase = 'Obligado'     THEN e.valor END) AS obligado_2025,
    MAX(CASE WHEN e.anio = 2025 AND e.fase = 'Pagado'       THEN e.valor END) AS pagado_2025,
    MAX(CASE WHEN e.anio = 2026 AND e.fase = 'Vigente'      THEN e.valor END) AS vigente_2026,
    MAX(CASE WHEN e.anio = 2026 AND e.fase = 'Comprometido' THEN e.valor END) AS comprometido_2026,
    MAX(CASE WHEN e.anio = 2026 AND e.fase = 'Obligado'     THEN e.valor END) AS obligado_2026,
    MAX(CASE WHEN e.anio = 2026 AND e.fase = 'Pagado'       THEN e.valor END) AS pagado_2026
FROM dbo.pgn_concepto c
LEFT JOIN dbo.pgn_ejecucion e ON e.concepto_id = c.id
GROUP BY c.id, c.nombre, c.nivel, c.unidad, c.orden;
GO
