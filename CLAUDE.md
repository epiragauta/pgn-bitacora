# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **Bitácora PGN 2025-I**, a web infographic dashboard for tracking Colombia's public investment budget (Presupuesto General de la Nación) from 2022-2025, developed by DNP/DPIP (Departamento Nacional de Planeación / Dirección de Programación de Inversiones Públicas).

**Architecture:** Three-tier system with SQLite database, FastAPI REST API, and standalone HTML frontend.

## Key Commands

### Database Setup
```bash
# Initialize database with seed data (Bitácora 2, 2025-I)
python etl/seed_data.py
```

This creates `db/pgn.db` with the complete schema and initial data.

### Running the API
```bash
# Development mode with auto-reload
uvicorn api.main:app --reload --port 8000

# Production mode
uvicorn api.main:app --host 0.0.0.0 --port 8080
```

API documentation available at: `http://localhost:8000/docs`

### Updating Data (New Bitácora)
```bash
# Load new bitácora from CSV files in etl/data/
python etl/update_bitacora.py \
  --numero 3 \
  --periodo 2025-II \
  --corte 2025-06-30 \
  --notas "Primer semestre 2025"
```

### Docker Deployment
```bash
# Build and run
docker build -t pgn-bitacora .
docker run -p 8080:8080 pgn-bitacora
```

The Dockerfile automatically runs `seed_data.py` during build to initialize the database.

## Architecture & Data Flow

### Three-Layer Architecture

1. **Data Layer (`db/`):**
   - SQLite database (`pgn.db`) with normalized schema
   - Schema defined in `db/schema.sql`
   - All tables reference `metadatos_bitacora` via `bitacora_id` foreign key
   - Supports multiple bitácoras (quarterly reports) in a single database

2. **API Layer (`api/main.py`):**
   - FastAPI REST API with 6 sections matching the frontend dashboard
   - Connection pooling via `get_db()` helper
   - CORS enabled for cross-origin requests
   - Serves static frontend files via `/` route (must be defined last)

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
2. **Evolución Presupuestal** (`evolucion_presupuestal`, `ejecucion_historica`)
3. **Regionalización** (`regionalizacion_resumen`, `regionalizacion_detalle_2025`)
4. **Ejecución** (`ejecucion_historica`, `apropiacion_por_sector`, `compromisos_pct_por_sector`)
5. **Vigencias Futuras** (`vigencias_futuras`)
6. **Ejecución Sectorial** (`ejecucion_sectorial_entidades`, `ejecucion_sectorial_mensual`)

**Units:** All monetary values in thousands of millions of COP (miles de millones), except vigencias futuras which are in constant 2025 pesos.

### ETL Pipeline

**Seed Data** (`etl/seed_data.py`):
- Hardcoded Python data for initial Bitácora 2 (2025-I)
- Creates schema and populates all tables
- Run once for initial setup

**Update Script** (`etl/update_bitacora.py`):
- CSV-based ETL for new quarterly reports
- Reads from `etl/data/*.csv`
- Inserts new `metadatos_bitacora` record and loads associated data
- Uses `INSERT OR REPLACE` for upserts

**CSV Structure:** See README.md sections on CSV formats for exact column names per table.

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

Endpoints are organized by dashboard section (tagged in FastAPI):

- **Sec 1:** `/api/transformaciones`, `/api/transformaciones/{transformador}/componentes`
- **Sec 2:** `/api/evolucion`, `/api/evolucion/inversion_historica`
- **Sec 3:** `/api/regionalizacion`, `/api/regionalizacion/historico`
- **Sec 4:** `/api/ejecucion`, `/api/ejecucion/sectores/apropiacion`, `/api/ejecucion/sectores/compromisos_pct`
- **Sec 5:** `/api/vigencias_futuras`, `/api/vigencias_futuras/totales`
- **Sec 6:** `/api/sectorial`, `/api/sectorial/mensual`
- **Dashboard:** `/api/resumen` (KPIs for hero section)
- **Metadata:** `/api/bitacoras`, `/api/bitacoras/{periodo}`

All endpoints return JSON. Row objects from SQLite are converted to dicts via `rows_to_list()` helper.

## Deployment Configurations

### Fly.io (`fly.toml`)
- App name: `app-old-dream-8565`
- Region: `mia` (Miami)
- Port: 8080
- Auto-start/stop enabled
- Memory: 256MB

### Docker
- Base: Python 3.11-slim
- Runs `seed_data.py` at build time
- Exposes port 8080
- Command: `uvicorn api.main:app --host 0.0.0.0 --port 8080`

**Note:** For production deployment, database should be volume-mounted or use external database to persist data across container restarts.

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
