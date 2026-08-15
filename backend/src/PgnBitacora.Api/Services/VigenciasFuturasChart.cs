using PgnBitacora.Api.Data;

namespace PgnBitacora.Api.Services;

/// <summary>
/// Datos del gráfico de vigencias futuras. Port de get_vigencias_chart()
/// de api/main.py.
///
/// Detalle que hay que respetar: los totales se calculan sumando los
/// valores SIN redondear y redondeando al final, mientras que cada serie
/// se redondea antes. Por eso el total puede no coincidir con la suma de
/// las series que se ven en pantalla — es el comportamiento del original y
/// se conserva tal cual.
///
/// Math.Round de .NET y round() de Python usan ambos redondeo al par más
/// cercano, así que los resultados coinciden sin ajustes.
/// </summary>
public static class VigenciasFuturasChart
{
    private static readonly string[] SectoresConNombre =
    [
        "TRANSPORTE",
        "IGUALDAD Y EQUIDAD",
        "HACIENDA",
        "DEFENSA Y POLICÍA",
        "SALUD Y PROTECCIÓN SOCIAL",
    ];

    private const string Otros = "OTROS SECTORES";

    private static readonly int[] Anios = Enumerable.Range(2027, 14).ToArray(); // 2027..2040

    public static async Task<object> ConstruirAsync(IDb db, int bitacoraId)
    {
        var filas = await db.QueryAsync("""
            SELECT v.vigencia_exec,
                   v.sector,
                   ROUND(CAST(v.valor_corriente_mmm AS FLOAT) / NULLIF(d.deflactor, 0), 3) AS valor_ctes
            FROM dbo.vigencias_futuras v
            JOIN dbo.deflactores_pib d
              ON d.bitacora_id = v.bitacora_id AND d.anio = v.vigencia_exec
            WHERE v.bitacora_id = @bid
              AND v.vigencia_exec BETWEEN 2027 AND 2040
            """, new { bid = bitacoraId });

        var pibFilas = await db.QueryAsync("""
            SELECT anio, pib_constante_mmm
            FROM dbo.deflactores_pib
            WHERE bitacora_id = @bid AND anio BETWEEN 2027 AND 2040
            """, new { bid = bitacoraId });

        var pib = pibFilas
            .Where(f => f["pib_constante_mmm"] is not null)
            .ToDictionary(f => Convert.ToInt32(f["anio"]), f => Convert.ToDouble(f["pib_constante_mmm"]));

        // Se acumula en double, no en decimal: el original hace estas sumas
        // en punto flotante de Python y el redondeo al par más cercano puede
        // caer del otro lado si el tipo intermedio cambia.
        var series = SectoresConNombre.Append(Otros).ToArray();
        var acum = series.ToDictionary(s => s, _ => new Dictionary<int, double>());

        foreach (var f in filas)
        {
            var sector = (string)f["sector"]!;
            var anio = Convert.ToInt32(f["vigencia_exec"]);
            var valor = f["valor_ctes"] is null ? 0d : Convert.ToDouble(f["valor_ctes"]);

            var serie = SectoresConNombre.Contains(sector) ? sector : Otros;
            acum[serie][anio] = acum[serie].GetValueOrDefault(anio) + valor;
        }

        var salidaSeries = series.Select(s => new Dictionary<string, object?>
        {
            ["sector"] = s,
            ["valores"] = Anios.Select(a => Math.Round(acum[s].GetValueOrDefault(a), 1)).ToArray(),
        }).ToList();

        var totales = Anios
            .Select(a => Math.Round(series.Sum(s => acum[s].GetValueOrDefault(a)), 1))
            .ToArray();

        var pctPib = Anios.Select((a, i) =>
                pib.TryGetValue(a, out var p) && p != 0
                    ? Math.Round(totales[i] / p * 100, 4)
                    : (double?)null)
            .ToArray();

        return new Dictionary<string, object?>
        {
            ["anios"] = Anios,
            ["series"] = salidaSeries,
            ["totales"] = totales,
            ["pct_pib"] = pctPib,
        };
    }
}
