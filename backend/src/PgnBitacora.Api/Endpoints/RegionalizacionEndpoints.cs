using PgnBitacora.Api.Data;

namespace PgnBitacora.Api.Endpoints;

/// <summary>
/// Sección 3 — Regionalización de la inversión.
///
/// Nota sobre el ordenamiento por texto: SQLite compara con BINARY (bytes
/// UTF-8) y, con COLLATE NOCASE, pliega solo el ASCII. Una collation
/// española ordena por diccionario, donde 'Córdoba' va ANTES que
/// 'Cundinamarca'; en SQLite va DESPUÉS, porque el byte de 'ó' (0xC3)
/// supera a cualquier carácter ASCII. Para que el orden de las filas sea
/// idéntico al de la API actual se usa Latin1_General_BIN2, que compara
/// unidades de código UTF-16 y reproduce ese mismo criterio.
/// </summary>
public static class RegionalizacionEndpoints
{
    public static void MapRegionalizacion(this IEndpointRouteBuilder app)
    {
        var grupo = app.MapGroup("/api/regionalizacion").WithTags("Sec 3 - Regionalización");

        grupo.MapGet("", async (int? vigencia, string? region, int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            var sql = """
                SELECT r.vigencia, r.tipo, r.region, r.departamento,
                       r.codigo_dane, d.nombre AS nombre_dane,
                       r.apropiacion_mmm, r.compromisos_mmm, r.obligaciones_mmm, r.pagos_mmm,
                       r.pct_compromisos, r.pct_obligaciones, r.pct_pagos, r.pct_participacion
                FROM dbo.regionalizacion r
                LEFT JOIN dbo.dane_departamentos d ON d.codigo = r.codigo_dane
                WHERE r.bitacora_id = @bid AND r.vigencia = @vigencia
                """;

            if (region is not null)
                sql += " AND r.region = @region";

            // COLLATE NOCASE del origen -> UPPER(...) + comparación binaria.
            sql += """
                 ORDER BY r.region COLLATE Latin1_General_BIN2,
                          UPPER(r.departamento) COLLATE Latin1_General_BIN2
                """;

            return await db.QueryAsync(sql, new
            {
                bid = ctx.Id,
                vigencia = vigencia ?? 2025,
                region = region?.ToUpperInvariant()
            });
        })
            .WithSummary("Departamentos regionalizados para un año dado, con código DANE.");

        grupo.MapGet("/historico", async (int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            return await db.QueryAsync("""
                SELECT vigencia, region, tipo,
                       ROUND(CAST(SUM(apropiacion_mmm) AS FLOAT),  3) AS apropiacion_mmm,
                       ROUND(CAST(SUM(compromisos_mmm) AS FLOAT),  3) AS compromisos_mmm,
                       ROUND(CAST(SUM(obligaciones_mmm) AS FLOAT), 3) AS obligaciones_mmm,
                       ROUND(CAST(SUM(pagos_mmm) AS FLOAT),        3) AS pagos_mmm,
                       ROUND(CAST(SUM(compromisos_mmm) AS FLOAT) * 100.0 / NULLIF(SUM(apropiacion_mmm), 0), 2) AS pct_compromisos
                FROM dbo.regionalizacion
                WHERE bitacora_id = @bid
                  AND tipo IN ('departamento', 'por_regionalizar', 'nacional')
                GROUP BY vigencia, region, tipo
                ORDER BY vigencia, region COLLATE Latin1_General_BIN2
                """, new { bid = ctx.Id });
        })
            .WithSummary("Totales por región, todos los años.");

        grupo.MapGet("/sectores", async (int? vigencia, string? region, int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            var sql = """
                SELECT vigencia, region, sector,
                       apropiacion_mmm, compromisos_mmm, obligaciones_mmm, pagos_mmm
                FROM dbo.regionalizacion_sectores
                WHERE bitacora_id = @bid AND vigencia = @vigencia
                """;

            if (region is not null)
                sql += " AND region = @region";

            sql += " ORDER BY region COLLATE Latin1_General_BIN2, apropiacion_mmm DESC, sector COLLATE Latin1_General_BIN2";

            return await db.QueryAsync(sql, new
            {
                bid = ctx.Id,
                vigencia = vigencia ?? 2026,
                region = region?.ToUpperInvariant()
            });
        })
            .WithSummary("Sectores por región.");

        grupo.MapGet("/mapa", async (int? vigencia, int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            return await db.QueryAsync("""
                SELECT r.codigo_dane, r.departamento, r.region,
                       r.apropiacion_mmm, r.compromisos_mmm,
                       r.pct_compromisos, r.pct_participacion
                FROM dbo.regionalizacion r
                WHERE r.bitacora_id = @bid AND r.vigencia = @vigencia AND r.tipo = 'departamento'
                ORDER BY r.region COLLATE Latin1_General_BIN2,
                         r.departamento COLLATE Latin1_General_BIN2
                """, new { bid = ctx.Id, vigencia = vigencia ?? 2025 });
        })
            .WithSummary("Datos para colorear el mapa GeoJSON por departamento.");

        grupo.MapGet("/departamento/{codigo_dane}", async (string codigo_dane, int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            var filas = await db.QueryAsync("""
                SELECT r.vigencia, r.departamento, r.region,
                       r.apropiacion_mmm, r.compromisos_mmm, r.obligaciones_mmm, r.pagos_mmm,
                       r.pct_compromisos, r.pct_obligaciones, r.pct_participacion
                FROM dbo.regionalizacion r
                WHERE r.bitacora_id = @bid AND r.codigo_dane = @codigo
                ORDER BY r.vigencia
                """, new { bid = ctx.Id, codigo = codigo_dane });

            return filas.Count == 0
                ? Results.NotFound(new { detail = $"Departamento con código DANE '{codigo_dane}' no encontrado" })
                : Results.Ok(filas);
        })
            .WithSummary("Serie histórica de un departamento por código DANE.");
    }
}
