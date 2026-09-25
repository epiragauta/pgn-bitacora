# Carga de la Bitácora 2026-II (corte 30 de junio de 2026) — SQL Server `dnp_dpip`

Paquete para el **DBA**: actualizar la base de datos del tablero (.NET/SQL Server) con el
nuevo corte, sin necesidad de ejecutar los ETL en Python.

## Archivos

| Archivo | Qué hace |
|---|---|
| `2026-II_2026-06-30_carga.sql` | **Script principal.** Inserta toda la bitácora 2026-II. Idempotente y transaccional. |
| `2026-II_2026-06-30_rollback.sql` | Reversa: elimina la bitácora 2026-II (por si hay que deshacer). |

## Requisitos

- La base `dnp_dpip` ya existe con el esquema del tablero (la aplicación ya está desplegada).
- El script **no** crea ni altera tablas: solo inserta datos.
- Herramienta: `sqlcmd` o SSMS. **No** requiere modo SQLCMD (el script no usa `GO`).

## Ejecución

```bash
sqlcmd -S <host,puerto> -d dnp_dpip -U <usuario> -P <clave> -b -i 2026-II_2026-06-30_carga.sql
```

O en **SSMS**: abrir el archivo y ejecutar (F5).

- Es **un solo lote transaccional** con `SET XACT_ABORT ON`: si cualquier sentencia
  falla, **se revierte todo** automáticamente. No deja cargas a medias.
- Es **idempotente**: si la bitácora 2026-II ya estuviera cargada, primero borra sus
  datos y la vuelve a insertar. Se puede re-ejecutar sin duplicar.
- Al final imprime el `id` asignado y una tabla de conteos de verificación.

## Verificación esperada (post-carga)

| Tabla | Filas (bitácora 2026-II) |
|---|---|
| inversion_transformaciones | 8 |
| inversion_componentes_pnd | 45 |
| ejecucion_transformaciones | 8 |
| apropiacion_por_sector | 273 |
| compromisos/obligaciones/pagos_pct_por_sector | 273 c/u |
| ejecucion_historica | 9 |
| ejecucion_sectorial_entidades | 1 494 |
| ejecucion_sectorial_mensual | 372 |
| regionalizacion | 175 |
| vigencias_futuras | 182 |
| deflactores_pib | 30 |
| credito_portafolio / entidad / historica | 24 / 18 / 4 |
| pgn_ejecucion (Evolución, **global**) | 560 |

Indicador de control: **Inversión vigente 2026 ≈ 89.472 mmm** (coincide en Sec 1, Sec 2 y Sec 4).

## Notas importantes

1. **`numero_bitacora` = 4.** Asume la numeración 2025-I=2, 2026-I=3 → 2026-II=**4**.
   Si en `dnp_dpip` la numeración difiere, ajustar ese valor en el `INSERT INTO
   dbo.metadatos_bitacora` del script (es una etiqueta, no afecta la lógica).

2. **La Evolución PGN es GLOBAL.** Las tablas `pgn_concepto`/`pgn_ejecucion` no están
   ligadas a una bitácora: el script las **reemplaza por completo** con las cifras del
   corte de junio. Por diseño, la sección "Evolución" pasa a mostrar el último corte para
   todas las bitácoras. Es el comportamiento correcto del tablero.

3. **Secciones sin fuente en este corte (SGP y "Sectores por región").** No hay archivo
   para junio, por lo que quedan **vacías** para 2026-II. Para que la aplicación las
   **oculte** limpiamente (en lugar de mostrar datos de ejemplo embebidos), el
   **frontend** del contenedor .NET debe estar actualizado con el ocultamiento
   data-driven. Esto es un **redepliegue de la aplicación** (imagen), no una tarea del
   DBA. Si la app aún no trae ese cambio, la sección SGP mostrará datos de ejemplo hasta
   que se redespliegue. Coordinar con el equipo de despliegue.

4. Tras la carga, **reiniciar la aplicación no es necesario**: el tablero resuelve la
   bitácora más reciente por fecha de corte en cada consulta y tomará 2026-II
   automáticamente.

## Reversa

```bash
sqlcmd -S <host,puerto> -d dnp_dpip -U <usuario> -P <clave> -b -i 2026-II_2026-06-30_rollback.sql
```

Elimina la bitácora 2026-II y sus datos. **No** restaura la Evolución PGN anterior
(al ser global, habría que recargarla desde el corte previo si se requiere).
