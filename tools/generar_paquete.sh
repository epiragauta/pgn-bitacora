#!/usr/bin/env bash
# tools/generar_paquete.sh — Arma el zip de despliegue para el servidor del DNP.
#
# Para qué: el servidor de IIS no tiene SDK de .NET, ni Python, ni el driver
# ODBC, y no debería tenerlos. Este paquete lleva la aplicación ya compilada
# y los datos como sentencias SQL, de modo que allá solo hacen falta IIS,
# el Hosting Bundle de ASP.NET Core 8 y sqlcmd.
#
# Uso:
#   ./tools/generar_paquete.sh                 # a dist/
#   ./tools/generar_paquete.sh /otra/carpeta
#
# Antes de correrlo, si los datos cambiaron:
#   export DNP_DPIP_CONN="..." && python tools/generar_seed_sql.py

set -euo pipefail
cd "$(dirname "$0")/.."

DESTINO="${1:-dist}"
VERSION="$(git describe --tags --always 2>/dev/null || echo sin-version)"
NOMBRE="bitacora-despliegue-${VERSION}"
TRABAJO="$(mktemp -d)"
RAIZ="$TRABAJO/bitacora-despliegue"
trap 'rm -rf "$TRABAJO"' EXIT

echo "== Publicando la aplicación"
dotnet publish backend/src/PgnBitacora.Api \
    -c Release -o "$RAIZ/app" --nologo -v quiet

# appsettings.Development.json no tiene por qué viajar a producción: solo
# añade ruido y podría contradecir a appsettings.Production.json.
rm -f "$RAIZ/app/appsettings.Development.json"

if [[ ! -f "$RAIZ/app/frontend/index.html" ]]; then
    echo "ERROR: el publish no incluyó el tablero." >&2
    echo "       Revisar el target CopiarFrontend en PgnBitacora.Api.csproj." >&2
    exit 1
fi

echo "== Copiando esquema, datos y guías"
mkdir -p "$RAIZ/deploy" "$RAIZ/db/mssql" "$RAIZ/docs"
cp deploy/Deploy-Bitacora.ps1  "$RAIZ/deploy/"
cp db/mssql/00[1-4]*.sql       "$RAIZ/db/mssql/"
cp docs/DESPLIEGUE_IIS.md      "$RAIZ/docs/"
cp deploy/LEEME.txt            "$RAIZ/"

# El destino es Windows: los .ps1 y .sql se leen con Notepad y se ejecutan
# con sqlcmd, y el zip no convierte finales de línea.
echo "== Normalizando finales de línea a CRLF"
find "$RAIZ" -type f \( -name '*.ps1' -o -name '*.sql' -o -name '*.md' -o -name '*.txt' \) \
    -exec sed -i 's/$/\r/; s/\r\r$/\r/' {} +

mkdir -p "$DESTINO"
SALIDA="$(cd "$DESTINO" && pwd)/${NOMBRE}.zip"
rm -f "$SALIDA"
(cd "$TRABAJO" && zip -rq "$SALIDA" bitacora-despliegue)

echo
echo "$SALIDA"
printf '  %s · %s archivos · %s\n' "$VERSION" \
    "$(unzip -l "$SALIDA" | tail -1 | awk '{print $2}')" \
    "$(du -h "$SALIDA" | cut -f1)"
echo
echo "Primera corrida en el servidor, en seco:"
echo '  .\deploy\Deploy-Bitacora.ps1 -SqlServer SQLSRV01 -Database SICODIS \'
echo '      -AppUser btcr_app -AppPassword $pw -WhatIf'
