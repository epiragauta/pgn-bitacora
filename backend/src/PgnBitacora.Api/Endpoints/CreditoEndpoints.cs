using PgnBitacora.Api.Data;

namespace PgnBitacora.Api.Endpoints;

/// <summary>
/// Sección 7 — Crédito externo (SCCI). Montos del portafolio en USD;
/// la ejecución presupuestal en mmm COP.
/// </summary>
public static class CreditoEndpoints
{
    public static void MapCredito(this IEndpointRouteBuilder app)
    {
        var grupo = app.MapGroup("/api/credito").WithTags("Sec 7 - Crédito Externo");

        grupo.MapGet("", async (string? fuente, string? sector, int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            var sql = """
                SELECT nombre, nombre_corto, fuente, contrato, sector, monto_usd, desembolsado_usd
                FROM dbo.credito_portafolio
                WHERE bitacora_id = @bid
                """;

            if (fuente is not null) sql += " AND fuente = @fuente";
            if (sector is not null) sql += " AND sector = @sector";

            sql += " ORDER BY monto_usd DESC, nombre COLLATE Latin1_General_BIN2";

            // El original solo normaliza a mayúsculas la fuente, no el sector.
            return await db.QueryAsync(sql, new
            {
                bid = ctx.Id,
                fuente = fuente?.ToUpperInvariant(),
                sector
            });
        })
            .WithSummary("Portafolio de créditos externos vigentes (BID, BM, CAF).");

        grupo.MapGet("/fuentes", async (int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            return await db.QueryAsync("""
                SELECT fuente,
                       COUNT(*) AS n_creditos,
                       ROUND(CAST(SUM(monto_usd) AS FLOAT), 2)        AS monto_usd,
                       ROUND(CAST(SUM(desembolsado_usd) AS FLOAT), 2) AS desembolsado_usd
                FROM dbo.credito_portafolio
                WHERE bitacora_id = @bid
                GROUP BY fuente
                ORDER BY monto_usd DESC, fuente COLLATE Latin1_General_BIN2
                """, new { bid = ctx.Id });
        })
            .WithSummary("Operaciones agrupadas por fuente de financiación.");

        grupo.MapGet("/sectores", async (int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            return await db.QueryAsync("""
                SELECT sector,
                       COUNT(*) AS n_creditos,
                       ROUND(CAST(SUM(monto_usd) AS FLOAT), 2)        AS monto_usd,
                       ROUND(CAST(SUM(desembolsado_usd) AS FLOAT), 2) AS desembolsado_usd,
                       ROUND(CAST(SUM(desembolsado_usd) AS FLOAT) * 100.0 / NULLIF(SUM(monto_usd), 0), 2) AS pct_desembolsado
                FROM dbo.credito_portafolio
                WHERE bitacora_id = @bid
                GROUP BY sector
                ORDER BY monto_usd DESC, sector COLLATE Latin1_General_BIN2
                """, new { bid = ctx.Id });
        })
            .WithSummary("Créditos y desembolsos agrupados por sector.");

        grupo.MapGet("/resumen", async (int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            var fila = await db.QuerySingleAsync("""
                SELECT COUNT(*) AS n_creditos,
                       ROUND(CAST(SUM(monto_usd) AS FLOAT), 2)        AS monto_total_usd,
                       ROUND(CAST(SUM(desembolsado_usd) AS FLOAT), 2) AS desembolsado_total_usd,
                       ROUND(CAST(SUM(desembolsado_usd) AS FLOAT) * 100.0 / NULLIF(SUM(monto_usd), 0), 2) AS pct_desembolsado
                FROM dbo.credito_portafolio
                WHERE bitacora_id = @bid
                """, new { bid = ctx.Id });

            return fila ?? new Dictionary<string, object?>();
        })
            .WithSummary("KPIs del portafolio de crédito externo.");

        grupo.MapGet("/ejecucion_entidad", async (int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            return await db.QueryAsync("""
                SELECT entidad, sector, apr_inicial_mmm, apr_vigente_mmm, compromiso_mmm,
                       obligacion_mmm, pago_mmm, pct_com, pct_ejec, pct_pago
                FROM dbo.credito_ejecucion_entidad
                WHERE bitacora_id = @bid
                ORDER BY apr_vigente_mmm DESC, entidad COLLATE Latin1_General_BIN2
                """, new { bid = ctx.Id });
        })
            .WithSummary("Ejecución presupuestal por entidad de los recursos de crédito externo.");

        grupo.MapGet("/ejecucion_historica", async (int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            return await db.QueryAsync("""
                SELECT anio, pct_comprometido, pct_ejecutado, pct_pagado,
                       vigente_mmm, comprometido_mmm, ejecutado_mmm, pagado_mmm
                FROM dbo.credito_ejecucion_historica
                WHERE bitacora_id = @bid
                ORDER BY anio
                """, new { bid = ctx.Id });
        })
            .WithSummary("Comparativo histórico de ejecución de crédito externo.");
    }
}
