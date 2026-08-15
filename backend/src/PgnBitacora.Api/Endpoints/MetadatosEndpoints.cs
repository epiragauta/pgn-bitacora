using PgnBitacora.Api.Data;

namespace PgnBitacora.Api.Endpoints;

public static class MetadatosEndpoints
{
    // Las fechas se formatean en SQL, no en .NET: la API Python emitía
    // "2026-03-31" y "2026-06-20 19:26:16", mientras que System.Text.Json
    // serializaría un DateTime como "2026-03-31T00:00:00". El frontend hace
    // corte_fecha.split('-'), así que el formato importa.
    private const string Columnas = """
        id, numero_bitacora, periodo,
        CONVERT(char(10), corte_fecha, 23)  AS corte_fecha,
        fuente_principal, elaborado_por,
        CONVERT(char(19), fecha_carga, 120) AS fecha_carga,
        notas,
        YEAR(corte_fecha) AS vigencia
        """;

    public static void MapMetadatos(this IEndpointRouteBuilder app)
    {
        var grupo = app.MapGroup("/api").WithTags("Metadatos");

        grupo.MapGet("/bitacoras", async (IDb db) =>
            await db.QueryAsync($"SELECT {Columnas} FROM dbo.metadatos_bitacora ORDER BY corte_fecha DESC"))
            .WithSummary("Lista todas las bitácoras cargadas (más reciente primero).");

        grupo.MapGet("/bitacoras/{periodo}", async (string periodo, IDb db) =>
        {
            var fila = await db.QuerySingleAsync(
                $"SELECT {Columnas} FROM dbo.metadatos_bitacora WHERE periodo = @periodo",
                new { periodo });

            return fila is null
                ? Results.NotFound(new { detail = $"Bitácora periodo '{periodo}' no encontrada" })
                : Results.Ok(fila);
        })
            .WithSummary("Metadatos de una bitácora por periodo (ej. 2026-I).");
    }
}
