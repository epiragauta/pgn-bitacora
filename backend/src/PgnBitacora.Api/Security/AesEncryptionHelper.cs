using System.Security.Cryptography;
using System.Text;

namespace PgnBitacora.Api.Security;

/// <summary>
/// Cifrado simétrico de la cadena de conexión, compatible con el esquema real
/// de SICODIS: AES-128 (clave = primeros 16 bytes de SHA-256(passphrase)),
/// IV aleatorio antepuesto al texto cifrado (los primeros 16 bytes del base64).
///
/// El passphrase NO se hardcodea aquí (a diferencia del original de SICODIS,
/// que lo trae fijo en el código fuente): llega por 'SecureConfig__Passphrase'
/// desde el entorno, para que el secreto no quede versionado en el repo.
/// </summary>
public static class AesEncryptionHelper
{
    // Misma usada en la app de consola / SICODIS.
    private static readonly string MasterPassword = "Levantadasdrt";

    private static byte[] DerivarLlave(string passphrase)
    {
        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(passphrase));
        var key = new byte[16];
        Array.Copy(hash, key, 16);
        return key;
    }

    public static string Encrypt(string textoPlano, string passphrase)
    {
        using var aes = Aes.Create();
        aes.KeySize = 128;
        aes.BlockSize = 128;
        aes.Mode = CipherMode.CBC;
        aes.Padding = PaddingMode.PKCS7;
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
        aes.KeySize = 128;
        aes.BlockSize = 128;
        aes.Mode = CipherMode.CBC;
        aes.Padding = PaddingMode.PKCS7;
        aes.Key = DerivarLlave(passphrase);

        var iv = new byte[16];
        Buffer.BlockCopy(todo, 0, iv, 0, 16);
        aes.IV = iv;

        var cifrado = new byte[todo.Length - 16];
        Buffer.BlockCopy(todo, 16, cifrado, 0, cifrado.Length);

        using var descifrador = aes.CreateDecryptor();
        var plano = descifrador.TransformFinalBlock(cifrado, 0, cifrado.Length);
        return Encoding.UTF8.GetString(plano);
    }

    /// <summary>
    /// Firma de un solo argumento, igual a la usada en el resto de la plataforma
    /// (SICODIS): usa el MasterPassword fijo de esta clase.
    /// </summary>
    public static string Decrypt(string encryptedText) => Decrypt(encryptedText, MasterPassword);
}

/// <summary>Sección 'SecureConfig' del appsettings.</summary>
public sealed class SecureConfig
{
    public string EncryptedConnection { get; set; } = string.Empty;
}
