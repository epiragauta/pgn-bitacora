# Plan de migración: FastAPI/SQLite → .NET 8 / SQL Server

**Proyecto:** Bitácora de Inversión Pública (DNP/DPIP)
**Fecha:** 2026-08-15
**Alcance:** backend y base de datos. El frontend (`frontend/index.html`) **no se modifica**.

---

## 1. Decisiones tomadas

| Decisión | Elección |
|---|---|
| ETL | Se mantiene en Python; solo cambia la capa de conexión (`sqlite3` → `pyodbc`) |
| Acceso a datos .NET | Dapper + SQL crudo (port ~1:1 de las consultas actuales) |
| Instancia SQL Server | Nueva BD `dnp_dpip` en el contenedor existente `umbraco-sqlserver` (mssql 2022, `127.0.0.1:1433`) |
| Nomenclatura | Prefijo `dnp_dpip` para **base de datos y login**. Los prefijos de tabla (`pgn_`, `sgp_`, `credito_`) se conservan como espacio de nombres por dominio; `sgr_` encaja sin cambios. La solución .NET conserva el nombre `PgnBitacora` |
| Transición | Convivencia temporal FastAPI + .NET con verificación automática de paridad JSON |
| Runtime | .NET 8 LTS, Minimal API (SDK 8.0.129 y 9.0.119 ya instalados en la máquina) |
| Tablas muertas | **No se migran** (ver §2.1) |
| Despliegue | **On-premise** en este servidor, detrás del Caddy existente. Se descartan Fly.io y Render (§6) |
| Autenticación | La API sigue siendo pública y de solo lectura. Se asegura en una fase posterior (§6.1) |
| Rama de trabajo | `migracion-dotnet-sqlserver` |

---

## 2. Situación actual (inventario)

| Componente | Estado |
|---|---|
| `api/main.py` | 949 líneas, FastAPI, **30 endpoints** en 8 secciones + metadatos + resumen |
| `db/pgn.db` | SQLite, 1,2 MB, **27 tablas + 1 vista**, ~5.400 filas |
| `etl/*.py` | 11 scripts (openpyxl → SQLite), ~2.500 líneas |
| `frontend/index.html` | 3.869 líneas, standalone, consume `/api` con fallback embebido |
| Despliegue | Docker (python:3.11-slim), `fly.toml`, `render.yaml` |

### 2.1 Deuda técnica detectada
- `db/schema.sql` **no refleja la BD real**: le faltan `dane_departamentos`, `regionalizacion`, `regionalizacion_sectores` (migraciones 003/004) y `pgn_concepto`/`pgn_ejecucion`/`pgn_vista_crosstab` (`schema_pgn.sql`). **La fuente de verdad es `db/pgn.db`.**
- Tablas muertas — **decidido: no se migran** (2026-08-15). Quedan fuera del DDL de la Fase 1 y de la carga de la Fase 2:

  | Tabla | Filas | Motivo |
  |---|---|---|
  | `legacy_regionalizacion_resumen` | 0 | vacía; reemplazada por `regionalizacion` (migración 003) |
  | `legacy_regionalizacion_detalle_2025` | 38 | sin endpoint que la consulte; reemplazada por `regionalizacion` |
  | `ejecucion_mensual_sectorial` | 0 | vacía; reemplazada por `ejecucion_sectorial_mensual` |
  | `evolucion_presupuestal` | 21 | reemplazada por `pgn_concepto` + `pgn_ejecucion` (`schema_pgn.sql`) |
  | `sqlite_sequence` | 24 | interna de SQLite; equivale a `IDENTITY` |

  El respaldo de `db/pgn.db` que se conserva en la Fase 7 mantiene la trazabilidad de estos datos.
  Efecto: se migran **23 tablas + 1 vista** (de 27). Ninguna de las descartadas es referenciada por los 30 endpoints — verificado sobre `api/main.py`.

---

## 3. Incompatibilidades SQLite → SQL Server (catálogo completo)

Esto es el corazón del riesgo de la migración. Cada ítem ya está localizado en el código.

### 3.1 Sintaxis de consulta

| # | Construcción SQLite | Ubicación | Traducción SQL Server |
|---|---|---|---|
| 1 | `strftime('%Y', corte_fecha)` | `main.py:43,61,71` (`resolve_bitacora`, `/api/bitacoras`) | `YEAR(corte_fecha)` |
| 2 | `ORDER BY x DESC NULLS LAST` | `main.py:439` (`/ejecucion/sectores/apropiacion`), `:666` (`/sectorial`) | `ORDER BY CASE WHEN x IS NULL THEN 1 ELSE 0 END, x DESC` |
| 3 | `ORDER BY ... COLLATE NOCASE` | `main.py:296` (`/regionalizacion`) | `COLLATE Modern_Spanish_CI_AI` |
| 4 | `WITH RECURSIVE arbol AS (...)` | `main.py:212` (`/evolucion/drilldown`) | Quitar `RECURSIVE`; añadir `OPTION (MAXRECURSION 10)` |
| 5 | `GROUP BY c.id` con columnas no agregadas | vista `pgn_vista_crosstab` | Listar todas las columnas en `GROUP BY` |
| 6 | `ORDER BY` dentro de un `CREATE VIEW` | vista `pgn_vista_crosstab` | Eliminarlo (el endpoint ya ordena por `orden`) |

### 3.2 División por cero — **el riesgo silencioso más importante**

SQLite devuelve `NULL` al dividir por cero; **SQL Server lanza el error 8134 y aborta la consulta**. Endpoints afectados:

| Endpoint | Denominador a proteger |
|---|---|
| `/api/evolucion/composicion` | `total.valor` |
| `/api/evolucion/tasa_ejecucion` | `v.valor` |
| `/api/evolucion/inversion_historica` | `v.valor`, `tot.valor` |
| `/api/ejecucion` | `eh.vigente_mmm` (3 divisiones) + 2 subconsultas |
| `/api/vigencias_futuras/totales` y `/chart` | `d.deflactor`, `d.pib_constante_mmm` |
| `/api/credito/sectores`, `/api/credito/resumen` | `SUM(monto_usd)` |
| `/api/resumen` | `d.deflactor` |

**Regla:** envolver **todo** denominador en `NULLIF(expr, 0)`. `/api/regionalizacion/historico` ya lo hace y sirve de patrón.

### 3.3 Tipos de datos

| SQLite | SQL Server | Nota |
|---|---|---|
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `INT IDENTITY(1,1) PRIMARY KEY` | Requiere `IDENTITY_INSERT` en la carga inicial |
| `TEXT` | `NVARCHAR(n)` | **Obligatorio `N`**: hay tildes en datos y claves (`ORINOQUÍA`, `PACÍFICO`, `Bogotá, D.C.`, `DEFENSA Y POLICÍA`) |
| `REAL` | `DECIMAL(18,6)` | Ver §3.5 |
| `BOOLEAN` | `BIT` | `es_total_region`, `es_total` |
| `DATE` / `DATETIME` | `DATE` / `DATETIME2(0)` | |
| `datetime('now')` | `SYSUTCDATETIME()` | default de `fecha_carga` |
| `CHECK(x IN (...))` | igual | compatible |

### 3.4 Collation — decisión crítica

SQLite compara texto de forma **binaria** (sensible a mayúsculas y tildes). Si la BD se crea con una collation `CI_AI`, `'PACÍFICO'` y `'PACIFICO'` pasarían a ser el mismo valor, lo que **fusionaría filas en los `GROUP BY` por región/sector/entidad y rompería restricciones `UNIQUE`** que hoy conviven.

**Decisión:** crear la BD con `Modern_Spanish_CS_AS` (case- y accent-sensitive, replica el comportamiento actual) y aplicar `COLLATE Modern_Spanish_CI_AI` **solo** en el `ORDER BY` de `/api/regionalizacion`, que es el único punto donde se quiere insensibilidad.

### 3.5 Precisión numérica y `ROUND`

**Corregido durante la Fase 3.** La suposición inicial —almacenar y calcular en `DECIMAL` para tener determinismo— resultó equivocada para la *paridad*: SQLite hace toda la aritmética en punto flotante de doble precisión, y `DECIMAL` da un resultado distinto en el último decimal por las reglas de escala de la división en SQL Server.

Caso real detectado en `/api/vigencias_futuras/totales`: `pct_pib` daba **1.2367** en `DECIMAL` frente al **1.2368** del original.

Regla definitiva, en dos niveles:

| Nivel | Tipo | Motivo |
|---|---|---|
| **Almacenamiento** | `DECIMAL(18,6)` | Valores exactos, sin sorpresas binarias en la carga |
| **Aritmética** | `CAST(x AS FLOAT)` | Reproduce el doble de SQLite en divisiones, sumas y `ROUND` |

Aplicado a toda expresión calculada: porcentajes, `SUM()` que se redondean y conversiones por deflactor. En C#, los servicios que replican cálculos de Python (`VigenciasFuturasChart`) acumulan en `double` por la misma razón. `Math.Round` de .NET y `round()` de Python usan ambos redondeo al par más cercano, así que no hace falta ajuste adicional.

### 3.9 Orden entre filas empatadas — divergencia aceptada

Varias consultas del original ordenan por un campo que tiene valores repetidos (`ORDER BY monto_usd DESC`) sin criterio de desempate. En ese caso **el orden de las filas empatadas es arbitrario y depende del motor**: se verificó que SQLite devuelve `Planeación` antes que `Organos de Control` con idéntico `monto_usd`, orden que no corresponde ni al `id` de inserción ni al alfabético, es decir, no es reproducible por ninguna regla.

Decisión: el backend .NET añade un **desempate explícito por la clave natural** (sector, entidad, nombre o componente, con `COLLATE Latin1_General_BIN2`). El resultado es estrictamente mejor que el original —estable entre ejecuciones y entre recargas del ETL— pero puede diferir del orden histórico en filas cuyo valor de ordenamiento es idéntico.

El comparador de la Fase 4 debe **clasificar aparte** este caso: si las dos respuestas contienen exactamente el mismo conjunto de filas y solo cambia la secuencia, es una diferencia de orden, no de datos.

### 3.6 Restricciones `UNIQUE` con columnas nulables

SQLite considera cada `NULL` distinto dentro de un `UNIQUE` (permite N filas); SQL Server los considera iguales (permite **una** sola).

- La única restricción realmente afectada era `evolucion_presupuestal UNIQUE(bitacora_id, vigencia, rubro, sub_rubro)` con `sub_rubro` nulable — **esa tabla queda descartada** (§2.1), así que el problema desaparece.
- `bitacora_id` está declarado nulable en todas las tablas, pero **no hay ni una fila con `NULL`** (verificado sobre `db/pgn.db`). En el DDL de SQL Server se declara `NOT NULL`, lo que elimina el riesgo y refuerza la integridad.

### 3.7 Contrato JSON con el frontend

El frontend lee claves **snake_case exactas** (`inversion_vigente_mmm`, `pct_c_av`, `total_constante_mmm`, `codigo_dane`…). Reglas para el backend .NET:

1. Devolver los resultados de Dapper como `IEnumerable<IDictionary<string, object>>` (`dynamic` / `DapperRow`), de modo que **los nombres de columna del SQL sean literalmente las claves JSON**. Así no hay que declarar 30 DTOs ni arriesgar renombres.
2. `JsonSerializerOptions`: **sin** `PropertyNamingPolicy` y **sin** `DefaultIgnoreCondition = WhenWritingNull` — FastAPI emite `null` explícito y el frontend distingue `null` de ausente (ej. `res.inv_pct_pib?…:…`).
3. `codigo_dane` es **texto con cero a la izquierda** (`'05'`, `'08'`): mantener `string` en la ruta y en el modelo, nunca `int`.
4. Rutas con parámetros acentuados/con espacios (`/transformaciones/{transformador}/componentes`) — ASP.NET Core las decodifica igual que Starlette.

### 3.8 Infraestructura del host

| FastAPI | ASP.NET Core |
|---|---|
| `app.mount("/data", StaticFiles(...))` | `UseStaticFiles` con `RequestPath="/data"` y `PhysicalFileProvider(data/)` |
| `app.mount("/", StaticFiles(html=True))` | `UseDefaultFiles()` + `UseStaticFiles()` sobre `frontend/`, **después** de mapear `/api` |
| `CORSMiddleware(origins=*, methods=GET)` | `AddCors` + política `AllowAnyOrigin().WithMethods("GET")` |
| `/docs` (Swagger automático) | Swashbuckle → `/swagger` |

---

## 4. Arquitectura destino

```
backend/
  PgnBitacora.sln
  src/PgnBitacora.Api/
    Program.cs                      # DI, CORS, static files, swagger, health
    Endpoints/
      MetadatosEndpoints.cs         # /api/bitacoras*
      TransformacionesEndpoints.cs  # Sec 1  (2 endpoints)
      EvolucionEndpoints.cs         # Sec 2  (6 endpoints)
      RegionalizacionEndpoints.cs   # Sec 3  (5 endpoints)
      EjecucionEndpoints.cs         # Sec 4  (6 endpoints)
      VigenciasFuturasEndpoints.cs  # Sec 5  (3 endpoints)
      SectorialEndpoints.cs         # Sec 6  (3 endpoints)
      CreditoEndpoints.cs           # Sec 7  (6 endpoints)
      SgpEndpoints.cs               # Sec 8  (3 endpoints)
      ResumenEndpoints.cs           # /api/resumen
    Data/
      ISqlConnectionFactory.cs      # SqlConnection por request
      BitacoraResolver.cs           # port de resolve_bitacora()
      Sql/                          # consultas como const string, una por endpoint
    Services/                       # los 4 endpoints con lógica fuera de SQL
      VigenciasFuturasChartService.cs   # agrupación en 6 series + %PIB
      MatrizSectoresService.cs          # pivot sector × vigencia
      ResumenService.cs                 # KPIs + fallback sin ejecucion_historica
      SgpResumenService.cs              # crecimiento y acumulado
    appsettings.json / appsettings.Development.json
db/mssql/
  001_schema.sql                    # DDL completo (tablas, PK/FK, índices)
  002_views.sql                     # pgn_vista_crosstab corregida
  003_seed_dane.sql                 # catálogo de 33 departamentos
etl/
  db.py                             # NUEVO: get_conn() pyodbc + helpers upsert/merge
  migrate_sqlite_to_mssql.py        # NUEVO: carga inicial de datos
tools/
  compare_apis.py                   # NUEVO: verificación de paridad JSON
  baseline/                         # snapshots JSON de la API Python
```

**Paquetes:** `Microsoft.Data.SqlClient`, `Dapper`, `Swashbuckle.AspNetCore`, `Microsoft.AspNetCore.Diagnostics.HealthChecks`.

**Conexión:** `ConnectionStrings:DnpDpip` vía variable de entorno `ConnectionStrings__DnpDpip` (dev: `dotnet user-secrets`). **Nunca** credenciales en el repositorio.

---

## 5. Fases de ejecución

### Fase 0 — Preparación y línea base — ✅ **COMPLETADA** (2026-08-15)
1. ~~Verificar conectividad al contenedor `umbraco-sqlserver`~~ → **hecho (2026-08-15)**: SQL Server 2022 CU22 (16.0.4225.2) Developer Edition sobre Ubuntu 22.04; collation de servidor `SQL_Latin1_General_CP1_CI_AS`; única base existente `sbn-ecp` (Umbraco).
2. Crear BD y login dedicado (la collation de base anula la del servidor, sin efecto sobre Umbraco):
   ```sql
   CREATE DATABASE dnp_dpip COLLATE Modern_Spanish_CS_AS;
   CREATE LOGIN dnp_dpip_app WITH PASSWORD = '<la define el usuario>';
   -- en dnp_dpip: db_datareader + db_datawriter + db_ddladmin (el ETL crea/modifica objetos)
   ```
3. **Línea base capturada**: `tools/endpoints.py` enumera **322 rutas** derivadas de los datos reales (cada vigencia, región, sector, transformador, concepto y código DANE presentes en la BD) y `tools/capture_baseline.py` congela su respuesta en `tools/baseline/` (2,3 MB). Resultado: **322/322 con HTTP 200, ninguna respuesta vacía.**
4. Esquema real extraído de `db/pgn.db` (no de `schema.sql`, desactualizado — §2.1).

**Resultados verificados:**

| Elemento | Estado |
|---|---|
| BD `dnp_dpip` | creada, `COLLATE Modern_Spanish_CS_AS` |
| Login `dnp_dpip_app` | creado, probado de extremo a extremo (lectura OK, sin acceso a `sbn-ecp`) |
| Roles | `db_datareader`, `db_datawriter`, `db_ddladmin` sobre `dnp_dpip` |
| Línea base | 322 rutas, 322 en HTTP 200, 0 vacías |
| Entorno Python | `.venv-baseline/` (ignorado por git) con `fastapi 0.115.12` |

> **Cobertura:** la primera pasada arrojó 6 respuestas vacías en `/api/transformaciones/{t}/componentes`. Causa: cada bitácora usa distinta convención de nombres (`CONVERGENCIA REGIONAL` en la 1, `5. CONVERGENCIA REGIONAL` en la 2) y el endpoint resuelve contra la bitácora más reciente. Se corrigió emparejando cada transformador con su `bitacora_id`; sin eso, esas 6 rutas no habrían verificado nada en la Fase 4.

### Fase 1 — Esquema SQL Server — ✅ **COMPLETADA** (2026-08-15)
- Escribir `db/mssql/001_schema.sql` con las **23 tablas vivas** (§2.1), aplicando §3.3, §3.4 y §3.6.
- FKs explícitas a `metadatos_bitacora(id)`, `pgn_concepto(id)`, `dane_departamentos(codigo)`.
- Índices equivalentes (normalizando `idx_vigencias_futuras_año` → `_anio`).
- `002_views.sql` con `pgn_vista_crosstab` corregida (§3.1 ítems 5 y 6).

**Criterio de aceptación — cumplido.** Los tres scripts corrieron sin error y se re-ejecutaron completos una segunda vez sin fallos ni duplicados (idempotencia verificada).

**Objetos creados en `dnp_dpip`:**

| Objeto | Cantidad |
|---|---|
| Tablas | 23 |
| Vistas | 1 (`pgn_vista_crosstab`) |
| Claves foráneas | 22 |
| Restricciones `UNIQUE` | 16 |
| Restricciones `CHECK` | 5 |
| Índices propios | 12 |
| Filas sembradas | 33 (`dane_departamentos`) |

**Comprobaciones adicionales:**
- Collation efectiva a nivel de columna: `Modern_Spanish_CS_AS`.
- Sensibilidad a tildes activa: `WHERE region = N'PACIFICO'` devuelve **0 filas** frente a las 3 de `N'PACÍFICO'` — es el comportamiento que replica a SQLite y evita la fusión silenciosa de regiones descrita en §3.4.
- La vista compila y responde (0 filas, con las tablas aún vacías).

> **Hallazgo:** `pgn_concepto.padre_id` se autorreferencia con `ON DELETE SET NULL` en SQLite. SQL Server prohíbe acciones en cascada sobre una FK que apunta a su propia tabla (error 1785), así que se degradó a `NO ACTION`, documentado en el propio DDL. No afecta a la aplicación: no hay borrados de conceptos en el flujo actual.

### Fase 2 — Migración de datos — ✅ **COMPLETADA** (2026-08-15)
- `etl/migrate_sqlite_to_mssql.py`: recorre tabla por tabla en orden de dependencia FK, con `SET IDENTITY_INSERT ON` para **preservar los `id` originales** (crítico: `pgn_ejecucion.concepto_id` y todos los `bitacora_id` son referencias por id).
- Validación automática: conteo de filas por tabla + suma de cada columna numérica, SQLite vs SQL Server.

**Resultado: 5.320 filas en 22 tablas, sin una sola diferencia.**

| Comprobación | Resultado |
|---|---|
| Conteos por tabla | 22/22 iguales |
| Sumas por columna numérica | todas dentro de 1e-6 |
| `id` preservados (`max(id)`) | iguales en las 5 tablas verificadas, incluida `ejecucion_sectorial_entidades` (3862) |
| Integridad referencial | 0 huérfanos en `pgn_ejecucion`; 0 filas de `regionalizacion` sin DANE |
| Tildes | `ORINOQUÍA`, `DEFENSA Y POLICÍA` y demás intactos |
| Vista | `pgn_vista_crosstab` devuelve las 28 filas; `Total PGN` 2026 = 547.017,088 |

Conexión desde Python vía **pyodbc + ODBC Driver 18**, ya instalado en el servidor.

**Criterio de aceptación:** los 22 conteos de tabla iguales y todas las sumas coincidiendo dentro de 1e-6 (23 tablas menos `dane_departamentos`, que la siembra `003_seed_dane.sql`).

### Fase 3 — Backend .NET — ✅ **COMPLETADA** (2026-08-15)
- Proyecto .NET 8 Minimal API en `backend/`, con Dapper, Microsoft.Data.SqlClient y Swashbuckle.
- Los 30 endpoints portados y agrupados por sección, aplicando el catálogo §3.
- Lógica que vivía en Python, portada a servicios C#: `VigenciasFuturasChart`, `MatrizSectores`, `Resumen` (con el respaldo para cuando falta `ejecucion_historica`) y `SgpResumen`.
- Sirve en el puerto 5080, en paralelo con FastAPI (8000).

**Criterio de aceptación — superado.** No solo responden las 322 rutas: la comparación completa contra la línea base ya arroja paridad casi total.

| Resultado sobre las 322 rutas | |
|---|---|
| HTTP 200 | **322/322** |
| Respuesta idéntica a la línea base | **318** |
| Diferencia solo de orden entre filas empatadas (§3.9) | 4 (`/api/credito`, `?fuente=BID`, `?sector=Planeación`, `/api/credito/sectores`) |
| **Diferencia de valor** | **0** |

**Decisiones de diseño relevantes:**

1. **El SQL es el contrato JSON.** Dapper devuelve diccionarios y los alias de columna se convierten literalmente en claves del JSON. Evita declarar 30 DTOs y elimina la clase de error más peligrosa: un renombre accidental haría que el frontend cayera en silencio a sus datos embebidos, sin error visible.
2. **Fechas formateadas en SQL** (`CONVERT(char(10), …, 23)` y `CONVERT(char(19), …, 120)`): .NET habría serializado `DateTime` como `2026-03-31T00:00:00`, y el frontend hace `corte_fecha.split('-')`.
3. **Conversor `decimal` a medida** que recorta ceros de relleno, para que `547017.088000` se emita como `547017.088`.
4. `GROUP BY` completos donde SQLite permitía columnas sin agregar (`/regionalizacion/historico`, `/vigencias_futuras/totales`). Verificado que no parten filas: cero grupos `(vigencia, region)` con más de un `tipo`.

### Fase 4 — Verificación de paridad — ✅ **COMPLETADA** (2026-08-15)

`tools/compare_apis.py` recorre las 322 rutas y **clasifica cada diferencia por tipo**, porque mezclarlas oculta las que importan:

| Tipo | Significado | Bloquea |
|---|---|---|
| `claves` | Cambió el conjunto de campos del JSON | Sí — el frontend cae en silencio a sus datos embebidos |
| `valores` | Mismas claves, distinto dato | Sí — error de traducción de SQL |
| `estado` | Códigos HTTP distintos | Sí |
| `orden` | Mismas filas, distinta secuencia | No — empates sin desempate en el original (§3.9) |

Dos modos: contra la API Python en vivo, o contra la línea base congelada (`--contra-linea-base`), que no requiere levantar FastAPI.

**Resultado — criterio de aceptación cumplido:**

| | |
|---|---|
| Rutas idénticas | **318 / 322** |
| Diferencias de **claves** | **0** |
| Diferencias de **valores** | **0** |
| Diferencias de **estado HTTP** | **0** |
| Diferencias solo de orden | 4 (`/api/credito` y variantes, por empate en `monto_usd`) |

#### Recursos estáticos

Se compararon byte a byte (SHA-256) los 8 recursos que `index.html` referencia y los 13 de segundo nivel dentro de los CSS. **Todos se sirven igual en ambos backends.**

> **Fallo encontrado y corregido:** `data/dptos.geojson` y `data/regiones.geojson` respondían **404 en .NET**. `StaticFileMiddleware` solo sirve extensiones con MIME conocido y `.geojson` no está en su tabla, mientras que `StaticFiles` de FastAPI sirve cualquier archivo. El mapa Leaflet habría quedado en blanco **sin ningún error en consola**. Se registró el tipo `application/geo+json` y se activó `ServeUnknownFileTypes` para replicar la permisividad del original y no volver a perder un recurso en silencio.

> **Nota, sin relación con la migración:** seis variantes de FontAwesome (`fa-brands`, `fa-regular`, `fa-v4compatibility`) dan 404 **en ambos backends** — nunca se vendorizaron en el repositorio; solo existe `fa-solid-900`. El comportamiento es idéntico al actual, así que no es una regresión, pero conviene saberlo si alguna vez se usa un icono de esas familias.

#### Pendiente: revisión visual

La comprobación automatizada en navegador no fue posible en esta sesión (extensión de Chrome no disponible). **Queda por hacer manualmente**: abrir `http://127.0.0.1:5080/` y recorrer las 8 secciones, el mapa Leaflet, los modales de información y el selector de bitácoras. Todo lo que el navegador solicita —API y estáticos— ya está verificado como idéntico, así que es una confirmación visual, no una búsqueda de fallos.

### Fase 5 — ETL contra SQL Server — ✅ **COMPLETADA** (2026-08-15), con un cargador bloqueado por su archivo fuente

Dos módulos nuevos concentran todo lo que cambiaba de motor, para que los cargadores conserven su lógica de lectura de Excel, que es donde vive el conocimiento del negocio:

- **`etl/db.py`** — conexión y equivalencias:

  | SQLite | Reemplazo | Por qué |
  |---|---|---|
  | `INSERT OR REPLACE` | `conn.upsert(...)` | No existe en SQL Server |
  | `cur.lastrowid` | `conn.insertar_devolviendo_id(...)` | `SCOPE_IDENTITY()` está acotado al **lote**, no a la sesión: en un `execute` posterior devuelve NULL |
  | `DROP TABLE` + `CREATE` | `conn.vaciar_bitacora(...)` | El esquema es de `db/mssql/`; borrar la tabla rompería las FK y la vista |
  | `PRAGMA foreign_keys` | (nada) | Las FK están siempre activas |
  | `:parametro` | `?` | pyodbc solo admite posicionales |
  | `row["col"]` | `row[0]` | Las filas de pyodbc no se indexan por nombre |

- **`etl/bases.py`** — localiza los Excel: variable `BASES_BITACORA` → `data/BASES_BITACORA/` → rutas históricas de Windows. Busca por patrón dentro de cada carpeta de sección, porque los nombres traen fechas y sufijos que cambian cada corte. **Elimina las rutas absolutas de Windows** que impedían ejecutar los ETL fuera del equipo original.

#### Verificación: el ETL reproduce la base migrada

Se cargaron los Excel en una base `dnp_dpip_pruebas` y se contrastó contra `dnp_dpip` con `tools/compare_bd.py`, que compara filas y suma de cada columna numérica por bitácora.

**Resultado: 20 de 21 tablas idénticas**, incluidas todas las sumas. La única restante es la del cargador que sigue bloqueado (ver abajo).

| Tabla | Migrado | ETL |
|---|---|---|
| `ejecucion_sectorial_entidades` | 1.455 | 1.455 ✅ |
| `apropiacion_por_sector` y las tres `*_pct_por_sector` | 273 c/u | 273 c/u ✅ |
| `regionalizacion` | 175 | 175 ✅ |
| `pgn_ejecucion` / `pgn_concepto` | 560 / 28 | 560 / 28 ✅ |
| `sgp_historico_componentes` | 95 | 95 ✅ |
| `credito_*` | 17 / 18 / 4 | 17 / 18 / 4 ✅ |
| `vigencias_futuras` | 193 | 193 ✅ |
| `deflactores_pib` | 30 | 30 ✅ |
| `regionalizacion_sectores` | 135 | **0** ⛔ |

#### ✅ Sección 5 validada (2026-08-15, tras regenerar `BASE_SIIF_2`)

El usuario regeneró la hoja `BASE_SIIF_2` en `5. VIGENCIAS FUTURAS/20260513 Nueva Base VF - Validada - Revisión Analistas.xlsx`, con la columna calculada `Valor_VF_Final (Actual)`. La fuente quedó validada en tres niveles:

| Nivel | Resultado |
|---|---|
| Lectura | 1.974 filas → **29 sectores × 30 años**, exactamente la forma esperada |
| Fila a fila | 193 claves `(año, sector)`: **0 faltantes, 0 sobrantes, 0 valores distintos** frente a lo migrado |
| Deflactores | 30 años, **0 diferencias** en deflactor y PIB |
| Extremo a extremo | `/api/vigencias_futuras`, `/totales` y `/chart` **idénticos a la línea base** sirviendo desde la base cargada por el ETL |

Un detalle que no estorbó: la columna viene con un espacio final (`'Valor_VF_Final (Actual) '`), que el cargador ya contemplaba.

#### ⛔ Un cargador aún bloqueado por su archivo fuente

`load_sectores_region.py` necesita la hoja **`sectores_por_region`** (tabla ya consolidada: región, sector, apropiación, compromisos, obligaciones, pagos, vigencia) en `3. REGIONALIZACIÓN/Consolidado Reg-Ejec-Marzo-2022-2026vf.xlsx`. El libro solo trae `Regionalizacion Mar-2022-2026`, y el archivo hermano de gráficas trae hojas por región sin consolidar. Consolidarlas aquí exigiría reimplementar un criterio de agregación no documentado, así que el cargador falla con un mensaje explícito en vez de publicar cifras dudosas. Afecta a `regionalizacion_sectores` (135 filas).

**Qué hace falta:** la versión del libro que incluya esa hoja, o la definición de cómo se consolida.

#### Mejoras de robustez aplicadas de paso

- `load_vigencias_futuras.py` acepta la hoja base bajo cualquiera de sus nombres conocidos y **localiza la fila de encabezados por contenido**, en vez de asumir que es la primera (la entrega de marzo trae una fila en blanco arriba).
- `load_ejecucion_sectorial.py` ya no parchea el esquema con `ALTER TABLE`: **verifica** contra `INFORMATION_SCHEMA` y falla si falta una columna. Que el cargador repare la base era encubrir un error de despliegue.
- `conn.upsert()` **avisa** cuando el origen trae claves repetidas. SQLite las resolvía en silencio quedándose con la última; ahora se conserva el mismo comportamiento pero queda registrado (la hoja `TD BITACORA` trae 51 duplicados de sector-año).

#### Scripts retirados o recortados

- **`etl/seed_data.py` eliminado**: sembraba la bitácora 2025-I, que ya está migrada, e insertaba en dos tablas descartadas (`evolucion_presupuestal`, `regionalizacion_detalle_2025`).
- **`etl/update_bitacora.py`**: se le quitaron los cargadores de regionalización y vigencias futuras. Escribían en `regionalizacion_detalle_2025` y en las columnas `valor_mmm_ctes` / `pct_pib` — **ya estaba roto contra el propio SQLite**, no por la migración. Conserva transformaciones, ejecución histórica, apropiación sectorial y ejecución sectorial.

#### Orden de ejecución

```bash
export DNP_DPIP_CONN="DRIVER={ODBC Driver 18 for SQL Server};SERVER=127.0.0.1,1433;DATABASE=dnp_dpip;UID=dnp_dpip_app;PWD=...;TrustServerCertificate=yes"

python etl/load_bitacora_excel.py --numero 3 --periodo 2026-I --corte 2026-03-31   # crea la bitácora
python etl/importar_pgn.py                 # Sec 2
python etl/load_regionalizacion.py         # Sec 3
python etl/load_sectores_region.py         # Sec 3 (requiere la hoja consolidada)
python etl/load_ejecucion_sectorial.py     # Sec 4 y 6
python etl/load_vigencias_futuras.py       # Sec 5 — debe ir DESPUÉS del primero
python etl/load_credito.py                 # Sec 7
python etl/load_sgp.py && python etl/load_sgp_componentes.py   # Sec 8
```

`load_bitacora_excel.py` va primero porque crea la bitácora que los demás resuelven. `load_vigencias_futuras.py` va después porque ambos escriben `vigencias_futuras` y el dedicado es el autoritativo: cubre 2025-2054 con 29 sectores, frente al pase parcial de `TD BITACORA` (2026-2040, 38 sectores) que reemplaza.

### Fase 6 — Empaquetado y despliegue on-premise — ✅ **COMPLETADA** (2026-08-15)

**Infraestructura verificada en el servidor (2026-08-15):**

| Elemento | Estado |
|---|---|
| Proxy inverso | **Caddy** (servicio del host, puertos 80/443, admin API en `127.0.0.1:2019`) |
| Patrón de `/etc/caddy/Caddyfile` | `subdominio.skaphe.com { reverse_proxy localhost:<puerto> }` — hoy `sbn-ecp` (3000) y `vault` (8181) |
| Red del SQL Server | `sbn-ecp_umbraco-network` (bridge), contenedor en `172.19.0.3` |
| Puertos ocupados | 22, 80, 443, 3000, 3002, 3027, 5173, 8080, 8443, 1433, 8181 |

**Trabajo:**
1. `Dockerfile` multi-stage (`sdk:8.0` → `aspnet:8.0`), copiando `frontend/` y `data/` al contenedor. TLS lo termina Caddy, así que el contenedor sirve HTTP plano.
2. `docker-compose.yml` que une el contenedor a la red **externa** `sbn-ecp_umbraco-network`, de modo que llegue al SQL Server por nombre de servicio en lugar de exponer el 1433. Publicar la API solo en loopback (`127.0.0.1:5080:8080`) — Caddy es el único que debe alcanzarla desde fuera.
3. Cadena de conexión vía variable de entorno / `env_file` fuera del repositorio (`.env` en `.gitignore`).
4. Añadir el bloque al `Caddyfile` siguiendo el patrón existente:
   ```
   bitacora.skaphe.com {
         reverse_proxy localhost:5080
     }
   ```
   *(subdominio a confirmar con quien administre el DNS)*
5. **Eliminar** `fly.toml` y `render.yaml`; ambos asumen Python + SQLite y ya no aplican. *(Nota: `fly.toml` declara `app = 'pgn-bitacora'` mientras `CLAUDE.md` documenta `app-old-dream-8565` — la inconsistencia se resuelve al retirarlos.)*
6. Reinicio automático: `restart: unless-stopped` en compose.
7. Actualizar `README.md` y `CLAUDE.md` (secciones de despliegue, comandos y arquitectura).

**Criterio de aceptación — cumplido**, salvo la publicación por Caddy, que depende del subdominio (ver más abajo).

| Comprobación | Resultado |
|---|---|
| `docker compose up -d --build` | contenedor `Up (healthy)` |
| Raíz, `/api/resumen`, `/data/dptos.geojson`, `/swagger` | 200 en los cuatro |
| Conexión a SQL Server por alias `sqlserver` | correcta, sin usar el 1433 publicado |
| **Paridad completa desde el contenedor** | **318/322 idénticas, 0 diferencias de claves, valores o estado** |
| Estáticos servidos desde la imagen | 8/8 con SHA-256 idéntico al original |
| `docker compose restart` | vuelve a `healthy` en ~12 s |

La suite de paridad se volvió a correr **contra el contenedor**, no contra el `dotnet run` de desarrollo: confirma que la imagen resuelve bien las rutas de `frontend/` y `data/`, y que la globalización dentro del contenedor maneja las tildes igual (algo que `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT` habría roto en silencio).

**Archivos añadidos:** `backend/Dockerfile`, `docker-compose.yml`, `.env.example`, `deploy/Caddyfile.snippet`.
**Archivos eliminados:** `fly.toml`, `render.yaml`.

#### Publicación por Caddy — pendiente de una decisión, no de trabajo

El bloque está escrito en `deploy/Caddyfile.snippet` pero **no se aplicó**, por dos razones: falta definir el subdominio con quien administre el DNS (pregunta abierta 7) y editar `/etc/caddy/Caddyfile` expone el servicio a internet, que es un cambio de cara al exterior. Cuando el nombre esté decidido:

```bash
sudo tee -a /etc/caddy/Caddyfile < deploy/Caddyfile.snippet
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

#### 6.1 Notas

- **Entorno:** este servidor es de **desarrollo y pruebas**, no de producción. La instancia es Developer Edition, que es justamente la edición gratuita que Microsoft licencia para ese uso, con el conjunto completo de funciones de Enterprise. No hay nada que ajustar en licenciamiento.
- **Destino de producción:** pendiente de definir cuando el proyecto salga de dev/test (§7, pregunta 9).
- **Autenticación:** por decisión explícita, la API queda pública y de solo lectura, igual que hoy. Para facilitar el aseguramiento posterior, los endpoints se agrupan con `MapGroup("/api")`, de forma que añadir `.RequireAuthorization()` más adelante sea un cambio de una línea. Se mantiene CORS restringido a `GET`.
- **Contraseña del login:** `dnp_dpip_app` se creó con `CHECK_POLICY = OFF` para admitir exactamente la contraseña definida por el usuario, que no cumple la política de complejidad de SQL Server (exige 3 de 4 categorías: mayúsculas, minúsculas, dígitos, símbolos). Es aceptable en dev/test; al pasar a producción conviene una contraseña conforme y `CHECK_POLICY = ON`.

### Fase 7 — Retiro de FastAPI *(0,5 día)*
- Eliminar `api/`, `requirements.txt` (queda el de ETL), `db/pgn.db` del flujo activo (conservar un respaldo etiquetado).
- Commit final y etiqueta de versión.

**Total estimado: 8–10 días de trabajo.**

---

## 6. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| División por cero aborta consultas | Alto — error 500 en producción | `NULLIF` sistemático (§3.2) + prueba de todos los endpoints en Fase 4 |
| Collation incorrecta fusiona regiones/sectores | Alto — cifras erróneas, silenciosas | BD en `CS_AS` (§3.4); el comparador detecta cambios de conteo |
| Renombre accidental de claves JSON | Alto — el frontend cae al *fallback* embebido sin avisar | Dapper → diccionarios; comparación de claves en Fase 4 |
| Diferencias de redondeo | Bajo | `DECIMAL` + tolerancia 1e-6 |
| BD compartida con Umbraco | Medio | BD y login separados; sin `sysadmin`; respaldo previo de la instancia |
| ETL sin archivos fuente disponibles | Medio — bloquea la prueba real de la Fase 5 | Solicitar `BASES_BITACORA/` antes de la Fase 5 |

---

## 7. Preguntas abiertas

Resueltas el 2026-08-15:

1. ~~**Tablas muertas**~~ → se descartan (§2.1).
2. ~~**Destino de producción**~~ → on-premise detrás de Caddy; se descartan Fly.io y Render (§6).
3. ~~**Autenticación**~~ → sigue pública por ahora; se asegura después (§6.1).
5. ~~**Autorización para `sqlcmd`**~~ → concedida; instancia verificada (Fase 0, paso 1).
6. ~~**Prefijo de nomenclatura**~~ → `dnp_dpip` para base de datos y login (§1).

4. ~~**Contraseña del login `dnp_dpip_app`**~~ → definida por el usuario y aplicada (§6.1). No se almacena en el repositorio; se inyecta por variable de entorno.

Pendientes:

7. **Subdominio público** de la aplicación (ej. `bitacora.skaphe.com`), a confirmar con quien administre el DNS.
8. **Archivos fuente `BASES_BITACORA/`**: no están en el repositorio y hacen falta para probar el ETL de extremo a extremo (Fase 5).
9. **Destino de producción**: este servidor es de desarrollo y pruebas. Falta definir dónde se despliega la versión productiva y qué instancia de SQL Server usará.
