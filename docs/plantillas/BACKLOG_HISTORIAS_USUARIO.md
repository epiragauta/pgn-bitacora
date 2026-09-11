# Backlog de Historias de Usuario — Bitácora de Inversión Pública

- **Proyecto:** Bitácora de Inversión Pública (DNP/DPIP)
- **Formato de criterios:** Gherkin (Dado / Cuando / Entonces). Plantilla en `PLANTILLA_ESPECIFICACION_HISTORIA_USUARIO.md`; pruebas en `PLANTILLA_ESPECIFICACION_PRUEBAS.md`.
- **Fecha:** 2026-08-24
- **Estado:** borrador para refinamiento.

> Este backlog recoge **todas las historias identificables** del sistema actual, para los cuatro roles: usuario del tablero, analista de datos (ETL), administrador/DevOps y desarrollador/integrador. Las cifras están en miles de millones de pesos (mmm) salvo indicación; una «bitácora» es un corte trimestral.

---

## Actores

| Rol | Descripción |
|-----|-------------|
| **Usuario del tablero** | Ciudadano, directivo o analista que consulta la infografía. Sin autenticación. |
| **Analista de datos (DPIP)** | Carga y actualiza las bitácoras trimestrales con el ETL. |
| **Administrador / DevOps** | Despliega, opera, respalda y monitorea el sistema. |
| **Desarrollador / integrador** | Consume la API pública de solo lectura. |

## Épicas

| Épica | Nombre | Rol principal | Historias |
|-------|--------|---------------|-----------|
| EP-00 | Navegación, encabezado y resiliencia | Usuario | HU-001 … HU-007 |
| EP-01 | Sección 1 — Inversiones PND | Usuario | HU-010, HU-011 |
| EP-02 | Sección 2 — Evolución presupuestal | Usuario | HU-020 … HU-025 |
| EP-03 | Sección 3 — Regionalización | Usuario | HU-030 … HU-034 |
| EP-04 | Sección 4 — Ejecución de la inversión | Usuario | HU-040 … HU-042 |
| EP-05 | Sección 5 — Vigencias futuras | Usuario | HU-050, HU-051 |
| EP-06 | Sección 6 — Ejecución sectorial | Usuario | HU-060, HU-061 |
| EP-07 | Sección 7 — Crédito externo | Usuario | HU-070, HU-071 |
| EP-08 | Sección 8 — Sistema General de Participaciones | Usuario | HU-080 … HU-082 |
| EP-09 | Bitácoras y metadatos | Usuario / sistema | HU-090, HU-091 |
| EP-10 | Cargue trimestral (ETL) | Analista de datos | HU-100 … HU-109 |
| EP-11 | Operación y despliegue | Administrador / DevOps | HU-110 … HU-116 |
| EP-12 | API e integración | Desarrollador | HU-120 … HU-123 |
| EP-13 | Calidad y verificación de paridad | QA/Doc · DevOps | HU-130 … HU-132 |

Prioridad en MoSCoW: **M**ust, **S**hould, **C**ould.

---

## EP-00 — Navegación, encabezado y resiliencia

### HU-001 — Ver los indicadores clave del encabezado
**Actor:** Usuario · **Prioridad:** Must · **Trazabilidad:** `GET /api/resumen` → `#hero`

> **Como** usuario del tablero **quiero** ver los indicadores clave de la inversión del año en curso **para** hacerme una idea del estado del presupuesto sin leer toda la página.

```gherkin
Escenario: Encabezado con la bitácora vigente
  Dado que existe al menos una bitácora cargada
  Cuando abro el tablero
  Entonces veo la apropiación vigente del año en curso en billones
  Y veo su porcentaje sobre el PIB y sobre el gasto total
  Y veo compromisos, obligaciones y pagos, cada uno con su porcentaje sobre la apropiación

Escenario: Los porcentajes de ejecución decrecen por etapa
  Dado que veo los indicadores del encabezado
  Entonces el porcentaje de compromisos es mayor o igual al de obligaciones
  Y el de obligaciones es mayor o igual al de pagos
```

### HU-002 — Cambiar de periodo con el selector de bitácoras
**Actor:** Usuario · **Prioridad:** Must · **Trazabilidad:** `GET /api/bitacoras`, `GET /api/bitacoras/{periodo}`

> **Como** usuario **quiero** elegir un corte trimestral distinto **para** comparar cómo evolucionó la ejecución entre periodos.

```gherkin
Escenario: Recarga total al cambiar de corte
  Dado que el tablero muestra la bitácora más reciente
  Cuando selecciono otro periodo en el selector de bitácoras
  Entonces todas las secciones se recargan con las cifras de esa fecha de corte
  Y el encabezado muestra la nueva fecha de corte

Escenario: Selector poblado con los cortes disponibles
  Dado que hay varias bitácoras cargadas
  Cuando abro el selector
  Entonces veo un elemento por cada bitácora, identificado por su periodo
```

### HU-003 — Consultar la explicación metodológica de una sección
**Actor:** Usuario · **Prioridad:** Should · **Trazabilidad:** iconos `i` / modales / panel lateral (`infoTexts`)

> **Como** usuario **quiero** abrir una ventana de ayuda en cada sección **para** entender qué mide, de dónde salen los datos y cómo interpretarlos.

```gherkin
Escenario: Abrir y cerrar la ventana de información
  Dado que estoy en una sección con icono "i"
  Cuando hago clic en el icono
  Entonces se abre una ventana con la explicación metodológica de esa sección
  Y puedo cerrarla con la X, con la tecla Esc o haciendo clic fuera

Escenario: Bloqueo de desplazamiento con la ventana abierta
  Dado que la ventana de información está abierta
  Cuando intento desplazar la página de fondo
  Entonces el fondo no se desplaza hasta cerrar la ventana
```

### HU-004 — Navegar entre las ocho secciones
**Actor:** Usuario · **Prioridad:** Must · **Trazabilidad:** `frontend/index.html` (navegación/anclas)

> **Como** usuario **quiero** recorrer las ocho secciones del tablero **para** encontrar el tema que me interesa.

```gherkin
Escenario: Acceso a cada sección
  Dado que estoy en el tablero
  Cuando selecciono una sección (1 a 8)
  Entonces la vista se posiciona en esa sección y muestra su contenido
```

### HU-005 — Seguir viendo el tablero aunque falle el servidor
**Actor:** Usuario · **Prioridad:** Must · **Trazabilidad:** función `af()` + datos embebidos `D`

> **Como** usuario **quiero** que la página nunca se vea rota **para** poder seguir consultándola aunque haya un problema de conexión.

```gherkin
Escenario: Degradación silenciosa a datos de respaldo
  Dado que la API no responde a una petición
  Cuando el tablero intenta cargar esa sección
  Entonces muestra los datos de respaldo embebidos
  Y no aparece una pantalla de error

Escenario: Preferencia por datos en vivo
  Dado que la API responde correctamente
  Cuando cargo una sección
  Entonces se muestran los datos de la API y no los de respaldo
```

### HU-006 — Conocer la fecha de corte y el origen del dato
**Actor:** Usuario · **Prioridad:** Should · **Trazabilidad:** `GET /api/resumen`, `/api/bitacoras`, pie de página

> **Como** usuario **quiero** ver la fecha de corte de la bitácora y las fuentes **para** saber a qué momento corresponden las cifras.

```gherkin
Escenario: Fecha de corte visible
  Dado que consulto una bitácora
  Entonces veo su fecha de corte en el encabezado y/o al pie
  Y las cifras corresponden a esa fecha
```

### HU-007 — Consultar el tablero en dispositivos móviles
**Actor:** Usuario · **Prioridad:** Should · **Trazabilidad:** CSS responsive de `index.html`

> **Como** usuario **quiero** consultar el tablero desde el celular **para** revisarlo sin un computador.

```gherkin
Escenario: Adaptación a pantalla estrecha
  Dado que abro el tablero en una pantalla angosta
  Entonces el contenido se reorganiza sin desbordar horizontalmente
  Y los gráficos y el mapa siguen siendo legibles y utilizables
```

---

## EP-01 — Sección 1 · Inversiones PND

### HU-010 — Ver la distribución por transformaciones del PND
**Actor:** Usuario · **Prioridad:** Must · **Trazabilidad:** `GET /api/transformaciones` → `#sec1`

> **Como** usuario **quiero** ver cuánto se asignó a cada transformación del PND 2022-2026 **para** entender las prioridades de la inversión.

```gherkin
Escenario: Reparto por transformación
  Dado que consulto la sección 1
  Entonces veo cada transformación con su monto vigente y su porcentaje del total
  Y la suma de los porcentajes es 100 %
```

### HU-011 — Desglosar los componentes de una transformación
**Actor:** Usuario · **Prioridad:** Should · **Trazabilidad:** `GET /api/transformaciones/{transformador}/componentes`

> **Como** usuario **quiero** desplegar los componentes de una transformación **para** ver en qué se concreta.

```gherkin
Escenario: Top 5 componentes más "Otros"
  Dado que veo la lista de transformaciones
  Cuando hago clic en una transformación
  Entonces se despliegan sus cinco componentes principales
  Y el resto se agrupa como "Otros componentes"
```

---

## EP-02 — Sección 2 · Evolución presupuestal

### HU-020 — Ver la evolución del PGN 2022-2026
**Actor:** Usuario · **Prioridad:** Must · **Trazabilidad:** `GET /api/evolucion` → `#sec2`

> **Como** usuario **quiero** ver el PGN por año desglosado en Funcionamiento, Inversión y Servicio de la Deuda **para** entender cómo cambió su tamaño y composición.

```gherkin
Escenario: Barras apiladas por componente
  Dado que consulto la sección 2
  Entonces veo una barra por vigencia (2022 a 2026)
  Y cada barra se compone de Funcionamiento, Inversión y Servicio de la Deuda
```

### HU-021 — Ver composición, tasa de ejecución y % del PIB
**Actor:** Usuario · **Prioridad:** Should · **Trazabilidad:** `/composicion`, `/tasa_ejecucion`, `/pct_pib`

> **Como** usuario **quiero** ver la composición, la tasa de ejecución y el peso sobre el PIB **para** analizar la evolución más allá del monto.

```gherkin
Escenario: Indicadores derivados por año
  Dado que consulto la sección 2 para un año
  Entonces veo la composición porcentual del gasto
  Y la tasa de ejecución
  Y el porcentaje sobre el PIB
```

### HU-022 — Explorar la tabla completa por concepto, año y fase
**Actor:** Usuario · **Prioridad:** Should · **Trazabilidad:** `/api/evolucion/tabla_completa`

> **Como** usuario **quiero** abrir la tabla completa del PGN **para** consultar el detalle por concepto, año y fase.

```gherkin
Escenario: Tabla ampliada
  Dado que estoy en la sección 2
  Cuando abro la tabla detallada
  Entonces veo todos los conceptos por año y por fase (Vigente, Comprometido, Obligado, Pagado)
  Y la tabla se muestra en una ventana ampliada
```

### HU-023 — Desglosar la jerarquía de conceptos (drilldown)
**Actor:** Usuario · **Prioridad:** Could · **Trazabilidad:** `/api/evolucion/drilldown`

> **Como** usuario **quiero** desglosar un concepto en sus subconceptos **para** llegar al detalle que me interesa.

```gherkin
Escenario: Descenso por el árbol de conceptos
  Dado que veo un concepto de nivel superior
  Cuando lo expando para un año y una fase
  Entonces veo sus subconceptos hijos con sus valores
```

### HU-024 — Ver anotaciones de eventos presupuestales
**Actor:** Usuario · **Prioridad:** Could · **Trazabilidad:** anotaciones en gráficas (Chart.js)

> **Como** usuario **quiero** ver marcados los eventos (adiciones, recortes, récords) **para** entender los saltos de la serie.

```gherkin
Escenario: Anotación sobre la serie
  Dado que veo la gráfica de evolución
  Entonces los eventos presupuestales relevantes aparecen anotados sobre la serie
```

### HU-025 — Ver la inversión histórica y su ejecución
**Actor:** Usuario · **Prioridad:** Should · **Trazabilidad:** `/api/evolucion/inversion_historica`

> **Como** usuario **quiero** ver la serie de % de compromisos, obligaciones, pagos y % del PIB **para** comparar la ejecución de la inversión entre vigencias.

```gherkin
Escenario: Serie de ejecución de la inversión
  Dado que consulto la sección 2
  Entonces veo por vigencia el % de compromisos, obligaciones y pagos
  Y el porcentaje de la inversión sobre el PIB
```

---

## EP-03 — Sección 3 · Regionalización

### HU-030 — Explorar el mapa interactivo de Colombia
**Actor:** Usuario · **Prioridad:** Must · **Trazabilidad:** `GET /api/regionalizacion/mapa`, GeoJSON, Leaflet → `#sec3`

> **Como** usuario **quiero** ver un mapa coloreado por la variable de ejecución **para** identificar de un vistazo la distribución territorial.

```gherkin
Escenario: Mapa coloreado
  Dado que consulto la sección 3
  Entonces veo el mapa de Colombia con cada departamento coloreado según la variable seleccionada
  Y existe una leyenda que explica la escala de color

Escenario: Capas del mapa presentes
  Dado que se cargan los GeoJSON de departamentos y regiones
  Cuando se renderiza el mapa
  Entonces las capas se dibujan (el mapa no queda en blanco)
```

### HU-031 — Ver el detalle de un departamento
**Actor:** Usuario · **Prioridad:** Should · **Trazabilidad:** `GET /api/regionalizacion/departamento/{codigo_dane}`

> **Como** usuario **quiero** hacer clic en un departamento **para** ver su serie histórica y sus cifras de ejecución.

```gherkin
Escenario: Panel lateral del departamento
  Dado que veo el mapa
  Cuando hago clic en un departamento
  Entonces se abre un panel lateral con su serie histórica y su ejecución

Escenario: Código DANE con cero a la izquierda
  Dado un departamento cuyo código DANE inicia en cero (p. ej. "05")
  Cuando consulto su detalle
  Entonces el código se maneja como texto y devuelve el departamento correcto
```

### HU-032 — Desglosar una región en departamentos y sectores
**Actor:** Usuario · **Prioridad:** Should · **Trazabilidad:** `/api/regionalizacion/historico`, `/sectores`

> **Como** usuario **quiero** hacer clic en una región **para** ver los departamentos que la componen y sus principales sectores.

```gherkin
Escenario: Desglose regional
  Dado que veo las regiones
  Cuando selecciono una región
  Entonces veo sus departamentos y los principales sectores de inversión
```

### HU-033 — Distinguir "Por regionalizar" y "Nacional"
**Actor:** Usuario · **Prioridad:** Should · **Trazabilidad:** `/api/regionalizacion`

> **Como** usuario **quiero** que los recursos "Por regionalizar" y "Nacional" se muestren aparte **para** que no distorsionen la comparación entre regiones.

```gherkin
Escenario: Categorías separadas
  Dado que consulto la regionalización
  Entonces "Por regionalizar" y "Nacional" aparecen como categorías separadas
  Y no se suman dentro de ninguna región geográfica
```

### HU-034 — Cambiar la variable de coloreo del mapa
**Actor:** Usuario · **Prioridad:** Could · **Trazabilidad:** `/api/regionalizacion/mapa` (parámetro de variable)

> **Como** usuario **quiero** elegir qué variable colorea el mapa **para** analizar distintas dimensiones (apropiación, % de compromisos).

```gherkin
Escenario: Recoloreo del mapa
  Dado que veo el mapa
  Cuando cambio la variable seleccionada
  Entonces el mapa se recolorea según la nueva variable y actualiza la leyenda
```

---

## EP-04 — Sección 4 · Ejecución de la inversión

### HU-040 — Ver la serie histórica de ejecución
**Actor:** Usuario · **Prioridad:** Must · **Trazabilidad:** `GET /api/ejecucion` → `#sec4`

> **Como** usuario **quiero** ver compromisos, obligaciones y pagos frente a la apropiación **para** medir el avance de la ejecución.

```gherkin
Escenario: Serie de ejecución
  Dado que consulto la sección 4
  Entonces veo por vigencia la apropiación y los % de compromisos, obligaciones y pagos
```

### HU-041 — Alternar métricas de ejecución por sector
**Actor:** Usuario · **Prioridad:** Should · **Trazabilidad:** `/api/ejecucion/sectores/{apropiacion,compromisos_pct,obligaciones_pct,pagos_pct}`

> **Como** usuario **quiero** cambiar entre las distintas métricas por sector **para** comparar la ejecución sectorial en la dimensión que me interese.

```gherkin
Escenario: Cambio de métrica
  Dado que veo la ejecución por sector
  Cuando selecciono otra métrica (apropiación / % compromisos / % obligaciones / % pagos)
  Entonces el gráfico se actualiza con esa métrica manteniendo el orden por sector
```

### HU-042 — Ver la matriz sector × vigencia
**Actor:** Usuario · **Prioridad:** Could · **Trazabilidad:** `/api/ejecucion/sectores/matriz` (servicio `MatrizSectores`)

> **Como** usuario **quiero** ver una matriz completa por sector y vigencia **para** analizar la evolución sectorial en una sola vista.

```gherkin
Escenario: Matriz completa
  Dado que abro la matriz de ejecución
  Entonces veo una fila por sector y una columna por vigencia con su valor correspondiente
```

---

## EP-05 — Sección 5 · Vigencias futuras

### HU-050 — Ver las vigencias futuras a precios constantes
**Actor:** Usuario · **Prioridad:** Must · **Trazabilidad:** `GET /api/vigencias_futuras/chart` (servicio `VigenciasFuturasChart`) → `#sec5`

> **Como** usuario **quiero** ver los compromisos de vigencias futuras en pesos constantes de 2026 **para** comparar años distintos de forma homogénea.

```gherkin
Escenario: Series deflactadas
  Dado que consulto la sección 5
  Entonces veo los cinco sectores de mayor peso y el resto agrupado
  Y los valores están en pesos constantes de 2026 (deflactados por el PIB del año)

Escenario: Horizonte de proyección
  Dado que consulto las vigencias futuras
  Entonces la serie llega hasta el horizonte previsto (hasta 2040 en la vista)
```

### HU-051 — Ver el peso sobre el PIB y los totales
**Actor:** Usuario · **Prioridad:** Should · **Trazabilidad:** `/api/vigencias_futuras/totales`

> **Como** usuario **quiero** ver el total por año y su porcentaje sobre el PIB proyectado **para** dimensionar el compromiso futuro.

```gherkin
Escenario: Totales y % del PIB
  Dado que consulto la sección 5
  Entonces veo el total de vigencias futuras por año
  Y su porcentaje sobre el PIB proyectado
```

---

## EP-06 — Sección 6 · Ejecución sectorial

### HU-060 — Comparar la curva mensual contra referencias
**Actor:** Usuario · **Prioridad:** Must · **Trazabilidad:** `/api/sectorial/mensual`, `/historico`

> **Como** usuario **quiero** ver la curva mensual de ejecución comparada con el año anterior, el promedio del cuatrienio y el mejor año **para** distinguir un rezago real de la estacionalidad normal del gasto.

```gherkin
Escenario: Curva mensual con referencias
  Dado que consulto un sector en la sección 6
  Entonces veo su curva mensual del año en curso
  Y las curvas de comparación: año anterior, promedio del cuatrienio y mejor año de la serie
```

### HU-061 — Ver entidades de un sector y su detalle
**Actor:** Usuario · **Prioridad:** Should · **Trazabilidad:** `/api/sectorial`

> **Como** usuario **quiero** desglosar un sector en sus entidades ejecutoras **para** ver quién ejecuta y cómo.

```gherkin
Escenario: Sector → entidades → detalle
  Dado que veo los sectores
  Cuando hago clic en un sector
  Entonces veo sus entidades ejecutoras
  Y al hacer clic en una entidad veo su detalle completo
```

---

## EP-07 — Sección 7 · Crédito externo

### HU-070 — Ver el portafolio de crédito por fuente y sector
**Actor:** Usuario · **Prioridad:** Must · **Trazabilidad:** `/api/credito/fuentes`, `/sectores`, `/resumen` → `#sec7`

> **Como** usuario **quiero** ver el portafolio de crédito con la banca multilateral (BID, Banco Mundial, CAF) **para** conocer montos contratados y desembolsados por fuente y sector.

```gherkin
Escenario: Portafolio en dólares
  Dado que consulto la sección 7
  Entonces veo los montos contratados y desembolsados en dólares
  Y agrupados por fuente (BID, Banco Mundial, CAF) y por sector
```

### HU-071 — Ver la ejecución presupuestal de los recursos de crédito
**Actor:** Usuario · **Prioridad:** Should · **Trazabilidad:** `/api/credito/ejecucion_entidad`, `/ejecucion_historica`

> **Como** usuario **quiero** ver la ejecución en pesos de los recursos de crédito (recursos 13 y 14) por entidad **para** seguir su uso presupuestal.

```gherkin
Escenario: Ejecución por entidad
  Dado que consulto la sección 7
  Entonces veo la ejecución presupuestal en pesos de los recursos de crédito por entidad
```

---

## EP-08 — Sección 8 · Sistema General de Participaciones

### HU-080 — Ver el histórico de participaciones del SGP
**Actor:** Usuario · **Prioridad:** Must · **Trazabilidad:** `/api/sgp/historico` → `#sec8`

> **Como** usuario **quiero** ver las transferencias del SGP 2022-2026 por participación **para** entender el panorama de la inversión territorial fuera del PGN.

```gherkin
Escenario: Histórico por participación
  Dado que consulto la sección 8
  Entonces veo las participaciones (educación, salud, agua potable, propósito general) por año
  Y se indica que el SGP no hace parte del PGN
```

### HU-081 — Ver la desagregación por componente
**Actor:** Usuario · **Prioridad:** Should · **Trazabilidad:** `/api/sgp/historico_componentes`

> **Como** usuario **quiero** desagregar cada participación en sus componentes **para** ver el detalle de las transferencias.

```gherkin
Escenario: Componentes del SGP
  Dado que consulto la sección 8
  Cuando abro la desagregación por componente
  Entonces veo el detalle por componente de cada participación
```

### HU-082 — Ver el resumen de crecimiento del SGP
**Actor:** Usuario · **Prioridad:** Could · **Trazabilidad:** `/api/sgp/resumen` (servicio `SgpResumen`)

> **Como** usuario **quiero** ver el crecimiento interanual y acumulado del SGP **para** dimensionar su evolución.

```gherkin
Escenario: Crecimiento y acumulado
  Dado que consulto la sección 8
  Entonces veo el crecimiento interanual y el acumulado del SGP
```

---

## EP-09 — Bitácoras y metadatos

### HU-090 — Listar las bitácoras disponibles
**Actor:** Usuario / sistema · **Prioridad:** Must · **Trazabilidad:** `GET /api/bitacoras`

> **Como** usuario **quiero** conocer las bitácoras disponibles **para** elegir el corte que quiero consultar.

```gherkin
Escenario: Listado de bitácoras
  Cuando solicito la lista de bitácoras
  Entonces recibo cada bitácora con su periodo y su fecha de corte
  Y están ordenadas de la más reciente a la más antigua
```

### HU-091 — Consultar una bitácora por periodo
**Actor:** Usuario / sistema · **Prioridad:** Should · **Trazabilidad:** `GET /api/bitacoras/{periodo}`

> **Como** usuario **quiero** consultar una bitácora por su periodo **para** enlazar directamente a un corte específico.

```gherkin
Escenario: Consulta por periodo existente
  Dado que existe la bitácora del periodo solicitado
  Cuando la consulto por su periodo
  Entonces recibo sus metadatos

Escenario: Periodo inexistente
  Dado que no existe una bitácora para el periodo solicitado
  Cuando la consulto
  Entonces recibo una respuesta que indica que no existe (sin error del servidor)
```

---

## EP-10 — Cargue trimestral (ETL)

### HU-100 — Crear una bitácora y cargar sus secciones base
**Actor:** Analista de datos · **Prioridad:** Must · **Trazabilidad:** `etl/load_bitacora_excel.py`

> **Como** analista **quiero** crear la bitácora del trimestre y cargar las secciones 1, 4, 5 y 6 **para** iniciar un nuevo corte.

```gherkin
Escenario: Alta de la bitácora
  Dado los Excel del corte y los parámetros (número, periodo, fecha de corte)
  Cuando ejecuto el cargador de la bitácora
  Entonces se crea el registro en metadatos_bitacora
  Y las tablas de las secciones que carga quedan asociadas a su bitacora_id
```

### HU-101 — Cargar la evolución presupuestal (Sección 2)
**Actor:** Analista de datos · **Prioridad:** Must · **Trazabilidad:** `etl/importar_pgn.py`, `data/evolucion_presupuestal.csv`

> **Como** analista **quiero** cargar la evolución presupuestal del PGN **para** actualizar la serie 2022-2026 de la sección 2.

```gherkin
Escenario: Recarga de conceptos y hechos
  Dado el archivo de evolución presupuestal actualizado
  Cuando ejecuto el cargador de la sección 2
  Entonces se recargan los conceptos y los hechos por año y fase
  Y el total del PGN del año corresponde a la fuente
```

### HU-102 — Cargar regionalización y sectores por región
**Actor:** Analista de datos · **Prioridad:** Must · **Trazabilidad:** `etl/load_regionalizacion.py`, `etl/load_sectores_region.py`

> **Como** analista **quiero** cargar la regionalización y sus sectores **para** alimentar el mapa y el desglose regional.

```gherkin
Escenario: Carga regional con tildes preservadas
  Dado el Excel de regionalización
  Cuando ejecuto los cargadores de la sección 3
  Entonces las regiones acentuadas (PACÍFICO, ORINOQUÍA) se conservan sin fusionarse
```

### HU-103 — Cargar la ejecución sectorial
**Actor:** Analista de datos · **Prioridad:** Must · **Trazabilidad:** `etl/load_ejecucion_sectorial.py`

> **Como** analista **quiero** cargar la ejecución sectorial y mensual **para** alimentar las secciones 4 y 6.

```gherkin
Escenario: Tope de vigencia según el corte
  Dado un Excel maestro que incluye vigencias posteriores al corte
  Cuando ejecuto el cargador de ejecución sectorial
  Entonces solo se cargan filas hasta la vigencia propia de la bitácora
  Y no se cuelan vigencias futuras al corte
```

### HU-104 — Cargar las vigencias futuras después del cargador base
**Actor:** Analista de datos · **Prioridad:** Must · **Trazabilidad:** `etl/load_vigencias_futuras.py`

> **Como** analista **quiero** cargar las vigencias futuras con su fuente autoritativa **para** que reemplace la carga parcial previa.

```gherkin
Escenario: Autoritativo sobre la carga parcial
  Dado que ya corrió el cargador base de la bitácora
  Cuando ejecuto el cargador dedicado de vigencias futuras
  Entonces la carga dedicada (29 sectores, 2025-2054) reemplaza a la parcial previa
```

### HU-105 — Cargar crédito externo y SGP
**Actor:** Analista de datos · **Prioridad:** Should · **Trazabilidad:** `etl/load_credito.py`, `etl/load_sgp.py`, `etl/load_sgp_componentes.py`

> **Como** analista **quiero** cargar crédito externo y SGP **para** completar las secciones 7 y 8.

```gherkin
Escenario: Carga de las secciones 7 y 8
  Dado los Excel de SCCI y SGP
  Cuando ejecuto los cargadores de crédito y SGP
  Entonces las secciones 7 y 8 quedan pobladas para la bitácora en curso
```

### HU-106 — Respetar el orden de ejecución del ETL
**Actor:** Analista de datos · **Prioridad:** Must · **Trazabilidad:** `MANUAL_OPERACION.md`

> **Como** analista **quiero** ejecutar los cargadores en el orden documentado **para** no romper dependencias entre secciones.

```gherkin
Escenario: Orden con la bitácora primero
  Dado un cargue nuevo
  Cuando ejecuto los cargadores
  Entonces primero corre el que crea la bitácora
  Y las vigencias futuras corren después del cargador base
```

### HU-107 — Validar la carga comparando dos bases
**Actor:** Analista de datos · **Prioridad:** Should · **Trazabilidad:** `tools/compare_bd.py`

> **Como** analista **quiero** contrastar la base cargada contra una de referencia **para** confirmar que las cifras coinciden antes de publicar.

```gherkin
Escenario: Conteos y sumas iguales
  Dado dos bases para un mismo periodo
  Cuando ejecuto la comparación por bitácora
  Entonces los conteos por tabla coinciden
  Y la suma de cada columna numérica coincide dentro de la tolerancia
```

### HU-108 — Evitar duplicados y registrar avisos en el upsert
**Actor:** Analista de datos · **Prioridad:** Should · **Trazabilidad:** `etl/db.py` (`upsert`)

> **Como** analista **quiero** que el cargador deduplique por clave y avise **para** no romper restricciones ni perder trazabilidad de claves repetidas en el origen.

```gherkin
Escenario: Deduplicación por clave
  Dado un lote con claves repetidas
  Cuando el cargador hace upsert
  Entonces conserva la última fila por clave
  Y registra un aviso de las filas descartadas
```

### HU-109 — Localizar los Excel por patrón de nombre
**Actor:** Analista de datos · **Prioridad:** Should · **Trazabilidad:** `etl/bases.py`

> **Como** analista **quiero** que el ETL encuentre los Excel por patrón **para** no editar rutas cada trimestre cuando cambian los nombres.

```gherkin
Escenario: Resolución por patrón y variable de entorno
  Dado que los archivos del corte están en la carpeta de bases
  Cuando ejecuto un cargador
  Entonces localiza el archivo por patrón dentro de la carpeta de la sección
  Y respeta la ruta indicada por la variable de entorno si está definida
```

---

## EP-11 — Operación y despliegue

### HU-110 — Desplegar el sistema con verificación de salud
**Actor:** Administrador / DevOps · **Prioridad:** Must · **Trazabilidad:** despliegue, `HEALTHCHECK`, `/health`

> **Como** administrador **quiero** desplegar el sistema con un chequeo de salud **para** confirmar que quedó operativo.

```gherkin
Escenario: Despliegue saludable
  Dado el artefacto/imagen y la configuración de producción
  Cuando despliego el sistema
  Entonces el servicio queda activo y saludable
  Y responde 200 en la raíz, en /api/resumen y en /swagger
```

### HU-111 — Servir tablero, API y GeoJSON desde la misma aplicación
**Actor:** Administrador / DevOps · **Prioridad:** Must · **Trazabilidad:** archivos estáticos + MIME `application/geo+json`

> **Como** administrador **quiero** que una sola aplicación sirva el frontend, la API y los GeoJSON **para** simplificar el despliegue.

```gherkin
Escenario: GeoJSON servido correctamente
  Dado el sistema desplegado
  Cuando solicito dptos.geojson y regiones.geojson
  Entonces responden 200 con el tipo application/geo+json
  Y el mapa del tablero renderiza sus capas
```

### HU-112 — Publicar con TLS tras el reverse proxy
**Actor:** Administrador / DevOps · **Prioridad:** Must · **Trazabilidad:** reverse proxy, TLS, publicación en loopback

> **Como** administrador **quiero** exponer el sistema solo por el reverse proxy con HTTPS **para** no exponer la aplicación directamente a la red.

```gherkin
Escenario: Acceso solo por HTTPS
  Dado el sistema publicado
  Cuando accedo por HTTP
  Entonces se redirige a HTTPS
  Y la aplicación solo escucha en loopback, no en la interfaz pública
```

### HU-113 — Gestionar credenciales fuera del repositorio
**Actor:** Administrador / DevOps · **Prioridad:** Must · **Trazabilidad:** cadena de conexión por entorno

> **Como** administrador **quiero** inyectar la cadena de conexión por entorno **para** no exponer credenciales en el código.

```gherkin
Escenario: Sin credenciales en el artefacto
  Dado el secreto configurado en el host
  Cuando arranca el servicio
  Entonces lee la cadena de conexión del entorno
  Y no hay credenciales en el artefacto ni en el repositorio
```

### HU-114 — Respaldar y restaurar la base de datos
**Actor:** Administrador / DevOps · **Prioridad:** Should · **Trazabilidad:** política de backup

> **Como** administrador **quiero** respaldar y poder restaurar la base **para** proteger la información ante fallas.

```gherkin
Escenario: Ciclo de respaldo y restauración
  Dado el plan de respaldos definido
  Cuando ejecuto un respaldo y luego una restauración de prueba
  Entonces la base restaurada conserva las cifras y las bitácoras
```

### HU-115 — Reiniciar sin pérdida de datos
**Actor:** Administrador / DevOps · **Prioridad:** Should · **Trazabilidad:** `restart: unless-stopped`, volumen de datos

> **Como** administrador **quiero** que el sistema se reinicie automáticamente **para** recuperarse de caídas sin intervención.

```gherkin
Escenario: Reinicio automático
  Dado el sistema en ejecución
  Cuando el host o el servicio se reinicia
  Entonces el servicio vuelve a quedar saludable
  Y no se pierde ninguna bitácora
```

### HU-116 — Monitorear el estado del servicio
**Actor:** Administrador / DevOps · **Prioridad:** Should · **Trazabilidad:** `/health`, observabilidad

> **Como** administrador **quiero** monitorear la salud del servicio **para** enterarme de una caída sin que la reporte un usuario.

```gherkin
Escenario: Alerta ante caída
  Dado el monitoreo configurado contra /health
  Cuando el servicio deja de responder
  Entonces se genera una alerta verificable
```

---

## EP-12 — API e integración

### HU-120 — Explorar la documentación interactiva de la API
**Actor:** Desarrollador · **Prioridad:** Should · **Trazabilidad:** Swagger en `/swagger`

> **Como** desarrollador **quiero** una documentación interactiva **para** entender y probar los endpoints sin leer el código.

```gherkin
Escenario: Swagger disponible
  Dado el sistema desplegado
  Cuando abro /swagger
  Entonces veo los endpoints agrupados por sección con sus parámetros y puedo probarlos
```

### HU-121 — Consumir los endpoints con bitácora opcional
**Actor:** Desarrollador · **Prioridad:** Must · **Trazabilidad:** `bitacora_id` opcional, `BitacoraResolver`

> **Como** desarrollador **quiero** consultar cualquier endpoint con o sin `bitacora_id` **para** obtener el corte que necesito o el más reciente por defecto.

```gherkin
Escenario: Sin bitácora → la más reciente
  Cuando consulto un endpoint sin bitacora_id
  Entonces recibo los datos de la bitácora más reciente por fecha de corte

Escenario: Con bitácora específica
  Cuando consulto un endpoint con un bitacora_id válido
  Entonces recibo los datos de ese corte
```

### HU-122 — Recibir un contrato JSON estable
**Actor:** Desarrollador · **Prioridad:** Must · **Trazabilidad:** `Data/Db.cs` (diccionarios), serialización sin política de nombres

> **Como** desarrollador **quiero** claves JSON estables en snake_case, nulos explícitos y códigos DANE como texto **para** integrar sin sorpresas de serialización.

```gherkin
Escenario: Claves y tipos estables
  Cuando consumo cualquier endpoint
  Entonces las claves son snake_case exactas iguales a los alias del SQL
  Y los valores nulos se emiten de forma explícita
  Y codigo_dane se emite como texto conservando el cero a la izquierda
```

### HU-123 — Acceder desde otro origen solo por GET
**Actor:** Desarrollador · **Prioridad:** Should · **Trazabilidad:** CORS restringido a GET

> **Como** desarrollador **quiero** consumir la API desde otro origen por GET **para** integrarla en un cliente web, sin métodos de escritura.

```gherkin
Escenario: CORS de solo lectura
  Cuando hago una petición GET desde otro origen
  Entonces la API responde permitiendo el origen
  Y no se permiten métodos de escritura
```

---

## EP-13 — Calidad y verificación de paridad

### HU-130 — Verificar la paridad contra la línea base
**Actor:** QA/Doc · DevOps · **Prioridad:** Must · **Trazabilidad:** `tools/compare_apis.py`, `tools/baseline/`

> **Como** responsable de calidad **quiero** comparar las respuestas contra la línea base congelada **para** garantizar que un cambio no rompió el tablero.

```gherkin
Escenario: Sin diferencias bloqueantes
  Dado el conjunto de rutas y la línea base congelada
  Cuando ejecuto la comparación
  Entonces no hay diferencias de claves, valores ni estado HTTP

Escenario: La línea base no se regenera para ocultar diferencias
  Dado que aparece una diferencia bloqueante
  Cuando investigo la causa
  Entonces corrijo el backend, no regenero la línea base
```

### HU-131 — Enumerar las rutas desde los datos reales
**Actor:** QA/Doc · DevOps · **Prioridad:** Should · **Trazabilidad:** `tools/endpoints.py`

> **Como** responsable de calidad **quiero** derivar las rutas a probar de los datos reales **para** que la cobertura crezca sola al cargar una bitácora nueva.

```gherkin
Escenario: Cobertura derivada de la base
  Dado el estado actual de la base
  Cuando enumero las rutas
  Entonces se generan las rutas con parámetros reales (vigencias, regiones, sectores, códigos DANE, conceptos)
```

### HU-132 — Clasificar las diferencias por tipo
**Actor:** QA/Doc · DevOps · **Prioridad:** Should · **Trazabilidad:** `tools/compare_apis.py`

> **Como** responsable de calidad **quiero** que las diferencias se clasifiquen por tipo **para** distinguir las que rompen el tablero de las inocuas.

```gherkin
Escenario: Orden entre filas empatadas no bloquea
  Dado dos respuestas con las mismas filas en distinto orden por un empate
  Cuando comparo
  Entonces la diferencia se clasifica como "orden" y no bloquea
  Y una diferencia de claves o valores sí bloquea
```

---

## Resumen de cobertura

| Épica | Historias | Rol |
|-------|-----------|-----|
| EP-00 Navegación y resiliencia | 7 | Usuario |
| EP-01 … EP-08 (8 secciones) | 21 | Usuario |
| EP-09 Bitácoras y metadatos | 2 | Usuario / sistema |
| EP-10 Cargue trimestral (ETL) | 10 | Analista de datos |
| EP-11 Operación y despliegue | 7 | Administrador / DevOps |
| EP-12 API e integración | 4 | Desarrollador |
| EP-13 Calidad y paridad | 3 | QA/Doc · DevOps |
| **Total** | **54** | — |

> Para refinar una historia con todos sus campos (estimación, DoR/DoD, trazabilidad detallada) use `PLANTILLA_ESPECIFICACION_HISTORIA_USUARIO.md`. Para especificar sus pruebas use `PLANTILLA_ESPECIFICACION_PRUEBAS.md`.
