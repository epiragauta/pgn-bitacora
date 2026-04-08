# Bitácora PGN 2025-I — Infografía Web DNP

**Inversión pública Colombia 2022-2025 · Dirección de Programación de Inversiones Públicas (DPIP)**

---

## Estructura del proyecto

```
pgn_infografia/
├── db/
│   ├── schema.sql          ← Esquema completo de la BD
│   └── pgn.db              ← SQLite generado al correr seed_data.py
├── etl/
│   ├── seed_data.py        ← Carga inicial (Bitácora 2, 2025-I)
│   ├── update_bitacora.py  ← Script para cargar nuevas bitácoras vía CSV
│   └── data/               ← Aquí van los CSVs para actualizaciones futuras
│       ├── inversion_transformaciones.csv
│       ├── ejecucion_historica.csv
│       ├── regionalizacion.csv
│       ├── apropiacion_sectores.csv
│       ├── vigencias_futuras.csv
│       └── ejecucion_sectorial.csv
├── api/
│   ├── __init__.py
│   └── main.py             ← FastAPI REST API
└── frontend/
    └── index.html          ← Infografía web completa (standalone)
```

---

## Instalación

```bash
pip install fastapi uvicorn
```

---

## Uso

### 1. Crear la base de datos con datos iniciales

```bash
python3 etl/seed_data.py
```

Esto crea `db/pgn.db` con todos los datos de la Bitácora 2, 2025-I.

### 2. Correr la API

```bash
uvicorn api.main:app --reload --port 8000
```

Documentación interactiva disponible en: `http://localhost:8000/docs`

### 3. Abrir la infografía

Abrir `frontend/index.html` en el navegador.  
- **Con API corriendo**: los datos se cargan dinámicamente.
- **Sin API**: la página funciona con datos embebidos (fallback automático).

---

## Endpoints principales

| Endpoint | Descripción |
|---|---|
| `GET /api/resumen` | KPIs principales para el dashboard |
| `GET /api/transformaciones?vigencia=2025` | Distribución por transformadores PND |
| `GET /api/evolucion` | Evolución presupuestal 2022-2025 |
| `GET /api/ejecucion` | Ejecución histórica inversión |
| `GET /api/regionalizacion` | Regionalización por dpto |
| `GET /api/vigencias_futuras/totales` | Totales VF 2026-2040 |
| `GET /api/sectorial?vigencia=2025` | Ejecución sectorial por entidad |

---

## Actualizar datos (nueva bitácora)

### Opción A — Script ETL con CSVs

1. Preparar CSVs en `etl/data/` con la estructura requerida (ver encabezados en seed_data.py)
2. Correr:

```bash
python3 etl/update_bitacora.py \
  --numero 3 \
  --periodo 2025-II \
  --corte 2025-06-30 \
  --notas "Primer semestre 2025"
```

### Opción B — Actualización manual directa en SQLite

```sql
-- 1. Crear registro de bitácora
INSERT INTO metadatos_bitacora (numero_bitacora, periodo, corte_fecha)
VALUES ('3', '2025-II', '2025-06-30');

-- 2. Insertar/actualizar datos usando el bid del paso anterior
INSERT OR REPLACE INTO ejecucion_historica (bitacora_id, vigencia, ...) VALUES (...);
```

### Opción C — Conexión directa SIIF/API externa

Modificar `etl/update_bitacora.py` para obtener los datos de la fuente en lugar de CSVs. La función de carga de cada tabla es idéntica.

---

## Estructura de CSVs para actualización

### `inversion_transformaciones.csv`
```
vigencia,transformador,inversion_mmm,peso_pct
2025,SEGURIDAD HUMANA Y JUSTICIA SOCIAL,32.149,38.29
```

### `ejecucion_historica.csv`
```
vigencia,vigente_mmm,compromisos_mmm,obligaciones_mmm,pagos_mmm,pct_compromisos,pct_obligaciones,pct_pagos,inv_pct_pib,inv_pct_gasto_total
2025,83961,36363,6628,6532,43,8,7.8,4.6,16
```

### `regionalizacion.csv`
```
region,departamento,vigente_mm,compromisos_mm,obligaciones_mm,pagos_mm,pct_ejec_compromisos,pct_ejec_obligaciones,pct_ejec_pagos,pct_participacion,principales_sectores
ANDINA,Bogotá,5906100,1515429,484913,479668,25.7,32.0,98.9,25.8,"[]"
```

### `vigencias_futuras.csv`
```
vigencia_exec,sector,valor_mmm_ctes,pct_pib
2026,TRANSPORTE,9651,1.01
```

### `ejecucion_sectorial.csv`
```
vigencia,sector,entidad,apr_vigente_mmm,compromisos_mmm,obligaciones_mmm,pct_c_av,pct_o_av
2025,TRANSPORTE,ANI,7.382,5.859,1.085,79,15
```

---

## Despliegue

### Frontend estático (GitHub Pages / Netlify)
El archivo `frontend/index.html` es completamente standalone — no requiere servidor para visualizarse. Sube la carpeta `frontend/` a cualquier hosting estático.

### API (Railway / Render / Fly.io)
```bash
# Procfile
web: uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

Cambiar `const API = 'http://localhost:8000/api'` en el HTML por la URL de producción.

---

## Fuentes de datos

| Tabla | Fuente |
|---|---|
| Transformaciones PND | Cálculo propio DPIP a partir del SIIF |
| Evolución presupuestal | MHCP – DNP |
| Regionalización | DPIP a partir de información PIIP (cierre marzo 2025) |
| Ejecución | SIIF Nación |
| Vigencias Futuras | DPIP – DNP |
| Ejecución Sectorial | SIIF Nación |

**Cifras:** Miles de millones de pesos corrientes, salvo vigencias futuras (constantes 2025).
