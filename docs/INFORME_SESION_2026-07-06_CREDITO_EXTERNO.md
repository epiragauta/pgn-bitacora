# Informe de Sesión
## Nueva Sección 7: Crédito Externo (SCCI)

**Fecha:** 6 de julio de 2026
**Bitácora:** PGN 2026-I (bitácora_id = 2)
**Fuente de datos:** `BASES_BITACORA/2026/Marzo/8. SCCI/Datos informe II 2026.xlsx` (hojas `Portafolio`, `Ejecución Entidad`, `Comp Ejección Anual Marzo`) y `BITACORA CR EXT.pdf` (contenido de referencia)

---

### 1. OBJETIVO

Incorporar a la Bitácora PGN una nueva sección dedicada al portafolio de Crédito Externo de la Nación, con integración completa de tres capas (base de datos, API y frontend), siguiendo el mismo patrón arquitectónico de las secciones 1 a 6 ya existentes.

---

### 2. RESUMEN EJECUTIVO

Se construyó la **Sección 7 — Crédito Externo**, compuesta por:

1. Un panel introductorio (drawer lateral) con el contexto del crédito externo como fuente de financiación complementaria al PGN (BID, Banco Mundial, CAF) y su relación con los recursos presupuestales 13 y 14.
2. Un bloque de **portafolio de crédito**: KPIs (cartera vigente, total contratado, desembolsado), donut de operaciones por fuente de financiación, gráfico y tabla de créditos/desembolsos por sector — construido a partir de la hoja `Portafolio` (17 operaciones BID/BM/CAF).
3. Un bloque de **ejecución presupuestal** de los recursos de crédito externo (recurso 13 y 14): tabla y gráfico de %Compromisos/%Ejecución/%Pago por entidad ejecutora, y un comparativo histórico 2023-2026 — construido a partir de las hojas `Ejecución Entidad` (18 entidades) y `Comp Ejección Anual Marzo`.

El número de sección (7) fue confirmado con el usuario: la carpeta fuente está numerada "8. SCCI", pero en la app se asignó el siguiente número secuencial disponible, dejando abierto el hueco de la sección "7. SDRT" (aún no desarrollada en la app) para cuando se implemente.

---

### 3. ACTIVIDADES REALIZADAS

#### 3.1 Análisis de la fuente de datos

- Lectura del PDF `BITACORA CR EXT.pdf` para definir el contenido esperado: datos generales del portafolio, créditos y desembolsos por sector, y ejecución presupuestal del recurso 13/14.
- Lectura de las hojas del archivo `Datos informe II 2026.xlsx` (19 hojas en total); identificación de las tres hojas relevantes: `Portafolio` (17 créditos con Nombre, Fuente, Nº Contrato, Monto, Desembolsado, Sector), `Ejecución Entidad` (18 entidades con Apr. inicial/vigente, Compromiso, Obligación, Pago y sus porcentajes) y `Comp Ejección Anual Marzo` (comparativo 2023-2026).
- Verificación cruzada: los totales agregados del Excel (por fuente y por sector) coinciden exactamente con las cifras del PDF — cartera vigente de 17 operaciones, total contratado **$1.316,88 M USD**, desembolsado **$534,03 M USD**.
- Confirmación de que la bitácora activa en la base de datos (`id=2`, corte 2026-03-31) corresponde al mismo corte del Excel de crédito.

#### 3.2 Base de datos

Se agregaron tres tablas nuevas a `db/schema.sql`:

- `credito_portafolio`: una fila por operación de crédito (nombre, fuente, contrato, sector, monto y desembolsado en USD).
- `credito_ejecucion_entidad`: ejecución presupuestal por entidad (apropiación inicial/vigente, compromiso, obligación, pago en miles de millones COP, y sus porcentajes).
- `credito_ejecucion_historica`: comparativo anual 2023-2026 (%Comprometido, %Ejecutado, %Pagado y sus valores absolutos).

#### 3.3 ETL

`etl/load_credito.py` — sigue el mismo patrón de `load_vigencias_futuras.py` (recrea las tablas leyendo el `CREATE TABLE` desde `schema.sql`, luego inserta). Convierte los montos de ejecución presupuestal de pesos crudos a miles de millones (`/1e9`) y las razones (0-1) a porcentaje (`*100`); el portafolio se mantiene en USD, igual que el PDF fuente.

#### 3.4 API

Seis endpoints nuevos bajo el tag `Sec 7 - Crédito Externo` en `api/main.py`: `/api/credito`, `/api/credito/fuentes`, `/api/credito/sectores`, `/api/credito/resumen`, `/api/credito/ejecucion_entidad`, `/api/credito/ejecucion_historica`. Durante las pruebas se detectó y corrigió un error de división entera de SQLite en el cálculo de `% desembolsado` (algunos sectores devolvían 0% en vez del valor real cuando las sumas eran exactas); se corrigió forzando aritmética de punto flotante (`* 100.0`) en ambas consultas afectadas.

#### 3.5 Frontend

- Nuevo enlace "Crédito" en la barra de navegación (el scrollspy existente es genérico y no requirió cambios).
- Nueva sección `#sec7` con: 3 KPIs, donut de operaciones por fuente (BID/BM/CAF) con leyenda, gráfico de barras y tabla de créditos/desembolsos por sector, tabla y gráfico de ejecución por entidad (recurso 13/14), y gráfico de barras horizontales del comparativo histórico 2023-2026.
- Datos embebidos de respaldo (`D.credF`, `D.credS`, `D.credE`, `D.credH`, `D.credResumen`) para el modo sin API, tomados de los valores ya verificados del Excel/PDF.
- Botones de expandir a pantalla completa para cada gráfico/tabla, integrados al sistema existente de modales (`openCardModal`).
- Panel lateral (drawer) con 3 pestañas: Contexto, Indicadores, Fuentes.

#### 3.6 Verificación y pruebas

- Ejecución del ETL contra `db/pgn.db`: 17 filas en `credito_portafolio`, 18 en `credito_ejecucion_entidad`, 4 en `credito_ejecucion_historica`, con verificación de totales coincidentes con el PDF.
- Pruebas de los seis endpoints vía servidor local (`uvicorn`, puerto de prueba efímero), incluyendo la corrección del bug de porcentaje por sector.
- Verificación visual en navegador (Chrome, vía automatización): KPIs, donut, gráficos de barras, tablas, drawer de información (3 pestañas) y modal de pantalla completa — sin errores de consola.

---

### 4. ARCHIVOS CREADOS / MODIFICADOS

| Archivo | Tipo | Cambios |
|---|---|---|
| `db/schema.sql` | Modificado | +46 líneas (3 tablas: `credito_portafolio`, `credito_ejecucion_entidad`, `credito_ejecucion_historica` + índice) |
| `etl/load_credito.py` | Nuevo | 136 líneas |
| `api/main.py` | Modificado | +99 líneas (6 endpoints) |
| `frontend/index.html` | Modificado | +319 líneas (sección 7, drawer, KPIs, gráficos, tablas, modales) |
| `db/pgn.db` | Modificado | datos de las 3 tablas nuevas (17 + 18 + 4 filas) |

---

### 5. COMMITS REALIZADOS

```
11cf45a  Sec 7: agregar sección Crédito Externo (SCCI)
```

Commit creado a pedido explícito del usuario, sin `push` al remoto.

---

### 6. PENDIENTES / PRÓXIMOS PASOS

- La carpeta fuente "7. SDRT" (Sistema de Seguimiento a Proyectos de Regalías o similar, según nomenclatura del cliente) aún no ha sido desarrollada en la app; ocupa el hueco entre la Sección 6 (Ejecución Sectorial) y la Sección 7 (Crédito Externo, numerada así por orden de incorporación y no por el número de su carpeta fuente).
- Evaluar si conviene mostrar también el detalle individual de cada uno de los 17 créditos (nombre completo, contrato, contratante) en una tabla expandible, dado que actualmente solo se exponen agregados por fuente y por sector.
- Confirmar con la fuente si el criterio de "recurso 13 y 14" debe documentarse con mayor detalle en el panel lateral para usuarios no familiarizados con la clasificación presupuestal del SIIF Nación.
