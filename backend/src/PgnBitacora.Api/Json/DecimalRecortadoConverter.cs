using System.Globalization;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace PgnBitacora.Api.Json;

/// <summary>
/// Serializa decimal sin ceros de relleno a la derecha.
///
/// SQL Server devuelve DECIMAL(18,6) conservando la escala, así que
/// System.Text.Json escribiría 547017.088000 donde la API Python escribía
/// 547017.088. Los dos son el mismo número y el frontend no notaría la
/// diferencia, pero el JSON queda más limpio y la comparación de paridad
/// de la Fase 4 no se llena de ruido.
/// </summary>
public sealed class DecimalRecortadoConverter : JsonConverter<decimal>
{
    public override decimal Read(ref Utf8JsonReader reader, Type tipo, JsonSerializerOptions opciones)
        => reader.GetDecimal();

    public override void Write(Utf8JsonWriter writer, decimal valor, JsonSerializerOptions opciones)
    {
        // Normalize() elimina los ceros no significativos (1.500000 -> 1.5)
        // sin alterar el valor. El +0.0000m fuerza esa normalización.
        var normalizado = valor / 1.000000000000000000000000000000000m;
        writer.WriteRawValue(normalizado.ToString(CultureInfo.InvariantCulture));
    }
}
