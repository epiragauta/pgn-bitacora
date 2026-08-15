using PgnBitacora.Api.Data;

namespace PgnBitacora.Api.Endpoints;

/// <summary>Sección 8 — Sistema General de Participaciones (SGP).</summary>
public static class SgpEndpoints
{
    public static void MapSgp(this IEndpointRouteBuilder app)
    {
        var grupo = app.MapGroup("/api/sgp").WithTags("Sec 8 - SGP");

        grupo.MapGet("/historico", async (int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            return await db.QueryAsync("""
                SELECT vigencia, educacion_mmm, salud_mmm, agua_potable_mmm, proposito_general_mmm,
                       alimentacion_escolar_mmm, riberenos_mmm, resguardos_indigenas_mmm,
                       fonpet_ae_mmm, total_mmm
                FROM dbo.sgp_historico_participacion
                WHERE bitacora_id = @bid
                ORDER BY vigencia
                """, new { bid = ctx.Id });
        })
            .WithSummary("Serie histórica del SGP por participación.");

        grupo.MapGet("/historico_componentes", async (int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            return await db.QueryAsync("""
                SELECT vigencia, orden, participacion, componente, es_total, valor_mmm
                FROM dbo.sgp_historico_componentes
                WHERE bitacora_id = @bid
                ORDER BY orden, vigencia
                """, new { bid = ctx.Id });
        })
            .WithSummary("Histórico del SGP desagregado por componente.");

        grupo.MapGet("/resumen", async (int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            return await Services.SgpResumen.ConstruirAsync(db, ctx.Id);
        })
            .WithSummary("KPIs del SGP: último año, crecimiento y acumulado.");
    }
}
