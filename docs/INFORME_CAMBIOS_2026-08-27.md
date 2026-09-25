# Informe de cambios — 27 de agosto de 2026

**Proyecto:** Bitácora de Inversión Pública — DNP / DPIP
**Contexto:** preparación del despliegue en el IIS del DNP, bajo `https://sicodis.dnp.gov.co/bitacora`
**Commits:** `002b192` · `5e1f2ef`

---

## Resumen

Dos cambios, con un mismo objetivo: que el paso a producción sea **un archivo y un comando**, en un servidor que no tiene —ni debe tener— SDK de .NET, Python ni driver ODBC.

| # | Cambio | Origen |
|---|---|---|
| 1 | `deploy/Deploy-Bitacora.ps1` unifica el despliegue completo | Requisito: integrarse a SICODIS y que sea sencillo |
| 2 | `tools/generar_paquete.sh` produce un `.zip` autocontenido | Requisito: entregar todo lo necesario para desplegar |

Por el camino aparecieron **cuatro defectos**, y conviene subrayar de dónde salió cada uno:

- Uno lo destapó el **destino** (una subruta en lugar de la raíz del dominio) y habría dejado el tablero mostrando cifras congeladas sin ningún error.
- Los otros tres los destapó **correr el script con `-WhatIf`**, y los cuatro vivían en el camino que solo recorre un servidor limpio: la primera corrida.

Es el mismo patrón de toda la migración: **ninguno fallaba de forma visible.**

---

## 1. Un solo script para todo el despliegue

### Qué había antes

`docs/DESPLIEGUE_IIS.md` describía el procedimiento a mano: crear la base, aplicar tres scripts SQL, cargar los datos con los ETL de Python, publicar la aplicación, copiarla, crear el grupo de aplicaciones, crear la aplicación anidada, escribir la cadena de conexión, dar permisos, reiniciar y comprobar. Correcto, pero once pasos manuales en un servidor ajeno, cada uno con su forma propia de salir mal.

### Qué hay ahora

```powershell
$pw = Read-Host 'Contraseña de btcr_app' -AsSecureString
.\deploy\Deploy-Bitacora.ps1 -SqlServer SQLSRV01 -Database SICODIS `
    -AppUser btcr_app -AppPassword $pw
```

Siete fases, en orden: requisitos → base de datos → publicación → copia → cadena de conexión → IIS → verificación.

| Propiedad | Cómo |
|---|---|
| **Idempotente** | Los cuatro `.sql` ya lo eran; el grupo de aplicaciones y la aplicación anidada se crean o se actualizan según existan |
| **`-WhatIf`** | Describe cada acción sin ejecutar ninguna, y verifica los requisitos igual |
| **Fases omitibles** | `-OmitirBaseDatos`, `-OmitirDatos`, `-OmitirIIS` — actualizar solo la aplicación es lo habitual |
| **PowerShell 5.1** | Sin construcciones exclusivas de la 7, y guardado **con BOM**: sin él, la 5.1 lee las tildes como basura |
| **Sin lock de archivos** | `app_offline.htm` antes de copiar, retirado después |

### Los datos viajan en SQL, no en Excel

`tools/generar_seed_sql.py` vuelca la base a `db/mssql/004_datos_iniciales.sql`: **5.320 filas** en 22 tablas, 517 KB.

Tres detalles que el volcado respeta, y que no son cosméticos:

- **`IDENTITY_INSERT` por tabla.** Los `id` no son decorativos: `btcr_pgn_ejecucion.concepto_id` y todos los `bitacora_id` los referencian. Regenerarlos rompería el modelo en silencio.
- **`N'...'` en todo texto.** Los datos llevan tildes y la collation es `CS_AS`.
- **Una sola transacción, con `SET XACT_ABORT ON`.** Si algo falla, no queda a medias.

Así el servidor del DNP solo necesita `sqlcmd`. **Los Excel fuente no salen de la máquina de desarrollo** — que es, además, la lección del informe anterior.

---

## 2. El primer cambio del frontend en todo el proyecto

Aquí está el defecto que destapó el destino, y es el más importante de este informe.

### Qué pasaba

El tablero pedía la API con ruta absoluta:

```javascript
const API = '/api';
```

Hospedado en la raíz, correcto. Como aplicación anidada en `https://sicodis.dnp.gov.co/bitacora/`, el navegador habría pedido:

```
https://sicodis.dnp.gov.co/api/resumen      ← fuera de la aplicación
```

### Por qué no se habría notado

Porque `af()` —la función que envuelve cada `fetch`— cae a los datos embebidos cuando una petición falla, **sin avisar**:

```javascript
async function af(p, fb){
  try{ const r = await fetch(API+p); if(!r.ok) throw 0; return await r.json(); }
  catch{ return fb; }   // ← ni un error en consola
}
```

El tablero se habría visto **funcionando**: todas las secciones dibujadas, todas las cifras presentes. Y todas congeladas en los valores embebidos en el HTML. Nadie habría tenido motivo para dudar de lo que estaba viendo.

### Corrección

```javascript
const API = new URL('api', document.baseURI).pathname;
```

Resuelve contra el documento y no contra el dominio: da `/api` en la raíz y `/bitacora/api` bajo subruta, **sin configuración**.

### Y la redirección que hace falta

El backend no necesitó cambios para la subruta —el módulo de IIS informa la ruta base al proceso— pero se añadieron dos cosas a `Program.cs`:

- **`Rutas:Base`**, para reproducir el escenario de subruta sin IIS y poder probarlo antes de desplegar.
- **Una redirección 301 de `/bitacora` a `/bitacora/`.** Sin la barra final, el navegador resuelve `vendor/` y `data/` contra la raíz del dominio: página sin estilos y mapa en blanco.

---

## 3. Lo que `-WhatIf` encontró

La simulación se corrió sobre el contenido del zip, con un banco que emula `sqlcmd`, `appcmd.exe`, `icacls`, el módulo `WebAdministration` y la unidad `IIS:`. Recorre las siete fases y termina en 0.

Encontró tres fallos. Los tres estaban en el camino que solo recorre un servidor limpio, es decir **la primera corrida real**:

| # | Fallo | Consecuencia |
|---|---|---|
| 1 | Configurar el grupo de aplicaciones daba error en vez de simularse | El `-WhatIf` **abortaba** y nunca llegaba al final |
| 2 | `icacls` se ejecutaba de verdad bajo `-WhatIf` | Una simulación modificaba permisos del disco |
| 3 | Anunciaba `Carpeta creada` sin crear nada | Salida engañosa |

El primero merece detalle. En una corrida en seco `New-WebAppPool` no crea el grupo —hace lo correcto—, y la línea siguiente lo configuraba:

```powershell
Set-ItemProperty "IIS:\AppPools\$AppPoolName" -Name managedRuntimeVersion -Value ''
# → Cannot find path 'IIS:\AppPools\bitacora' because it does not exist.
```

Contra una ruta inexistente de la unidad `IIS:` eso es un error, no un aviso: el script se detenía ahí. Y ese es exactamente el escenario de la primera corrida, en un IIS donde el grupo todavía no existe. Corregido con una guarda `Test-Path` que, cuando el grupo no está, narra lo que haría.

> Los tres son fallos **del modo simulación**, no del despliegue real. Pero un `-WhatIf` que aborta antes de terminar deja de servir para lo único que se le pide: mirar antes de tocar.

---

## 4. El paquete

`tools/generar_paquete.sh` produce `dist/bitacora-despliegue-<version>.zip` — 6,4 MB comprimidos, 18,7 MB al abrir, 118 entradas:

```
bitacora-despliegue/
├── LEEME.txt                 requisitos y los dos comandos a correr
├── deploy/Deploy-Bitacora.ps1
├── db/mssql/00{1,2,3,4}*.sql esquema, vistas, DANE y datos
├── app/                      la aplicación publicada, con el tablero
└── docs/DESPLIEGUE_IIS.md
```

El script detecta la carpeta `app/` incluida, así que no hay que pasarle `-PublishPath`.

Dos cosas que el generador hace y que a mano se olvidan:

- **Falla si el `publish` no incluyó el tablero.** Ya pasó una vez: `dotnet publish` produce la API sin `frontend/`, y el sitio responde 404 en la raíz. Lo resuelve un target de MSBuild en el `.csproj`; la comprobación existe para que un cambio en ese target no pase inadvertido.
- **Convierte a CRLF** los `.ps1`, `.sql`, `.md` y `.txt`. El destino es Windows y **el zip no convierte finales de línea**. El BOM del `.ps1` se conserva.

### Requisitos en el servidor

- Windows Server con IIS
- **ASP.NET Core 8 Hosting Bundle** — instala `AspNetCoreModuleV2`; después, `iisreset`
- `sqlcmd` y acceso a la instancia
- PowerShell 5.1 o superior, como administrador

Nada más. Ni SDK de .NET, ni Python, ni ODBC.

---

## 5. Verificación

### El binario extraído del zip, contra la base real

Levantado con `Rutas__Base=/bitacora`:

| Prueba | Resultado |
|---|---|
| Tablero | 200 · 221.733 B |
| `/api/resumen` | 200 · bitácora 2026-I, 88.401,231 mmm |
| `data/dptos.geojson` | 200 · `application/geo+json` · 1,2 MB |
| `data/regiones.geojson` | 200 · `application/geo+json` |
| `/bitacora` sin barra final | **301** → `/bitacora/` |
| Acentuación | `PACÍFICO` |
| `data/BASES_BITACORA/` | **404** |

Las dos últimas filas no son adorno: la primera es la razón de la collation `CS_AS`, y la segunda es el hallazgo del informe del 20 de agosto.

### Lo demás

| Comprobación | Resultado |
|---|---|
| Los cuatro `.sql` sobre una base limpia | 21/21 tablas idénticas a producción, `id` conservados, cero huérfanos de FK |
| Suite de 322 rutas bajo la subruta | Pasa |
| Suite de 322 rutas sobre el paquete publicado | Pasa, configurado solo con `appsettings.Production.json` |
| Sintaxis del script | Pasa el analizador de PowerShell, sin construcciones de la versión 7 |
| Encoding del `.ps1` en el zip | UTF-8 con BOM, CRLF, 63 caracteres acentuados intactos |
| Simulación `-WhatIf` sobre el zip extraído | Recorre las siete fases, termina en 0, **no escribe nada** |

### El límite de esta verificación, dicho con claridad

**Una corrida con `sqlcmd`, `appcmd` e IIS simulados no prueba que funcione en Windows.** Prueba el flujo del script: el orden de las fases, las guardas, los mensajes, que `-WhatIf` no toque nada. No prueba el entorno.

Lo que no se ha probado en ningún momento:

- Un IIS real, con su Hosting Bundle y su `AspNetCoreModuleV2`
- El `sqlcmd` real contra la instancia del DNP
- Los permisos efectivos de `IIS AppPool\bitacora` sobre `C:\inetpub\bitacora`
- El sitio `SICODIS` y sus enlaces existentes

Por eso el `LEEME.txt` indica que **la primera corrida sea con `-WhatIf`**: en un servidor limpio, esa corrida verifica los requisitos —Hosting Bundle incluido— y describe cada paso, sin modificar nada.

---

## Archivos

| Archivo | Estado |
|---|---|
| `deploy/Deploy-Bitacora.ps1` | Nuevo · 412 líneas, luego corregido |
| `deploy/LEEME.txt` | Nuevo |
| `tools/generar_paquete.sh` | Nuevo |
| `tools/generar_seed_sql.py` | Nuevo · 195 líneas |
| `db/mssql/004_datos_iniciales.sql` | Nuevo · generado, no se edita a mano |
| `frontend/index.html` | `const API` resuelve contra `document.baseURI` |
| `backend/src/PgnBitacora.Api/Program.cs` | `Rutas:Base` y redirección 301 |
| `docs/DESPLIEGUE_IIS.md` | §0 despliegue automatizado, §0.1 subruta, §2 el paquete |
| `README.md`, `CLAUDE.md` | Referencia al paquete y a las reglas del despliegue |

---

## Pendiente

| # | Asunto | De quién |
|---|---|---|
| 1 | Correr `-WhatIf` en el servidor del DNP y revisar su salida | DNP |
| 2 | Confirmar el nombre de la instancia, la base y las credenciales de la aplicación | DNP |
| 3 | La API sigue siendo pública y de solo lectura, por decisión explícita; asegurarla queda para después | Pendiente de antes |
| 4 | Definir el servidor de producción (pregunta abierta 9 del plan de migración) | DNP |

---

## Documentos relacionados

- [`DESPLIEGUE_IIS.md`](DESPLIEGUE_IIS.md) — la guía operativa, con diagnóstico del 502.5 y reversión
- [`INFORME_CAMBIOS_2026-08-20.md`](INFORME_CAMBIOS_2026-08-20.md) — prefijo `btcr_`, credenciales y los dos hallazgos de seguridad
- [`INFORME_MIGRACION_DOTNET_SQLSERVER.md`](INFORME_MIGRACION_DOTNET_SQLSERVER.md) — la migración completa
- [`PLAN_MIGRACION_DOTNET_SQLSERVER.md`](PLAN_MIGRACION_DOTNET_SQLSERVER.md) — catálogo de incompatibilidades entre motores
