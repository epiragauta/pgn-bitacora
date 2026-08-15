# Manual técnico — Bitácora de Inversión Pública

**Para:** desarrolladores que van a modificar el backend, la base o los ETL
**Requisitos previos:** .NET SDK 8, Docker, Python 3.10+, ODBC Driver 18 for SQL Server
**Actualizado:** 15 de agosto de 2026

> Antes de tocar el backend, lee las **tres reglas de §3**. Cada una nació de un defecto real y las tres fallan sin producir ningún error visible.

---

## 1. Puesta en marcha del entorno

### 1.1 Base de datos

```bash
# Una sola vez, como sa
docker exec -i umbraco-sqlserver /opt/mssql-tools18/bin/sqlcmd \
    -S localhost -U sa -P "$SA_PASSWORD" -C -i /dev/stdin <<'SQL'
CREATE DATABASE dnp_dpip COLLATE Modern_Spanish_CS_AS;
GO
CREATE LOGIN dnp_dpip_app WITH PASSWORD='...', DEFAULT_DATABASE=dnp_dpip, CHECK_POLICY=OFF;
GO
USE dnp_dpip;
CREATE USER dnp_dpip_app FOR LOGIN dnp_dpip_app;
ALTER ROLE db_datareader ADD MEMBER dnp_dpip_app;
ALTER ROLE db_datawriter ADD MEMBER dnp_dpip_app;
ALTER ROLE db_ddladmin  ADD MEMBER dnp_dpip_app;
GO
SQL

# Esquema — idempotente, ejecutar en orden
for f in db/mssql/*.sql; do
  docker exec -i umbraco-sqlserver /opt/mssql-tools18/bin/sqlcmd \
      -S localhost -U sa -P "$SA_PASSWORD" -C -b -d dnp_dpip -i /dev/stdin < "$f"
done
```

La collation **no es un detalle de configuración**: ver §3.2.

### 1.2 API

```bash
# Desarrollo local
export ConnectionStrings__DnpDpip="Server=127.0.0.1,1433;Database=dnp_dpip;User Id=dnp_dpip_app;Password=...;TrustServerCertificate=True"
dotnet run --project backend/src/PgnBitacora.Api --urls http://127.0.0.1:5080

# Contenedor
cp .env.example .env      # poner la contraseña real
docker compose up -d --build
```

Tablero en `/`, API en `/api`, documentación interactiva en `/swagger`, salud en `/health`.

### 1.3 Herramientas Python

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt      # pyodbc + openpyxl
export DNP_DPIP_CONN="DRIVER={ODBC Driver 18 for SQL Server};SERVER=127.0.0.1,1433;DATABASE=dnp_dpip;UID=dnp_dpip_app;PWD=...;TrustServerCertificate=yes"
```

Ojo con los dos formatos de cadena de conexión: **.NET usa el formato ADO.NET** (`Server=...;Database=...`) y **Python el formato ODBC** (`DRIVER={...};SERVER=...;DATABASE=...`). No son intercambiables.

---

## 2. Estructura del backend

```
backend/src/PgnBitacora.Api/
├── Program.cs                  DI, CORS, Swagger, estáticos, manejo de 404
├── Endpoints/
│   ├── MetadatosEndpoints.cs        /api/bitacoras
│   ├── TransformacionesEndpoints.cs Sec 1
│   ├── EvolucionEndpoints.cs        Sec 2
│   ├── RegionalizacionEndpoints.cs  Sec 3
│   ├── EjecucionEndpoints.cs        Sec 4
│   ├── VigenciasFuturasEndpoints.cs Sec 5
│   ├── SectorialEndpoints.cs        Sec 6
│   ├── CreditoEndpoints.cs          Sec 7
│   ├── SgpEndpoints.cs              Sec 8
│   └── ResumenEndpoints.cs          KPIs del encabezado
├── Services/                   Lógica que no cabe en SQL
├── Data/
│   ├── Db.cs                   Dapper → diccionarios
│   ├── BitacoraResolver.cs     Resolución de la bitácora activa
│   └── FilaExtensions.cs
└── Json/
    └── DecimalRecortadoConverter.cs
```

Cada archivo de `Endpoints/` expone un método de extensión `MapXxx()` que `Program.cs` invoca. Para añadir una sección, se crea la clase y se registra allí.

---

## 3. Las tres reglas

### 3.1 Los alias de columna del SQL son las claves del JSON

`Db.cs` devuelve `IDictionary<string, object?>`, no objetos tipados:

```csharp
var filas = await db.QueryAsync("""
    SELECT vigencia, sector, vigente_mmm
    FROM dbo.apropiacion_por_sector
    WHERE bitacora_id = @bid
    """, new { bid = ctx.Id });
```

Ese SQL produce exactamente `{"vigencia":…, "sector":…, "vigente_mmm":…}`.

**Por qué importa:** el frontend lee claves snake_case exactas y, si falta una, cae a sus datos embebidos **sin mostrar error**. Un renombre en una refactorización dejaría el tablero mostrando cifras viejas sin que nadie lo note. Con diccionarios no hay dónde equivocarse.

Corolarios que no se deben romper:

- No introducir `PropertyNamingPolicy` en la serialización.
- No activar `DefaultIgnoreCondition = WhenWritingNull`: el frontend distingue `null` de ausente.
- `codigo_dane` es **texto con cero a la izquierda** (`'05'`), nunca entero.

### 3.2 La collation debe seguir siendo `Modern_Spanish_CS_AS`

Sensible a mayúsculas y tildes. Con una insensible, `PACÍFICO` y `PACIFICO` colapsan en un mismo valor y `GROUP BY region` fusiona filas silenciosamente.

Comprobación rápida:

```sql
SELECT COUNT(*) FROM dbo.dane_departamentos WHERE region = N'PACIFICO';  -- debe dar 0
SELECT COUNT(*) FROM dbo.dane_departamentos WHERE region = N'PACÍFICO';  -- debe dar 3
```

### 3.3 Toda aritmética calculada va en `FLOAT`

El almacenamiento es `DECIMAL(18,6)`; las **expresiones** se castean:

```sql
ROUND(CAST(SUM(compromisos_mmm) AS FLOAT) * 100.0 / NULLIF(SUM(apropiacion_mmm), 0), 2)
```

Dos cosas en esa línea:

- **`CAST(... AS FLOAT)`** reproduce la doble precisión del motor original. Con `DECIMAL`, un porcentaje del PIB daba 1,2367 donde la serie histórica tenía 1,2368.
- **`NULLIF(denominador, 0)`** evita el error 8134. El motor anterior devolvía nulo al dividir por cero; SQL Server aborta la consulta entera.

En C#, los servicios que replican cálculos del backend anterior acumulan en `double` por la misma razón.

---

## 4. Patrones de consulta

### 4.1 Ordenamiento por texto

El motor original comparaba texto por bytes, donde los acentuados quedan **después** de todo el ASCII (`Córdoba` después de `Cundinamarca`). Una collation española ordena por diccionario y lo pondría antes. Para conservar el orden histórico:

```sql
ORDER BY region COLLATE Latin1_General_BIN2
```

Donde el original usaba comparación sin distinguir mayúsculas:

```sql
ORDER BY UPPER(departamento) COLLATE Latin1_General_BIN2
```

### 4.2 Desempates

Donde se ordena por un campo con valores repetidos, hay que añadir un desempate por clave natural. Sin él, el orden depende del plan de ejecución y cambia entre despliegues:

```sql
ORDER BY monto_usd DESC, sector COLLATE Latin1_General_BIN2
```

### 4.3 CTE recursiva

Sin la palabra `RECURSIVE`, y conviene acotar la profundidad:

```sql
WITH arbol AS (
    SELECT id, nombre, nivel, padre_id, orden FROM dbo.pgn_concepto WHERE nombre = @concepto
    UNION ALL
    SELECT c.id, c.nombre, c.nivel, c.padre_id, c.orden
    FROM dbo.pgn_concepto c JOIN arbol a ON c.padre_id = a.id
)
SELECT ... FROM arbol a ...
OPTION (MAXRECURSION 10)
```

### 4.4 Fechas

Se formatean **en SQL**, no en .NET:

```sql
CONVERT(char(10), corte_fecha, 23)  AS corte_fecha    -- 2026-03-31
CONVERT(char(19), fecha_carga, 120) AS fecha_carga    -- 2026-06-20 19:26:16
```

Serializar un `DateTime` produciría `2026-03-31T00:00:00`, y el frontend hace `corte_fecha.split('-')`.

### 4.5 Nulos al final

El original escribía `NULLS LAST` explícitamente. No hace falta traducirlo: ambos motores tratan `NULL` como el valor más bajo, así que `ORDER BY x DESC` ya los deja al final.

---

## 5. Los ETL

### 5.1 `etl/db.py` — capa de conexión

Envoltorio con la forma de la API de sqlite3 que usaban los cargadores, para que solo cambiara la conexión y no su lógica de negocio.

| Método | Reemplaza a | Detalle que importa |
|---|---|---|
| `conectar()` | `sqlite3.connect` | Lee `DNP_DPIP_CONN` |
| `conn.upsert(tabla, cols, filas, claves)` | `INSERT OR REPLACE` | **Deduplica el lote por clave conservando la última fila** y avisa por stderr. El motor anterior aplicaba la sentencia fila a fila, así que los duplicados del origen no chocaban; al insertar en bloque sí |
| `conn.insertar_devolviendo_id(sql, params)` | `cur.lastrowid` | `SCOPE_IDENTITY()` está acotado al **lote**, no a la sesión: en un `execute` posterior devuelve `NULL`, por eso el INSERT y la consulta viajan juntos |
| `conn.vaciar_bitacora(tablas, bid)` | `DROP TABLE` + `CREATE` | El esquema pertenece a `db/mssql/`; borrar la tabla rompería las FK y la vista |
| `with conn:` | igual que sqlite3 | Confirma o revierte, pero **no cierra**: los cargadores siguen consultando después del bloque |

Dos diferencias de pyodbc que hay que tener presentes:

- Solo admite parámetros **posicionales** (`?`), no `:nombre`.
- Sus filas **no** se indexan por nombre: `fila[0]`, no `fila["id"]`.

### 5.2 `etl/bases.py` — localización de archivos

Resuelve en orden: variable `BASES_BITACORA` → `data/BASES_BITACORA/` → rutas históricas de Windows. Busca **por patrón** dentro de cada carpeta de sección, porque los nombres traen fechas y sufijos que cambian cada trimestre.

```python
FILE = bases.excel(5, "*Base VF*.xlsx")     # sección 5, por patrón
```

Ignora los temporales `~$...` que deja Excel cuando alguien tiene el archivo abierto.

### 5.3 Escribir un cargador nuevo

1. Leer el Excel con `openpyxl` y armar las filas en memoria.
2. Obtener la bitácora con `dbmod.bitacora_reciente(conn)`.
3. Escribir con `conn.upsert(...)` indicando la clave natural.
4. **No** crear ni borrar tablas: eso es de `db/mssql/`.
5. Si algo falta en el origen, **fallar con un mensaje que diga qué falta y dónde**, no adivinar. Ver `load_vigencias_futuras.py` como referencia.

### 5.4 Localizar la fila de encabezados

Los libros no siempre traen la cabecera en la primera fila. Buscarla por contenido en vez de asumir la posición, como hace `load_vigencias_futuras.py`.

---

## 6. Verificación obligatoria

**Ningún cambio del backend está terminado sin esto:**

```bash
python tools/compare_apis.py --contra-linea-base
```

Recorre 322 rutas y clasifica las diferencias:

| Tipo | Significado | ¿Bloquea? |
|---|---|---|
| `claves` | Cambió el conjunto de campos del JSON | **Sí** — rompe el frontend en silencio |
| `valores` | Mismas claves, distinto dato | **Sí** — error de traducción |
| `estado` | Códigos HTTP distintos | **Sí** |
| `orden` | Mismas filas, distinta secuencia | No — empates sin desempate en el original |

**La línea base de `tools/baseline/` es la red de seguridad.** Se capturó de la API previa a la migración. **Nunca regenerarla para hacer desaparecer una diferencia**: eso destruye justamente la garantía. Solo se regenera cuando los datos cambian a propósito, con `tools/capture_baseline.py`.

Para comparar dos bases después de un cargue:

```bash
python tools/compare_bd.py --a dnp_dpip --b dnp_dpip_pruebas --periodo 2026-I
```

---

## 7. Tareas frecuentes

### Añadir un endpoint

1. Crear el método en la clase de `Endpoints/` que corresponda a la sección.
2. Escribir el SQL con los alias que el frontend espera (§3.1), `NULLIF` en denominadores y `CAST(... AS FLOAT)` en cálculos.
3. Añadir la ruta a `tools/endpoints.py` para que entre en la verificación.
4. Capturar su respuesta en la línea base y correr el comparador.

### Añadir una columna

1. Añadirla a `db/mssql/001_schema.sql` **con guarda de idempotencia**.
2. Aplicar el script.
3. Actualizar el cargador correspondiente.
4. Verificar paridad: el resto de endpoints no debe cambiar.

### Añadir un año a la vista crosstab

`pgn_vista_crosstab` tiene un bloque `MAX(CASE WHEN ...)` por año y fase. Replicar el bloque con el año nuevo en `db/mssql/002_views.sql` y volver a aplicarlo (usa `CREATE OR ALTER`).

---

## 8. Diagnóstico

| Síntoma | Causa probable |
|---|---|
| El tablero muestra cifras viejas y no da error | El frontend cayó a sus datos embebidos: alguna clave del JSON cambió o el endpoint falló. Revisar la consola del navegador |
| El mapa aparece en blanco | Los GeoJSON devuelven 404. Verificar el registro del tipo `application/geo+json` en `Program.cs` |
| Error 8134 | División por cero: falta un `NULLIF` |
| Regiones o sectores fusionados | La base se creó con collation insensible a tildes |
| Porcentajes con el último decimal distinto | Falta un `CAST(... AS FLOAT)` en la expresión |
| `SCOPE_IDENTITY()` devuelve `NULL` | El INSERT y la consulta van en lotes separados; usar `insertar_devolviendo_id()` |
| El contenedor no conecta a la base | Verificar que esté unido a `sbn-ecp_umbraco-network` y que use el alias `sqlserver` |

Logs: `docker compose logs -f api`.

---

## Documentos relacionados

- `docs/ARQUITECTURA.md` — visión de conjunto y decisiones de diseño
- `docs/MANUAL_OPERACION.md` — cargue trimestral y despliegue
- `docs/PLAN_MIGRACION_DOTNET_SQLSERVER.md` — catálogo completo de incompatibilidades entre motores, con los casos reales que las motivaron
