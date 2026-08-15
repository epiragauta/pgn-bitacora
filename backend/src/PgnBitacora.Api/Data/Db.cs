using System.Data;
using Dapper;
using Microsoft.Data.SqlClient;

namespace PgnBitacora.Api.Data;

/// <summary>
/// Acceso a datos. Deliberadamente delgado: las consultas viven en los
/// endpoints y los resultados se devuelven como diccionarios, de modo que
/// los alias de columna del SQL sean literalmente las claves del JSON.
///
/// Esto no es pereza: el frontend (frontend/index.html) lee claves
/// snake_case exactas y, si una no coincide, cae en silencio a sus datos
/// embebidos sin mostrar error. Con DTOs tipados bastaría un renombre
/// accidental para romperlo; aquí el SQL es el contrato.
/// </summary>
public interface IDb
{
    Task<IReadOnlyList<IDictionary<string, object?>>> QueryAsync(string sql, object? parametros = null);
    Task<IDictionary<string, object?>?> QuerySingleAsync(string sql, object? parametros = null);
}

public sealed class Db : IDb
{
    private readonly string _cadena;

    public Db(IConfiguration config)
    {
        _cadena = config.GetConnectionString("DnpDpip")
            ?? throw new InvalidOperationException(
                "Falta la cadena de conexión 'DnpDpip'. Definir ConnectionStrings__DnpDpip " +
                "como variable de entorno o vía 'dotnet user-secrets'.");
    }

    private SqlConnection Abrir() => new(_cadena);

    public async Task<IReadOnlyList<IDictionary<string, object?>>> QueryAsync(string sql, object? parametros = null)
    {
        using IDbConnection cn = Abrir();
        var filas = await cn.QueryAsync(sql, parametros);
        // Se copia a un Dictionary concreto: DapperRow es un tipo interno y
        // System.Text.Json no garantiza serializarlo como objeto.
        return filas
            .Cast<IDictionary<string, object>>()
            .Select(f => (IDictionary<string, object?>)new Dictionary<string, object?>(f!))
            .ToList();
    }

    public async Task<IDictionary<string, object?>?> QuerySingleAsync(string sql, object? parametros = null)
    {
        var filas = await QueryAsync(sql, parametros);
        return filas.Count > 0 ? filas[0] : null;
    }
}
