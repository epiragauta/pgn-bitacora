# Especificación de Pruebas de Historias de Usuario — Plantilla

> **Instrucciones para el analista de pruebas / QA**
> Esta plantilla especifica las pruebas que verifican cada historia de usuario del proyecto **Bitácora de Inversión Pública** (DNP/DPIP).
> - Reemplace todo texto entre `⟨ ⟩` por el contenido real. Elimine las notas en _cursiva_ al finalizar.
> - **Una ficha de pruebas por historia de usuario** (`HU-NN` del `BACKLOG_HISTORIAS_USUARIO.md`).
> - Cada **criterio de aceptación (Gherkin)** de la historia debe quedar cubierto por **al menos un caso de prueba**. La cobertura se demuestra en la matriz de trazabilidad (§4.5).
> - Numere los casos como `CP-⟨NN⟩` y manténgalos trazables con la historia, el criterio y el componente de código.
> - Aproveche la red de verificación del proyecto: `tools/compare_apis.py` (paridad de la API contra la línea base), `tools/compare_bd.py` (dos bases tabla por tabla), `tools/endpoints.py` (enumeración de rutas). Muchas pruebas de API se automatizan con ellas.

---

## Portada / control del documento

| Campo | Valor |
|-------|-------|
| Proyecto | Bitácora de Inversión Pública — DNP/DPIP |
| Documento | Especificación de Pruebas de Historias de Usuario |
| Versión | ⟨1.0⟩ |
| Fecha | ⟨AAAA-MM-DD⟩ |
| Autor (QA) | ⟨nombre⟩ |
| Estado | ⟨Borrador / En revisión / Aprobado⟩ |

**Historial de cambios**

| Versión | Fecha | Autor | Descripción |
|---------|-------|-------|-------------|
| ⟨1.0⟩ | ⟨AAAA-MM-DD⟩ | ⟨⟩ | Versión inicial |

---

## 1. Introducción

### 1.1 Propósito
_⟨Definir las pruebas que validan que las historias de usuario se cumplen.⟩_

### 1.2 Alcance
_⟨Qué historias/épicas cubre esta especificación.⟩_

### 1.3 Referencias
_⟨`BACKLOG_HISTORIAS_USUARIO.md`, `PLANTILLA_ESPECIFICACION_HISTORIA_USUARIO.md`, `ARQUITECTURA.md`, `MANUAL_OPERACION.md`, Swagger `/swagger`.⟩_

---

## 2. Estrategia de pruebas

### 2.1 Niveles
| Nivel | Qué valida | Herramienta / técnica |
|-------|------------|-----------------------|
| Aceptación (UI) | Que la historia entrega el valor esperado en el tablero | Manual en navegador / automatización E2E |
| Funcional de API | Respuesta correcta de cada endpoint | Cliente HTTP / Swagger / scripts |
| Paridad / regresión | Que un cambio no altera la respuesta respecto a la línea base | `tools/compare_apis.py --contra-linea-base` |
| Datos (ETL) | Que el cargue reproduce las cifras de la fuente | `tools/compare_bd.py` |
| No funcional | Rendimiento, resiliencia offline, responsive, accesibilidad, seguridad | Según el caso |

### 2.2 Tipos de prueba (etiquetas)
`Funcional` · `Frontera` · `Negativa` · `Regresión` · `Integración` · `Resiliencia` · `Rendimiento` · `Seguridad` · `Datos`.

### 2.3 Entornos y datos
- **Entorno:** ⟨URL de pruebas / local⟩. **Base:** ⟨`dnp_dpip` / `dnp_dpip_pruebas`⟩.
- **Bitácora de referencia:** ⟨periodo y fecha de corte usados como datos base⟩.
- **Regla de oro:** la línea base congelada (`tools/baseline/`) **no se regenera** para hacer desaparecer una diferencia.

### 2.4 Criterios de entrada y salida
- **Entrada:** la historia está «Lista» (DoR), el entorno está desplegado y hay una bitácora cargada.
- **Salida:** todos los casos `Must` pasan; 0 diferencias bloqueantes de paridad; los defectos abiertos están registrados y priorizados.

### 2.5 Convenciones
- **ID de caso:** `CP-⟨NN⟩` (opcionalmente `CP-⟨HU⟩-⟨n⟩`).
- **Prioridad:** Alta / Media / Baja (alineada con la prioridad MoSCoW de la historia).
- **Estado:** `No ejecutado` / `Pasó` / `Falló` / `Bloqueado` / `N/A`.

---

## 3. Ficha de especificación de pruebas por historia

> _Copie esta ficha por cada historia de usuario._

### Pruebas de HU-⟨NN⟩ — ⟨título de la historia⟩

| Atributo | Valor |
|----------|-------|
| **Historia** | HU-⟨NN⟩ |
| **Épica** | ⟨EP-NN⟩ |
| **Objetivo de prueba** | ⟨qué se busca verificar en una frase⟩ |
| **Componente(s)** | ⟨`GET /api/…` · sección `#secN` · `etl/…` · `tools/…`⟩ |
| **Precondiciones generales** | ⟨entorno desplegado; bitácora ⟨periodo⟩ cargada; …⟩ |

**3.1 Escenarios de prueba (Gherkin)** — _derivados de los criterios de aceptación de la historia_

```gherkin
Escenario: ⟨nombre — normalmente coincide con un criterio de aceptación⟩
  Dado ⟨precondición⟩
  Cuando ⟨acción⟩
  Entonces ⟨resultado verificable⟩

Escenario: ⟨caso de frontera o negativo⟩
  Dado ⟨…⟩
  Cuando ⟨…⟩
  Entonces ⟨…⟩
```

**3.2 Casos de prueba (tabla)**

| ID | Título | Tipo | Prioridad | Precondición | Datos de prueba | Pasos | Resultado esperado | Criterio cubierto | Resultado obtenido | Estado |
|----|--------|------|-----------|--------------|-----------------|-------|--------------------|-------------------|--------------------|--------|
| CP-⟨NN⟩ | ⟨título⟩ | ⟨Funcional⟩ | ⟨Alta⟩ | ⟨…⟩ | ⟨parámetros / bitácora⟩ | ⟨1. … 2. … 3. …⟩ | ⟨lo que debe ocurrir⟩ | ⟨escenario/criterio⟩ | ⟨se llena al ejecutar⟩ | ⟨No ejecutado⟩ |
| CP-⟨NN+1⟩ | ⟨…⟩ | ⟨Negativa⟩ | ⟨Media⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |

**3.3 Datos de prueba**
- ⟨Valores concretos: bitácora/periodo, `bitacora_id`, `codigo_dane`, sector, transformador, año, fase…⟩

**3.4 Requisitos no funcionales a verificar**
- ⟨Rendimiento (tiempo de respuesta), resiliencia offline, responsive, accesibilidad, seguridad, según aplique.⟩

**3.5 Matriz de trazabilidad criterio ↔ caso**

| Criterio de aceptación (Gherkin) | Caso(s) de prueba |
|----------------------------------|-------------------|
| ⟨Escenario 1⟩ | ⟨CP-NN⟩ |
| ⟨Escenario 2⟩ | ⟨CP-NN+1⟩ |

---

### Pruebas de HU-⟨NN+1⟩ — ⟨título⟩
_⟨Repita la ficha completa.⟩_

---

## 4. Ejemplo trabajado — Pruebas de HU-002 «Cambiar de periodo con el selector de bitácoras»

| Atributo | Valor |
|----------|-------|
| **Historia** | HU-002 |
| **Épica** | EP-00 — Navegación, encabezado y resiliencia |
| **Objetivo de prueba** | Verificar que al cambiar de bitácora todo el tablero se recarga con las cifras del corte elegido. |
| **Componente(s)** | `GET /api/bitacoras`, `GET /api/bitacoras/{periodo}`, `GET /api/resumen`, selector en `#hero` |
| **Precondiciones generales** | Entorno desplegado; al menos **dos** bitácoras cargadas (p. ej. 2025-I y 2026-I). |

**4.1 Escenarios de prueba (Gherkin)**

```gherkin
Escenario: Recarga total al cambiar de corte
  Dado que el tablero muestra la bitácora más reciente (2026-I)
  Cuando selecciono el periodo 2025-I en el selector
  Entonces el encabezado muestra la fecha de corte de 2025-I
  Y las ocho secciones se recargan con las cifras de 2025-I

Escenario: El selector lista todos los cortes
  Dado que hay dos bitácoras cargadas
  Cuando abro el selector
  Entonces veo un elemento por cada bitácora, ordenados del más reciente al más antiguo

Escenario: Degradación si falla la carga del nuevo corte
  Dado que la API deja de responder al cambiar de periodo
  Cuando selecciono otro periodo
  Entonces el tablero no muestra una pantalla de error
  Y conserva o sustituye por datos de respaldo sin romperse
```

**4.2 Casos de prueba**

| ID | Título | Tipo | Prioridad | Precondición | Datos | Pasos | Resultado esperado | Criterio | Estado |
|----|--------|------|-----------|--------------|-------|-------|--------------------|----------|--------|
| CP-002-1 | Cambio de bitácora recarga el tablero | Funcional | Alta | 2 bitácoras cargadas | Periodo destino: 2025-I | 1. Abrir el tablero (muestra 2026-I). 2. Abrir el selector. 3. Elegir 2025-I | El encabezado muestra el corte de 2025-I y las 8 secciones reflejan sus cifras | Escenario 1 | No ejecutado |
| CP-002-2 | Selector lista y ordena los cortes | Funcional | Media | 2 bitácoras cargadas | — | 1. Abrir el selector | Aparecen 2026-I y 2025-I, del más reciente al más antiguo | Escenario 2 | No ejecutado |
| CP-002-3 | `GET /api/bitacoras` devuelve los cortes | Integración | Alta | API arriba | — | 1. `GET /api/bitacoras` | 200; lista con periodo y fecha de corte por bitácora | Escenario 2 | No ejecutado |
| CP-002-4 | Consulta por periodo aplica el corte | Integración | Alta | API arriba | periodo=2025-I | 1. `GET /api/resumen?bitacora_id=⟨id 2025-I⟩` | 200; los KPIs corresponden a 2025-I | Escenario 1 | No ejecutado |
| CP-002-5 | Resiliencia al fallar el cambio | Resiliencia | Media | API detenida a mitad | Periodo destino: 2025-I | 1. Detener la API. 2. Cambiar de periodo | No hay pantalla de error; el tablero sigue visible con datos de respaldo | Escenario 3 | No ejecutado |
| CP-002-6 | Periodo inexistente | Negativa | Baja | API arriba | periodo=2099-I | 1. `GET /api/bitacoras/2099-I` | Respuesta que indica «no existe» sin error 5xx | — | No ejecutado |

**4.3 Datos de prueba**
- Bitácoras: **2026-I** (corte 2026-03-31) y **2025-I** (corte 2025-03-31).
- `bitacora_id` de cada una, obtenidos de `GET /api/bitacoras`.

**4.4 Requisitos no funcionales**
- La recarga del tablero al cambiar de periodo responde en un tiempo razonable (⟨definir umbral, p. ej. < 2 s⟩).
- Resiliencia: la página nunca queda en blanco (HU-005).

**4.5 Matriz de trazabilidad criterio ↔ caso**

| Criterio de aceptación | Caso(s) |
|------------------------|---------|
| Recarga total al cambiar de corte | CP-002-1, CP-002-4 |
| El selector lista todos los cortes | CP-002-2, CP-002-3 |
| Degradación si falla la carga | CP-002-5 |
| (Robustez adicional) periodo inexistente | CP-002-6 |

---

## 5. Registro de ejecución (resumen)

| Corrida | Fecha | Versión / commit | Total | Pasaron | Fallaron | Bloqueados | N/A | Observaciones |
|---------|-------|------------------|-------|---------|----------|------------|-----|---------------|
| ⟨1⟩ | ⟨AAAA-MM-DD⟩ | ⟨hash⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ |

**Defectos registrados**

| ID defecto | Caso que lo detectó | Severidad | Estado | Descripción |
|------------|---------------------|-----------|--------|-------------|
| ⟨DEF-01⟩ | ⟨CP-NN⟩ | ⟨Alta/Media/Baja⟩ | ⟨Abierto/Corregido⟩ | ⟨⟩ |

---

## 6. Anexos
_⟨Colecciones de peticiones HTTP, capturas, salidas de `compare_apis.py` / `compare_bd.py`, datos de prueba.⟩_
