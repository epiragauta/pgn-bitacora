-- ============================================================
-- queries_evolucion.sql — Consultas para Sección 2: Evolución Presupuestal
-- Tablas: pgn_concepto, pgn_ejecucion
-- ============================================================

-- ─────────────────────────────────────────────────────────────
-- Q1 — Evolución del Total PGN por año y fase (serie de tiempo)
-- Uso UI: gráfico de líneas o barras agrupadas que muestra las
--         4 fases del PGN total para los años disponibles.
--         20 puntos: 5 años × 4 fases.
-- ─────────────────────────────────────────────────────────────
SELECT
    e.anio,
    e.fase,
    e.valor
FROM pgn_ejecucion  e
JOIN pgn_concepto   c ON c.id = e.concepto_id
WHERE c.nombre = 'Total PGN'
  AND c.unidad = 'Miles mm COP'
ORDER BY e.anio, e.fase;


-- ─────────────────────────────────────────────────────────────
-- Q2 — Composición del presupuesto Vigente por categoría principal
-- Parámetro: :anio (ej. 2025)
-- Uso UI: gráfico de barras apiladas / donut del panel principal
--         de Evolución para un año dado.
--         Devuelve únicamente los rubros de nivel 2 en COP.
-- ─────────────────────────────────────────────────────────────
WITH total AS (
    SELECT e.valor AS total_vigente
    FROM   pgn_ejecucion e
    JOIN   pgn_concepto  c ON c.id = e.concepto_id
    WHERE  c.nombre = 'Total PGN'
      AND  c.unidad = 'Miles mm COP'
      AND  e.anio   = :anio
      AND  e.fase   = 'Vigente'
)
SELECT
    c.nombre                                            AS concepto,
    e.valor                                             AS valor,
    ROUND(e.valor * 100.0 / total.total_vigente, 2)    AS pct_total
FROM pgn_ejecucion e
JOIN pgn_concepto  c ON c.id = e.concepto_id
CROSS JOIN total
WHERE c.nivel  = 2
  AND c.unidad = 'Miles mm COP'
  AND e.anio   = :anio
  AND e.fase   = 'Vigente'
ORDER BY c.orden;


-- ─────────────────────────────────────────────────────────────
-- Q3 — Tasa de ejecución por año (Pagado / Vigente × 100)
-- Uso UI: tarjetas de KPI o tabla comparativa que muestra
--         cuánto del presupuesto total se pagó efectivamente
--         a corte de marzo para cada vigencia.
-- ─────────────────────────────────────────────────────────────
SELECT
    v.anio,
    v.valor                                         AS vigente,
    p.valor                                         AS pagado,
    ROUND(p.valor * 100.0 / v.valor, 2)             AS tasa_ejecucion_pct
FROM pgn_ejecucion v
JOIN pgn_ejecucion p
     ON  p.anio        = v.anio
     AND p.concepto_id = v.concepto_id
     AND p.fase        = 'Pagado'
JOIN pgn_concepto  c ON c.id = v.concepto_id
WHERE c.nombre = 'Total PGN'
  AND c.unidad = 'Miles mm COP'
  AND v.fase   = 'Vigente'
ORDER BY v.anio;


-- ─────────────────────────────────────────────────────────────
-- Q4 — Drilldown jerárquico de un concepto y todos sus descendientes
-- Parámetros: :concepto_nombre (ej. 'Funcionamiento')
--             :anio            (ej. 2025)
--             :fase            (ej. 'Vigente')
-- Uso UI: panel lateral (drawer) que detalla la composición
--         interna de un rubro al hacer clic en él.
--         Usa CTE recursivo; devuelve en orden de display.
-- ─────────────────────────────────────────────────────────────
WITH RECURSIVE arbol AS (
    -- Nodo raíz: el concepto solicitado
    SELECT c.id, c.nombre, c.nivel, c.padre_id, c.orden
    FROM   pgn_concepto c
    WHERE  c.nombre = :concepto_nombre

    UNION ALL

    -- Descendientes en cualquier nivel
    SELECT c.id, c.nombre, c.nivel, c.padre_id, c.orden
    FROM   pgn_concepto c
    JOIN   arbol        a ON c.padre_id = a.id
)
SELECT
    a.nivel,
    a.nombre,
    e.valor,
    COALESCE(p.nombre, '') AS padre
FROM   arbol        a
JOIN   pgn_ejecucion e ON e.concepto_id = a.id
LEFT JOIN pgn_concepto p ON p.id = a.padre_id
WHERE  e.anio = :anio
  AND  e.fase = :fase
ORDER BY a.orden;


-- ─────────────────────────────────────────────────────────────
-- Q5 — Comparativo % PIB para grandes rubros (serie histórica)
-- Uso UI: gráfico de líneas superpuestas que muestra cómo
--         Funcionamiento, Deuda e Inversión evolucionan como
--         fracción del PIB a través de los años. Solo Vigente.
--         Los valores se convierten a porcentaje × 100 para
--         legibilidad en ejes (0,238 → 23.8).
-- ─────────────────────────────────────────────────────────────
SELECT
    e.anio,
    c.nombre                        AS concepto,
    ROUND(e.valor * 100, 4)         AS valor_pct_pib
FROM pgn_ejecucion e
JOIN pgn_concepto  c ON c.id = e.concepto_id
WHERE c.nivel  = 2
  AND c.unidad = '% PIB'
  AND e.fase   = 'Vigente'
ORDER BY e.anio, c.orden;
