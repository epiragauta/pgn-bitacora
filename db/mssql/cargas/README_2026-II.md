# Carga de la Bitácora 2026-II (corte 30 de junio de 2026) — esquema `btcr_`

Paquete para el **DBA**: actualizar la base de datos del tablero (.NET/SQL Server) con el
nuevo corte, sin ejecutar los ETL en Python. **Todas las tablas llevan el prefijo `btcr_`**
(convivencia en una base compartida).

## Archivos

| Archivo | Qué hace |
|---|---|
| `2026-II_2026-06-30_carga.sql` | **Script principal.** Inserta toda la bitácora 2026-II. Idempotente y transaccional. |
| `2026-II_2026-06-30_rollback.sql` | Reversa: elimina la bitácora 2026-II. |

## Requisitos

- La base ya existe con el esquema `btcr_` del tablero (la aplicación ya está desplegada).
- El script **no** crea ni altera tablas: solo inserta datos.
- Herramienta: `sqlcmd` o SSMS. **No** requiere modo SQLCMD (el script no usa `GO`).

## Ejecución

```bash
sqlcmd -S <host,puerto> -d <BASE> -U <usuario> -P <clave> -b -i 2026-II_2026-06-30_carga.sql
```

O en **SSMS**: abrir el archivo y ejecutar (F5).

- Es **un solo lote transaccional** con `SET XACT_ABORT ON`: si algo falla, **se revierte
  todo** automáticamente.
- Es **idempotente**: si la bitácora 2026-II ya existiera, primero borra sus datos y la
  vuelve a insertar. Re-ejecutable sin duplicar.
- Al final imprime el `id` asignado y una tabla de conteos de verificación.

## Verificación esperada (post-carga)

| Tabla | Filas (2026-II) |
|---|---|
| btcr_inversion_transformaciones | 8 |
| btcr_apropiacion_por_sector | 273 |
| btcr_ejecucion_historica | 9 |
| btcr_regionalizacion | 175 |
| btcr_vigencias_futuras | 182 |
| btcr_credito_portafolio | 24 |
| btcr_pgn_ejecucion (Evolución, **global**) | 560 |

Indicador de control: **Inversión vigente 2026 ≈ 89.472 mmm** (coincide en Sec 1, Sec 2 y Sec 4).

## Notas importantes

1. **`numero_bitacora` = 4** (asume 2025-I=2, 2026-I=3 → 2026-II=4). Si la numeración en la
   base difiere, ajustar ese valor en el `INSERT INTO dbo.btcr_metadatos_bitacora`.

2. **La Evolución PGN es GLOBAL.** `btcr_pgn_concepto`/`btcr_pgn_ejecucion` no están ligadas
   a una bitácora: el script las **reemplaza por completo** con las cifras de junio. Por
   diseño, la sección "Evolución" pasa a mostrar el último corte. Es el comportamiento
   correcto del tablero.

3. **Secciones sin fuente en este corte (SGP y "Sectores por región").** Quedan **vacías**
   para 2026-II. Para que la aplicación las **oculte** limpiamente (en vez de mostrar datos
   de ejemplo), el **frontend** del contenedor .NET debe estar actualizado con el
   ocultamiento data-driven. Es un **redepliegue de la aplicación**, no tarea del DBA.
   Coordinar con el equipo de despliegue.

4. Tras la carga, **no** hace falta reiniciar la aplicación: el tablero resuelve la bitácora
   más reciente por fecha de corte en cada consulta.

## Reversa

```bash
sqlcmd -S <host,puerto> -d <BASE> -U <usuario> -P <clave> -b -i 2026-II_2026-06-30_rollback.sql
```

Elimina la bitácora 2026-II y sus datos. **No** restaura la Evolución PGN anterior.
