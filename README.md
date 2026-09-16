# Bitácora de Inversión Pública — DNP / DPIP

**Inversión pública Colombia 2022-2026 · Dirección de Programación de Inversiones Públicas**

Dashboard web sobre el Presupuesto General de la Nación, con seguimiento adicional a Crédito Externo y al Sistema General de Participaciones.

**Arquitectura:** base de datos SQL Server, API REST en .NET 8 y frontend HTML autónomo.

> **Todas las tablas llevan el prefijo `btcr_`**, para poder convivir en una base compartida con otros sistemas de la entidad. Las rutas de la API no se prefijan: el prefijo es de almacenamiento, no del contrato público.

> La migración desde FastAPI/SQLite se completó el 2026-08-15. El histórico de decisiones, el catálogo de incompatibilidades entre motores y los resultados de cada fase están en [`docs/PLAN_MIGRACION_DOTNET_SQLSERVER.md`](docs/PLAN_MIGRACION_DOTNET_SQLSERVER.md) — vale la pena leerlo antes de tocar el backend.

---

## Documentación

| Documento | Para quién |
|---|---|
| [Arquitectura](docs/ARQUITECTURA.md) | Visión de conjunto, modelo de datos y decisiones de diseño |
| [Manual técnico](docs/MANUAL_TECNICO.md) | Desarrolladores que modifican el backend, la base o los ETL |
| [Manual de operación](docs/MANUAL_OPERACION.md) | Cargue trimestral, despliegue e incidencias |
| [Despliegue en IIS](docs/DESPLIEGUE_IIS.md) | Publicar en Windows/IIS, con el script `deploy/Deploy-Bitacora.ps1` |
| [Manual de usuario](docs/MANUAL_USUARIO.md) | Analistas y directivos que consultan el tablero |
| [Informe de la migración](docs/INFORME_MIGRACION_DOTNET_SQLSERVER.md) | Actividades, hallazgos y resultados del paso a .NET / SQL Server |
| [Informe de cambios 2026-08-20](docs/INFORME_CAMBIOS_2026-08-20.md) | Trabajo posterior: prefijo `btcr_`, despliegue en IIS y dos hallazgos de seguridad |
| [Informe de cambios 2026-08-27](docs/INFORME_CAMBIOS_2026-08-27.md) | Paquete de despliegue para IIS, hospedaje bajo subruta y lo que reveló `-WhatIf` |
| [Plan de migración](docs/PLAN_MIGRACION_DOTNET_SQLSERVER.md) | Bitácora técnica con el catálogo de incompatibilidades entre motores |
| [Guía de ETLs](docs/etl_uso.md) | Detalle de cada cargador |

Las versiones web de arquitectura y de los dos manuales de usuario están en `docs/web/` y publicadas como páginas compartibles.

---

## Estructura

```
.
├── backend/                       ← API .NET 8 (destino)
│   ├── Dockerfile
│   └── src/PgnBitacora.Api/
│       ├── Endpoints/             ← una clase por sección del dashboard
│       ├── Services/              ← lógica que no cabe en SQL
│       ├── Data/                  ← Dapper + resolución de bitácora
│       └── Json/
├── db/
│   ├── mssql/                     ← DDL de SQL Server (fuente de verdad)
│   │   ├── 001_schema.sql
│   │   ├── 002_views.sql
│   │   └── 003_seed_dane.sql
│   └── legacy/                    ← archivo histórico SQLite (ver su README)
├── etl/                           ← cargadores desde Excel + migrador de datos
│   └── migrate_sqlite_to_mssql.py
├── tools/
│   ├── endpoints.py               ← enumera las 322 rutas a verificar
│   ├── capture_baseline.py        ← congela las respuestas de referencia
│   ├── compare_apis.py            ← verifica paridad entre backends
│   └── baseline/                  ← respuestas de referencia
├── frontend/index.html            ← dashboard standalone
├── data/                          ← GeoJSON de departamentos y regiones
├── deploy/
│   ├── Deploy-Bitacora.ps1     ← despliegue completo en IIS
│   └── Caddyfile.snippet       ← bloque de proxy inverso
└── docker-compose.yml
```

---

## Puesta en marcha

### Requisitos
- Docker con Compose
- SQL Server accesible (en este servidor: contenedor `umbraco-sqlserver`, red `sbn-ecp_umbraco-network`)
- Para desarrollo local sin contenedor: .NET SDK 8

### 1. Preparar la base

```bash
# Crear base y login (una sola vez, como sa)
docker exec -i umbraco-sqlserver /opt/mssql-tools18/bin/sqlcmd \
    -S localhost -U sa -P "$SA_PASSWORD" -C -i /dev/stdin <<'SQL'
CREATE DATABASE MI_BASE COLLATE Modern_Spanish_CS_AS;   -- el nombre es libre
GO
CREATE LOGIN USUARIO WITH PASSWORD='...', DEFAULT_DATABASE=MI_BASE, CHECK_POLICY=OFF;
GO
USE MI_BASE;
CREATE USER USUARIO FOR LOGIN USUARIO;
ALTER ROLE db_datareader ADD MEMBER USUARIO;
ALTER ROLE db_datawriter ADD MEMBER USUARIO;
ALTER ROLE db_ddladmin  ADD MEMBER USUARIO;
GO
SQL

# Aplicar el esquema (idempotente)
for f in db/mssql/*.sql; do
  docker exec -i umbraco-sqlserver /opt/mssql-tools18/bin/sqlcmd \
      -S localhost -U sa -P "$SA_PASSWORD" -C -b -d "$MI_BASE" -i /dev/stdin < "$f"
done
```

**La collation `Modern_Spanish_CS_AS` no es opcional.** Con una collation insensible a tildes, `PACÍFICO` y `PACIFICO` pasan a ser el mismo valor y los `GROUP BY` por región fusionarían filas en silencio.

### 2. Cargar los datos

```bash
pip install pyodbc                       # requiere ODBC Driver 18
python etl/migrate_sqlite_to_mssql.py    # migra desde db/legacy/pgn.db y valida
```

### 3. Levantar la API

```bash
cp .env.example .env      # y poner la contraseña real
docker compose up -d --build
```

Disponible en `http://127.0.0.1:5080` — dashboard en la raíz, API en `/api`, documentación en `/swagger`.

#### Desarrollo sin contenedor

```bash
export ConnectionStrings__DnpDpip="Server=127.0.0.1,1433;Database=MI_BASE;User Id=USUARIO;Password=...;TrustServerCertificate=True"
dotnet run --project backend/src/PgnBitacora.Api --urls http://127.0.0.1:5080
```

---

## Verificar que nada cambió

Cualquier modificación del backend debe pasar esta comprobación antes de darse por buena. La referencia es el comportamiento congelado de la API anterior, que se conserva como red de seguridad:

```bash
python tools/compare_apis.py --contra-linea-base
```

Recorre 322 rutas y clasifica las diferencias por tipo. Las de **claves**, **valores** o **estado HTTP** hacen fallar el comando; las de **orden** entre filas empatadas se reportan sin bloquear (el original no define desempate — ver §3.9 del plan).

También compara dos instancias en vivo, útil para contrastar un despliegue contra otro:

```bash
python tools/compare_apis.py --base-a http://otra-instancia:5080
```

Si se cambian los datos a propósito, hay que regenerar la referencia con `python tools/capture_baseline.py`, que apunta al backend .NET.

---

## Endpoints

30 endpoints agrupados por sección del dashboard. Listado completo e interactivo en `/swagger`.

| Sección | Ruta base |
|---|---|
| Dashboard | `/api/resumen` |
| Metadatos | `/api/bitacoras` |
| 1 · Transformaciones PND | `/api/transformaciones` |
| 2 · Evolución presupuestal | `/api/evolucion` |
| 3 · Regionalización | `/api/regionalizacion` |
| 4 · Ejecución | `/api/ejecucion` |
| 5 · Vigencias futuras | `/api/vigencias_futuras` |
| 6 · Ejecución sectorial | `/api/sectorial` |
| 7 · Crédito externo | `/api/credito` |
| 8 · SGP | `/api/sgp` |

Todos aceptan `bitacora_id` opcional; sin él responden con la bitácora más reciente.

---

## Despliegue

**On-premise**, detrás del Caddy del host. El contenedor publica **solo en loopback** (`127.0.0.1:5080`) y se une a la red del SQL Server para alcanzarlo por el alias `sqlserver`, sin depender del 1433 publicado.

Se publica en **https://dnp-btcr.skaphe.com** añadiendo el bloque de [`deploy/Caddyfile.snippet`](deploy/Caddyfile.snippet) a `/etc/caddy/Caddyfile` y recargando Caddy, que gestiona el certificado TLS automáticamente.

### Servirla por IP y puerto

Para llegar al tablero sin pasar por el subdominio, en `.env`:

```bash
API_BIND=0.0.0.0        # por omisión 127.0.0.1
API_PUERTO=5080         # 8080 está ocupado por Umbraco en este servidor
```

y `docker compose up -d`. Queda en `http://<ip-del-host>:5080/`. El tablero
no necesita ningún cambio: resuelve sus rutas contra `document.baseURI`, así
que funciona igual en la raíz de un puerto que bajo una subruta.

**Es HTTP en claro.** Por una IP no se puede emitir un certificado, así que
el navegador la marcará como no segura y el tráfico viaja sin cifrar. El
contenido ya es público, pero las dos formas de acceso no son equivalentes;
si se quiere solo la de IP, hay que retirar además el bloque de Caddy.

> Docker publica los puertos con sus propias reglas de iptables, que
> **esquivan ufw**. Limitar quién alcanza ese puerto exige reglas en la
> cadena `DOCKER-USER`, no en ufw.

### En IIS (el destino del DNP)

```bash
./tools/generar_paquete.sh     # deja dist/bitacora-despliegue-<version>.zip
```

Se copia al servidor, se descomprime y se corre `deploy\Deploy-Bitacora.ps1`
desde su carpeta. Lleva la aplicación compilada y los datos como sentencias
SQL: allá solo hacen falta IIS, el Hosting Bundle de ASP.NET Core 8 y `sqlcmd`.
Conviene que la primera corrida sea con `-WhatIf`. Detalle en
[`docs/DESPLIEGUE_IIS.md`](docs/DESPLIEGUE_IIS.md).

> Fly.io y Render quedaron descartados: la instancia de SQL Server no es alcanzable desde ellos.

---

## Actualizar datos (nueva bitácora)

Los cargadores escriben directamente en SQL Server. Toman la conexión de `DNP_DPIP_CONN` y localizan los Excel bajo `data/BASES_BITACORA/<corte>/` (o donde apunte la variable `BASES_BITACORA`).

```bash
export DNP_DPIP_CONN="DRIVER={ODBC Driver 18 for SQL Server};SERVER=...;DATABASE=MI_BASE;..."

python etl/load_bitacora_excel.py --numero 3 --periodo 2026-I --corte 2026-03-31
python etl/importar_pgn.py                 # Sec 2
python etl/load_regionalizacion.py         # Sec 3
python etl/load_sectores_region.py         # Sec 3
python etl/load_ejecucion_sectorial.py     # Sec 4 y 6
python etl/load_vigencias_futuras.py       # Sec 5
python etl/load_credito.py                 # Sec 7
python etl/load_sgp.py && python etl/load_sgp_componentes.py   # Sec 8
```

**El orden importa.** `load_bitacora_excel.py` crea la bitácora que los demás resuelven, y `load_vigencias_futuras.py` debe ir después porque reemplaza la carga parcial de la sección 5 que hace el primero.

Para comprobar que una carga reprodujo lo esperado, contra otra base:

```bash
python tools/compare_bd.py --a BASE_REFERENCIA --b BASE_A_VERIFICAR --periodo 2026-I
```

Uso detallado por script en [`docs/etl_uso.md`](docs/etl_uso.md).

---

## Fuentes de datos

| Sección | Fuente |
|---|---|
| Transformaciones PND | Cálculo propio DPIP a partir del SIIF |
| Evolución presupuestal | MHCP – DNP |
| Regionalización | DPIP a partir de información PIIP |
| Ejecución | SIIF Nación |
| Vigencias Futuras | DPIP – DNP |
| Ejecución Sectorial | SIIF Nación |
| Crédito Externo | SCCI |
| SGP | DNP |

**Cifras:** miles de millones de pesos corrientes, salvo vigencias futuras, que la API convierte a constantes 2026 aplicando el deflactor del PIB.
