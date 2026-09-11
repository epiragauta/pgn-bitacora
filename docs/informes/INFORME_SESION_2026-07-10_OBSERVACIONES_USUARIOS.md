# Informe de Sesión
## Corrección de observaciones de usuarios — Secciones 2, 3, 4 y 6

**Fecha:** 10 de julio de 2026
**Bitácoras afectadas:** PGN 2025-I (bitácora_id = 1) y PGN 2026-I (bitácora_id = 2)
**Commit:** `ad32646` — *"Corregir observaciones de usuarios: Sec 2, 3, 4 y 6"*

---

### 1. OBJETIVO

Revisar y corregir un conjunto de observaciones reportadas por usuarios sobre la Bitácora PGN, relativas a la Sección 4 (Ejecución de la Inversión), Sección 6 (Ejecución Sectorial), la sincronización de los paneles informativos con la bitácora seleccionada, la Sección 2 (Evolución Presupuestal) y la Sección 3 (Regionalización).

---

### 2. RESUMEN EJECUTIVO

Se atendieron seis observaciones, dos de ellas (Evolución Presupuestal y Ejecución Presupuestal) originadas en hallazgos propios durante la investigación de las primeras observaciones reportadas:

1. **Sec 4 — Desfase entre título y datos mostrados:** el título de la sección decía "2022-2026" pero los gráficos y tablas cortaban en 2025.
2. **Sec 4 — Pantalla completa incompleta:** el gráfico "Apropiación top sectores" solo mostraba 6 sectores al ampliarlo, en vez de todos.
3. **Sec 6 — Entidad duplicada:** la "Comisión de Regulación de Agua Potable y Saneamiento Básico (CRA)" y otras 109 entidades aparecían fragmentadas en dos filas en la tabla histórica por diferencias de tildes en su nombre.
4. **Paneles informativos:** varios textos de los paneles laterales mencionaban un rango de años fijo ("2022-2025" o "2025") que no se actualizaba al cambiar de bitácora.
5. **Sec 2 — Evolución Presupuestal:** el total de Funcionamiento no coincidía con la ejecución real del SIIF por un error de suma del rubro Transferencias en la vigencia 2026 (reportado y corregido por el usuario en el archivo fuente).
6. **Sec 3 — Regionalización:** la región Insular (Archipiélago de San Andrés) debía reportarse consolidada dentro de la región Caribe, como "Caribe - Insular".

Durante la investigación de la observación 1 se detectaron y corrigieron además dos problemas de fondo no reportados explícitamente por el usuario: datos de vigencia 2026 filtrados incorrectamente en la bitácora 2025-I, y un endpoint de la API que ignoraba por completo el parámetro de bitácora.

---

### 3. ACTIVIDADES REALIZADAS

#### 3.1 Sección 4 — Ejecución de la Inversión

- Se identificaron cuatro filtros de año hardcodeados en el frontend (`d.y<=2025`, `v<=2025`) en las funciones `_buildMixEjHist`, `_buildAprHist`, `_renderAprHistTbl` y `rHBars`, que truncaban artificialmente los gráficos "Ejecución presupuestal histórica", "Apropiación histórica inversión" y "Apropiación top sectores" a 2025, pese a que la base de datos ya tenía cargados los datos de 2026.
- Se eliminaron esos cortes y se actualizaron las etiquetas estáticas ("2022-2025" → "2022-2026") en tarjetas, modales y el panel informativo de la sección.
- Se refactorizó `rHBars` en `_renderHBars(containerId, mtz, limit)`, permitiendo reutilizar la misma lógica con `limit=6` para la vista compacta y `limit=null` (todos los sectores) para la vista de pantalla completa.

#### 3.2 Sección 6 — Ejecución Sectorial

- Se confirmó que el caso reportado de la CRA no se debía a espacios al final del texto (hipótesis inicial del usuario) sino a **inconsistencia de tildes** entre vigencias: los años 2018-2023 conservaban la grafía con tildes y 2024-2026 la tenían sin tildes, generando dos "entidades" distintas al agrupar por nombre exacto en el frontend.
- Se auditó toda la tabla `ejecucion_sectorial_entidades` y se encontraron **110 entidades** con este patrón en la bitácora 2026-I y **3** en la 2025-I (no solo la CRA).
- Se normalizaron **465 filas**, eligiendo como grafía canónica la variante con más tildes (ortografía correcta) por grupo de (bitácora, sector, nombre sin tildes).
- Se agregó `canonicalize_entidades()` a `etl/load_ejecucion_sectorial.py` para que esta normalización se aplique automáticamente en cada recarga futura, evitando que el problema reaparezca en la próxima bitácora.

#### 3.3 Paneles informativos (drawers)

- Se implementó un motor de plantillas ligero (`_drRender`, variable `_drVars`) que sustituye placeholders `{{V}}` / `{{INV_BILL}}` en los textos de los paneles justo antes de mostrarlos, recalculados en cada `init(bid)` a partir de la bitácora activa.
- Se convirtieron a plantilla dinámica los textos de Sec 1 (vigencia y monto de inversión), Sec 2 (rango histórico), Sec 4 (rango histórico y pregunta de contexto), Sec 5 (año base de precios constantes) y Sec 8 (rango de evolución del SGP).
- Se dejó sin cambios el rango "PND 2022-2026", por tratarse del período fijo del Plan Nacional de Desarrollo y no de una ventana de datos disponibles.
- Verificado alternando entre bitácoras 2026-I y 2025-I: los paneles reflejan correctamente la vigencia y cifras de la bitácora activa en cada caso.

#### 3.4 Hallazgo colateral — Datos de vigencia 2026 en la bitácora 2025-I

- Al revisar la bitácora 2025-I tras el punto 3.1, se detectó que 6 tablas (`ejecucion_historica`, `apropiacion_por_sector` y sus 3 tablas `*_pct_por_sector`, `ejecucion_sectorial_entidades`, `ejecucion_sectorial_mensual`) tenían filas de vigencia 2026 que no debían existir en un corte de marzo de 2025.
- **Causa raíz:** `load_ejecucion_sectorial.py` calculaba el "año actual" (`anio_max`) como el año máximo presente en el Excel maestro acumulativo, en vez de basarse en la vigencia propia de la bitácora que se estaba cargando. Al recargar la bitácora 2025-I el 12 de abril de 2026 con una copia del Excel que ya incluía datos de marzo 2026, el script coló esa vigencia futura.
- Se corrigió el ETL para que tome la vigencia objetivo desde `metadatos_bitacora.corte_fecha` y descarte cualquier fila del Excel posterior a esa vigencia.
- Se limpiaron **676 filas** indebidas en la bitácora 2025-I.
- Adicionalmente se encontró que `/api/ejecucion` (usado por los gráficos de Sec 4) leía de una tabla legada (`pgn_ejecucion`/`pgn_concepto`) sin ninguna columna `bitacora_id`, por lo que **ignoraba completamente** qué bitácora estaba seleccionada. Se reescribió el endpoint para leer de `ejecucion_historica` filtrado por bitácora, con respaldo a la tabla legada solo para los campos `% PIB` / `% gasto total` (que no estaban poblados para la bitácora 2026-I en la tabla nueva), evitando así una regresión visual en la vista por defecto.
- **Nota pendiente:** se detectó que el mismo patrón (lectura de la tabla legada sin filtro de bitácora) afecta también a todos los endpoints de la Sección 2 (`/api/evolucion*`). No se corrigió porque no existe aún un reemplazo bitácora-consciente completo para esos datos (la tabla `evolucion_presupuestal` solo tiene información cargada para la bitácora 2025-I).

#### 3.5 Sección 2 — Evolución Presupuestal

- El usuario identificó que no sumaba correctamente el rubro Transferencias (afectando Apropiación Vigente, Compromisos, Obligaciones y Pagos) en la vigencia 2026, y corrigió el archivo fuente `2026-03-31Estructura_Evolución PGN y Reg-Ejec-marzo.xlsx`.
- Se extrajeron los 28 conceptos × 5 años × 4 fases (560 valores) de la hoja "Evolucion PGN" y se comparó contra los datos vigentes: el único cambio real estaba en la línea "Resto" (dentro de Transferencias → Funcionamiento) de la vigencia 2026, en sus 4 fases, propagándose a Funcionamiento y Total PGN.
- Se verificó que el dato anterior tenía una inconsistencia lógica (Comprometido > Vigente en la línea "Resto"), consistente con el error reportado.
- Se reemplazaron los valores en `data/evolucion_presupuestal.csv` (conservando nombres de concepto, jerarquía y orden) y se recargó `pgn_concepto`/`pgn_ejecucion` con `etl/importar_pgn.py`.
- Se actualizaron en el frontend el dato de respaldo offline (`D.ev`) y la tabla estática "Resumen PGN 2022-2026" (no se llenaba por API) con los valores y porcentajes recalculados.

#### 3.6 Sección 3 — Regionalización

- El usuario indicó que la región Insular (Archipiélago de San Andrés, Providencia y Santa Catalina) debía reportarse consolidada dentro de Caribe, según el archivo `Consolidado Reg-Ejec-Marzo-2022-2026-Graficasvf.xlsx` (que ya no trae una pestaña "Región Insular" separada).
- Se consultó al usuario la etiqueta preferida para la región fusionada; eligió **"CARIBE - INSULAR"**.
- Se renombraron 40 filas en `regionalizacion`, 27 en `regionalizacion_sectores` y 8 en `dane_departamentos` (para ambas bitácoras y todas las vigencias disponibles).
- Se actualizaron `etl/load_regionalizacion.py` (incluida la ruta al archivo fuente, que había cambiado de nombre y ya no existía en disco) y `etl/load_sectores_region.py` para que futuras recargas apliquen la fusión automáticamente.
- Se actualizó el mapeo GeoJSON→región del mapa (para que tanto el polígono continental como el de la Región Insular coloreen y respondan igual), el orden de tarjetas de región y los datos de respaldo offline.
- Verificado en navegador: 5 tarjetas de región (antes 6), "CARIBE - INSULAR" con apropiación 15,6 Bill., y 8 departamentos listados al hacer clic (los 7 del Caribe continental + San Andrés), con cifras idénticas a la captura de referencia del usuario.

#### 3.7 Verificación y pruebas

- Todas las correcciones se probaron levantando instancias locales efímeras de `uvicorn` (puertos de prueba), verificando tanto las respuestas de la API vía `curl` como el comportamiento visual en navegador (Chrome, vía automatización), alternando entre las bitácoras 2025-I y 2026-I donde aplicaba.
- Antes de cada modificación destructiva sobre `db/pgn.db` se generó una copia de respaldo en el directorio temporal de la sesión.

---

### 4. ARCHIVOS MODIFICADOS

| Archivo | Cambios principales |
|---|---|
| `frontend/index.html` | Quitar cortes de año hardcodeados en Sec 4; refactor `_renderHBars`; motor de plantillas de paneles informativos (`_drRender`/`_drVars`); fusión de región Caribe-Insular (mapeo GeoJSON, orden de tarjetas, fallback offline); tabla estática "Resumen PGN" y `D.ev` actualizados |
| `api/main.py` | Reescritura de `/api/ejecucion` para leer `ejecucion_historica` por bitácora con respaldo a `pgn_ejecucion` |
| `etl/load_ejecucion_sectorial.py` | `canonicalize_entidades()`; tope de vigencia según `metadatos_bitacora.corte_fecha` |
| `etl/load_regionalizacion.py` | Fusión Caribe-Insular en `REGION_NORM`; ruta de archivo fuente actualizada |
| `etl/load_sectores_region.py` | Fusión Caribe-Insular en `REGION_NORM` |
| `data/evolucion_presupuestal.csv` | 24 valores corregidos (vigencia 2026, rubro Transferencias/Resto) |
| `db/pgn.db` | Normalización de entidades (Sec 6); limpieza de 676 filas de vigencia 2026 en bitácora 2025-I; recarga de `pgn_concepto`/`pgn_ejecucion`; fusión Caribe-Insular en 3 tablas |

---

### 5. COMMITS REALIZADOS

```
ad32646  Corregir observaciones de usuarios: Sec 2, 3, 4 y 6
```

Commit creado a pedido explícito del usuario, sin `push` al remoto.

---

### 6. PENDIENTES / PRÓXIMOS PASOS

- **Sección 2 sin filtro de bitácora:** todos los endpoints `/api/evolucion*` leen de la tabla legada `pgn_ejecucion`/`pgn_concepto`, que no tiene columna `bitacora_id`. Al seleccionar la bitácora 2025-I, esta sección seguirá mostrando los datos más recientes (2026) en vez de los propios de esa bitácora. Requiere completar `evolucion_presupuestal` para la bitácora 2026-I antes de poder migrar los endpoints.
- **Documentación desactualizada:** `docs/2. Integracion_datos_evolucion_presupuestal.md` (sección 6, "Estado real de implementación") afirma que las tablas `pgn_concepto`/`pgn_ejecucion` no existen; en realidad sí existen y son las que usa la API desde el 27 de junio de 2026. No se corrigió por no haber sido solicitado.
- **Migración histórica sin actualizar:** `db/migrations/003_regionalizacion_multiagno.sql` conserva la clasificación original de `dane_departamentos` (Insular separado de Caribe). No se modificó por tratarse de un script de migración ya aplicado; solo es relevante si se reconstruye la base de datos desde cero.
- **Mojibake preexistente:** se observó que los nombres de región "ORINOQUÍA" y "PACÍFICO" presentan doble codificación UTF-8 en algunas respuestas JSON de la API. Es un problema anterior a esta sesión, no relacionado con las observaciones atendidas; no se corrigió.
