using PgnBitacora.Api.Data;

namespace PgnBitacora.Api.Endpoints;

/// <summary>
/// Sección 5 — Vigencias futuras.
///
/// La tabla guarda pesos corrientes; la conversión a constantes 2026 se
/// hace al vuelo dividiendo por el deflactor del año. Ese deflactor es un
/// denominador, así que va protegido con NULLIF.
/// </summary>
public static class VigenciasFuturasEndpoints
{
    public static void MapVigenciasFuturas(this IEndpointRouteBuilder app)
    {
        var grupo = app.MapGroup("/api/vigencias_futuras").WithTags("Sec 5 - Vigencias Futuras");

        grupo.MapGet("", async (string? sector, int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            var sql = """
                SELECT vigencia_exec, sector, valor_corriente_mmm
                FROM dbo.vigencias_futuras
                WHERE bitacora_id = @bid
                """;

            if (sector is not null)
                sql += " AND sector = @sector";

            sql += " ORDER BY vigencia_exec, valor_corriente_mmm DESC, sector COLLATE Latin1_General_BIN2";

            return await db.QueryAsync(sql, new { bid = ctx.Id, sector = sector?.ToUpperInvariant() });
        })
            .WithSummary("Vigencias futuras por sector en pesos corrientes.");

        grupo.MapGet("/totales", async (int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            // CAST a FLOAT: SQLite hace toda la aritmética en doble precisión.
            // Con DECIMAL el resultado difería en el último decimal (1.2367
            // frente a 1.2368) por las reglas de escala de la división.
            return await db.QueryAsync("""
                SELECT v.vigencia_exec,
                       ROUND(CAST(SUM(v.valor_corriente_mmm) AS FLOAT), 3) AS total_corriente_mmm,
                       d.deflactor,
                       ROUND(CAST(SUM(v.valor_corriente_mmm) AS FLOAT) / NULLIF(d.deflactor, 0), 3) AS total_constante_mmm,
                       CASE WHEN d.pib_constante_mmm > 0
                            THEN ROUND(CAST(SUM(v.valor_corriente_mmm) AS FLOAT) / NULLIF(d.deflactor, 0)
                                       / NULLIF(d.pib_constante_mmm, 0) * 100, 4)
                            ELSE NULL END AS pct_pib
                FROM dbo.vigencias_futuras v
                LEFT JOIN dbo.deflactores_pib d
                       ON d.bitacora_id = v.bitacora_id AND d.anio = v.vigencia_exec
                WHERE v.bitacora_id = @bid
                  AND v.vigencia_exec BETWEEN 2027 AND 2040
                GROUP BY v.vigencia_exec, d.deflactor, d.pib_constante_mmm
                ORDER BY v.vigencia_exec
                """, new { bid = ctx.Id });
        })
            .WithSummary("Total por año: corrientes, deflactor, constantes y % PIB.");

        grupo.MapGet("/chart", async (int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            return await Services.VigenciasFuturasChart.ConstruirAsync(db, ctx.Id);
        })
            .WithSummary("Seis series en constantes 2026 más % PIB (2027-2040).");
    }
}
