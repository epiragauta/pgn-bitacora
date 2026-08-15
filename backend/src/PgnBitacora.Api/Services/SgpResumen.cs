using PgnBitacora.Api.Data;

namespace PgnBitacora.Api.Services;

/// <summary>KPIs del SGP. Port de get_sgp_resumen() de api/main.py.</summary>
public static class SgpResumen
{
    public static async Task<object> ConstruirAsync(IDb db, int bitacoraId)
    {
        var filas = await db.QueryAsync("""
            SELECT vigencia, total_mmm
            FROM dbo.sgp_historico_participacion
            WHERE bitacora_id = @bid
            ORDER BY vigencia
            """, new { bid = bitacoraId });

        if (filas.Count == 0)
            return new Dictionary<string, object?>();

        var ultimo = filas[^1];
        var anterior = filas.Count > 1 ? filas[^2] : null;

        decimal? TotalDe(IDictionary<string, object?>? f) =>
            f?["total_mmm"] is { } v ? Convert.ToDecimal(v) : null;

        var totalUltimo = TotalDe(ultimo);
        var totalAnterior = TotalDe(anterior);
        var acumulado = filas.Sum(f => TotalDe(f) ?? 0m);

        return new Dictionary<string, object?>
        {
            ["vigencia_reciente"] = ultimo["vigencia"],
            ["total_reciente_mmm"] = totalUltimo,
            ["vigencia_anterior"] = anterior?["vigencia"],
            ["total_anterior_mmm"] = totalAnterior,
            ["crecimiento_pct"] = totalAnterior is not null && totalAnterior != 0m && totalUltimo is not null
                ? Math.Round((totalUltimo.Value / totalAnterior.Value - 1) * 100, 2)
                : null,
            ["total_acumulado_mmm"] = Math.Round(acumulado, 3),
        };
    }
}
