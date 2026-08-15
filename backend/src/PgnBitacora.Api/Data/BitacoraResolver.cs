namespace PgnBitacora.Api.Data;

/// <summary>
/// Port de resolve_bitacora() de api/main.py: resuelve el par
/// (bitacora_id, vigencia). Sin parámetro, la bitácora más reciente.
///
/// strftime('%Y', corte_fecha) de SQLite se traduce a YEAR(corte_fecha).
/// </summary>
public static class BitacoraResolver
{
    public sealed record Contexto(int Id, int Vigencia);

    public static async Task<Contexto> ResolverAsync(IDb db, int? bitacoraId)
    {
        const string baseSql = "SELECT id, YEAR(corte_fecha) AS vigencia FROM dbo.metadatos_bitacora";

        var fila = bitacoraId is not null
            ? await db.QuerySingleAsync($"{baseSql} WHERE id = @id", new { id = bitacoraId })
            : await db.QuerySingleAsync($"{baseSql} ORDER BY corte_fecha DESC OFFSET 0 ROWS FETCH NEXT 1 ROWS ONLY");

        if (fila is null)
            throw new BitacoraNoEncontradaException("Bitácora no encontrada");

        return new Contexto(Convert.ToInt32(fila["id"]), Convert.ToInt32(fila["vigencia"]));
    }
}

public sealed class BitacoraNoEncontradaException(string mensaje) : Exception(mensaje);
