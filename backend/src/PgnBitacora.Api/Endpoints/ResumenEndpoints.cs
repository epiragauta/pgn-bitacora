using PgnBitacora.Api.Data;

namespace PgnBitacora.Api.Endpoints;

/// <summary>KPIs principales del encabezado de la infografía.</summary>
public static class ResumenEndpoints
{
    public static void MapResumen(this IEndpointRouteBuilder app)
    {
        app.MapGet("/api/resumen", async (int? bitacora_id, IDb db) =>
        {
            var ctx = await BitacoraResolver.ResolverAsync(db, bitacora_id);
            return await Services.Resumen.ConstruirAsync(db, ctx.Id, ctx.Vigencia);
        })
            .WithTags("Dashboard")
            .WithSummary("KPIs principales para el dashboard.");
    }
}
