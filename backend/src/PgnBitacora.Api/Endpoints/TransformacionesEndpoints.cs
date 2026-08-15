using PgnBitacora.Api.Data;

namespace PgnBitacora.Api.Endpoints;

/// <summary>Sección 1 — Transformaciones del PND 2022-2026.</summary>
public static class TransformacionesEndpoints
{
    public static void MapTransformaciones(this IEndpointRouteBuilder app)
    {
        var grupo = app.MapGroup("/api").WithTags("Sec 1 - Transformaciones PND");

        grupo.MapGet("/transformaciones", async (int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            return await db.QueryAsync("""
                SELECT t.transformador, t.inversion_mmm, t.peso_pct,
                       e.compromisos_mmm, e.obligaciones_mmm, e.pagos_mmm,
                       e.pct_c_av, e.pct_o_av, e.pct_p_av
                FROM dbo.inversion_transformaciones t
                LEFT JOIN dbo.ejecucion_transformaciones e
                       ON t.bitacora_id   = e.bitacora_id
                      AND t.vigencia      = e.vigencia
                      AND t.transformador = e.transformador
                WHERE t.bitacora_id = @bid AND t.vigencia = @vigencia
                ORDER BY t.inversion_mmm DESC, t.transformador COLLATE Latin1_General_BIN2
                """, new { bid = ctx.Id, vigencia = ctx.Vigencia });
        })
            .WithSummary("Distribución de inversión por transformadores del PND.");

        grupo.MapGet("/transformaciones/{transformador}/componentes",
            async (string transformador, int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            return await db.QueryAsync("""
                SELECT componente, vigente_mmm, peso_pct
                FROM dbo.inversion_componentes_pnd
                WHERE bitacora_id = @bid AND vigencia = @vigencia AND transformador = @transformador
                ORDER BY vigente_mmm DESC, componente COLLATE Latin1_General_BIN2
                """, new { bid = ctx.Id, vigencia = ctx.Vigencia, transformador });
        })
            .WithSummary("Componentes de un transformador del PND.");
    }
}
