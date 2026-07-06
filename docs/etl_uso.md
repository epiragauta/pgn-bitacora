# ETLs — Guía de uso

Scripts de carga de datos fuente hacia la base de datos `db/pgn.db`. Todos requieren Python 3.10+ y `openpyxl` (`pip install openpyxl`).

Los archivos Excel fuente residen en `C:\ws\dnp\ws\BASES_BITACORA\{año}\{mes}\{N. SECCIÓN}\`.

---

## seed_data.py — Carga inicial

Inicializa la BD con datos embebidos (Bitácora 2, 2025-I). Se ejecuta una sola vez para crear el esquema y poblar todas las tablas.

```bash
python etl/seed_data.py
```

**Cuándo usarlo:** configuración inicial del entorno o cuando se necesita resetear la BD a un estado base conocido.

---

## load_vigencias_futuras.py — Sec 5

Carga **Vigencias Futuras** desde los datos fuente SIIF. Popula dos tablas:

- `deflactores_pib` — DEFLACTOR PIB BASE 2026 + PIB corriente/constante por año (leído de hoja `TD BITACORA`)
- `vigencias_futuras` — pivot (sector × año) en pesos corrientes mmm (leído de hoja `BASE_SIIF_2`)

```bash
python etl/load_vigencias_futuras.py
```

**Archivo fuente:**
```
BASES_BITACORA\{año}\{mes}\5. VIGENCIAS FUTURAS\
  └── 20260513 Nueva Base VF - Validada - Revisión Analistas.xlsx
        ├── BASE_SIIF_2   ← datos crudos SIIF (1 974 registros)
        └── TD BITACORA   ← deflactores y PIB
```

**Flujo interno:**
1. Lee `TD BITACORA` (filas ≤ 75) → extrae deflactores y PIB por año
2. Lee `BASE_SIIF_2` → agrega `SUM(Valor_VF_Final)` por `(Nombre_Sector, Vigencia)`
3. Divide por `1e9` para convertir pesos → mmm
4. Carga en BD (DROP + CREATE + INSERT para ambas tablas)

**Salida esperada:**
```
✓ deflactores_pib:   30 filas cargadas
✓ vigencias_futuras: 193 filas cargadas  (29 sectores × años)
```

**La transformación a precios constantes ocurre en la API**, no en el ETL:
```sql
-- /api/vigencias_futuras/chart
valor_constante_mmm = valor_corriente_mmm / deflactor
pct_pib = valor_constante_mmm / pib_constante_mmm * 100
```

Los 29 sectores individuales se agrupan en 6 series en la capa de API:
TRANSPORTE · IGUALDAD Y EQUIDAD · HACIENDA · DEFENSA Y POLICÍA · SALUD Y PROTECCIÓN SOCIAL · OTROS SECTORES

**Para una nueva bitácora:** edita la constante `FILE` al inicio del script apuntando al nuevo Excel, luego ejecuta.

---

## load_regionalizacion.py — Sec 3

Carga datos de regionalización de inversión 2022–2026 desde Excel.

```bash
# Ruta por defecto
python etl/load_regionalizacion.py

# Ruta personalizada
python etl/load_regionalizacion.py --xlsx "ruta/al/Consolidado Reg-Ejec-Marzo-2022-2026.xlsx"
```

**Archivo fuente:**
```
BASES_BITACORA\{año}\{mes}\3. REGIONALIZACIÓN\
  └── Consolidado Reg-Ejec-Marzo-2022-2026.xlsx
```

**Tablas que carga:** `regionalizacion_resumen`, `regionalizacion_detalle_2025`

---

## load_ejecucion_sectorial.py — Sec 4 y 6

Carga ejecución detallada mensual por entidad desde el archivo BASE DETALLE MENSUAL.

```bash
python etl/load_ejecucion_sectorial.py \
  --excel "ruta/BASE DETALLE MENSUAL INVERSIÓN 2018-2026.xlsx" \
  --db db/pgn.db \
  --bitacora-id 2 \
  --mes-corte MAR
```

**Parámetros:**

| Parámetro | Descripción | Ejemplo |
|-----------|-------------|---------|
| `--excel` | Ruta al Excel fuente | `".../BASE DETALLE MENSUAL..."` |
| `--db` | Ruta a la BD SQLite | `db/pgn.db` |
| `--bitacora-id` | ID de la bitácora destino | `2` |
| `--mes-corte` | Mes de corte (3 letras) | `MAR`, `JUN`, `SEP`, `DIC` |

**Archivo fuente:**
```
BASES_BITACORA\{año}\{mes}\6. EJECUCIÓN SECTORIAL\
  └── BASE DETALLE MENSUAL INVERSIÓN 2018-2026.xlsx
```

**Tablas que carga:** `ejecucion_sectorial_entidades`, `ejecucion_sectorial_mensual`

---

## load_bitacora_excel.py — Sec 1, 4, 6 (carga completa)

ETL principal para carga de una bitácora completa desde archivos Excel fuente. Cubre Secciones 1, 4 y 6.

```bash
# Con valores por defecto
python etl/load_bitacora_excel.py

# Especificando período y corte
python etl/load_bitacora_excel.py --periodo 2026-I --corte 2026-03-31

# Reemplazar si ya existe la bitácora
python etl/load_bitacora_excel.py --replace
```

**Secciones que carga:**
- Sec 1: Transformaciones PND, componentes y ejecución por transformación
- Sec 4: Apropiación por sector (vigencia actual)
- Sec 6: Ejecución sectorial por entidad

**Secciones pendientes** (requieren ETL separado):
- Sec 2: Evolución presupuestal histórica
- Sec 3: Regionalización → usar `load_regionalizacion.py`
- Sec 5: Vigencias Futuras → usar `load_vigencias_futuras.py`
- Sec 6 mensual: Series históricas → usar `load_ejecucion_sectorial.py`

---

## update_bitacora.py — Actualización desde CSVs

Alternativa CSV-based para cargar una nueva bitácora. Lee archivos desde `etl/data/*.csv`.

```bash
python etl/update_bitacora.py \
  --numero 3 \
  --periodo 2025-II \
  --corte 2025-06-30 \
  --notas "Segundo semestre 2025"
```

---

## load_evolucion_presupuestal.py — Sec 2 (pendiente)

> **Estado:** archivo fuente identificado; script ETL **pendiente de crear**.

**Archivo fuente:**
```
BASES_BITACORA\{año}\{mes}\2. EVOLUCIÓN PRESUPUESTAL\
  └── 2026-03-31Estructura_Evolución PGN y Reg-Ejec-marzo.xlsx
        └── Evolucion PGN   ← hoja única con datos PGN
```

**Tablas que cargará:** `evolucion_presupuestal`

**Especificación:** ver `docs/2. Integracion_datos_evolucion_presupuestal.md` sección 7 (jerarquía de conceptos, filas a omitir, columnas por año/fase, nota sobre fila duplicada F35).

**Notas clave:**
- Unidades ya en mmm (declaradas en fila 2 del Excel) — sin conversión
- Omitir fila duplicada F35 (idéntica a F34, "Inversión")
- Omitir filas de porcentaje: F6, F8, F22, F33
- Omitir sub-encabezado de fases: F9
- Año 2026 disponible en el Excel (cols 17–20) pero no está en la BD actual

---

## Orden de ejecución para nueva bitácora

Para cargar una bitácora completa desde cero con todos los ETLs Excel:

```bash
# 1. Carga principal (Sec 1, 4, 6)
python etl/load_bitacora_excel.py --periodo 2026-II --corte 2026-06-30

# 2. Evolución presupuestal (Sec 2) — pendiente: crear el script
# python etl/load_evolucion_presupuestal.py

# 3. Regionalización (Sec 3)
python etl/load_regionalizacion.py --xlsx "ruta/Consolidado Reg-Ejec-*.xlsx"

# 4. Ejecución sectorial mensual (Sec 4, 6 detalle)
python etl/load_ejecucion_sectorial.py \
  --excel "ruta/BASE DETALLE MENSUAL INVERSIÓN *.xlsx" \
  --bitacora-id <nuevo_id> --mes-corte JUN

# 5. Vigencias Futuras (Sec 5)
python etl/load_vigencias_futuras.py   # editar FILE al inicio si cambió el Excel

# 6. Reiniciar API
uvicorn api.main:app --reload --port 8000
```
