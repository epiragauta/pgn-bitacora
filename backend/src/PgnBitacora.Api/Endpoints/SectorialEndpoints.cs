using PgnBitacora.Api.Data;

namespace PgnBitacora.Api.Endpoints;

/// <summary>Sección 6 — Ejecución sectorial por entidad y serie mensual.</summary>
public static class SectorialEndpoints
{
    public static void MapSectorial(this IEndpointRouteBuilder app)
    {
        var grupo = app.MapGroup("/api/sectorial").WithTags("Sec 6 - Ejecución Sectorial");

        grupo.MapGet("", async (string? sector, int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            var sql = """
                SELECT vigencia, sector, entidad, apr_vigente_mmm,
                       compromisos_mmm, obligaciones_mmm, pct_c_av, pct_o_av
                FROM dbo.ejecucion_sectorial_entidades
                WHERE bitacora_id = @bid AND vigencia = @vigencia
                """;

            if (sector is not null)
                sql += " AND sector = @sector";

            sql += " ORDER BY sector COLLATE Latin1_General_BIN2, apr_vigente_mmm DESC, entidad COLLATE Latin1_General_BIN2";

            return await db.QueryAsync(sql, new
            {
                bid = ctx.Id,
                vigencia = ctx.Vigencia,
                sector = sector?.ToUpperInvariant()
            });
        })
            .WithSummary("Ejecución sectorial por entidad.");

        grupo.MapGet("/mensual", async (string? sector, int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            var sql = """
                SELECT vigencia, sector, mes,
                       pct_compromisos_2025, pct_compromisos_2024,
                       pct_compromisos_prom, pct_compromisos_mejor,
                       pct_obligaciones_2025, pct_obligaciones_2024,
                       pct_obligaciones_prom, pct_obligaciones_mejor
                FROM dbo.ejecucion_sectorial_mensual
                WHERE bitacora_id = @bid AND vigencia = @vigencia
                """;

            if (sector is not null)
                sql += " AND sector = @sector";

            sql += " ORDER BY sector COLLATE Latin1_General_BIN2, mes";

            return await db.QueryAsync(sql, new
            {
                bid = ctx.Id,
                vigencia = ctx.Vigencia,
                sector = sector?.ToUpperInvariant()
            });
        })
            .WithSummary("Ejecución mensual comparada con años anteriores.");

        grupo.MapGet("/historico", async (string? sector, int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            var sql = """
                SELECT vigencia, sector, entidad,
                       apr_vigente_mmm, compromisos_mmm, obligaciones_mmm,
                       pct_c_av, pct_o_av
                FROM dbo.ejecucion_sectorial_entidades
                WHERE bitacora_id = @bid AND vigencia >= 2022
                """;

            if (sector is not null)
                sql += " AND sector = @sector";

            sql += """
                 ORDER BY sector COLLATE Latin1_General_BIN2,
                          entidad COLLATE Latin1_General_BIN2,
                          vigencia
                """;

            return await db.QueryAsync(sql, new { bid = ctx.Id, sector = sector?.ToUpperInvariant() });
        })
            .WithSummary("Entidades por sector con todas las vigencias disponibles.");
    }
}
