# Despliegue en IIS — Bitácora de Inversión Pública

**Para:** quien despliegue la aplicación en un servidor Windows con IIS
**Actualizado:** 20 de agosto de 2026

> IIS es el destino natural de una aplicación ASP.NET Core: el despliegue es **publicar una carpeta y apuntar un sitio a ella**. No hace falta Docker, ni proxy inverso adicional, ni cambiar una línea de código.

---

> **El nombre de la base es libre.** Los scripts de `db/mssql/` no llevan `USE` ni lo presuponen, y todas las tablas van con el prefijo `btcr_`, así que el esquema puede instalarse en una base propia o dentro de una compartida con otros sistemas. En los ejemplos de esta guía, `MI_BASE` es un marcador: sustitúyelo por el nombre real.

---

## 0. Despliegue automatizado

Todo lo que describe esta guía está unificado en un script:

```powershell
$pw = Read-Host 'Contraseña de la aplicación' -AsSecureString
.\deploy\Deploy-Bitacora.ps1 -SqlServer SQLSRV01 -Database SICODIS `
                              -AppUser btcr_app -AppPassword $pw
```

Hace, en orden: verifica requisitos → crea las tablas y carga los datos →
publica la aplicación → crea el grupo de aplicaciones y la aplicación
anidada en IIS → escribe la cadena de conexión → verifica por HTTP.

Es **idempotente**: volver a ejecutarlo actualiza lo que exista. Admite
`-WhatIf` para ver qué haría sin tocar nada, y omitir fases con
`-OmitirBaseDatos`, `-OmitirDatos` u `-OmitirIIS`.

| Parámetro | Por defecto |
|---|---|
| `-SiteName` | `SICODIS` — sitio de IIS que la hospeda |
| `-AppName` | `bitacora` — resulta en `/bitacora/` |
| `-PhysicalPath` | `C:\inetpub\bitacora` |
| `-PublishPath` | ninguno; publica desde el código. Con él, usa una carpeta ya publicada y **no requiere el SDK en el servidor** |
| `-DeployUser` / `-DeployPassword` | ninguno; usa autenticación de Windows para ejecutar los scripts |
| `-Force` | recarga los datos aunque la base ya tenga bitácoras |

El resto de la guía explica lo que el script hace, para poder revisarlo o
ejecutarlo a mano.

---

## 0.1 Hospedaje bajo subruta

La aplicación se integra como **aplicación anidada** del sitio SICODIS, de
modo que queda en `https://sicodis.dnp.gov.co/bitacora/`. Hereda el
dominio y el certificado del sitio padre; no hace falta DNS nuevo.

> **Lo que esto obligó a cambiar.** El tablero pedía la API con ruta
> absoluta (`/api`), que bajo una subruta apuntaría a
> `https://sicodis.dnp.gov.co/api/…` — fuera de la aplicación. Y como el
> frontend cae a sus datos embebidos cuando una petición falla, se habría
> visto **funcionando pero con cifras congeladas y sin ningún error**.
> Ahora la resuelve contra `document.baseURI`, así que da `/api` en la
> raíz y `/bitacora/api` bajo subruta, sin configuración.

Del lado del backend no hubo que cambiar nada: el módulo de IIS informa la
ruta base y ASP.NET Core la aplica. Para reproducir el escenario sin IIS
—en desarrollo o en el contenedor— está la variable `Rutas__Base`:

```bash
Rutas__Base=/bitacora dotnet run --project backend/src/PgnBitacora.Api
# el tablero queda en http://localhost:5080/bitacora/
```

Una petición a `/bitacora` sin barra final se redirige con 301 a
`/bitacora/`. Sin esa barra, el navegador resolvería `vendor/` y `data/`
contra la raíz del dominio: página sin estilos y mapa en blanco.

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

La forma corta, que deja un único `.zip` con todo lo que el servidor necesita:

```bash
./tools/generar_paquete.sh          # deja dist/bitacora-despliegue-<version>.zip
```

Ese archivo se copia al servidor, se descomprime, y desde su carpeta se corre
el script del §0. No hace falta nada más: ni el SDK de .NET, ni Python, ni el
driver ODBC. El script detecta la carpeta `app\` incluida en el paquete, así
que no hay que pasarle `-PublishPath`.

```
bitacora-despliegue/
├── LEEME.txt                 requisitos y los dos comandos a correr
├── deploy/Deploy-Bitacora.ps1
├── db/mssql/00{1,2,3,4}*.sql esquema, vistas, DANE y datos
├── app/                      la aplicación publicada, con el tablero
└── docs/DESPLIEGUE_IIS.md    esta guía
```

El generador falla si el `publish` no incluyó el tablero, y convierte los
`.ps1`, `.sql`, `.md` y `.txt` a CRLF, porque el destino es Windows y el zip
no convierte finales de línea por sí solo.

### Publicar a mano


Es lo que hace `generar_paquete.sh` por dentro. Sirve para publicar desde
otro equipo y pasar la carpeta con `-PublishPath`.

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

## 3.1 El sitio padre y sus reglas de reescritura

**Esto ocurrió en el despliegue real del 28 de agosto de 2026.** Merece leerse
antes de instalar, porque el síntoma no se parece a la causa y porque el
despliegue *aparenta* haber salido bien.

### El síntoma

El tablero cargaba. En la consola del navegador:

```
Uncaught SyntaxError: Unexpected token '<'  (leaflet.js:1:1)
Uncaught SyntaxError: Unexpected token '<'  (chart.umd.min.js:1:1)
Uncaught ReferenceError: Chart is not defined
```

`Unexpected token '<'` en la columna 1 significa siempre lo mismo: el servidor
devolvió HTML donde se esperaba otra cosa. Y en efecto:

```
GET /bitacora/vendor/leaflet.js   -> 200  text/html   <!doctype html> ... <title>SICODIS</title>
GET /bitacora/api/resumen         -> 200  text/html   <!doctype html> ... <title>SICODIS</title>
```

Todo lo que colgaba de `/bitacora/` —excepto la página misma— lo estaba
respondiendo la aplicación Angular de SICODIS, con HTTP **200**.

### La causa

SICODIS es una SPA, y como toda SPA tiene una regla que manda al `index.html`
cualquier URL que no corresponda a un archivo físico:

```xml
<rule name="Angular">
  <match url=".*" />
  <conditions>
    <add input="{REQUEST_FILENAME}" matchType="IsFile"      negate="true" />
    <add input="{REQUEST_FILENAME}" matchType="IsDirectory" negate="true" />
  </conditions>
  <action type="Rewrite" url="/" />
</rule>
```

Dos hechos de IIS que se combinan mal:

1. Las reglas de `<rewrite>` **se heredan** por la jerarquía de configuración,
   de modo que la aplicación anidada las recibe.
2. El módulo de reescritura corre en `RQ_BEGIN_REQUEST`, **antes** de que IIS
   elija el manejador de la aplicación. La regla del padre gana.

Y el `inheritInChildApplications="false"` que trae el `web.config` generado no
lo evita: impide que *nuestra* configuración baje a hijos nuestros, no que la
del padre suba hasta nosotros.

De ahí el patrón exacto que se observó:

| URL | `{REQUEST_FILENAME}` | Regla | Resultado |
|---|---|---|---|
| `/bitacora/` | `C:\inetpub\bitacora`, existe como directorio | no dispara | el tablero, bien |
| `/bitacora/vendor/leaflet.js` | `…\bitacora\vendor\leaflet.js`, **no existe** — el archivo real está bajo `frontend\` | dispara | HTML de SICODIS |
| `/bitacora/api/resumen` | jamás será un archivo | dispara | HTML de SICODIS |

Solo funcionaba la página, que es justo la que hace creer que todo está bien.

### Por qué era peor de lo que parecía

`/api/*` devolvía **HTTP 200**. El tablero solo comprueba `r.ok`, así que la
respuesta pasaba el filtro, `r.json()` fallaba al encontrar `<`, y el `catch`
de `af()` caía a los datos embebidos **sin avisar**.

El tablero se veía completo, con todas sus secciones y todas sus cifras. Y
todas las cifras eran las congeladas en el HTML, no las de la base.

### La corrección

`backend/src/PgnBitacora.Api/web.config` descarta las reglas heredadas, y
`dotnet publish` lo fusiona con el `<handlers>` que genera el SDK:

```xml
<location path="." inheritInChildApplications="false">
  <system.webServer>
    <rewrite>
      <rules>
        <clear />
      </rules>
    </rewrite>
  </system.webServer>
</location>
```

**Para arreglar un servidor ya desplegado** no hace falta volver a instalar:
basta editar `C:\inetpub\bitacora\web.config` y añadir ese bloque `<rewrite>`
dentro de `<system.webServer>`. Guardar el archivo recicla el grupo de
aplicaciones por sí solo.

### Si aparece un error 500.19

Significa que la sección `rewrite` está bloqueada en `applicationHost.config`.
Se desbloquea con:

```powershell
%windir%\system32\inetsrv\appcmd.exe unlock config -section:system.webServer/rewrite
```

La alternativa, si el administrador del sitio padre prefiere no desbloquearla,
es excluir la subruta en la regla de SICODIS:

```xml
<add input="{REQUEST_URI}" pattern="^/bitacora" negate="true" />
```

### La lección para la verificación

La fase 7 del script comprobaba el código HTTP. Todas estas rutas devolvían
**200**, así que habría declarado exitoso un despliegue en el que no
funcionaba ni la API ni una sola biblioteca del tablero.

Ahora cada comprobación declara qué debe contener la respuesta —tipo MIME y
una cadena— y reconoce el caso concreto:

```
   AVISO api/resumen   tipo 'text/html', se esperaba 'application/json'
   AVISO    Devuelve HTML: el sitio padre está atendiendo esta ruta.
```


---

## 4. La cadena de conexión

La aplicación la lee de la clave `ConnectionStrings:DnpDpip`. Hay dos formas.

**Opción A — `appsettings.Production.json`** junto al `.dll`:

```json
{
  "ConnectionStrings": {
    "DnpDpip": "Server=SERVIDOR_SQL;Database=MI_BASE;User Id=USUARIO;Password=...;TrustServerCertificate=True"
  }
}
```

**Opción B — variable de entorno en `web.config`:**

```xml
<aspNetCore processPath="dotnet" arguments=".\PgnBitacora.Api.dll"
            stdoutLogEnabled="false" hostingModel="inprocess">
  <environmentVariables>
    <environmentVariable name="ConnectionStrings__DnpDpip"
                         value="Server=SERVIDOR_SQL;Database=MI_BASE;..." />
    <environmentVariable name="ASPNETCORE_ENVIRONMENT" value="Production" />
  </environmentVariables>
</aspNetCore>
```

**Lo más limpio, si el SQL Server está en el mismo dominio:** autenticación integrada de Windows. Se le da permiso a la identidad del grupo de aplicaciones sobre la base y la cadena queda **sin contraseña**:

```
Server=SERVIDOR_SQL;Database=MI_BASE;Integrated Security=true;TrustServerCertificate=True
```

Es la opción recomendada en un entorno institucional: no hay credencial que rotar ni que se filtre en un archivo de configuración.

### Los datos viajan en un .sql

`db/mssql/004_datos_iniciales.sql` lleva las 5.320 filas como sentencias
INSERT, de modo que el servidor solo necesite `sqlcmd`. **No hace falta
Python ni el driver ODBC en el servidor de IIS**, ni copiar allí los
Excel fuente.

Se regenera desde el equipo de desarrollo cuando cambien los datos:

```bash
python tools/generar_seed_sql.py
```

Conserva los `id` originales con `IDENTITY_INSERT` —son referencias
reales, no números decorativos— y va en una sola transacción: si algo
falla, no queda a medias.

### Convivencia en una base compartida

Todas las tablas llevan el prefijo `btcr_` (`btcr_metadatos_bitacora`, `btcr_pgn_concepto`, …), igual que sus restricciones e índices. Eso permite instalar el esquema **dentro de una base existente de la entidad** sin colisionar con otros sistemas: basta con ejecutar `db/mssql/*.sql` sobre ella.

Si se hace así, los permisos del usuario de la aplicación pueden acotarse a esas tablas en lugar de a la base entera.

### Si se crea una base nueva, la collation no es negociable

```sql
CREATE DATABASE MI_BASE COLLATE Modern_Spanish_CS_AS;
```

Si en cambio el esquema se instala en una base **existente**, hay que verificar su collation antes:

```sql
SELECT DATABASEPROPERTYEX('MI_BASE', 'Collation');
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
