using PgnBitacora.Api.Data;

namespace PgnBitacora.Api.Services;

/// <summary>
/// Pivot sector × vigencia con apropiación y los tres porcentajes de
/// ejecución. Port de get_sectores_matriz() de api/main.py: la combinación
/// se arma en memoria a partir de cuatro consultas, igual que el original.
///
/// El orden de sectores usa comparación ordinal para replicar el sorted()
/// de Python, que ordena por punto de código y no por diccionario.
/// </summary>
public static class MatrizSectores
{
    public static async Task<object> ConstruirAsync(IDb db, int bitacoraId)
    {
        var p = new { bid = bitacoraId };

        var apr = await db.QueryAsync(
            "SELECT vigencia, sector, vigente_mmm FROM dbo.apropiacion_por_sector WHERE bitacora_id=@bid", p);
        var cmp = await db.QueryAsync(
            "SELECT vigencia, sector, pct_compromisos FROM dbo.compromisos_pct_por_sector WHERE bitacora_id=@bid", p);
        var obl = await db.QueryAsync(
            "SELECT vigencia, sector, pct_obligaciones FROM dbo.obligaciones_pct_por_sector WHERE bitacora_id=@bid", p);
        var pag = await db.QueryAsync(
            "SELECT vigencia, sector, pct_pagos FROM dbo.pagos_pct_por_sector WHERE bitacora_id=@bid", p);

        // El universo de vigencias y sectores lo define la apropiación,
        // igual que en el original.
        var vigencias = apr.Select(f => Convert.ToInt32(f["vigencia"])).Distinct().OrderBy(v => v).ToList();
        var sectores = apr.Select(f => (string)f["sector"]!).Distinct()
                          .OrderBy(s => s, StringComparer.Ordinal).ToList();

        static Dictionary<(int, string), object?> Indexar(
            IReadOnlyList<IDictionary<string, object?>> filas, string columna) =>
            filas.ToDictionary(
                f => (Convert.ToInt32(f["vigencia"]), (string)f["sector"]!),
                f => f[columna]);

        var mApr = Indexar(apr, "vigente_mmm");
        var mCmp = Indexar(cmp, "pct_compromisos");
        var mObl = Indexar(obl, "pct_obligaciones");
        var mPag = Indexar(pag, "pct_pagos");

        static object?[] Serie(Dictionary<(int, string), object?> mapa, List<int> vigencias, string sector) =>
            vigencias.Select(v => mapa.GetValueOrDefault((v, sector))).ToArray();

        var resultado = sectores.Select(s => new Dictionary<string, object?>
        {
            ["sector"] = s,
            ["apr"] = Serie(mApr, vigencias, s),
            ["pct_c"] = Serie(mCmp, vigencias, s),
            ["pct_o"] = Serie(mObl, vigencias, s),
            ["pct_p"] = Serie(mPag, vigencias, s),
        }).ToList();

        return new Dictionary<string, object?>
        {
            ["vigencias"] = vigencias,
            ["sectores"] = resultado,
        };
    }
}
