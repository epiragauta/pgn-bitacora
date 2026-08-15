# Artefactos SQLite — retirados en la fase 7 (2026-08-15)

Esta carpeta es un **archivo histórico**. Nada del sistema en marcha la lee:
la base viva es SQL Server (`dnp_dpip`), cuyo DDL está en `db/mssql/`.

Se conserva por trazabilidad. La bitácora 2025-I y buena parte de las series
históricas se construyeron aquí antes de que existiera el esquema SQL Server,
así que este es el único registro de cómo estaban los datos antes de migrar.

| Archivo | Qué es |
|---|---|
| `pgn.db` | Base SQLite completa (1,2 MB) tal como quedó antes del corte. Origen de la migración de la fase 2 |
| `schema.sql` | Esquema SQLite original. **Ya estaba desactualizado antes de migrar**: no incluía `regionalizacion`, `dane_departamentos`, `regionalizacion_sectores` ni las tablas `pgn_*` |
| `schema_pgn.sql` | DDL de `pgn_concepto` / `pgn_ejecucion` y la vista crosstab |
| `migrations/` | Migraciones 003 y 004, que `schema.sql` nunca incorporó |
| `queries_evolucion.sql` | Consultas exploratorias de la sección 2 |

También incluye tablas que **no se migraron** por estar vacías o reemplazadas
(`evolucion_presupuestal`, `legacy_regionalizacion_*`, `ejecucion_mensual_sectorial`);
si alguna vez se necesitan, están aquí. El detalle y el motivo de cada
descarte está en `docs/PLAN_MIGRACION_DOTNET_SQLSERVER.md` §2.1.

`etl/migrate_sqlite_to_mssql.py` sigue apuntando a `pgn.db` en esta ruta. Ya
cumplió su función —la migración está hecha y verificada— pero se conserva
porque documenta con precisión la equivalencia entre ambos esquemas.

**No volver a cargar datos aquí.** Los ETL escriben directamente en SQL Server.
