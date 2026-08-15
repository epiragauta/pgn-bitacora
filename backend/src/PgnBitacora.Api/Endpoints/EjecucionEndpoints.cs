using PgnBitacora.Api.Data;

namespace PgnBitacora.Api.Endpoints;

/// <summary>
/// Sección 4 — Ejecución de la inversión.
///
/// Sobre "NULLS LAST": el origen lo escribe explícitamente y SQL Server no
/// admite esa cláusula, pero tampoco hace falta. Ambos motores tratan NULL
/// como el valor más bajo, así que un ORDER BY ... DESC ya deja los nulos
/// al final en los dos.
/// </summary>
public static class EjecucionEndpoints
{
    public static void MapEjecucion(this IEndpointRouteBuilder app)
    {
        var grupo = app.MapGroup("/api/ejecucion").WithTags("Sec 4 - Ejecución");

        grupo.MapGet("", async (int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            // inv_pct_pib e inv_pct_gasto_total no siempre están poblados en
            // ejecucion_historica; se completan desde la serie pgn_* como respaldo.
            return await db.QueryAsync("""
                SELECT eh.vigencia, eh.vigente_mmm, eh.compromisos_mmm,
                       eh.obligaciones_mmm, eh.pagos_mmm,
                       ROUND(CAST(eh.compromisos_mmm AS FLOAT)  * 100.0 / NULLIF(eh.vigente_mmm, 0), 2) AS pct_compromisos,
                       ROUND(CAST(eh.obligaciones_mmm AS FLOAT) * 100.0 / NULLIF(eh.vigente_mmm, 0), 2) AS pct_obligaciones,
                       ROUND(CAST(eh.pagos_mmm AS FLOAT)        * 100.0 / NULLIF(eh.vigente_mmm, 0), 2) AS pct_pagos,
                       COALESCE(eh.inv_pct_pib, (
                           SELECT ROUND(CAST(pib.valor AS FLOAT) * 100, 1)
                           FROM dbo.pgn_ejecucion pib
                           JOIN dbo.pgn_concepto cpib ON cpib.id = pib.concepto_id
                                AND cpib.nombre = 'Inversión como % del PIB'
                           WHERE pib.anio = eh.vigencia AND pib.fase = 'Vigente'
                       )) AS inv_pct_pib,
                       COALESCE(eh.inv_pct_gasto_total, (
                           SELECT ROUND(CAST(v.valor AS FLOAT) * 100.0 / NULLIF(tot.valor, 0), 1)
                           FROM dbo.pgn_ejecucion v
                           JOIN dbo.pgn_concepto c ON c.id = v.concepto_id
                                AND c.nombre = 'Inversión' AND c.unidad = 'Miles mm COP'
                           JOIN dbo.pgn_ejecucion tot ON tot.anio = v.anio AND tot.fase = 'Vigente'
                           JOIN dbo.pgn_concepto ctot ON ctot.id = tot.concepto_id
                                AND ctot.nombre = 'Total PGN' AND ctot.unidad = 'Miles mm COP'
                           WHERE v.anio = eh.vigencia AND v.fase = 'Vigente'
                       )) AS inv_pct_gasto_total
                FROM dbo.ejecucion_historica eh
                WHERE eh.bitacora_id = @bid AND eh.vigencia >= 2022
                ORDER BY eh.vigencia
                """, new { bid = ctx.Id });
        })
            .WithSummary("Ejecución histórica de inversión por vigencia.");

        grupo.MapGet("/sectores/apropiacion", async (int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            return await db.QueryAsync("""
                SELECT vigencia, sector, vigente_mmm
                FROM dbo.apropiacion_por_sector
                WHERE bitacora_id = @bid AND vigencia = @vigencia
                ORDER BY vigente_mmm DESC, sector COLLATE Latin1_General_BIN2
                """, new { bid = ctx.Id, vigencia = ctx.Vigencia });
        })
            .WithSummary("Apropiación vigente por sector.");

        grupo.MapGet("/sectores/compromisos_pct", async (int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            return await db.QueryAsync("""
                SELECT vigencia, sector, pct_compromisos
                FROM dbo.compromisos_pct_por_sector
                WHERE bitacora_id = @bid AND vigencia = @vigencia
                ORDER BY pct_compromisos DESC, sector COLLATE Latin1_General_BIN2
                """, new { bid = ctx.Id, vigencia = ctx.Vigencia });
        })
            .WithSummary("% de compromisos sobre apropiación por sector.");

        grupo.MapGet("/sectores/obligaciones_pct", async (int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            return await db.QueryAsync("""
                SELECT vigencia, sector, pct_obligaciones
                FROM dbo.obligaciones_pct_por_sector
                WHERE bitacora_id = @bid AND vigencia = @vigencia
                ORDER BY pct_obligaciones DESC, sector COLLATE Latin1_General_BIN2
                """, new { bid = ctx.Id, vigencia = ctx.Vigencia });
        })
            .WithSummary("% de obligaciones sobre apropiación por sector.");

        grupo.MapGet("/sectores/pagos_pct", async (int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            return await db.QueryAsync("""
                SELECT vigencia, sector, pct_pagos
                FROM dbo.pagos_pct_por_sector
                WHERE bitacora_id = @bid AND vigencia = @vigencia
                ORDER BY pct_pagos DESC, sector COLLATE Latin1_General_BIN2
                """, new { bid = ctx.Id, vigencia = ctx.Vigencia });
        })
            .WithSummary("% de pagos sobre apropiación por sector.");

        grupo.MapGet("/sectores/matriz", async (int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            return await Services.MatrizSectores.ConstruirAsync(db, ctx.Id);
        })
            .WithSummary("Matriz por sector y vigencia: apropiación, %C, %O, %P.");
    }
}
