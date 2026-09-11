# Documento de Arquitectura de Software

**Proyecto:** Bitácora PGN — Infografía Web de Inversión Pública
**Entidad:** Departamento Nacional de Planeación (DNP) · Dirección de Programación de Inversiones Públicas (DPIP)
**Versión del documento:** 1.0
**Fecha:** 2026-09-11
**Autor:** _(equipo de desarrollo DPIP)_
**Estado:** Vigente

---

## Tabla de contenido

1. [Introducción](#1-introducción)
2. [Objetivos y restricciones arquitectónicas](#2-objetivos-y-restricciones-arquitectónicas)
3. [Visión general de la arquitectura](#3-visión-general-de-la-arquitectura)
4. [Vista lógica (capas y componentes)](#4-vista-lógica-capas-y-componentes)
5. [Vista de datos](#5-vista-de-datos)
6. [Vista de procesos (flujos)](#6-vista-de-procesos-flujos)
7. [Vista de despliegue](#7-vista-de-despliegue)
8. [Vista de implementación (organización del código)](#8-vista-de-implementación-organización-del-código)
9. [Decisiones de arquitectura](#9-decisiones-de-arquitectura-adr)
10. [Atributos de calidad](#10-atributos-de-calidad)
11. [Riesgos y deuda técnica](#11-riesgos-y-deuda-técnica)
12. [Glosario](#12-glosario)

---

## 1. Introducción

### 1.1 Propósito

Este documento describe la arquitectura del sistema **Bitácora PGN**, una infografía web que
presenta el seguimiento del Presupuesto General de la Nación (PGN) — con foco en la inversión
pública — para el período 2022-2026. Está dirigido al equipo técnico, al analista documentador
y a quienes den mantenimiento o evolucionen el sistema.

### 1.2 Alcance

El sistema cubre ocho secciones temáticas de análisis presupuestal:

| # | Sección | Contenido |
|---|---------|-----------|
| 1 | Transformaciones PND | Inversión distribuida por los transformadores del Plan Nacional de Desarrollo |
| 2 | Evolución Presupuestal | Serie histórica del PGN por rubro (funcionamiento, inversión, deuda) |
| 3 | Regionalización | Distribución territorial de la inversión por departamento/región (con mapa) |
| 4 | Ejecución | Ejecución histórica de la inversión y por sector (apropiación, compromisos, obligaciones, pagos) |
| 5 | Vigencias Futuras | Compromisos de vigencias futuras a precios constantes (base 2026) |
| 6 | Ejecución Sectorial | Ejecución mensual y por entidad dentro de cada sector |
| 7 | Crédito Externo | Portafolio y ejecución de crédito externo (BID, BM, CAF) |
| 8 | SGP | Sistema General de Participaciones (histórico y componentes) |

### 1.3 Referencias

- `README.md` — instalación y uso.
- `CLAUDE.md` — guía técnica del repositorio.
- `docs/etl_uso.md` — uso detallado de los scripts ETL.
- `db/schema.sql` — esquema de la base de datos.
- Documentación interactiva de la API (OpenAPI/Swagger): `http://localhost:8000/docs`.

---

## 2. Objetivos y restricciones arquitectónicas

### 2.1 Objetivos

- Publicar una infografía **navegable y visualmente fiel** a la identidad DNP 2026 / BDC GOV.CO v5.0.
- Permitir **actualización periódica** de datos (bitácoras trimestrales/semestrales) sin reescribir la aplicación.
- Soportar **múltiples bitácoras** (cortes) coexistiendo en una misma base de datos.
- Funcionar tanto **con API** (datos dinámicos) como **sin API** (datos embebidos de respaldo).

### 2.2 Restricciones

- **Presupuesto de infraestructura reducido:** base de datos embebida (SQLite), sin motor de BD dedicado.
- **Frontend autónomo:** un único archivo HTML que debe poder abrirse sin servidor.
- **Fuentes de datos externas:** los insumos provienen de archivos Excel de SIIF Nación y cálculos DPIP; no hay integración en línea con SIIF (a la fecha de este documento).
- **Cifras monetarias** en miles de millones de pesos (mmm) corrientes, salvo vigencias futuras (precios constantes 2026).

---

## 3. Visión general de la arquitectura

El sistema sigue una **arquitectura de tres capas** con un pipeline **ETL** desacoplado que
alimenta la capa de datos.

```
        ┌──────────────────────────────────────────────────────────────┐
        │                    FUENTES DE DATOS                           │
        │   Excel SIIF Nación · cálculos DPIP · PIIP · SCCI · SGP       │
        └───────────────────────────┬──────────────────────────────────┘
                                     │  (carga manual periódica)
                                     ▼
        ┌──────────────────────────────────────────────────────────────┐
        │  CAPA ETL (Python)                                            │
        │  etl/seed_data.py · etl/load_*.py · etl/update_bitacora.py    │
        └───────────────────────────┬──────────────────────────────────┘
                                     │  INSERT / UPSERT
                                     ▼
        ┌──────────────────────────────────────────────────────────────┐
        │  CAPA DE DATOS                                                │
        │  SQLite  db/pgn.db   (esquema db/schema.sql + migrations/)    │
        └───────────────────────────┬──────────────────────────────────┘
                                     │  SQL (solo lectura en runtime)
                                     ▼
        ┌──────────────────────────────────────────────────────────────┐
        │  CAPA DE APLICACIÓN / API  (FastAPI + Uvicorn)               │
        │  api/main.py — ~40 endpoints REST /api/* (JSON)              │
        │  + servidor de archivos estáticos (frontend y /data)         │
        └───────────────────────────┬──────────────────────────────────┘
                                     │  HTTP/JSON  +  estáticos
                                     ▼
        ┌──────────────────────────────────────────────────────────────┐
        │  CAPA DE PRESENTACIÓN  (Navegador)                           │
        │  frontend/index.html — HTML/CSS/JS standalone                │
        │  Chart.js (gráficos) · Leaflet (mapa) · fallback embebido    │
        └──────────────────────────────────────────────────────────────┘
```

**Patrón de operación dual del frontend:** cada consumo de datos se realiza con la función
`af(path, fallback)` que intenta `fetch(API+path)` y, ante cualquier error, devuelve el
conjunto de datos embebido. Esto permite que la infografía funcione publicada como sitio
estático (sin API) o servida por la API (con datos vivos).

---

## 4. Vista lógica (capas y componentes)

### 4.1 Capa de presentación — `frontend/index.html`

- Archivo **standalone** (~3.900 líneas) con CSS y JavaScript embebidos.
- **Librerías (auto-alojadas en `frontend/vendor/`, sin CDN):**
  - `chart.umd.min.js` — Chart.js para gráficos de barras, líneas y dona.
  - `leaflet.js` + `leaflet.css` — mapa coroplético de regionalización.
  - `nunito-sans.css` / fuentes — tipografía institucional.
  - Font Awesome — iconografía.
- **Datos geográficos:** `frontend/data/dptos.geojson` y `regiones.geojson`.
- **Sistema de diseño DNP 2026:** tokens de color en variables CSS (`--t` turquesa `#00c3c1`,
  `--m` magenta `#fe1b7b`, `--a` amarillo `#ffca00`, etc.), franja tricolor de marca y
  soporte de tema conmutable vía atributo `data-tema`.
- **Estructura:** una sección HTML por área temática (`#hero`, `#sec1` … `#sec8`), navegación
  fija superior, y sistema de modales informativos (`openInfoModal`, objeto `infoTexts`).
- **Configuración de entorno:** `const API='/api'` (línea ~1104). Para consumir una API remota
  se cambia esta constante.

### 4.2 Capa de aplicación / API — `api/main.py`

- Framework **FastAPI** servido por **Uvicorn** (ASGI).
- **CORS** habilitado (`CORSMiddleware`) para permitir consumo cross-origin.
- **Acceso a datos:** helper `get_db()` abre conexión SQLite; `rows_to_list()` convierte filas
  a diccionarios; `resolve_bitacora()` resuelve la bitácora vigente cuando no se especifica `bitacora_id`.
- **~40 endpoints REST** agrupados por sección (tags de FastAPI). Todos devuelven JSON y aceptan
  el parámetro opcional `bitacora_id` para consultar cortes históricos.
- **Servidor de estáticos:** al final del archivo se montan `/data` (GeoJSON) y `/` (frontend)
  con `StaticFiles`. **El montaje de `/` debe declararse después de todas las rutas `/api`.**
- **Lógica de negocio en runtime:** por ejemplo, el endpoint `/api/vigencias_futuras/chart`
  deflacta valores corrientes a constantes 2026 (`valor_constante = valor_corriente / deflactor`)
  y agrupa 29 sectores individuales en 6 series para graficar.

**Mapa resumido de endpoints** (ver `/docs` para el detalle):

| Sección | Endpoints representativos |
|---------|---------------------------|
| Metadatos | `GET /api/bitacoras`, `GET /api/bitacoras/{periodo}` |
| Sec 1 | `GET /api/transformaciones`, `.../{transformador}/componentes` |
| Sec 2 | `GET /api/evolucion`, `.../composicion`, `.../tasa_ejecucion`, `.../pct_pib`, `.../drilldown`, `.../inversion_historica` |
| Sec 3 | `GET /api/regionalizacion`, `.../historico`, `.../sectores`, `.../mapa`, `.../departamento/{codigo_dane}` |
| Sec 4 | `GET /api/ejecucion`, `.../sectores/{apropiacion\|compromisos_pct\|obligaciones_pct\|pagos_pct\|matriz}` |
| Sec 5 | `GET /api/vigencias_futuras`, `.../totales`, `.../chart` |
| Sec 6 | `GET /api/sectorial`, `.../mensual`, `.../historico` |
| Sec 7 | `GET /api/credito`, `.../fuentes`, `.../sectores`, `.../resumen`, `.../ejecucion_entidad`, `.../ejecucion_historica` |
| Sec 8 | `GET /api/sgp/historico`, `.../historico_componentes`, `.../resumen` |
| Dashboard | `GET /api/resumen` (KPIs del hero) |

### 4.3 Capa de datos — `db/pgn.db`

- **SQLite** con esquema normalizado (`db/schema.sql`) y migraciones incrementales (`db/migrations/*.sql`).
- **Tabla de control:** `metadatos_bitacora` — un registro por corte; todas las tablas de datos
  la referencian mediante `bitacora_id` (FK). Esto habilita el seguimiento histórico multi-bitácora.
- Detalle en la [Vista de datos](#5-vista-de-datos).

### 4.4 Capa ETL — `etl/`

Scripts Python que transforman los Excel fuente al esquema relacional:

| Script | Rol |
|--------|-----|
| `seed_data.py` | Carga inicial embebida (Bitácora 2, 2025-I); crea esquema y puebla todas las tablas. |
| `update_bitacora.py` | Carga de nuevas bitácoras desde CSV (`etl/data/*.csv`) con `INSERT OR REPLACE`. |
| `load_bitacora_excel.py` | Secciones 1, 4, 6 desde Excel. |
| `load_regionalizacion.py` / `load_sectores_region.py` | Sección 3. |
| `load_ejecucion_sectorial.py` | Secciones 4 y 6 (detalle mensual). |
| `load_vigencias_futuras.py` | Sección 5 (hojas `BASE_SIIF_2` y `TD BITACORA`). |
| `load_credito.py` | Sección 7 (crédito externo). |
| `load_sgp.py` / `load_sgp_componentes.py` | Sección 8 (SGP). |
| `importar_pgn.py` | Utilidad de importación general. |

> **Nota — backend .NET incipiente:** existe una carpeta `backend/` con un esqueleto de proyecto
> .NET 8 (`PgnBitacora.Api`) que a la fecha de este documento **no contiene código fuente
> operativo** (solo artefactos de restauración/compilación). Se documenta como exploración de una
> posible migración futura; **el backend en producción es el de FastAPI** (`api/main.py`).

---

## 5. Vista de datos

### 5.1 Modelo conceptual

`metadatos_bitacora` es el eje central. Cada tabla de datos se asocia a un corte mediante
`bitacora_id`. La mayoría de tablas de detalle aplican restricciones `UNIQUE` sobre
(`bitacora_id`, `vigencia`, …) para soportar cargas idempotentes (upsert).

```
                          ┌───────────────────────┐
                          │   metadatos_bitacora  │  (1 fila por corte)
                          │  id · numero · periodo│
                          │  corte_fecha · notas  │
                          └───────────┬───────────┘
                                      │ 1
                    ┌─────────────────┼─────────────────┐  * (bitacora_id FK)
                    ▼                 ▼                 ▼
         Sec 1: inversion_*    Sec 2: evolucion_*   Sec 3: regionalizacion_*
         Sec 4: ejecucion_*    Sec 5: vigencias_futuras / deflactores_pib
         Sec 6: ejecucion_sectorial_*   Sec 7: credito_*   Sec 8: sgp_*
```

### 5.2 Tablas por sección

| Sección | Tablas principales |
|---------|--------------------|
| Control | `metadatos_bitacora` |
| 1 – Transformaciones PND | `inversion_transformaciones`, `inversion_componentes_pnd`, `ejecucion_transformaciones` |
| 2 – Evolución Presupuestal | `evolucion_presupuestal` |
| 3 – Regionalización | `regionalizacion_resumen`, `regionalizacion_detalle_2025` |
| 4 – Ejecución | `ejecucion_historica`, `apropiacion_por_sector`, `compromisos_pct_por_sector`, `obligaciones_pct_por_sector`, `pagos_pct_por_sector`, `ejecucion_mensual_sectorial` |
| 5 – Vigencias Futuras | `vigencias_futuras`, `deflactores_pib` |
| 6 – Ejecución Sectorial | `ejecucion_sectorial_entidades`, `ejecucion_sectorial_mensual` |
| 7 – Crédito Externo | `credito_portafolio`, `credito_ejecucion_entidad`, `credito_ejecucion_historica` |
| 8 – SGP | `sgp_historico_participacion`, `sgp_historico_componentes` |

### 5.3 Convenciones de unidades

- Sufijo **`_mmm`**: miles de millones de pesos.
- Sufijo **`_mm`**: millones de pesos (usado en regionalización).
- Sufijo **`_pct`** / `pct_*`: porcentajes.
- **Vigencias futuras:** se almacenan a **precios corrientes** (`valor_corriente_mmm`) y la API
  las convierte a **constantes 2026** en tiempo de consulta usando `deflactores_pib`.

### 5.4 Índices

Se definen índices para las consultas frecuentes por vigencia, sector, entidad, región,
año de vigencias futuras, entidad de crédito y componentes SGP (ver final de `db/schema.sql`).

### 5.5 Migraciones

`db/migrations/` contiene scripts SQL incrementales (p. ej. `003_regionalizacion_multiagno.sql`,
`004_regionalizacion_sectores.sql`) aplicados sobre el esquema base para evoluciones puntuales.

---

## 6. Vista de procesos (flujos)

### 6.1 Flujo de actualización de datos (nueva bitácora)

```
Analista/DPIP ──► Prepara Excel/CSV fuente
             ──► Ejecuta ETL correspondiente (load_*.py o update_bitacora.py)
             ──► Se crea/actualiza registro en metadatos_bitacora
             ──► INSERT OR REPLACE en tablas de la sección (idempotente)
             ──► Reinicia API para servir el nuevo corte
             ──► Frontend muestra automáticamente la bitácora vigente
```

### 6.2 Flujo de renderizado de la infografía (runtime)

```
Navegador carga index.html
   └─► Por cada sección: af('/api/...', fallbackEmbebido)
          ├─ éxito ► render con datos vivos de la API
          └─ error ► render con datos embebidos (modo standalone)
   └─► Chart.js dibuja gráficos · Leaflet dibuja mapa coroplético
   └─► Interacción: modales informativos, conmutador de tema, drill-downs
```

### 6.3 Flujo de deflactación (Vigencias Futuras)

```
GET /api/vigencias_futuras/chart
   └─► lee vigencias_futuras (corriente) + deflactores_pib
   └─► valor_constante = valor_corriente / deflactor   (base 2026)
   └─► agrupa 29 sectores en 6 series
   └─► devuelve JSON listo para Chart.js
```

---

## 7. Vista de despliegue

### 7.1 Entorno local (desarrollo)

```
python etl/seed_data.py                       # crea db/pgn.db
uvicorn api.main:app --reload --port 8000      # API + frontend en http://localhost:8000
```

### 7.2 Contenedor (Docker)

- Imagen base `python:3.11-slim`.
- Instala `requirements.txt` (FastAPI 0.115.12, Uvicorn 0.34.0).
- Ejecuta `seed_data.py` en build **si no existe** `db/pgn.db`.
- Expone el puerto **8080**; arranca `uvicorn api.main:app --host 0.0.0.0 --port 8080`.

### 7.3 Plataformas PaaS

| Plataforma | Archivo | Notas |
|------------|---------|-------|
| **Render** | `render.yaml` | Build: `pip install -r requirements.txt && python etl/seed_data.py`; start con `$PORT`. |
| **Fly.io** | `fly.toml` | App `pgn-bitacora`, región `iad`, puerto 8080, auto start/stop, VM 1 GB. |

### 7.4 Frontend como sitio estático

`frontend/` puede publicarse en GitHub Pages / Netlify sin servidor. En ese modo la infografía
usa los datos embebidos de respaldo (o se apunta `const API` a una API remota).

> **Persistencia:** al ejecutarse `seed_data.py` en build, la base de datos vive dentro del
> contenedor. Para conservar datos entre reinicios se recomienda **montar un volumen** o usar una
> base de datos externa. Ver [Riesgos y deuda técnica](#11-riesgos-y-deuda-técnica).

---

## 8. Vista de implementación (organización del código)

```
pgn-bitacora/
├── api/
│   └── main.py                 # FastAPI: endpoints REST + estáticos
├── db/
│   ├── schema.sql              # Esquema completo
│   ├── pgn.db                  # SQLite generado por el ETL
│   └── migrations/*.sql        # Migraciones incrementales
├── etl/
│   ├── seed_data.py            # Carga inicial embebida
│   ├── update_bitacora.py      # Carga por CSV
│   └── load_*.py               # Cargas por sección desde Excel
├── frontend/
│   ├── index.html              # Infografía standalone
│   ├── vendor/                 # Chart.js, Leaflet, fuentes, Font Awesome
│   └── data/*.geojson          # Geografía para el mapa
├── docs/                       # Documentación e informes
├── backend/                    # Esqueleto .NET 8 (exploratorio, no operativo)
├── Dockerfile · fly.toml · render.yaml · requirements.txt
└── README.md · CLAUDE.md
```

---

## 9. Decisiones de arquitectura (ADR)

| ID | Decisión | Motivación | Consecuencia |
|----|----------|-----------|--------------|
| ADR-1 | **SQLite** como motor de datos | Simplicidad, cero administración, portabilidad | No apto para escritura concurrente intensiva; ideal para carga batch + lectura. |
| ADR-2 | **Frontend standalone** con fallback embebido | Publicable sin servidor; resiliencia ante caída de API | Duplicación de datos (embebidos vs BD); riesgo de desincronización. |
| ADR-3 | **ETL desacoplado** de la API | Separar carga (batch) de servicio (runtime) | La actualización requiere ejecución manual + reinicio de API. |
| ADR-4 | **Modelo multi-bitácora** con `bitacora_id` | Comparar cortes históricos | Todas las consultas deben resolver la bitácora vigente. |
| ADR-5 | **Deflactación en runtime** (Sec 5) | Guardar datos crudos SIIF y calcular constantes al vuelo | Cálculo repetido por request; se evita almacenar valores derivados. |
| ADR-6 | **Dependencias auto-alojadas** (sin CDN) | Funcionamiento offline / redes restringidas de la entidad | Hay que versionar y actualizar `vendor/` manualmente. |

---

## 10. Atributos de calidad

- **Disponibilidad / resiliencia:** el frontend degrada con elegancia a datos embebidos si la API no responde.
- **Portabilidad:** stack liviano (Python + SQLite + HTML) desplegable en Docker, Render o Fly.io.
- **Mantenibilidad:** separación clara ETL / datos / API / presentación; endpoints agrupados por sección.
- **Usabilidad:** identidad visual institucional, navegación por secciones, modales de contexto, mapa interactivo.
- **Rendimiento:** consultas indexadas; volumen de datos moderado (BD ~1,2 MB).
- **Seguridad:** aplicación de solo lectura de datos públicos; sin autenticación (no maneja datos sensibles). CORS abierto.

---

## 11. Riesgos y deuda técnica

| Riesgo / deuda | Impacto | Mitigación sugerida |
|----------------|---------|--------------------|
| BD dentro del contenedor (sin volumen) | Pérdida de datos al reiniciar | Volumen persistente o BD externa. |
| Datos embebidos duplicados en el HTML | Desincronización con la BD | Documentar el proceso de regeneración; automatizar. |
| Carga ETL manual + reinicio | Error humano, indisponibilidad breve | Script orquestador / recarga sin downtime. |
| CORS totalmente abierto | Exposición innecesaria | Restringir orígenes en producción. |
| Dependencias `vendor/` sin gestión de versiones | Vulnerabilidades sin parchear | Registrar versiones y revisar periódicamente. |
| Backend `.NET` incompleto | Confusión sobre el backend vigente | Mantener nota explícita (hecho en §4.4) o retirar la carpeta. |

---

## 12. Glosario

| Término | Definición |
|---------|------------|
| **PGN** | Presupuesto General de la Nación. |
| **DNP** | Departamento Nacional de Planeación. |
| **DPIP** | Dirección de Programación de Inversiones Públicas. |
| **PND** | Plan Nacional de Desarrollo. |
| **SIIF** | Sistema Integrado de Información Financiera (Nación). |
| **SGP** | Sistema General de Participaciones. |
| **Bitácora** | Reporte periódico (corte) de seguimiento presupuestal. |
| **Vigencia** | Año fiscal. |
| **Vigencias futuras** | Autorizaciones de gasto que comprometen presupuesto de vigencias posteriores. |
| **mmm** | Miles de millones de pesos. |
| **Deflactor** | Factor para convertir valores corrientes a constantes (base 2026). |
| **ETL** | Extract, Transform, Load (extracción, transformación y carga de datos). |

---

_Documento vivo: actualícese ante cambios estructurales del sistema (nuevas secciones, cambio de
motor de datos, migración de backend, etc.)._
