#Requires -Version 5.1
#Requires -RunAsAdministrator

<#
.SYNOPSIS
    Despliega la Bitácora de Inversión Pública en IIS como aplicación
    anidada, y prepara su base de datos.

.DESCRIPTION
    Unifica los tres pasos del despliegue:

      1. Base de datos  — crea las tablas y carga los datos sobre una base
                          existente. Todas las tablas llevan el prefijo
                          btcr_, así que puede ser una base compartida.
      2. Publicación    — compila y empaqueta la aplicación.
      3. IIS            — crea el grupo de aplicaciones y la aplicación
                          anidada, y escribe la cadena de conexión.

    Cada paso puede omitirse. El script es idempotente: volver a correrlo
    actualiza lo que exista sin duplicar nada.

    En el servidor solo hacen falta IIS, el ASP.NET Core 8 Hosting Bundle
    y sqlcmd. NO hace falta Python ni el driver ODBC: los datos viajan en
    db\mssql\004_datos_iniciales.sql.

.PARAMETER SqlServer
    Instancia de SQL Server. Ej.: 'SQLSRV01' o 'SQLSRV01\INSTANCIA,1433'.

.PARAMETER Database
    Base de datos existente donde se instalan las tablas btcr_*.
    El script NO la crea: debe existir y tener collation
    Modern_Spanish_CS_AS (se verifica y se advierte si no).

.PARAMETER AppUser
    Login de SQL con el que la aplicación se conectará en tiempo de
    ejecución. Necesita db_datareader sobre la base.

.PARAMETER AppPassword
    Contraseña de AppUser, como SecureString.

.PARAMETER DeployUser
    Login de SQL para ejecutar los scripts. Necesita db_ddladmin y
    db_datawriter. Si se omite, sqlcmd usa autenticación de Windows con
    la identidad de quien ejecuta el script.

.PARAMETER DeployPassword
    Contraseña de DeployUser, como SecureString.

.PARAMETER SiteName
    Sitio de IIS que hospedará la aplicación anidada.

.PARAMETER AppName
    Nombre de la aplicación dentro del sitio. Con 'bitacora', la URL
    resultante es https://<sitio>/bitacora/.

.PARAMETER PhysicalPath
    Carpeta del servidor donde quedan los archivos publicados.

.PARAMETER PublishPath
    Carpeta ya publicada (salida de `dotnet publish`). Si se omite, el
    script la genera, para lo cual necesita el SDK de .NET.

.PARAMETER Force
    Carga los datos aunque las tablas ya tengan filas. Sin esta opción,
    el script se detiene antes de sobrescribir información existente.

.EXAMPLE
    $app = Read-Host 'Contraseña de la aplicación' -AsSecureString
    .\Deploy-Bitacora.ps1 -SqlServer SQLSRV01 -Database SICODIS `
                          -AppUser btcr_app -AppPassword $app

.EXAMPLE
    # Solo actualizar la aplicación, sin tocar la base
    .\Deploy-Bitacora.ps1 -SqlServer SQLSRV01 -Database SICODIS `
                          -AppUser btcr_app -AppPassword $app -OmitirBaseDatos

.NOTES
    Guía completa y diagnóstico: docs\DESPLIEGUE_IIS.md
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)][string]   $SqlServer,
    [Parameter(Mandatory = $true)][string]   $Database,
    [Parameter(Mandatory = $true)][string]   $AppUser,
    [Parameter(Mandatory = $true)][securestring] $AppPassword,

    [string]       $DeployUser,
    [securestring] $DeployPassword,

    [string] $SiteName     = 'SICODIS',
    [string] $AppName      = 'bitacora',
    [string] $PhysicalPath = 'C:\inetpub\bitacora',
    [string] $AppPoolName  = 'bitacora',
    [string] $PublishPath,

    [string] $UrlVerificacion = '',

    [switch] $OmitirBaseDatos,
    [switch] $OmitirDatos,
    [switch] $OmitirIIS,
    [switch] $SinSwagger,
    [switch] $Force
)

$ErrorActionPreference = 'Stop'
$RaizRepo = Split-Path -Parent $PSScriptRoot
$DirSql   = Join-Path $RaizRepo 'db\mssql'
$Proyecto = Join-Path $RaizRepo 'backend\src\PgnBitacora.Api'

# ── Salida ──────────────────────────────────────────────────
function Write-Paso  { param($t) Write-Host "`n== $t" -ForegroundColor Cyan }
function Write-Ok    { param($t) Write-Host "   OK    $t" -ForegroundColor Green }
function Write-Info  { param($t) Write-Host "         $t" -ForegroundColor Gray }
function Write-Aviso { param($t) Write-Host "   AVISO $t" -ForegroundColor Yellow }
function Stop-Con    { param($t) Write-Host "   ERROR $t" -ForegroundColor Red; exit 1 }

function ConvertFrom-Secure {
    param([securestring] $s)
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
    try   { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

# ── sqlcmd ──────────────────────────────────────────────────
function Invoke-Sql {
    <#  Ejecuta un archivo .sql o una consulta.
        -b hace que sqlcmd devuelva código distinto de cero ante un error;
        sin eso, un fallo de SQL pasaría inadvertido y el despliegue
        continuaría sobre una base a medio construir. #>
    param(
        [string] $Archivo,
        [string] $Consulta,
        [switch] $Silencioso
    )
    $a = @('-S', $SqlServer, '-d', $Database, '-b', '-C')
    if ($DeployUser) {
        $a += @('-U', $DeployUser, '-P', (ConvertFrom-Secure $DeployPassword))
    } else {
        $a += '-E'
    }
    if ($Archivo)  { $a += @('-i', $Archivo) }
    if ($Consulta) { $a += @('-Q', $Consulta, '-h', '-1', '-W') }

    $salida = & sqlcmd @a 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host ($salida | Out-String) -ForegroundColor Red
        Stop-Con "sqlcmd falló ($(if ($Archivo) { Split-Path -Leaf $Archivo } else { 'consulta' }))"
    }
    if (-not $Silencioso -and $salida) { $salida }
}

# ══════════════════════════════════════════════════════════════
# 1. Requisitos
# ══════════════════════════════════════════════════════════════
Write-Paso 'Verificando requisitos'

if (-not (Get-Command sqlcmd -ErrorAction SilentlyContinue)) {
    Stop-Con 'No se encontró sqlcmd. Viene con SQL Server o con las Command Line Utilities.'
}
Write-Ok 'sqlcmd disponible'

if (-not $OmitirIIS) {
    try { Import-Module WebAdministration -ErrorAction Stop }
    catch { Stop-Con 'No se pudo cargar WebAdministration. ¿Está instalado el rol de IIS?' }
    Write-Ok 'Módulo WebAdministration cargado'

    # El Hosting Bundle registra AspNetCoreModuleV2. Sin él, IIS responde
    # 500.19 y la causa no es evidente en el log del sitio.
    $modulos = & "$env:windir\system32\inetsrv\appcmd.exe" list modules 2>$null
    if ($modulos -notmatch 'AspNetCoreModuleV2') {
        Stop-Con @'
Falta el ASP.NET Core 8 Hosting Bundle (módulo AspNetCoreModuleV2).
Instalarlo DESPUÉS de IIS y reiniciar:  net stop was /y ; net start w3svc
'@
    }
    Write-Ok 'AspNetCoreModuleV2 registrado'

    if (-not (Test-Path "IIS:\Sites\$SiteName")) {
        $sitios = (Get-ChildItem IIS:\Sites | Select-Object -ExpandProperty Name) -join ', '
        Stop-Con "No existe el sitio '$SiteName'. Sitios disponibles: $sitios"
    }
    Write-Ok "Sitio '$SiteName' encontrado"
}

foreach ($f in @('001_schema.sql', '002_views.sql', '003_seed_dane.sql')) {
    if (-not (Test-Path (Join-Path $DirSql $f))) { Stop-Con "Falta $DirSql\$f" }
}
Write-Ok 'Scripts de esquema presentes'

# ══════════════════════════════════════════════════════════════
# 2. Base de datos
# ══════════════════════════════════════════════════════════════
if ($OmitirBaseDatos) {
    Write-Paso 'Base de datos omitida (-OmitirBaseDatos)'
} else {
    Write-Paso "Preparando la base '$Database' en $SqlServer"

    $collation = (Invoke-Sql -Consulta "SET NOCOUNT ON; SELECT CONVERT(nvarchar(128), DATABASEPROPERTYEX('$Database','Collation'))" -Silencioso:$false | Out-String).Trim()
    Write-Info "Collation: $collation"
    if ($collation -notmatch 'Modern_Spanish_CS_AS') {
        # No se aborta: puede haber una collation equivalente sensible a
        # mayúsculas y tildes. Pero conviene mirarlo antes de continuar.
        Write-Aviso @"
La collation esperada es Modern_Spanish_CS_AS.
Con una insensible a tildes, PACÍFICO y PACIFICO se vuelven el mismo
valor y las agrupaciones por región fusionan filas SIN dar error.
"@
        if (-not $Force -and -not $PSCmdlet.ShouldContinue('¿Continuar de todos modos?', 'Collation distinta')) { exit 1 }
    } else {
        Write-Ok 'Collation correcta'
    }

    foreach ($f in @('001_schema.sql', '002_views.sql', '003_seed_dane.sql')) {
        if ($PSCmdlet.ShouldProcess($Database, "Ejecutar $f")) {
            Invoke-Sql -Archivo (Join-Path $DirSql $f) -Silencioso | Out-Null
            Write-Ok $f
        }
    }

    $nTablas = (Invoke-Sql -Consulta "SET NOCOUNT ON; SELECT COUNT(*) FROM sys.tables WHERE name LIKE 'btcr[_]%'" | Out-String).Trim()
    Write-Info "Tablas btcr_ en la base: $nTablas"

    # ── Datos ──
    $archivoDatos = Join-Path $DirSql '004_datos_iniciales.sql'
    if ($OmitirDatos) {
        Write-Info 'Carga de datos omitida (-OmitirDatos)'
    } elseif (-not (Test-Path $archivoDatos)) {
        Write-Aviso "No se encontró 004_datos_iniciales.sql; la base queda con las tablas vacías.
         Se genera desde el equipo de desarrollo con: python tools/generar_seed_sql.py"
    } else {
        $filas = [int]((Invoke-Sql -Consulta 'SET NOCOUNT ON; SELECT COUNT(*) FROM dbo.btcr_metadatos_bitacora' | Out-String).Trim())
        if ($filas -gt 0 -and -not $Force) {
            Write-Aviso "La base ya tiene $filas bitácora(s) cargada(s). El script de datos las REEMPLAZA."
            Write-Info  'Para continuar de todos modos, volver a ejecutar con -Force.'
        } elseif ($PSCmdlet.ShouldProcess($Database, 'Cargar datos iniciales')) {
            Write-Info 'Cargando datos (una sola transacción)...'
            Invoke-Sql -Archivo $archivoDatos
            Write-Ok 'Datos cargados'
        }
    }
}

# ══════════════════════════════════════════════════════════════
# 3. Publicación
# ══════════════════════════════════════════════════════════════
# El paquete de despliegue trae la aplicación ya publicada en .\app, de
# modo que el servidor no necesite el SDK de .NET. Si está, se usa.
if (-not $PublishPath -and (Test-Path (Join-Path $RaizRepo 'app\PgnBitacora.Api.dll'))) {
    $PublishPath = Join-Path $RaizRepo 'app'
    $DelPaquete  = $true
}

if (-not $PublishPath) {
    Write-Paso 'Publicando la aplicación'
    if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
        Stop-Con @'
No se encontró el SDK de .NET para publicar.
Opciones: instalarlo, o publicar en otro equipo y pasar la carpeta con -PublishPath.
'@
    }
    $PublishPath = Join-Path $env:TEMP "bitacora-publish-$(Get-Date -Format yyyyMMddHHmmss)"
    if ($PSCmdlet.ShouldProcess($Proyecto, 'dotnet publish')) {
        & dotnet publish $Proyecto -c Release -o $PublishPath --nologo
        if ($LASTEXITCODE -ne 0) { Stop-Con 'Falló dotnet publish' }
    }
    Write-Ok "Publicado en $PublishPath"
} else {
    $origen = if ($DelPaquete) { 'incluida en el paquete' } else { "indicada: $PublishPath" }
    Write-Paso "Usando la aplicación $origen"
    if (-not (Test-Path $PublishPath)) { Stop-Con "No existe $PublishPath" }
}

# El tablero viaja con la aplicación por un target de MSBuild. Sin él, la
# API respondería pero la raíz daría 404, con solo una advertencia en el log.
if (-not (Test-Path (Join-Path $PublishPath 'frontend\index.html'))) {
    Stop-Con 'La carpeta publicada no contiene frontend\index.html. Revisar el target CopiarFrontend del .csproj.'
}
Write-Ok 'El paquete incluye el tablero'

# ══════════════════════════════════════════════════════════════
# 4. Copia de archivos
# ══════════════════════════════════════════════════════════════
Write-Paso "Desplegando en $PhysicalPath"

if (-not (Test-Path $PhysicalPath)) {
    New-Item -ItemType Directory -Path $PhysicalPath -Force | Out-Null
    if (-not $WhatIfPreference) { Write-Ok 'Carpeta creada' }
}

# app_offline.htm detiene la aplicación y libera los .dll, que de otro
# modo quedan bloqueados y hacen fallar la copia.
$offline = Join-Path $PhysicalPath 'app_offline.htm'
if ($PSCmdlet.ShouldProcess($PhysicalPath, 'Copiar archivos')) {
    Set-Content -Path $offline -Encoding UTF8 -Value @'
<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Actualizando</title></head><body style="font-family:sans-serif;padding:3rem">
<h1>Actualizando la Bitácora</h1><p>El tablero volverá en unos segundos.</p>
</body></html>
'@
    Start-Sleep -Seconds 2

    try {
        Copy-Item -Path (Join-Path $PublishPath '*') -Destination $PhysicalPath -Recurse -Force
        Write-Ok 'Archivos copiados'
    } finally {
        Remove-Item $offline -ErrorAction SilentlyContinue
    }
}

# ══════════════════════════════════════════════════════════════
# 5. Cadena de conexión
# ══════════════════════════════════════════════════════════════
Write-Paso 'Escribiendo la configuración'

# Va en appsettings.Production.json y no en web.config porque `publish`
# regenera web.config en cada actualización y borraría lo que se le
# añada. Cuando ASPNETCORE_ENVIRONMENT no está definida, .NET asume
# Production, así que este archivo se carga solo.
$cadena = "Server=$SqlServer;Database=$Database;User Id=$AppUser;Password=$(ConvertFrom-Secure $AppPassword);TrustServerCertificate=True"
$config = [ordered]@{
    ConnectionStrings = [ordered]@{ DnpDpip = $cadena }
    Swagger           = [ordered]@{ Habilitado = (-not $SinSwagger.IsPresent) }
}
$rutaConfig = Join-Path $PhysicalPath 'appsettings.Production.json'
if ($PSCmdlet.ShouldProcess($rutaConfig, 'Escribir configuración')) {
    $config | ConvertTo-Json -Depth 5 | Set-Content -Path $rutaConfig -Encoding UTF8
    Write-Ok 'appsettings.Production.json'
    Write-Info "Servidor: $SqlServer   Base: $Database   Usuario: $AppUser"
}

# ══════════════════════════════════════════════════════════════
# 6. IIS
# ══════════════════════════════════════════════════════════════
if ($OmitirIIS) {
    Write-Paso 'Configuración de IIS omitida (-OmitirIIS)'
} else {
    Write-Paso 'Configurando IIS'

    if (-not (Test-Path "IIS:\AppPools\$AppPoolName")) {
        if ($PSCmdlet.ShouldProcess($AppPoolName, 'Crear grupo de aplicaciones')) {
            New-WebAppPool -Name $AppPoolName | Out-Null
            Write-Ok "Grupo de aplicaciones '$AppPoolName' creado"
        }
    } else {
        Write-Info "El grupo de aplicaciones '$AppPoolName' ya existía"
    }

    # 'Sin código administrado': IIS no ejecuta .NET Framework aquí, solo
    # hospeda el proceso de .NET Core. Con un valor distinto, la respuesta
    # es 502.5 y el motivo no aparece en ningún log evidente.
    #
    # El Test-Path no es redundante con el bloque anterior: en una simulación
    # el grupo no se creó, y configurar una ruta inexistente de la unidad IIS:
    # es un error, no un aviso. Sin esta guarda, -WhatIf aborta aquí.
    if (Test-Path "IIS:\AppPools\$AppPoolName") {
        Set-ItemProperty "IIS:\AppPools\$AppPoolName" -Name managedRuntimeVersion -Value ''
        Set-ItemProperty "IIS:\AppPools\$AppPoolName" -Name managedPipelineMode   -Value 'Integrated'
        Set-ItemProperty "IIS:\AppPools\$AppPoolName" -Name startMode             -Value 'AlwaysRunning'
        Write-Ok 'Grupo de aplicaciones: Sin código administrado, canalización integrada'
    } else {
        Write-Info 'Se configuraría: Sin código administrado, canalización integrada, AlwaysRunning'
    }

    $rutaApp = "IIS:\Sites\$SiteName\$AppName"
    if (-not (Test-Path $rutaApp)) {
        if ($PSCmdlet.ShouldProcess("$SiteName/$AppName", 'Crear aplicación anidada')) {
            New-WebApplication -Site $SiteName -Name $AppName `
                               -PhysicalPath $PhysicalPath -ApplicationPool $AppPoolName | Out-Null
            Write-Ok "Aplicación '/$AppName' creada dentro de '$SiteName'"
        }
    } else {
        Set-ItemProperty $rutaApp -Name physicalPath    -Value $PhysicalPath
        Set-ItemProperty $rutaApp -Name applicationPool -Value $AppPoolName
        Write-Info "La aplicación '/$AppName' ya existía; se actualizó su configuración"
    }

    $identidad = "IIS AppPool\$AppPoolName"
    if ($PSCmdlet.ShouldProcess($PhysicalPath, "Conceder lectura a '$identidad'")) {
        & icacls $PhysicalPath /grant "${identidad}:(OI)(CI)RX" /T /Q | Out-Null
        Write-Ok "Permisos de lectura para '$identidad'"
    }

    if (Test-Path "IIS:\AppPools\$AppPoolName") {
        Restart-WebAppPool -Name $AppPoolName
        Write-Ok 'Grupo de aplicaciones reiniciado'
    } else {
        Write-Info "Se reiniciaría el grupo de aplicaciones '$AppPoolName'"
    }
}

# ══════════════════════════════════════════════════════════════
# 7. Verificación
# ══════════════════════════════════════════════════════════════
Write-Paso 'Verificando'

# En una simulación no se consulta el sitio: -WhatIf debe describir lo que
# haría, no producir tráfico hacia el servidor de la entidad.
if ($WhatIfPreference) {
    Write-Info 'Omitida: -WhatIf no ejecuta la verificación por HTTP.'
    Write-Host "`n== Simulación terminada (no se modificó nada)" -ForegroundColor Cyan
    return
}

if (-not $UrlVerificacion) {
    $binding = (Get-WebBinding -Name $SiteName | Select-Object -First 1).bindingInformation
    $host_    = ($binding -split ':')[2]
    $esquema = if ((Get-WebBinding -Name $SiteName | Select-Object -First 1).protocol -eq 'https') { 'https' } else { 'http' }
    if ($host_) { $UrlVerificacion = "${esquema}://$host_/$AppName/" }
}

if ($UrlVerificacion) {
    Write-Info "URL: $UrlVerificacion"
    Start-Sleep -Seconds 3
    foreach ($ruta in @('health', 'api/resumen', '')) {
        $url = ($UrlVerificacion.TrimEnd('/') + '/' + $ruta).TrimEnd('/')
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 30
            Write-Ok ("{0,-46} HTTP {1}" -f $url, $r.StatusCode)
        } catch {
            $codigo = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 'sin respuesta' }
            Write-Aviso ("{0,-46} {1}" -f $url, $codigo)
        }
    }
} else {
    Write-Aviso 'No se pudo deducir la URL del sitio. Verificar manualmente.'
}

Write-Host "`n== Despliegue terminado" -ForegroundColor Cyan
Write-Host @"

  Tablero:  $UrlVerificacion
  Carpeta:  $PhysicalPath
  Base:     $Database en $SqlServer

  Comprobación completa desde un equipo con Python:
      python tools/compare_apis.py --contra-linea-base --base-b $($UrlVerificacion.TrimEnd('/'))

  Debe dar cero diferencias de claves, valores y estado HTTP.
  Diagnóstico y errores frecuentes: docs\DESPLIEGUE_IIS.md

"@ -ForegroundColor Gray
