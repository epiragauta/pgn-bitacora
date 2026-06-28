# Guía de integración — Módulo Evolución Presupuestal PGN

Este documento describe cómo incorporar el nuevo schema `pgn_concepto` / `pgn_ejecucion`
a la base de datos SQLite de la aplicación sin afectar las demás secciones.

---

## 1. Reemplazar el schema anterior

Las tablas que este módulo reemplaza son `evolucion_presupuestal` y `ejecucion_historica`
(usada parcialmente por la Sección 2). El DDL en `db/schema_pgn.sql` solo opera sobre
tablas con prefijo `pgn_`; el resto del schema (`metadatos_bitacora`, secciones 1, 3–6)
no se toca.

### Pasos recomendados

```bash
# 1. Hacer backup antes de cualquier cambio destructivo
cp db/pgn.db db/pgn.db.bak

# 2. Aplicar solo el DDL del módulo PGN (no el schema.sql completo)
sqlite3 db/pgn.db < db/schema_pgn.sql

# 3. Importar el CSV con datos 2022-2026
python etl/importar_pgn.py data/evolucion_presupuestal.csv db/pgn.db

# 4. Verificar
sqlite3 db/pgn.db "SELECT COUNT(*) FROM pgn_concepto; SELECT COUNT(*) FROM pgn_ejecucion;"
```

Si necesitas mantener la base de datos de producción intacta mientras preparas la migración,
usa ATTACH para trabajar sobre una copia:

```sql
-- Desde una sesión SQLite apuntando a la BD de producción
ATTACH 'db/pgn_nuevo.db' AS nuevo;
-- ...importar en pgn_nuevo.db, validar, luego renombrar el archivo
```

### ¿Qué pasa con las tablas antiguas?

`evolucion_presupuestal` y `ejecucion_historica` no se eliminan automáticamente.
Si la API todavía referencia esas tablas, actualiza los endpoints correspondientes
antes de eliminarlas manualmente:

```sql
DROP TABLE IF EXISTS evolucion_presupuestal;
-- ejecucion_historica también es usada por Sección 4; evaluar antes de borrar
```

---

## 2. Actualizar datos año a año

El flujo para incorporar un nuevo año (ej. 2027) es siempre el mismo:

1. Agregar las filas del nuevo año al CSV (mismas columnas, mismos conceptos o nuevos).
2. Ejecutar el script — usa `INSERT OR REPLACE` con la restricción `UNIQUE(anio, fase, concepto_id)`,
   por lo que registros existentes se sobreescriben y los nuevos se insertan sin duplicar.

```bash
python etl/importar_pgn.py data/evolucion_presupuestal_2027.csv db/pgn.db
```

Si el CSV acumula todos los años (como el actual), re-ejecutar el script es seguro:
el DDL borra y recrea las tablas, luego los 560+ registros se insertan frescos.

Para una actualización incremental sin DROP (conservar histórico mientras se añade un año):

```python
# Alternativa: llamar solo a los pasos C sin ejecutar el DDL
# Requiere que los conceptos ya existan en pgn_concepto.
conn.executemany(
    'INSERT OR REPLACE INTO pgn_ejecucion(anio, fase, concepto_id, valor) VALUES(?,?,?,?)',
    hechos_nuevos
)
```

### Agregar 2027 a la vista crosstab

La vista `pgn_vista_crosstab` tiene los años hardcodeados. Al incorporar un nuevo año,
agregar el bloque correspondiente en `db/schema_pgn.sql` y re-ejecutar el DDL:

```sql
MAX(CASE WHEN e.anio=2027 AND e.fase='Vigente'       THEN e.valor END) AS vigente_2027,
MAX(CASE WHEN e.anio=2027 AND e.fase='Comprometido'  THEN e.valor END) AS comprometido_2027,
MAX(CASE WHEN e.anio=2027 AND e.fase='Obligado'      THEN e.valor END) AS obligado_2027,
MAX(CASE WHEN e.anio=2027 AND e.fase='Pagado'        THEN e.valor END) AS pagado_2027,
```

---

## 3. Convención de nombres

Todas las tablas y vistas de este módulo usan el prefijo **`pgn_`**:

| Objeto             | Tipo  | Propósito                                      |
|--------------------|-------|------------------------------------------------|
| `pgn_concepto`     | Tabla | Jerarquía de conceptos presupuestales          |
| `pgn_ejecucion`    | Tabla | Hechos: valor por (año, fase, concepto)        |
| `pgn_vista_crosstab` | Vista | Formato ancho para compatibilidad con la app |

Esta convención garantiza que nunca colisione con las tablas de otras secciones
(`inversion_*`, `ejecucion_*`, `regionalizacion_*`, `vigencias_*`).

Si en el futuro se modulariza la BD, el prefijo permite identificar y migrar
el módulo de forma autónoma.

---

## 4. Conectar las queries a la API FastAPI

Los cinco queries de `db/queries_evolucion.sql` se traducen directamente a endpoints
en `api/main.py`. Ejemplo para Q1:

```python
@app.get("/api/evolucion/total_pgn")
def evolucion_total_pgn(db=Depends(get_db)):
    rows = db.execute("""
        SELECT e.anio, e.fase, e.valor
        FROM   pgn_ejecucion e
        JOIN   pgn_concepto  c ON c.id = e.concepto_id
        WHERE  c.nombre = 'Total PGN'
          AND  c.unidad = 'Miles mm COP'
        ORDER BY e.anio, e.fase
    """).fetchall()
    return rows_to_list(rows)
```

Para Q2 y Q4 (con parámetros), usar Query params de FastAPI:

```python
@app.get("/api/evolucion/composicion")
def composicion_vigente(anio: int, db=Depends(get_db)):
    rows = db.execute("... WHERE e.anio = ?", (anio,)).fetchall()
    return rows_to_list(rows)
```

### Endpoint de drilldown jerárquico (Q4)

```python
@app.get("/api/evolucion/drilldown")
def drilldown(concepto: str, anio: int, fase: str = "Vigente", db=Depends(get_db)):
    rows = db.execute("""
        WITH RECURSIVE arbol AS (
            SELECT id, nombre, nivel, padre_id, orden
            FROM   pgn_concepto WHERE nombre = ?
            UNION ALL
            SELECT c.id, c.nombre, c.nivel, c.padre_id, c.orden
            FROM   pgn_concepto c JOIN arbol a ON c.padre_id = a.id
        )
        SELECT a.nivel, a.nombre, e.valor, COALESCE(p.nombre,'') AS padre
        FROM   arbol a
        JOIN   pgn_ejecucion  e ON e.concepto_id = a.id
        LEFT JOIN pgn_concepto p ON p.id = a.padre_id
        WHERE  e.anio = ? AND e.fase = ?
        ORDER BY a.orden
    """, (concepto, anio, fase)).fetchall()
    return rows_to_list(rows)
```

---

## 5. Datos de fallback en el frontend

El frontend (`frontend/index.html`) tiene un objeto `D` con datos embebidos como fallback
cuando la API no responde. Si se actualizan los datos en la BD, actualizar también el
objeto `D.evolucion` con los valores del Q1 para que el modo offline muestre cifras recientes.
