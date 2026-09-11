# Análisis consolidado de fuentes de datos — Bitácora PGN

**Alcance:** Todas las fuentes Excel procesadas en los ETLs de la Bitácora 2026-I  
**Fecha:** 2026-06-29  
**Autor:** Edwin Piragauta / Claude Code

Este documento consolida los hallazgos transversales de los procesos ETL implementados para la Bitácora PGN 2026-I: inconsistencias de unidades, datos redundantes, homologación de nombres, decisiones de diseño en la base de datos y recomendaciones para futuras integraciones.

---

## 1. Unidades monetarias — heterogeneidad entre fuentes

El problema más recurrente en todas las fuentes es que **cada archivo usa una unidad monetaria diferente**, sin que haya una convención explícita documentada en los propios archivos.

### 1.1 Tabla resumen por fuente

| Fuente (archivo) | Sección | Unidad declarada | Unidad real | Factor a mmm |
|---|---|---|---|---|
| `Inversiones 2026 - PND 2022-2026.xlsx` hoja `Base` | Sec 1 | No declarada | Pesos COP | ÷ 1 000 000 000 |
| `seed_data.py` (datos embebidos) | Sec 1 y 2 | mmm (en comentario) | mmm | — |
| `2026-03-31Estructura_Evolución PGN y Reg-Ejec-marzo.xlsx` hoja `Evolucion PGN` | Sec 2 | **Miles de millones** (declarado en fila 2) | mmm | — *(ya en mmm)* |
| `Consolidado Reg-Ejec-Marzo-2022-2026_v_2.0.xlsx` | Sec 3 | Millones de pesos | Millones COP | ÷ 1 000 |
| `BASE DETALLE MENSUAL INVERSIÓN 2018-2026.xlsx` | Sec 4 y 6 | No declarada | Pesos COP | ÷ 1 000 000 000 |
| `20260513 Nueva Base VF - Validada.xlsx` hoja `BASE_SIIF_2` | Sec 5 | No declarada | Pesos COP | ÷ 1 000 000 000 |
| `20260513 Nueva Base VF - Validada.xlsx` hoja `TD BITACORA` — PIB corrientes | Sec 5 | Millones de pesos | Millones COP | ÷ 1 000 |
| `TD BITACORA` — sección constantes | Sec 5 | mmm explícito | mmm pesos ctes. 2026 | — |

### 1.2 Inconsistencia interna en un mismo archivo

El archivo de Vigencias Futuras (`20260513 Nueva Base VF.xlsx`) usa **dos unidades dentro del mismo libro**:

- Hoja `BASE_SIIF_2`: valores en **pesos COP** (p.ej. `24 626 376 371`)
- Hoja `TD BITACORA`, fila PIB corrientes: en **millones de pesos** (`1 929 474`)
- Hoja `TD BITACORA`, sección constantes: ya calculada en **mmm**

Esto obligó a aplicar conversiones distintas según la fila leída, lo que no es evidente a primera vista.

### 1.3 Impacto en el esquema de la BD — sufijo de columna

Para mitigar la ambigüedad, el esquema adopta sufijos explícitos:

| Sufijo | Significado | Tablas donde aparece |
|---|---|---|
| `_mmm` | Miles de millones (÷ 1 000 000 000) | Todas las tablas monetarias principales |
| `_mm` | Millones (÷ 1 000 000) | `regionalizacion_resumen`, `regionalizacion_detalle_2025` |
| `_pct` | Porcentaje (0-100) | Columnas de ejecución |
| `_corriente_mmm` | Pesos corrientes, en mmm | `vigencias_futuras` |
| `_constante_mmm` | Pesos constantes base 2026, en mmm | `deflactores_pib` |

> ⚠️ **Inconsistencia detectada:** las tablas de regionalización usan `_mm` (millones), mientras todas las demás usan `_mmm` (miles de millones). Esto significa que los valores de regionalización son **1 000 veces más grandes** en número que los equivalentes de otras secciones para la misma magnitud. Ver sección 4.1 para la recomendación.

---

## 2. Datos redundantes entre fuentes

### 2.1 Datos de ejecución histórica — tres fuentes para el mismo dato

La tabla `ejecucion_historica` se alimenta de tres fuentes distintas con diferente cobertura:

| Fuente | Años cubiertos | Nivel de detalle | ¿Activa? |
|---|---|---|---|
| `seed_data.py` (hardcoded) | 2022–2025 (4 años) | Solo totales nacionales | Sí (bitácora 2025-I) |
| `BASE DETALLE MENSUAL INVERSIÓN.xlsx` | 2018–2026 (9 años) | Proyecto por proyecto | Sí (bitácora 2026-I) |
| `evolucion_presupuestal` (seed) | 2022–2025 | Rubros PGN (func/inv/deuda) | Sí, pero no conectada a ejecucion_historica |

Los % de ejecución (`pct_compromisos`, `pct_obligaciones`) que aparecen en `ejecucion_historica` **se pueden calcular a partir de los datos de `ejecucion_sectorial_entidades`**, pero actualmente el ETL `load_ejecucion_sectorial.py` los calcula y los vuelve a insertar como datos separados.

### 2.2 Tabla dinámica vs datos crudos — Vigencias Futuras

La hoja `TD BITACORA` del archivo de VF es literalmente una tabla dinámica de Excel que ya realizó el `SUM(Valor_VF_Final)` por sector × vigencia. El ETL optó por no leer esta tabla pre-calculada sino replicar el pivot desde `BASE_SIIF_2` para mayor trazabilidad. Como resultado:

- Los valores entre el pivot del ETL y los de `TD BITACORA` **coinciden al 100%** (verificado para 2027)
- Sin embargo, mantener ambas fuentes en el archivo Excel genera confusión: un analista podría leer `TD BITACORA` directamente y creer estar leyendo datos crudos

### 2.3 Sector en múltiples tablas (sin FK)

El nombre del sector aparece como campo `TEXT` en al menos 9 tablas distintas sin una tabla maestra de referencia:

```
inversion_transformaciones    → columna: transformador
ejecucion_transformaciones    → columna: transformador
inversion_componentes_pnd     → columna: transformador
apropiacion_por_sector        → columna: sector
compromisos_pct_por_sector    → columna: sector
obligaciones_pct_por_sector   → columna: sector
pagos_pct_por_sector          → columna: sector
ejecucion_sectorial_entidades → columna: sector
vigencias_futuras             → columna: sector
```

Un error tipográfico en cualquier ETL produciría un sector fantasma sin ninguna advertencia de la BD. Ver sección 4.2.

### 2.4 Cuatro tablas de porcentajes por sector que podrían ser una

Las tablas `apropiacion_por_sector`, `compromisos_pct_por_sector`, `obligaciones_pct_por_sector` y `pagos_pct_por_sector` tienen exactamente la misma clave primaria compuesta `(bitacora_id, vigencia, sector)`. Son cuatro tablas donde una sola resolvería el mismo problema:

```sql
-- Diseño actual (4 tablas):
apropiacion_por_sector(bitacora_id, vigencia, sector, vigente_mmm)
compromisos_pct_por_sector(bitacora_id, vigencia, sector, pct_compromisos)
obligaciones_pct_por_sector(bitacora_id, vigencia, sector, pct_obligaciones)
pagos_pct_por_sector(bitacora_id, vigencia, sector, pct_pagos)

-- Diseño consolidado (1 tabla):
ejecucion_por_sector(bitacora_id, vigencia, sector,
                     vigente_mmm, pct_compromisos, pct_obligaciones, pct_pagos)
```

Esto además eliminaría 3 JOINs en las consultas de la API de Sec 4.

---

## 3. Homologación y normalización de nombres de sectores

### 3.1 El mismo sector con múltiples denominaciones

El sector es la dimensión de análisis más repetida en todas las secciones, pero **cada fuente usa nombres distintos** para el mismo ente:

| Nombre en fuente | Nombre canónico en BD | Fuente del alias |
|---|---|---|
| `AGROPECUARIO` | `AGRICULTURA Y DESARROLLO RURAL` | Versiones históricas SIIF (hasta ~2020) |
| `CIENCIA Y TECNOLOGÍA` / `CIENCIA Y TECNOLOGIA` | `CIENCIA, TECNOLOGÍA E INNOVACIÓN` | Cambio de nombre institucional |
| `COMUNICACIONES` | `TECNOLOGÍAS DE LA INFORMACIÓN Y LAS COMUNICACIONES` | Cambio de nombre ministerio |
| `EMPLEO PUBLICO` | `EMPLEO PÚBLICO` | Falta de tildes en exportaciones SIIF antiguas |
| `PRESIDENCIA DE LA REPUBLICA` | `PRESIDENCIA DE LA REPÚBLICA` | Ídem |
| `CONGRESO DE LA REPUBLICA` | `CONGRESO DE LA REPÚBLICA` | Ídem |
| `JURISDICCION ESPECIAL PARA LA PAZ` | `SISTEMA INTEGRAL DE VERDAD, JUSTICIA, REPARACIÓN Y NO REPETICIÓN` | Cambio de denominación legal |
| `FISCALIA` | `FISCALÍA` | Falta de tilde |
| `REGISTRADURIA` | `REGISTRADURÍA` | Ídem |
| `PLANEACION` | `PLANEACIÓN` | Ídem |
| `INFORMACION ESTADISTICA` | `INFORMACIÓN ESTADÍSTICA` | Ídem |
| `Quindio` | `QUINDÍO` | Falta de tilde en regionalización |

El ETL `load_ejecucion_sectorial.py` implementa este mapeo en `SECTOR_MAP`. Los demás ETLs confían en que SIIF ya envía los nombres canónicos para años recientes.

### 3.2 MAYÚSCULAS vs Título Case en los mismos datos

El archivo de regionalización (`Consolidado Reg-Ejec-Marzo-2022-2026_v_2.0.xlsx`) entrega **cada fila de región duplicada**: una en MAYÚSCULAS (que es el total de la región según el Excel) y otra en Título Case (que el ETL trata como el dato real). Por ejemplo:

```
Fila 1: ANDINA  →  apropiacion=133.44  (total de región calculado por Excel)
Fila 2: Andina  →  apropiacion=133.44  (mismo valor — redundante)
```

El ETL descarta las filas en MAYÚSCULAS (las recalcula como suma de departamentos). Sin embargo, esta doble representación es una característica estructural del archivo que requiere atención en cada nuevo período.

### 3.3 Diferencia en el catálogo de sectores entre secciones

| Sección | N.° sectores | Observación |
|---|---|---|
| Sec 4 (ejecución histórica) | 31 | Incluye histórico 2018–2026 con sectores renombrados |
| Sec 5 (vigencias futuras) | 29 | Sectores activos 2025–2054; no incluye `REGISTRADURÍA`, `INTELIGENCIA` |
| Sec 6 (ejecución sectorial) | ~29–31 | Varía según año del corte |
| Agrupación gráfico Sec 5 | 6 | Consolidación analítica para visualización |

No existe una tabla maestra de sectores que permita unificar estas tres visiones.

---

## 4. Problemas de diseño en el esquema — recomendaciones

### 4.1 Unidad inconsistente en regionalización (`_mm` vs `_mmm`)

**Situación actual:** las tablas `regionalizacion_resumen` y `regionalizacion_detalle_2025` usan el sufijo `_mm` (millones) porque el Excel fuente entrega millones. Todas las demás tablas usan `_mmm` (miles de millones).

**Recomendación:** convertir los valores al cargar (÷ 1 000) y renombrar las columnas a `_mmm` para mantener coherencia. El valor de referencia 2026 para la región ANDINA pasaría de `133.44` (mm) a `0.133` (mmm), que es la representación correcta en la escala usada por la app.

```sql
-- Antes:
apropiacion_mm  DECIMAL(14,3)   -- 133.440 (millones)

-- Después (recomendado):
apropiacion_mmm DECIMAL(14,3)   -- 0.133 (miles de millones)
```

### 4.2 Ausencia de tabla maestra de sectores

**Situación actual:** el nombre del sector se repite como texto libre en 9 tablas. Un cambio de nombre no se propaga automáticamente.

**Recomendación:** crear una tabla `sectores` que sirva de referencia:

```sql
CREATE TABLE sectores (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre   TEXT UNIQUE NOT NULL,           -- nombre canónico
    alias    TEXT,                           -- nombres alternativos (JSON array)
    activo   BOOLEAN DEFAULT 1
);
```

Y reemplazar las columnas `sector TEXT` por `sector_id INTEGER REFERENCES sectores(id)`. Esto habilita:
- Validación automática de nombres al insertar
- Cambios de nombre sin actualizar 9 tablas
- Consultas de qué sectores tienen datos en cada sección

### 4.3 Columnas de año hardcodeadas en `ejecucion_sectorial_mensual`

**Situación actual:** la tabla tiene columnas fijas con años embebidos en el nombre:

```sql
pct_compromisos_2025   -- semánticamente: "año del corte"
pct_compromisos_2024   -- semánticamente: "año anterior"
```

Para la Bitácora 2026-I (corte marzo 2026), `pct_compromisos_2025` contiene datos de **2026**, lo que es confuso. En la Bitácora 2027-I, ambas columnas quedarán desactualizadas.

**Recomendación:** reemplazar por un diseño con filas por año en lugar de columnas:

```sql
CREATE TABLE ejecucion_sectorial_mensual_v2 (
    bitacora_id   INTEGER REFERENCES metadatos_bitacora(id),
    vigencia      INTEGER NOT NULL,   -- año del dato (2024, 2025, 2026…)
    sector        TEXT    NOT NULL,
    mes           INTEGER NOT NULL,
    tipo          TEXT    NOT NULL,   -- 'actual', 'anterior', 'promedio', 'mejor'
    pct_compromisos  DECIMAL(5,2),
    pct_obligaciones DECIMAL(5,2)
);
```

### 4.4 Cuatro tablas de porcentajes por sector

Ver sección 2.4. Consolidar en una tabla `ejecucion_por_sector` reduciría el esquema de 4 a 1 tabla sin pérdida de información.

### 4.5 Fuente de Sec 2 identificada — ETL pendiente

**Actualización 2026-06-29:** se identificó y analizó el archivo fuente de la Sección 2.

**Archivo fuente:**
```
BASES_BITACORA\2026\Marzo\2. EVOLUCIÓN PRESUPUESTAL\
  └── 2026-03-31Estructura_Evolución PGN y Reg-Ejec-marzo.xlsx
        └── hoja: Evolucion PGN
```

**Hallazgos del análisis:**
- Unidades: **miles de millones de pesos** (declaradas en el propio archivo; no requiere conversión)
- Estructura: 5 años (2022–2026) × 4 fases (Vigente, Compromisos, Obligaciones, Pagos) × 28 conceptos en 3 niveles jerárquicos
- La BD actual solo usa los 4 rubros de nivel 1; el Excel tiene 24 conceptos adicionales de detalle sin explotar
- Año 2026 disponible en el Excel pero **no cargado en la BD** (seed_data solo cubre 2022–2025)
- Problemas de calidad: fila duplicada (F34=F35, ambas "Inversión") y error tipográfico en "Serivicio de la Deuda Pública Interna" (F28)
- Los valores de Inversión y Servicio de la Deuda del seed coinciden con el Excel; Funcionamiento y Total difieren porque el seed proviene de la Bitácora 2025-I (corte distinto)

**Situación actual:** los datos de `evolucion_presupuestal` siguen cargándose desde `seed_data.py` con valores hardcodeados. No existe aún un ETL para esta sección.

**Recomendación:** crear `etl/load_evolucion_presupuestal.py` siguiendo el patrón de los demás ETLs de Excel. La lectura es directa (sin conversión de unidades); el único preprocesamiento es omitir la fila duplicada F35, las filas de porcentaje (F6, F8, F22, F33) y el sub-encabezado (F9). Ver sección 7 de `docs/2. Integracion_datos_evolucion_presupuestal.md` para la especificación detallada.

### 4.6 `inv_pct_pib` e `inv_pct_gasto_total` sin fuente ETL

Las columnas `inv_pct_pib` e `inv_pct_gasto_total` en `ejecucion_historica` se cargan como `NULL` por el ETL. Los valores de referencia vienen hardcodeados en `seed_data.py` y no existe un archivo fuente identificado para calcularlos automáticamente.

El PIB constante está disponible en `deflactores_pib`, lo que permite calcular `inv_pct_pib` directamente en SQL:

```sql
UPDATE ejecucion_historica eh
SET inv_pct_pib = (
    SELECT ROUND(eh.vigente_mmm / d.pib_constante_mmm * 100, 2)
    FROM deflactores_pib d
    WHERE d.bitacora_id = eh.bitacora_id AND d.anio = eh.vigencia
)
WHERE inv_pct_pib IS NULL;
```

---

## 5. Precios corrientes vs constantes — gestión del precio base

### 5.1 Estado actual por tabla

| Tabla | Tipo de precio | Base |
|---|---|---|
| Todas las tablas de ejecución | Corrientes | Año del dato (heterogéneo) |
| `vigencias_futuras` | Corrientes | Año del dato (2025–2054) |
| `deflactores_pib` | Constantes | 2026 |
| Gráfico Sec 5 (generado en API) | Constantes | 2026 |
| `seed_data.py` — datos Sec 1 y 2 | Corrientes | 2025 |

### 5.2 Decisión de diseño adoptada para Sec 5

La deflactación **no se realiza en el ETL** sino en la capa de API, mediante JOIN con `deflactores_pib`. Esto permite:
- Cambiar el año base de deflactación sin re-correr el ETL
- Consultar valores corrientes y constantes desde la misma BD
- Auditar el proceso de deflactación en SQL transparente

Esta misma arquitectura podría aplicarse a otras secciones si en el futuro se requiere presentar series históricas en precios constantes.

### 5.3 Precio base cambiante entre bitácoras

La Bitácora 2025-I usaba `constantes 2025`; la Bitácora 2026-I usa `constantes 2026`. Esto implica que los valores absolutos del gráfico de Sec 5 **no son comparables entre bitácoras** sin re-deflactar. La columna `deflactor` en `deflactores_pib` almacena la cadena completa de factores, lo que permite calcular cualquier año base.

---

## 6. Patrones estructurales de los archivos Excel fuente

Los archivos Excel fuente de la Bitácora comparten varios patrones recurrentes:

### 6.1 Archivos con hojas de tipo "resumen pivot" + "base transaccional"

| Archivo | Hoja transaccional | Hoja pivot/resumen |
|---|---|---|
| VF `20260513 Nueva Base VF.xlsx` | `BASE_SIIF_2` | `TD BITACORA` |
| Inversiones PND `Inversiones 2026.xlsx` | `Base` | `% part. por Transformación`, `Ejecución transformaciones` |
| Ejecución `BASE DETALLE MENSUAL.xlsx` | `BASE` | (no identificada) |

**Recomendación:** siempre leer la hoja transaccional y derivar los resúmenes en el ETL, no confiar en las hojas pivot (que pueden tener filtros activos no evidentes).

### 6.2 Filas de encabezado no siempre en la fila 1

| Archivo | Fila del encabezado | Filas previas |
|---|---|---|
| Regionalización | Fila 3 | 2 filas de metadata (título, período) |
| VF `TD BITACORA` | Fila 7 | 6 filas de filtros de tabla dinámica |
| Inversiones PND | Fila 1 | Ninguna |
| Ejecución sectorial | Fila 1 | Ninguna |

Los ETLs de regionalización y VF usan detección dinámica de la fila de encabezado (buscando palabras clave). Esta estrategia es más robusta que asumir un número de fila fijo.

### 6.3 Nombre de columna con espacios residuales

En `BASE_SIIF_2`, la columna de valores se llama `'Valor_VF_Final (Actual) '` (con espacio al final). El ETL maneja esto con:

```python
VAL_C = SC.get('Valor_VF_Final (Actual)') or SC.get('Valor_VF_Final (Actual) ')
```

**Recomendación:** aplicar siempre `.strip()` a todos los nombres de columna al construir el diccionario de índices, como práctica estándar en todos los ETLs futuros.

### 6.4 Valores monetarios como texto con formato regional

En algunas celdas los números aparecen como texto con formato colombiano:
`"1.234.567,89"` (punto para miles, coma para decimales)

El patrón de conversión adoptado:
```python
s.replace('.', '').replace(',', '.')  # → "1234567.89"
```

Puede producir resultados incorrectos si el valor tiene solo parte decimal (p.ej. `"0,89"` → `"089"` → `89.0`). La implementación actual asume que no hay valores menores a 1 000 con separador de miles, lo cual es válido para cifras presupuestales pero debe verificarse en cada nueva fuente.

---

## 7. Mapa de fuentes vs tablas de BD

Resumen de la trazabilidad fuente → tabla para la Bitácora 2026-I:

| Sección | Fuente Excel | Hoja | ETL | Tablas BD |
|---|---|---|---|---|
| Sec 1 | `Inversiones 2026 - PND 2022-2026.xlsx` | `Base`, `Ejecución transformaciones` | `load_bitacora_excel.py` | `inversion_transformaciones`, `inversion_componentes_pnd`, `ejecucion_transformaciones` |
| Sec 2 | `2026-03-31Estructura_Evolución PGN y Reg-Ejec-marzo.xlsx` *(fuente identificada; ETL pendiente)* | `Evolucion PGN` | `seed_data.py` (hardcoded) | `evolucion_presupuestal` |
| Sec 3 | `Consolidado Reg-Ejec-Marzo-2022-2026_v_2.0.xlsx` (`sectores_por_region` se lee de la versión sin sufijo) | `Regionalizacion Mar-2022-2026`, `sectores_por_region` | `load_regionalizacion.py`, `load_sectores_region.py` | `regionalizacion`, `regionalizacion_sectores` |
| Sec 4 | `BASE DETALLE MENSUAL INVERSIÓN 2018-2026.xlsx` | `BASE` | `load_ejecucion_sectorial.py` | `ejecucion_historica`, `apropiacion_por_sector`, `compromisos_pct_por_sector` |
| Sec 5 | `20260513 Nueva Base VF - Validada.xlsx` | `BASE_SIIF_2`, `TD BITACORA` | `load_vigencias_futuras.py` | `vigencias_futuras`, `deflactores_pib` |
| Sec 6 | `BASE DETALLE MENSUAL INVERSIÓN 2018-2026.xlsx` | `BASE` | `load_ejecucion_sectorial.py` | `ejecucion_sectorial_entidades`, `ejecucion_sectorial_mensual` |

---

## 8. Resumen de acciones recomendadas

### Prioridad alta (impactan calidad de datos o mantenibilidad)

| # | Acción | Tablas afectadas | Esfuerzo |
|---|---|---|---|
| 1 | Estandarizar unidades de regionalización de `_mm` a `_mmm` | `regionalizacion_resumen`, `regionalizacion_detalle_2025` | Medio |
| 2 | Crear `etl/load_evolucion_presupuestal.py` desde `2026-03-31Estructura_Evolución PGN y Reg-Ejec-marzo.xlsx` (fuente identificada) | `evolucion_presupuestal` | Medio |
| 3 | Calcular `inv_pct_pib` automáticamente desde `deflactores_pib` | `ejecucion_historica` | Bajo |
| 4 | Aplicar `.strip()` a todos los nombres de columna en ETLs | Todos los ETLs | Bajo |

### Prioridad media (mejoran el modelo de datos)

| # | Acción | Beneficio |
|---|---|---|
| 5 | Consolidar 4 tablas de porcentajes por sector en 1 | Simplifica API y esquema |
| 6 | Rediseñar `ejecucion_sectorial_mensual` con filas por año | Elimina columnas con años hardcodeados |
| 7 | Crear tabla maestra `sectores` con FK en las tablas que lo usan | Valida nombres e integra catálogos |

### Prioridad baja (buenas prácticas para futuras bitácoras)

| # | Acción | Beneficio |
|---|---|---|
| 8 | Siempre leer hoja transaccional, nunca la pivot | Mayor trazabilidad |
| 9 | Documentar la unidad monetaria en la primera fila del Excel fuente | Reduce tiempo de análisis |
| 10 | Extender `deflactores_pib` para cubrir también precios constantes en Sec 4 | Comparabilidad interanual |
