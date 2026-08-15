using PgnBitacora.Api.Data;

namespace PgnBitacora.Api.Endpoints;

/// <summary>
/// Sección 2 — Evolución presupuestal del PGN (modelo pgn_concepto/pgn_ejecucion).
///
/// Es la sección con más traducciones delicadas:
///   · NULLIF en todo denominador — SQLite devuelve NULL al dividir por
///     cero, SQL Server aborta con el error 8134.
///   · WITH RECURSIVE -> WITH (SQL Server no lleva la palabra RECURSIVE).
/// </summary>
public static class EvolucionEndpoints
{
    public static void MapEvolucion(this IEndpointRouteBuilder app)
    {
        var grupo = app.MapGroup("/api/evolucion").WithTags("Sec 2 - Evolución Presupuestal");

        grupo.MapGet("", async (string? rubro, int? bitacora_id, IDb db) =>
        {
            // El alias 'Servicio Deuda' lo espera el frontend; el dato se
            // guarda como 'Servicio de la Deuda'.
            var sql = """
                SELECT e.anio AS vigencia,
                       REPLACE(c.nombre, 'Servicio de la Deuda', 'Servicio Deuda') AS rubro,
                       e.valor AS vigente_mmm
                FROM dbo.pgn_ejecucion e
                JOIN dbo.pgn_concepto  c ON c.id = e.concepto_id
                WHERE c.nivel = 2 AND c.unidad = 'Miles mm COP' AND e.fase = 'Vigente'
                """;

            if (rubro is not null)
                sql += " AND REPLACE(c.nombre,'Servicio de la Deuda','Servicio Deuda') = @rubro";

            sql += " ORDER BY e.anio, c.orden";
            return await db.QueryAsync(sql, new { rubro });
        })
            .WithSummary("Apropiación vigente por rubro principal (nivel 2).");

        grupo.MapGet("/composicion", async (int anio, string? fase, IDb db) =>
            await db.QueryAsync("""
                WITH total AS (
                    SELECT e.valor
                    FROM   dbo.pgn_ejecucion e
                    JOIN   dbo.pgn_concepto  c ON c.id = e.concepto_id
                    WHERE  c.nombre = 'Total PGN' AND c.unidad = 'Miles mm COP'
                      AND  e.anio = @anio AND e.fase = @fase
                )
                SELECT c.nombre AS concepto, e.valor,
                       ROUND(CAST(e.valor AS FLOAT) * 100.0 / NULLIF(total.valor, 0), 2) AS pct_total
                FROM dbo.pgn_ejecucion e
                JOIN dbo.pgn_concepto  c ON c.id = e.concepto_id
                CROSS JOIN total
                WHERE c.nivel = 2 AND c.unidad = 'Miles mm COP'
                  AND e.anio = @anio AND e.fase = @fase
                ORDER BY c.orden
                """, new { anio, fase = fase ?? "Vigente" }))
            .WithSummary("Composición porcentual del PGN por categoría principal.");

        grupo.MapGet("/tasa_ejecucion", async (IDb db) =>
            await db.QueryAsync("""
                SELECT v.anio, v.valor AS vigente, p.valor AS pagado,
                       ROUND(CAST(p.valor AS FLOAT) * 100.0 / NULLIF(v.valor, 0), 2) AS tasa_ejecucion_pct
                FROM dbo.pgn_ejecucion v
                JOIN dbo.pgn_ejecucion p
                     ON p.anio = v.anio AND p.concepto_id = v.concepto_id AND p.fase = 'Pagado'
                JOIN dbo.pgn_concepto c ON c.id = v.concepto_id
                WHERE c.nombre = 'Total PGN' AND c.unidad = 'Miles mm COP' AND v.fase = 'Vigente'
                ORDER BY v.anio
                """))
            .WithSummary("Tasa de ejecución (Pagado/Vigente) del Total PGN por año.");

        grupo.MapGet("/pct_pib", async (IDb db) =>
            await db.QueryAsync("""
                SELECT e.anio, c.nombre AS concepto,
                       ROUND(CAST(e.valor AS FLOAT) * 100, 4) AS valor_pct_pib
                FROM dbo.pgn_ejecucion e
                JOIN dbo.pgn_concepto  c ON c.id = e.concepto_id
                WHERE c.nivel = 2 AND c.unidad = '% PIB' AND e.fase = 'Vigente'
                ORDER BY e.anio, c.orden
                """))
            .WithSummary("Grandes rubros como % del PIB.");

        grupo.MapGet("/drilldown", async (string concepto, int anio, string? fase, IDb db) =>
            await db.QueryAsync("""
                WITH arbol AS (
                    SELECT id, nombre, nivel, padre_id, orden
                    FROM dbo.pgn_concepto WHERE nombre = @concepto
                    UNION ALL
                    SELECT c.id, c.nombre, c.nivel, c.padre_id, c.orden
                    FROM dbo.pgn_concepto c
                    JOIN arbol a ON c.padre_id = a.id
                )
                SELECT a.nivel, a.nombre, e.valor, COALESCE(p.nombre, '') AS padre
                FROM arbol a
                JOIN dbo.pgn_ejecucion e ON e.concepto_id = a.id
                LEFT JOIN dbo.pgn_concepto p ON p.id = a.padre_id
                WHERE e.anio = @anio AND e.fase = @fase
                ORDER BY a.orden
                OPTION (MAXRECURSION 10)
                """, new { concepto, anio, fase = fase ?? "Vigente" }))
            .WithSummary("Árbol jerárquico de un concepto y sus descendientes.");

        grupo.MapGet("/tabla_completa", async (IDb db) =>
            await db.QueryAsync("SELECT * FROM dbo.pgn_vista_crosstab ORDER BY orden"))
            .WithSummary("Todos los conceptos × años × fases en formato pivot.");

        grupo.MapGet("/inversion_historica", async (int? bitacora_id, IDb db) =>
            await db.QueryAsync("""
                SELECT v.anio                                              AS vigencia,
                       v.valor                                             AS vigente_mmm,
                       com.valor                                           AS compromisos_mmm,
                       obl.valor                                           AS obligaciones_mmm,
                       pag.valor                                           AS pagados_mmm,
                       ROUND(CAST(com.valor AS FLOAT) * 100.0 / NULLIF(v.valor, 0), 2)    AS pct_compromisos,
                       ROUND(CAST(obl.valor AS FLOAT) * 100.0 / NULLIF(v.valor, 0), 2)    AS pct_obligaciones,
                       ROUND(CAST(pag.valor AS FLOAT) * 100.0 / NULLIF(v.valor, 0), 2)    AS pct_pagos,
                       ROUND(CAST(pib.valor AS FLOAT) * 100, 1)                           AS inv_pct_pib,
                       ROUND(CAST(v.valor AS FLOAT) * 100.0 / NULLIF(tot.valor, 0), 1)    AS inv_pct_gasto_total
                FROM dbo.pgn_ejecucion v
                JOIN dbo.pgn_ejecucion com ON com.anio=v.anio AND com.concepto_id=v.concepto_id AND com.fase='Comprometido'
                JOIN dbo.pgn_ejecucion obl ON obl.anio=v.anio AND obl.concepto_id=v.concepto_id AND obl.fase='Obligado'
                JOIN dbo.pgn_ejecucion pag ON pag.anio=v.anio AND pag.concepto_id=v.concepto_id AND pag.fase='Pagado'
                JOIN dbo.pgn_ejecucion pib ON pib.anio=v.anio AND pib.fase='Vigente'
                JOIN dbo.pgn_concepto  cpib ON cpib.id=pib.concepto_id AND cpib.nombre='Inversión como % del PIB'
                JOIN dbo.pgn_ejecucion tot ON tot.anio=v.anio AND tot.fase='Vigente'
                JOIN dbo.pgn_concepto  ctot ON ctot.id=tot.concepto_id AND ctot.nombre='Total PGN' AND ctot.unidad='Miles mm COP'
                JOIN dbo.pgn_concepto  c    ON c.id=v.concepto_id AND c.nombre='Inversión' AND c.unidad='Miles mm COP'
                WHERE v.fase = 'Vigente'
                ORDER BY v.anio
                """))
            .WithSummary("Serie histórica de inversión con indicadores macroeconómicos.");
    }
}
