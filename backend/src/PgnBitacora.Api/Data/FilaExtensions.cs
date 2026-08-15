namespace PgnBitacora.Api.Data;

public static class FilaExtensions
{
    /// <summary>
    /// Lee una columna de una fila devolviendo null si no existe, en lugar
    /// de lanzar. IDictionary no trae GetValueOrDefault (solo lo tienen
    /// Dictionary e IReadOnlyDictionary).
    /// </summary>
    public static object? Valor(this IDictionary<string, object?> fila, string columna)
        => fila.TryGetValue(columna, out var v) ? v : null;
}
