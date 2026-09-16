using System.Security.Cryptography;
using System.Text;

namespace PgnBitacora.Api.Security;

/// <summary>
/// Cifrado simétrico de la cadena de conexión, con la misma convención que
/// el resto de la plataforma (SICODIS): AES con llave derivada del passphrase
/// mediante SHA-256, de modo que un texto legible de cualquier longitud
/// produzca siempre una llave AES-256 de 32 bytes.
///
/// Diferencia deliberada frente al original: el IV es aleatorio y se antepone
/// al texto cifrado (los primeros 16 bytes del base64). Así dos cifrados del
/// mismo valor no coinciden y no hay que gestionar un IV fijo por separado.
///
/// El passphrase NO se embebe en el binario: llega por configuración
/// (variable de entorno 'SecureConfig__Passphrase'), para que el secreto no
/// viaje en el repositorio ni en la imagen.
/// </summary>
public static class AesEncryptionHelper
{
    private static byte[] DerivarLlave(string passphrase) =>
        SHA256.HashData(Encoding.UTF8.GetBytes(passphrase));

    public static string Encrypt(string textoPlano, string passphrase)
    {
        using var aes = Aes.Create();
        aes.Key = DerivarLlave(passphrase);
        aes.GenerateIV();

        using var cifrador = aes.CreateEncryptor();
        var datos = Encoding.UTF8.GetBytes(textoPlano);
        var cifrado = cifrador.TransformFinalBlock(datos, 0, datos.Length);

        // [ IV (16 bytes) | texto cifrado ] → base64
        var salida = new byte[aes.IV.Length + cifrado.Length];
        Buffer.BlockCopy(aes.IV, 0, salida, 0, aes.IV.Length);
        Buffer.BlockCopy(cifrado, 0, salida, aes.IV.Length, cifrado.Length);
        return Convert.ToBase64String(salida);
    }

    public static string Decrypt(string textoCifradoBase64, string passphrase)
    {
        var todo = Convert.FromBase64String(textoCifradoBase64);
        if (todo.Length <= 16)
            throw new CryptographicException(
                "El texto cifrado es demasiado corto para contener el IV de 16 bytes.");

        using var aes = Aes.Create();
        aes.Key = DerivarLlave(passphrase);

        var iv = new byte[16];
        Buffer.BlockCopy(todo, 0, iv, 0, 16);
        aes.IV = iv;

        using var descifrador = aes.CreateDecryptor();
        var plano = descifrador.TransformFinalBlock(todo, 16, todo.Length - 16);
        return Encoding.UTF8.GetString(plano);
    }
}

/// <summary>Sección 'SecureConfig' del appsettings.</summary>
public sealed class SecureConfig
{
    public string EncryptedConnection { get; set; } = string.Empty;
    /// <summary>
    /// Passphrase para derivar la llave. Puede venir en el appsettings, pero
    /// lo esperado es sobreescribirlo con 'SecureConfig__Passphrase' desde el
    /// entorno para que no quede versionado.
    /// </summary>
    public string Passphrase { get; set; } = string.Empty;
}
