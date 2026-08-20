# Despliegue en IIS — Bitácora de Inversión Pública

**Para:** quien despliegue la aplicación en un servidor Windows con IIS
**Actualizado:** 20 de agosto de 2026

> IIS es el destino natural de una aplicación ASP.NET Core: el despliegue es **publicar una carpeta y apuntar un sitio a ella**. No hace falta Docker, ni proxy inverso adicional, ni cambiar una línea de código.

---

## 1. Requisitos en el servidor Windows

| Componente | Nota |
|---|---|
| Windows Server con **IIS** habilitado | Rol «Servidor web (IIS)» |
| **ASP.NET Core 8 Hosting Bundle** | Lo único que hay que instalar. Trae el runtime y el módulo `AspNetCoreModuleV2` que IIS necesita |
| Acceso a **SQL Server** | Desde el servidor de IIS, por red |

Instalar el Hosting Bundle **después** de IIS. Si se hace al revés, hay que repararlo. Luego reiniciar IIS:

```
net stop was /y
net start w3svc
```

Comprobar que el módulo quedó registrado:

```
%windir%\system32\inetsrv\appcmd.exe list modules | findstr AspNetCore
```

**No hace falta instalar el SDK de .NET** en el servidor: la aplicación se publica ya compilada desde otra máquina.

---

## 2. Generar el paquete

Desde el equipo de desarrollo — Linux, Windows o macOS, es indistinto:

```bash
dotnet publish backend/src/PgnBitacora.Api -c Release -o publicar
```

Produce una carpeta de ~18 MB con todo lo necesario:

```
publicar/
├── PgnBitacora.Api.dll      la aplicación
├── web.config               generado solo — es lo que IIS lee
├── appsettings.json
├── *.dll                    dependencias
└── frontend/                el tablero, con vendor/ y data/
```

Dos cosas que conviene entender:

- **`web.config` se genera automáticamente.** Declara el handler `AspNetCoreModuleV2` con `hostingModel="inprocess"`: la aplicación corre dentro del proceso de IIS. Es el modo por defecto y el más rápido; no hay que editarlo salvo para añadir variables de entorno (§4).
- **`frontend/` se copia por un target de MSBuild** definido en el `.csproj`. Sin él, `publish` produciría la API sin tablero y el sitio respondería 404 en la raíz. Se copia solo `frontend/`; la carpeta `data/` del repositorio —con los Excel fuente del DNP— queda deliberadamente fuera.

---

## 3. Configurar el sitio en IIS

**Copiar** la carpeta al servidor, por ejemplo a `C:\inetpub\bitacora`.

**Crear el grupo de aplicaciones** con una particularidad importante:

| Ajuste | Valor |
|---|---|
| Versión de .NET CLR | **Sin código administrado** |
| Modo de canalización | Integrada |
| Identidad | `ApplicationPoolIdentity` |

«Sin código administrado» desconcierta la primera vez, pero es correcto: IIS no ejecuta .NET Framework aquí, solo hospeda el proceso de .NET Core.

**Crear el sitio** apuntando la ruta física a esa carpeta, asignarle el grupo de aplicaciones y el enlace HTTPS con su certificado.

**Dar permiso de lectura** a la identidad del grupo de aplicaciones:

```
icacls "C:\inetpub\bitacora" /grant "IIS AppPool\bitacora:(OI)(CI)RX"
```

---

## 4. La cadena de conexión

La aplicación la lee de la clave `ConnectionStrings:DnpDpip`. Hay dos formas.

**Opción A — `appsettings.Production.json`** junto al `.dll`:

```json
{
  "ConnectionStrings": {
    "DnpDpip": "Server=SERVIDOR_SQL;Database=dnp_dpip;User Id=dnp_dpip_app;Password=...;TrustServerCertificate=True"
  }
}
```

**Opción B — variable de entorno en `web.config`:**

```xml
<aspNetCore processPath="dotnet" arguments=".\PgnBitacora.Api.dll"
            stdoutLogEnabled="false" hostingModel="inprocess">
  <environmentVariables>
    <environmentVariable name="ConnectionStrings__DnpDpip"
                         value="Server=SERVIDOR_SQL;Database=dnp_dpip;..." />
    <environmentVariable name="ASPNETCORE_ENVIRONMENT" value="Production" />
  </environmentVariables>
</aspNetCore>
```

**Lo más limpio, si el SQL Server está en el mismo dominio:** autenticación integrada de Windows. Se le da permiso a la identidad del grupo de aplicaciones sobre la base y la cadena queda **sin contraseña**:

```
Server=SERVIDOR_SQL;Database=dnp_dpip;Integrated Security=true;TrustServerCertificate=True
```

Es la opción recomendada en un entorno institucional: no hay credencial que rotar ni que se filtre en un archivo de configuración.

### Convivencia en una base compartida

Todas las tablas llevan el prefijo `btcr_` (`btcr_metadatos_bitacora`, `btcr_pgn_concepto`, …), igual que sus restricciones e índices. Eso permite instalar el esquema **dentro de una base existente de la entidad** sin colisionar con otros sistemas: basta con ejecutar `db/mssql/*.sql` sobre ella.

Si se hace así, los permisos del usuario de la aplicación pueden acotarse a esas tablas en lugar de a la base entera.

### La base que se cree debe respetar la collation

```sql
CREATE DATABASE dnp_dpip COLLATE Modern_Spanish_CS_AS;
```

No es un detalle: con una collation insensible a tildes, `PACÍFICO` y `PACIFICO` se vuelven el mismo valor y las agrupaciones por región fusionan filas **sin dar error**. Ver la regla 2 del manual técnico.

---

## 5. Verificación

```powershell
curl.exe -s -o NUL -w "%{http_code}`n" https://SERVIDOR/health       # 200
curl.exe -s -o NUL -w "%{http_code}`n" https://SERVIDOR/             # 200, el tablero
curl.exe -s -o NUL -w "%{http_code}`n" https://SERVIDOR/api/resumen  # 200
```

Y la verificación completa de las 322 rutas contra la línea base, desde cualquier equipo con Python:

```bash
python tools/compare_apis.py --contra-linea-base --base-b https://SERVIDOR
```

Debe dar cero diferencias de claves, valores y estado HTTP. Es la misma comprobación que se corre tras cualquier cambio del backend.

---

## 6. Diagnóstico

| Síntoma | Causa habitual |
|---|---|
| **HTTP 500.19** | Falta el Hosting Bundle, o se instaló antes que IIS. Reinstalar y reiniciar IIS |
| **HTTP 500.30** — no arranca | La aplicación falló al iniciar, casi siempre por la cadena de conexión. Activar `stdoutLogEnabled="true"` y revisar `logs\stdout` |
| **HTTP 502.5** | El grupo de aplicaciones no está en «Sin código administrado» |
| **404 en la raíz** | Falta `frontend/` en la carpeta publicada. Verificar que el target de MSBuild se ejecutó |
| **Mapa en blanco** | Los `.geojson` no llegan. Los sirve la aplicación, no IIS, así que revisar el registro del tipo MIME en `Program.cs` |
| **No conecta a la base** | Cortafuegos, o la identidad del grupo de aplicaciones sin permisos si se usa autenticación integrada |

Para ver el detalle del arranque, activar el log en `web.config` (`stdoutLogEnabled="true"`) y **volver a desactivarlo después**: crece sin límite.

---

## 7. Actualizaciones posteriores

```bash
dotnet publish backend/src/PgnBitacora.Api -c Release -o publicar
```

Copiar sobre la carpeta existente y reciclar el grupo de aplicaciones. Para evitar bloqueos de archivo durante la copia, dejar un `app_offline.htm` en la raíz del sitio antes de copiar y borrarlo al terminar: IIS detiene la aplicación mientras exista.

**Cuidado:** si se usó la opción A del §4, conservar el `appsettings.Production.json`, que se sobrescribe en cada actualización. Con la opción B el `web.config` también se regenera, así que hay que volver a añadir el bloque de variables — razón adicional para preferir la autenticación integrada.

---

## 8. Diferencias frente al despliegue actual en contenedor

| Aspecto | Contenedor (hoy) | IIS |
|---|---|---|
| TLS | Caddy, certificado automático | IIS, certificado administrado por la entidad |
| Proceso | Kestrel en el contenedor | Kestrel dentro de IIS (in-process) |
| Actualizar | `docker compose up -d --build` | Copiar carpeta y reciclar |
| Configuración | `.env` | `web.config` o `appsettings.Production.json` |
| Reinicio automático | `restart: unless-stopped` | Grupo de aplicaciones de IIS |

**El código es idéntico en ambos.** No hay compilación condicional ni ramas por entorno: el mismo artefacto corre en los dos sitios. Se verificó ejecutando la carpeta publicada de forma aislada y corriendo contra ella la suite de 322 rutas, con el mismo resultado que el contenedor.

---

## Documentos relacionados

- `docs/MANUAL_OPERACION.md` — cargue trimestral e incidencias
- `docs/MANUAL_TECNICO.md` — para modificar el código
- `docs/ARQUITECTURA.md` — visión de conjunto
