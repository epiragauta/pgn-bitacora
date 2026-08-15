# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **Bitácora de Inversión Pública**, a web infographic dashboard for tracking Colombia's public investment budget (Presupuesto General de la Nación) from 2022-2026, developed by DNP/DPIP (Departamento Nacional de Planeación / Dirección de Programación de Inversiones Públicas).

**Architecture:** Three-tier system with SQL Server database, .NET 8 REST API, and standalone HTML frontend.

## ⚠️ Migration in progress — read this first

The backend is being migrated **FastAPI/SQLite → .NET 8/SQL Server**. Both stacks coexist until the cutover. The authoritative plan, decisions, and per-phase results are in **`docs/PLAN_MIGRACION_DOTNET_SQLSERVER.md`** — read it before touching the backend.

| Component | State |
|---|---|
| SQL Server DB `dnp_dpip` | ✅ migrated (5,320 rows, 23 tables) |
| .NET 8 backend (`backend/`) | ✅ 30 endpoints, parity verified |
| Frontend | ✅ unchanged — do not modify for the migration |
| ETL scripts (`etl/`) | ⏳ still write to SQLite (phase 5 pending) |
| FastAPI (`api/main.py`) | ⏳ legacy, retired in phase 7 |

**Three rules that are load-bearing.** Each was a real bug found during migration:

1. **All computed SQL arithmetic must be `CAST(... AS FLOAT)`.** SQLite computes in double precision; `DECIMAL` produced `1.2367` where the original gave `1.2368`. Storage stays `DECIMAL(18,6)`; only expressions are cast.
2. **The database collation must stay `Modern_Spanish_CS_AS`.** With an accent-insensitive collation, `PACÍFICO` and `PACIFICO` collapse into one value and `GROUP BY region` silently merges rows.
3. **The SQL column aliases *are* the JSON keys.** The frontend reads exact snake_case keys and falls back to embedded data **silently, with no error**, if one is missing. Dapper returns dictionaries precisely so no rename can slip through. Never introduce a JSON naming policy.

Any backend change must pass `python tools/compare_apis.py --contra-linea-base` before being considered done.

## Key Commands

### Running the .NET API
```bash
# Container (production-like, on-premise)
cp .env.example .env          # set the real password
docker compose up -d --build  # http://127.0.0.1:5080

# Local development
export ConnectionStrings__DnpDpip="Server=127.0.0.1,1433;Database=dnp_dpip;User Id=dnp_dpip_app;Password=...;TrustServerCertificate=True"
dotnet run --project backend/src/PgnBitacora.Api --urls http://127.0.0.1:5080
```

API docs at `/swagger`; the dashboard is served at `/`.

### Verifying parity (mandatory after backend changes)
```bash
python tools/compare_apis.py --contra-linea-base   # vs frozen baseline
python tools/compare_apis.py                       # vs live FastAPI on :8000
```
Differences in **keys**, **values** or **HTTP status** fail the command. Differences in **row order among tied rows** are reported but do not block — the original defines no tiebreaker there.

### SQL Server schema
```bash
# Idempotent; run in order
for f in db/mssql/*.sql; do
  docker exec -i umbraco-sqlserver /opt/mssql-tools18/bin/sqlcmd \
      -S localhost -U sa -P "$SA_PASSWORD" -C -b -d dnp_dpip -i /dev/stdin < "$f"
done
```

### Migrating data from SQLite
```bash
python etl/migrate_sqlite_to_mssql.py                 # migrate + validate
python etl/migrate_sqlite_to_mssql.py --solo-validar  # validate only
```
Preserves original `id` values via `IDENTITY_INSERT` — they are real references (`pgn_ejecucion.concepto_id`, every `bitacora_id`).

### Running the legacy FastAPI (comparison only)
```bash
uvicorn api.main:app --reload --port 8000
```

### Updating Data (New Bitácora)
```bash
# Load new bitácora from CSV files in etl/data/
python etl/update_bitacora.py \
  --numero 3 \
  --periodo 2025-II \
  --corte 2025-06-30 \
  --notas "Primer semestre 2025"
```

### Docker Deployment (on-premise)
```bash
docker compose up -d --build       # builds backend/Dockerfile, context = repo root
docker compose logs -f api
```

- The container publishes **only on loopback** (`127.0.0.1:5080`); Caddy on the host terminates TLS and proxies to it. Block to add: `deploy/Caddyfile.snippet`.
- It joins the external network `sbn-ecp_umbraco-network` to reach SQL Server by its service alias `sqlserver`, instead of relying on the published 1433.
- The connection string comes from `.env` (gitignored); `.env.example` is the template.
- The image carries `frontend/` and `data/`; `Program.cs` locates them by walking up for `frontend/index.html`.
- The root `Dockerfile` is the **legacy Python one** and is removed in phase 7.

## Architecture & Data Flow

### Three-Layer Architecture

1. **Data Layer:**
   - SQL Server database `dnp_dpip`, collation `Modern_Spanish_CS_AS` (see rule 2 above)
   - DDL in `db/mssql/` — `001_schema.sql`, `002_views.sql`, `003_seed_dane.sql`, all idempotent
   - `db/pgn.db` (SQLite) is the migration source; `db/schema.sql` is **outdated** — the real schema was `db/pgn.db`
   - All tables reference `metadatos_bitacora` via `bitacora_id`, declared `NOT NULL`
   - Supports multiple bitácoras (quarterly reports) in a single database

2. **API Layer (`backend/src/PgnBitacora.Api/`):**
   - .NET 8 Minimal API with Dapper, one `Endpoints/*.cs` class per dashboard section
   - `Services/` holds the logic that does not fit in SQL: `VigenciasFuturasChart`, `MatrizSectores`, `Resumen`, `SgpResumen`
   - `Data/Db.cs` returns dictionaries so SQL aliases become JSON keys (rule 3)
   - `Data/BitacoraResolver.cs` ports `resolve_bitacora()`; no argument means the most recent bitácora
   - Dates are formatted **in SQL** (`CONVERT(char(10), …, 23)`) — .NET would emit `2026-03-31T00:00:00` and the frontend does `corte_fecha.split('-')`
   - Text `ORDER BY` uses `COLLATE Latin1_General_BIN2` to reproduce SQLite's binary ordering, where accented characters sort after all ASCII
   - Serves the frontend and `/data` statically, with `.geojson` registered explicitly — otherwise the map layers 404 and Leaflet renders blank with no error

3. **Frontend (`frontend/index.html`):**
   - **Standalone HTML file** with embedded CSS and JavaScript
   - Works with or without API (fallback to embedded data)
   - Chart.js for visualizations
   - Uses DNP 2026 design system (turquesa #00c3c1, magenta #fe1b7b, amarillo #ffca00)
   - Modal system for contextual information (see `infoTexts` object)

### Database Schema Key Points

**Central Table:** `metadatos_bitacora`
- Each bitácora (quarterly report) has one record
- All data tables use `bitacora_id` foreign key
- Enables historical tracking across multiple periods

**Section Tables:**
1. **Transformaciones PND** (`inversion_transformaciones`, `inversion_componentes_pnd`, `ejecucion_transformaciones`)
2. **Evolución Presupuestal** (`pgn_concepto`, `pgn_ejecucion`, view `pgn_vista_crosstab`) — the old `evolucion_presupuestal` table was dropped in the migration
3. **Regionalización** (`regionalizacion`, `regionalizacion_sectores`)
4. **Ejecución** (`ejecucion_historica`, `apropiacion_por_sector`, `compromisos_pct_por_sector`)
5. **Vigencias Futuras** (`vigencias_futuras`, `deflactores_pib`)
6. **Ejecución Sectorial** (`ejecucion_sectorial_entidades`, `ejecucion_sectorial_mensual`)

**Units:** All monetary values in thousands of millions of COP (miles de millones). Vigencias futuras are stored as raw current prices (`valor_corriente_mmm`); the API converts to constant 2026 prices on the fly using `deflactores_pib`.

**Vigencias Futuras — two-table design:**
- `vigencias_futuras`: raw pivot from SIIF (29 individual sectors × years, current prices mmm)
- `deflactores_pib`: DEFLACTOR PIB BASE 2026 + PIB corriente/constante by year
- The API endpoint `/api/vigencias_futuras/chart` applies `valor_constante = valor_corriente / deflactor` and groups into 6 series for the chart.

### ETL Pipeline

All loaders write to **SQL Server** through two shared modules — never open a connection yourself:

- **`etl/db.py`** — connection plus the sqlite3-shaped helpers the loaders expect.
  - `conectar()` reads `DNP_DPIP_CONN` (falls back to a local dev string).
  - `conn.upsert(tabla, columnas, filas, claves)` replaces `INSERT OR REPLACE`. It **deduplicates the batch by key, keeping the last row**, because SQLite applied that statement row by row and duplicates inside one batch would otherwise trip the UNIQUE constraint. It warns on stderr when it drops one.
  - `conn.insertar_devolviendo_id(sql, params)` replaces `cur.lastrowid`. `SCOPE_IDENTITY()` is scoped to the batch, not the session, so the INSERT and the lookup must travel together — a separate `execute` returns NULL.
  - `conn.vaciar_bitacora(tablas, bid)` replaces the `DROP TABLE` + `CREATE` that several loaders used to do. **Loaders must not create or drop tables**: the schema belongs to `db/mssql/`, and dropping would break the FKs and `pgn_vista_crosstab`.
  - `with conn:` commits or rolls back but does **not** close, matching sqlite3.
- **`etl/bases.py`** — locates the source workbooks. Resolution order: `BASES_BITACORA` env var → `data/BASES_BITACORA/` → the historical Windows paths. Files are matched by glob inside each numbered section folder, since names carry dates and suffixes that change every quarter.

Note that pyodbc only supports positional `?` parameters — no `:named` parameters like sqlite3 — and its rows do not support `row["column"]` access.

**Excel loaders** (source files under `data/BASES_BITACORA/<corte>/`):

| Script | Sección | Fuente Excel |
|--------|---------|--------------|
| `etl/load_bitacora_excel.py` | Sec 1, 4, 5, 6 | Secciones 1 y 5; **crea la bitácora** — correr primero |
| `etl/importar_pgn.py` | Sec 2 | CSV `data/evolucion_presupuestal.csv` |
| `etl/load_regionalizacion.py` | Sec 3 | `3. REGIONALIZACIÓN/Consolidado Reg-Ejec-*Graficas*.xlsx` |
| `etl/load_sectores_region.py` | Sec 3 | `3. REGIONALIZACIÓN/Consolidado Reg-Ejec-*.xlsx`, hoja `sectores_por_region` |
| `etl/load_ejecucion_sectorial.py` | Sec 4, 6 | `6. EJECUCIÓN SECTORIAL/BASE DETALLE MENSUAL *.xlsx` |
| `etl/load_vigencias_futuras.py` | Sec 5 | `5. VIGENCIAS FUTURAS/*.xlsx`, hojas `BASE_SIIF_2` y `TD BITACORA` |
| `etl/load_credito.py` | Sec 7 | `8. SCCI/Datos informe*.xlsx` |
| `etl/load_sgp.py`, `etl/load_sgp_componentes.py` | Sec 8 | `7. SDRT/SGP_*_Bitacora.xlsx` |

**Order matters.** `load_bitacora_excel.py` creates the bitácora row that every other loader resolves via `bitacora_reciente()`. `load_vigencias_futuras.py` must run *after* it: both write `vigencias_futuras`, and the dedicated loader is authoritative (29 sectors, 2025-2054) over the partial `TD BITACORA` pass (38 sectors, 2026-2040), which it wipes and replaces.

**`etl/update_bitacora.py`** (CSV path) now covers only transformaciones, ejecución histórica, apropiación sectorial and ejecución sectorial. Its regionalización and vigencias-futuras loaders were removed: they wrote to `regionalizacion_detalle_2025` (a dropped table) and to `valor_mmm_ctes`/`pct_pib` (columns that stopped existing well before the migration). Use the Excel loaders for those sections.

**`etl/seed_data.py` was retired** — it seeded the 2025-I bitácora that now lives migrated in SQL Server, and inserted into two tables the migration dropped.

See `docs/etl_uso.md` for detailed usage instructions per script.

### Frontend-API Integration

The frontend (`index.html`) has dual-mode operation:

1. **API Mode:** Fetches data from `/api/*` endpoints
2. **Fallback Mode:** Uses embedded `D` object with hardcoded data

The `af()` function (`async fetch`) handles fallback automatically:
```javascript
async function af(p,fb){
  try{
    const r=await fetch(API+p);
    if(!r.ok)throw 0;
    return await r.json();
  }catch{
    return fb;  // fallback data
  }
}
```

**Important:** To deploy frontend to static hosting (GitHub Pages, Netlify), it works standalone without modifications. To connect to production API, change `const API='/api'` to production URL.

## API Endpoints Structure

30 endpoints, one `Endpoints/*.cs` class per dashboard section (tagged for Swagger). Full interactive listing at `/swagger`.

- **Sec 1:** `/api/transformaciones`, `/api/transformaciones/{transformador}/componentes`
- **Sec 2:** `/api/evolucion` + `/composicion`, `/tasa_ejecucion`, `/pct_pib`, `/drilldown`, `/tabla_completa`, `/inversion_historica`
- **Sec 3:** `/api/regionalizacion` + `/historico`, `/sectores`, `/mapa`, `/departamento/{codigo_dane}`
- **Sec 4:** `/api/ejecucion` + `/sectores/{apropiacion,compromisos_pct,obligaciones_pct,pagos_pct,matriz}`
- **Sec 5:** `/api/vigencias_futuras`, `/totales`, `/chart`
- **Sec 6:** `/api/sectorial`, `/mensual`, `/historico`
- **Sec 7:** `/api/credito` + `/fuentes`, `/sectores`, `/resumen`, `/ejecucion_entidad`, `/ejecucion_historica`
- **Sec 8:** `/api/sgp/historico`, `/historico_componentes`, `/resumen`
- **Dashboard:** `/api/resumen` (KPIs for hero section)
- **Metadata:** `/api/bitacoras`, `/api/bitacoras/{periodo}`

All return JSON. Rows come back from Dapper as dictionaries so SQL column aliases are the JSON keys verbatim (rule 3). `codigo_dane` is a **string** with a leading zero (`'05'`), never an int.

`tools/endpoints.py` enumerates all 322 routes worth testing, deriving parameters from the data actually present in the database — so coverage grows on its own when a new bitácora is loaded.

## Deployment Configuration

**On-premise only.** Fly.io and Render were dropped: neither can reach the SQL Server instance, which listens on `127.0.0.1:1433`. `fly.toml` and `render.yaml` were removed — they assumed Python plus a local SQLite baked into the image.

| Piece | Value |
|---|---|
| Compose file | `docker-compose.yml` (repo root) |
| Image build | `backend/Dockerfile`, context = repo root |
| Published port | `127.0.0.1:5080` → container `8080` |
| Reverse proxy | Caddy on the host (`/etc/caddy/Caddyfile`), snippet in `deploy/Caddyfile.snippet` |
| Docker network | `sbn-ecp_umbraco-network` (external), SQL Server alias `sqlserver` |
| Restart policy | `unless-stopped`, with a `HEALTHCHECK` against `/health` |

This server is a **development and test** environment. The production target is still undefined (open question 9 in the migration plan). Developer Edition is the correct, freely licensed edition for dev/test use.

Data lives in the SQL Server volume, not in the image, so container restarts do not lose it.

## Design System (BDC GOV.CO v5.0 / DNP 2026)

**Color Palette:**
- Turquesa (primary): `#00c3c1` - innovation
- Magenta: `#fe1b7b` - transformation
- Amarillo: `#ffca00` - development
- Naranja (secondary): `#fbb03b`
- Morado (secondary): `#7f47dd`

**Typography:** Nunito Sans (Google Fonts)

**Components:**
- `.stag` - Section tags with numbered badges
- `.card` with `.bt`, `.bm`, `.ba` - Cards with colored top borders
- `.modal-overlay` + `.modal-content` - Info modal system
- `.info-icon` - Circular "i" icons for contextual information

When modifying frontend, maintain visual consistency with existing components and DNP brand guidelines.

## Working with Data Updates

To add a new bitácora (quarterly report):

1. Prepare CSV files in `etl/data/` with required columns (see README.md)
2. Run `update_bitacora.py` with appropriate parameters
3. Restart API to load new data
4. Frontend automatically shows latest data via API

**Alternative:** For SIIF Nación integration or external API, modify `update_bitacora.py` to fetch data programmatically instead of reading CSVs. The database insertion logic remains identical.

## Frontend Modal System

To add informational modals to additional sections:

1. Add icon to section tag HTML:
```html
<i class="info-icon" onclick="openInfoModal('Title', 'key-id')">i</i>
```

2. Define content in `infoTexts` object:
```javascript
const infoTexts = {
  'key-id': 'Informational text...'
};
```

The modal system handles opening, closing (X button, ESC key, outside click), and scroll locking automatically.
