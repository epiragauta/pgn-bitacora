# Informe de actividades — Migración a .NET 8 / SQL Server

**Proyecto:** Bitácora de Inversión Pública — DNP / DPIP
**Periodo:** 15 de agosto de 2026
**Rama:** `migracion-dotnet-sqlserver` · **Versión resultante:** `v3.0.0`
**Estado:** completada y en producción en https://dnp-btcr.skaphe.com

---

## 1. Resumen ejecutivo

Se migró el backend de la Bitácora de Inversión Pública de **FastAPI sobre SQLite** a **.NET 8 sobre SQL Server**, sin modificar una sola línea del frontend.

El criterio que gobernó todo el trabajo fue la **paridad verificable**: cada cambio debía demostrarse equivalente al comportamiento anterior, no suponerse. Para eso se congeló la respuesta de las 322 rutas de la API original *antes* de tocar nada, y esa línea base se usó como vara de medida en cada fase.

| Resultado | |
|---|---|
| Rutas verificadas | 322 |
| Respuestas idénticas a la API anterior | **318** |
| Diferencias de claves, valores o estado HTTP | **0** |
| Diferencias de orden entre filas empatadas | 4 (documentadas y aceptadas) |
| Tablas migradas | 23 + 1 vista |
| Filas migradas | 5.320, con validación de conteo y suma por columna |
| Modificaciones al frontend | **ninguna** |

Se detectaron y corrigieron **cuatro defectos que habrían llegado a producción sin aviso visible**, detallados en §4.

---

## 2. Punto de partida

| Componente | Antes | Después |
|---|---|---|
| Base de datos | SQLite (`db/pgn.db`, 1,2 MB) | SQL Server 2022 (`dnp_dpip`) |
| API | FastAPI + Python, 949 líneas | .NET 8 Minimal API + Dapper |
| ETL | 11 scripts Python → SQLite | 10 scripts Python → SQL Server |
| Despliegue | Contenedor Python, Fly.io/Render | Contenedor .NET on-premise tras Caddy |
| Frontend | HTML autónomo con Chart.js y Leaflet | *sin cambios* |

**Deuda técnica encontrada al inicio:** `db/schema.sql` no reflejaba la base real —le faltaban las tablas de dos migraciones y todo el modelo `pgn_*`—, de modo que el esquema hubo que extraerlo de la base misma y no de su documentación.

---

## 3. Actividades por fase

### Fase 0 — Preparación y línea base

- Creación de la base `dnp_dpip` con collation `Modern_Spanish_CS_AS` y un login dedicado con permisos acotados.
- **Congelamiento de la línea base:** `tools/endpoints.py` enumera 322 rutas derivándolas de los datos reales (cada vigencia, región, sector, transformador y código DANE existente), y `tools/capture_baseline.py` guardó su respuesta. Resultado: 322/322 en HTTP 200.

> La primera pasada arrojó 6 respuestas vacías. La causa: cada bitácora usa distinta convención de nombres para los transformadores y el endpoint resuelve contra la más reciente. Se corrigió emparejando cada transformador con su bitácora; sin eso, esas 6 rutas habrían pasado todas las verificaciones posteriores sin comprobar nada.

### Fase 1 — Esquema SQL Server

DDL idempotente en `db/mssql/`: 23 tablas, 22 claves foráneas, 16 restricciones `UNIQUE`, 5 `CHECK`, 12 índices y la vista `pgn_vista_crosstab`. Se verificó re-ejecutando los tres scripts completos sin error ni duplicados.

### Fase 2 — Migración de datos

`etl/migrate_sqlite_to_mssql.py` copió 5.320 filas preservando los `id` originales mediante `IDENTITY_INSERT` — no son números decorativos, son referencias reales. Validación automática de conteo y suma por columna: **cero diferencias**.

### Fase 3 — Backend .NET

Los 30 endpoints portados, agrupados por sección del tablero. La lógica que no cabía en SQL se llevó a servicios C#: gráfico de vigencias futuras, matriz de sectores, resumen del tablero y resumen del SGP.

### Fase 4 — Verificación de paridad

`tools/compare_apis.py` recorre las 322 rutas y **clasifica las diferencias por tipo**, porque no todas pesan igual: un cambio en el conjunto de claves rompe el frontend en silencio, mientras que un orden distinto entre filas empatadas es inocuo.

### Fase 5 — ETL contra SQL Server

Dos módulos nuevos concentran lo que cambiaba de motor (`etl/db.py` y `etl/bases.py`), de modo que los cargadores conservaran intacta su lógica de lectura de Excel, que es donde vive el conocimiento del negocio.

Verificación: se cargaron los Excel en una base de pruebas y se contrastó contra la migrada. **21 de 21 tablas idénticas**, incluidas las sumas de todas las columnas numéricas.

### Fase 6 — Empaquetado y despliegue

Imagen multi-etapa, contenedor publicado **solo en loopback** y unido a la red del SQL Server para alcanzarlo por su alias interno. La suite de paridad se volvió a correr contra el contenedor, no contra el entorno de desarrollo.

### Fase 7 — Retiro de FastAPI

Última comparación en vivo entre ambas APIs minutos antes del corte: 318/322 idénticas, cero diferencias bloqueantes. Se retiraron `api/`, el Dockerfile de Python y las dependencias asociadas; SQLite pasó a `db/legacy/` como archivo histórico.

### Publicación

Bloque de Caddy aplicado, certificado de Let's Encrypt emitido automáticamente y la suite completa corrida **contra la URL pública** — no contra loopback —, lo que confirma que el proxy no altera cuerpos, cabeceras ni la codificación de las tildes en las rutas.

---

## 4. Defectos detectados y corregidos

Los cuatro comparten un rasgo: **ninguno producía un error visible**. Habrían llegado a producción como datos silenciosamente equivocados o pantallas en blanco.

### 4.1 Aritmética en `DECIMAL` en lugar de punto flotante

SQLite calcula en doble precisión. Al replicar las consultas con `DECIMAL`, el porcentaje del PIB de vigencias futuras daba **1,2367 donde el original daba 1,2368**.

**Corrección:** el almacenamiento sigue en `DECIMAL(18,6)`, pero toda expresión calculada se castea a `FLOAT`. Sin la línea base, esta diferencia de un dígito habría pasado inadvertida.

### 4.2 Los GeoJSON del mapa devolvían 404

El middleware de archivos estáticos de .NET solo sirve extensiones con tipo MIME conocido, y `.geojson` no está en su tabla; el equivalente de Python servía cualquier archivo. **El mapa de Colombia habría quedado en blanco sin un solo mensaje en consola.**

**Corrección:** registro explícito del tipo `application/geo+json`.

### 4.3 Riesgo de fusión de regiones por collation

Con una collation insensible a tildes, `PACÍFICO` y `PACIFICO` pasan a ser el mismo valor y las agrupaciones por región fusionarían filas. Se eligió `Modern_Spanish_CS_AS` y se verificó: `WHERE region = N'PACIFICO'` devuelve 0 filas frente a las 3 de `N'PACÍFICO'`.

### 4.4 División por cero

SQLite devuelve nulo; SQL Server lanza error y aborta la consulta. Se localizaron siete endpoints con denominadores sin proteger y se envolvieron en `NULLIF`.

### Además, en los datos de origen

- Una celda del Excel de sectores por región traía `Año = 1` en vez de `2026`. No habría fallado la carga: simplemente la región Andina habría perdido Transporte —su mayor sector, 6.408 mmm— del tablero. Se añadió validación de rango que aborta señalando la celda exacta.
- La hoja `TD BITACORA` contiene 51 claves sector-año duplicadas que el motor anterior descartaba en silencio. Se conserva el comportamiento, pero ahora queda registrado.

---

## 5. Decisiones de diseño relevantes

| Decisión | Motivo |
|---|---|
| **Los alias de columna del SQL son las claves del JSON** | El frontend lee claves exactas y, si falta una, cae a sus datos embebidos **sin mostrar error**. Devolver diccionarios desde Dapper hace imposible que un renombre se cuele |
| **Fechas formateadas en SQL** | .NET habría emitido `2026-03-31T00:00:00` y el frontend hace `corte_fecha.split('-')` |
| **Ordenamiento con collation binaria** | Reproduce el criterio de SQLite, donde los caracteres acentuados ordenan después de todo el ASCII |
| **Desempates explícitos** | Donde el original ordenaba por un campo con valores repetidos, su orden era arbitrario y no reproducible; se prefirió un orden estable entre ejecuciones |
| **Preservar la ortografía acentuada de las entidades** | Una entrega posterior del Excel traía 67 entidades sin tildes; el tablero conserva la grafía correcta sin revertir renombres institucionales legítimos |

---

## 6. Situación de los archivos fuente

Durante la fase 5 se constató que los libros Excel entregados eran **una revisión posterior** a la que originó los datos migrados. Dos cargadores quedaron bloqueados hasta que se regeneraron las hojas faltantes (`BASE_SIIF_2` y `sectores_por_region`), lo que el usuario resolvió en el transcurso del trabajo.

Se optó deliberadamente por **fallar con un mensaje explícito** en lugar de derivar los valores faltantes de columnas crudas: se comprobó que ninguna de ellas reproducía las cifras migradas, con una desviación mínima de 95.009 mmm sobre el total.

Persiste una diferencia legítima: la fuente aplica retroactivamente renombres institucionales, como `MINISTERIO DE CULTURA` → `MINISTERIO DE LAS CULTURAS, LAS ARTES Y LOS SABERES`. El tablero debe reflejarlos.

---

## 7. Entregables

| Entregable | Ubicación |
|---|---|
| Backend .NET 8 | `backend/` |
| Esquema SQL Server | `db/mssql/` |
| ETL contra SQL Server | `etl/` |
| Herramientas de verificación | `tools/` |
| Plan y bitácora técnica de la migración | `docs/PLAN_MIGRACION_DOTNET_SQLSERVER.md` |
| Arquitectura | `docs/ARQUITECTURA.md` |
| Manual técnico | `docs/MANUAL_TECNICO.md` |
| Manual de usuario del tablero | `docs/MANUAL_USUARIO.md` |
| Manual de operación | `docs/MANUAL_OPERACION.md` |

Trece commits, uno por fase, cada uno con su verificación registrada.

---

## 8. Pendientes

Ninguno bloqueante.

| Pendiente | Nota |
|---|---|
| Revisión visual del tablero en navegador | Todo lo que el navegador solicita está verificado como idéntico; falta la confirmación visual |
| Definir el destino de producción | Este servidor es de desarrollo y pruebas |
| Autenticación | La API es pública y de solo lectura por decisión explícita. Los endpoints ya están agrupados para que asegurarla sea un cambio de una línea |
| Ortografía de una entidad renombrada | Llega sin tilde desde la fuente; corregirlo allí es lo natural |
