using PgnBitacora.Api.Data;

namespace PgnBitacora.Api.Services;

/// <summary>
/// KPIs del encabezado del dashboard. Port de get_resumen() de api/main.py.
///
/// Conserva el respaldo del original: si la bitácora no tiene fila en
/// ejecucion_historica para su vigencia, los totales se derivan sumando
/// ejecucion_transformaciones y los porcentajes se calculan al vuelo (con
/// un decimal, no dos), dejando en null los indicadores macro.
/// </summary>
public static class Resumen
{
    public static async Task<object> ConstruirAsync(IDb db, int bitacoraId, int vigencia)
    {
        var meta = await db.QuerySingleAsync("""
            SELECT periodo, CONVERT(char(10), corte_fecha, 23) AS corte_fecha, numero_bitacora
            FROM dbo.metadatos_bitacora WHERE id = @bid
            """, new { bid = bitacoraId });

        var p = new { bid = bitacoraId, vigencia };

        var inv = await db.QuerySingleAsync(
            "SELECT * FROM dbo.ejecucion_historica WHERE bitacora_id = @bid AND vigencia = @vigencia", p);

        Dictionary<string, object?> datos;

        if (inv is null)
        {
            var totales = await db.QuerySingleAsync("""
                SELECT ROUND(CAST(SUM(apr_vigente_mmm) AS FLOAT),  3) AS vigente_mmm,
                       ROUND(CAST(SUM(compromisos_mmm) AS FLOAT),  3) AS compromisos_mmm,
                       ROUND(CAST(SUM(obligaciones_mmm) AS FLOAT), 3) AS obligaciones_mmm,
                       ROUND(CAST(SUM(pagos_mmm) AS FLOAT),        3) AS pagos_mmm
                FROM dbo.ejecucion_transformaciones
                WHERE bitacora_id = @bid AND vigencia = @vigencia
                """, p);

            datos = totales is not null
                ? new Dictionary<string, object?>(totales)
                : new Dictionary<string, object?>();

            decimal Valor(string clave) => datos.GetValueOrDefault(clave) is { } v ? Convert.ToDecimal(v) : 0m;

            var vigente = Valor("vigente_mmm");
            decimal? Pct(string clave) =>
                vigente != 0m ? Math.Round(Valor(clave) / vigente * 100, 1) : null;

            datos["pct_compromisos"] = Pct("compromisos_mmm");
            datos["pct_obligaciones"] = Pct("obligaciones_mmm");
            datos["pct_pagos"] = Pct("pagos_mmm");
            datos["inv_pct_pib"] = null;
            datos["inv_pct_gasto_total"] = null;
        }
        else
        {
            datos = new Dictionary<string, object?>(inv);
        }

        var totalTransf = await db.QuerySingleAsync("""
            SELECT SUM(inversion_mmm) AS total
            FROM dbo.inversion_transformaciones
            WHERE bitacora_id = @bid AND vigencia = @vigencia
            """, p);

        var vfTotal = await db.QuerySingleAsync("""
            SELECT ROUND(SUM(CAST(v.valor_corriente_mmm AS FLOAT) / NULLIF(d.deflactor, 0)), 1) AS total
            FROM dbo.vigencias_futuras v
            JOIN dbo.deflactores_pib d
              ON d.bitacora_id = v.bitacora_id AND d.anio = v.vigencia_exec
            WHERE v.bitacora_id = @bid AND v.vigencia_exec BETWEEN 2027 AND 2040
            """, new { bid = bitacoraId });

        return new Dictionary<string, object?>
        {
            ["bitacora_id"] = bitacoraId,
            ["vigencia"] = vigencia,
            ["periodo"] = meta?.Valor("periodo"),
            ["numero_bitacora"] = meta?.Valor("numero_bitacora"),
            ["corte_fecha"] = meta?.Valor("corte_fecha"),
            ["inversion_vigente_mmm"] = datos.GetValueOrDefault("vigente_mmm"),
            ["inversion_compromisos_mmm"] = datos.GetValueOrDefault("compromisos_mmm"),
            ["inversion_obligaciones_mmm"] = datos.GetValueOrDefault("obligaciones_mmm"),
            ["inversion_pagos_mmm"] = datos.GetValueOrDefault("pagos_mmm"),
            ["pct_compromisos"] = datos.GetValueOrDefault("pct_compromisos"),
            ["pct_obligaciones"] = datos.GetValueOrDefault("pct_obligaciones"),
            ["pct_pagos"] = datos.GetValueOrDefault("pct_pagos"),
            ["inv_pct_pib"] = datos.GetValueOrDefault("inv_pct_pib"),
            ["inv_pct_gasto_total"] = datos.GetValueOrDefault("inv_pct_gasto_total"),
            ["total_transformaciones_mmm"] = totalTransf?.Valor("total"),
            ["vigencias_futuras_total_mmm"] = vfTotal?.Valor("total"),
            ["fuente"] = "SIIF Nación / DPIP - DNP",
        };
    }
}
