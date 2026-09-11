# Manual Técnico — Plantilla

> **Instrucciones para el analista**
> Complete esta plantilla a partir del código fuente del proyecto **Bitácora PGN**.
> - Reemplace `⟨ ⟩` por contenido real; elimine las notas en _cursiva_ al finalizar.
> - Verifique cada afirmación contra el repositorio (`api/main.py`, `db/schema.sql`, `etl/`, `Dockerfile`, `fly.toml`, `render.yaml`, `requirements.txt`).
> - Este manual está dirigido a **personal técnico**: quien instala, despliega, mantiene o evoluciona el sistema.

---

## Portada / control del documento

| Campo | Valor |
|-------|-------|
| Proyecto | Bitácora PGN — Infografía Web de Inversión Pública (DNP/DPIP) |
| Documento | Manual Técnico |
| Versión | ⟨1.0⟩ |
| Fecha | ⟨AAAA-MM-DD⟩ |
| Autor | ⟨nombre del analista⟩ |
| Estado | ⟨Borrador / En revisión / Aprobado⟩ |

**Historial de cambios**

| Versión | Fecha | Autor | Descripción |
|---------|-------|-------|-------------|
| ⟨1.0⟩ | ⟨AAAA-MM-DD⟩ | ⟨⟩ | Versión inicial |

---

## 1. Introducción

### 1.1 Propósito del manual
_⟨Para qué sirve y a quién está dirigido.⟩_

### 1.2 Descripción general del sistema
_⟨Resumen funcional: infografía web de seguimiento del PGN, 8 secciones temáticas, multi-bitácora.⟩_

### 1.3 Alcance
_⟨Qué cubre y qué no cubre este manual.⟩_

### 1.4 Documentos relacionados
_⟨`ARQUITECTURA.md`, `README.md`, `docs/etl_uso.md`, Manual de Usuario, Especificación de Casos de Uso.⟩_

---

## 2. Arquitectura del sistema (resumen)

_⟨Resuma en media página la arquitectura de tres capas + ETL. Referencie `docs/ARQUITECTURA.md` para el detalle. Incluya el diagrama de capas.⟩_

| Capa | Tecnología | Ubicación en el repo |
|------|-----------|----------------------|
| Presentación | HTML/CSS/JS, Chart.js, Leaflet | `frontend/` |
| Aplicación/API | FastAPI + Uvicorn (Python) | `api/main.py` |
| Datos | SQLite | `db/pgn.db`, `db/schema.sql` |
| ETL | Python | `etl/` |

---

## 3. Requisitos del entorno

### 3.1 Software base

| Componente | Versión | Notas |
|-----------|---------|-------|
| Python | ⟨3.11⟩ | ⟨imagen base del Dockerfile⟩ |
| FastAPI | ⟨0.115.12⟩ | ⟨`requirements.txt`⟩ |
| Uvicorn | ⟨0.34.0⟩ | ⟨`requirements.txt`⟩ |
| openpyxl | ⟨—⟩ | ⟨requerido por los ETL de Excel⟩ |
| SQLite | ⟨embebido en Python⟩ | |
| Docker | ⟨opcional⟩ | ⟨despliegue en contenedor⟩ |

### 3.2 Hardware / recursos
_⟨CPU, RAM (p. ej. Fly.io usa VM de 1 GB), almacenamiento.⟩_

### 3.3 Dependencias del frontend (auto-alojadas)
_⟨`frontend/vendor/`: Chart.js, Leaflet, Nunito Sans, Font Awesome. Sin CDN.⟩_

---

## 4. Instalación y configuración

### 4.1 Obtener el código
```bash
⟨git clone …⟩
cd pgn-bitacora
```

### 4.2 Instalar dependencias
```bash
pip install -r requirements.txt
⟨pip install openpyxl   # si se usarán los ETL de Excel⟩
```

### 4.3 Inicializar la base de datos
```bash
python etl/seed_data.py        # crea db/pgn.db con la Bitácora 2 (2025-I)
```

### 4.4 Ejecutar en desarrollo
```bash
uvicorn api.main:app --reload --port 8000
# Infografía:  http://localhost:8000/
# API docs:    http://localhost:8000/docs
```

### 4.5 Variables de configuración
_⟨Documente parámetros configurables: puerto, `const API` en `frontend/index.html`, orígenes CORS, ruta de la BD, `$PORT` en PaaS.⟩_

| Parámetro | Ubicación | Valor por defecto | Descripción |
|-----------|-----------|-------------------|-------------|
| ⟨`API`⟩ | ⟨`frontend/index.html`⟩ | ⟨`/api`⟩ | ⟨URL base de la API⟩ |
| ⟨puerto⟩ | ⟨comando uvicorn⟩ | ⟨8000/8080⟩ | ⟨⟩ |

---

## 5. Estructura del proyecto

```
⟨árbol de directorios comentado — reutilice la §8 de ARQUITECTURA.md⟩
```

_⟨Explique brevemente la responsabilidad de cada carpeta/archivo clave.⟩_

---

## 6. Modelo de datos

### 6.1 Diagrama entidad-relación
_⟨Incluya el diagrama; centro en `metadatos_bitacora` y FK `bitacora_id`.⟩_

### 6.2 Diccionario de datos

> _Diligencie una tabla por cada tabla de `db/schema.sql`._

**Tabla: ⟨`nombre_tabla`⟩** — ⟨propósito⟩

| Columna | Tipo | Nulo | Restricción | Descripción |
|---------|------|------|-------------|-------------|
| ⟨`id`⟩ | ⟨INTEGER⟩ | ⟨No⟩ | ⟨PK⟩ | ⟨⟩ |
| ⟨`bitacora_id`⟩ | ⟨INTEGER⟩ | ⟨Sí⟩ | ⟨FK → metadatos_bitacora⟩ | ⟨corte al que pertenece⟩ |
| ⟨…⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ |

### 6.3 Convenciones de unidades
_⟨`_mmm` miles de millones, `_mm` millones, `_pct` porcentajes; vigencias futuras en corrientes deflactadas en runtime.⟩_

### 6.4 Índices y migraciones
_⟨Liste índices de `schema.sql` y describa el proceso de aplicar `db/migrations/*.sql`.⟩_

---

## 7. API REST

### 7.1 Convenciones generales
_⟨Base `/api`, formato JSON, parámetro común `bitacora_id`, resolución de bitácora vigente, CORS, helpers `get_db`/`rows_to_list`/`resolve_bitacora`.⟩_

### 7.2 Catálogo de endpoints

> _Diligencie una ficha por endpoint (o agrupe por sección). La fuente de verdad es OpenAPI en `/docs`._

**⟨`GET /api/…`⟩** — ⟨descripción⟩

| Aspecto | Detalle |
|---------|---------|
| Método / ruta | ⟨`GET /api/…`⟩ |
| Sección (tag) | ⟨Sec N⟩ |
| Función en código | ⟨`api/main.py:get_…`⟩ |
| Parámetros | ⟨`bitacora_id` (opt), `sector` (opt), …⟩ |
| Respuesta (ejemplo) | ```json\n⟨{ … }⟩\n``` |
| Tablas consultadas | ⟨⟩ |
| Reglas/observaciones | ⟨p. ej. deflactación, agrupaciones⟩ |

_⟨Repita para el resto. Como mínimo cubra: Metadatos, Sec 1–8 y Dashboard `/api/resumen`.⟩_

---

## 8. Componente ETL

### 8.1 Panorama de scripts
_⟨Reutilice la tabla de la §4.4 de ARQUITECTURA.md y `docs/etl_uso.md`.⟩_

| Script | Sección | Fuente | Tablas destino |
|--------|---------|--------|----------------|
| ⟨`load_vigencias_futuras.py`⟩ | ⟨5⟩ | ⟨Excel VF (`BASE_SIIF_2`, `TD BITACORA`)⟩ | ⟨`vigencias_futuras`, `deflactores_pib`⟩ |
| ⟨…⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ |

### 8.2 Procedimiento de actualización de datos (nueva bitácora)
```bash
⟨python etl/update_bitacora.py --numero 3 --periodo 2025-II --corte 2025-06-30 --notas "…"⟩
```
_⟨Detalle: preparar Excel/CSV, ejecutar ETL, verificar, reiniciar API. Incluya ubicación de fuentes:
`C:\ws\dnp\ws\BASES_BITACORA\{año}\{mes}\{N. SECCIÓN}\`.⟩_

### 8.3 Estructura de los archivos fuente (CSV/Excel)
_⟨Documente encabezados y hojas esperadas por cada carga; vea README.md y `docs/etl_uso.md`.⟩_

---

## 9. Frontend

### 9.1 Organización
_⟨`index.html` standalone; secciones `#hero`, `#sec1`–`#sec8`; sistema de diseño DNP 2026 (tokens CSS); tema conmutable `data-tema`.⟩_

### 9.2 Modo dual (API + fallback)
_⟨Explique la función `af(path, fallback)` y el objeto de datos embebidos.⟩_

### 9.3 Librerías y assets
_⟨Chart.js, Leaflet, GeoJSON (`frontend/data/`), fuentes, iconos.⟩_

### 9.4 Sistema de modales informativos
_⟨`openInfoModal` + objeto `infoTexts`; cómo agregar nuevos.⟩_

---

## 10. Despliegue

### 10.1 Docker
```bash
docker build -t pgn-bitacora .
docker run -p 8080:8080 pgn-bitacora
```
_⟨Explique que el Dockerfile ejecuta `seed_data.py` en build si no existe la BD.⟩_

### 10.2 Render
_⟨`render.yaml`: buildCommand, startCommand con `$PORT`.⟩_

### 10.3 Fly.io
_⟨`fly.toml`: app, región, puerto 8080, auto start/stop, VM.⟩_

### 10.4 Frontend estático
_⟨Publicación en GitHub Pages/Netlify; ajustar `const API`.⟩_

### 10.5 Persistencia de datos
_⟨Advertencia: la BD vive en el contenedor; usar volumen o BD externa para persistir.⟩_

---

## 11. Operación y mantenimiento

### 11.1 Respaldo y restauración
_⟨Copia de `db/pgn.db` (existen respaldos `*.bak_AAAAMMDD`); procedimiento de restauración.⟩_

### 11.2 Registro (logs) y monitoreo
_⟨Salida de Uvicorn; healthcheck; auto start/stop en Fly.io.⟩_

### 11.3 Actualización de dependencias
_⟨`requirements.txt` y `frontend/vendor/`.⟩_

### 11.4 Solución de problemas (troubleshooting)

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| ⟨La infografía muestra datos viejos⟩ | ⟨API no reiniciada tras ETL / fallback embebido⟩ | ⟨reiniciar API; verificar `const API`⟩ |
| ⟨Error 500 en un endpoint⟩ | ⟨BD sin la bitácora / esquema desactualizado⟩ | ⟨correr `seed_data.py` o migraciones⟩ |
| ⟨Mapa no carga⟩ | ⟨GeoJSON no servido en `/data`⟩ | ⟨verificar montaje estático⟩ |

---

## 12. Seguridad
_⟨Aplicación de solo lectura de datos públicos; sin autenticación; CORS abierto (restringir orígenes en producción); consideraciones de exposición.⟩_

---

## 13. Pruebas
_⟨Estrategia de pruebas: verificación de endpoints vía `/docs`, validación de cargas ETL, revisión visual del frontend. Documente casos y resultados si existen.⟩_

---

## 14. Anexos
_⟨Ejemplos de payloads, comandos frecuentes, esquema SQL completo, referencias.⟩_
