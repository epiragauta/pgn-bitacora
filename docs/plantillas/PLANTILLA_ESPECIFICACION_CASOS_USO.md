# Especificación de Casos de Uso — Plantilla

> **Instrucciones para el analista**
> Esta plantilla se diligencia a partir del código fuente del proyecto **Bitácora PGN**.
> - Reemplace todo texto entre `⟨ ⟩` por el contenido real. Elimine las notas en _cursiva_ al finalizar.
> - **Un archivo por caso de uso** o una sección por caso de uso dentro de un documento maestro; sea consistente.
> - Cada endpoint de `api/main.py` y cada interacción principal del `frontend/index.html` suele corresponder a uno o más casos de uso.
> - Numere los casos de uso como `CU-01`, `CU-02`, … y manténgalos trazables con requisitos y componentes del código.

---

## Portada / control del documento

| Campo | Valor |
|-------|-------|
| Proyecto | Bitácora PGN — Infografía Web de Inversión Pública (DNP/DPIP) |
| Documento | Especificación de Casos de Uso |
| Versión | ⟨1.0⟩ |
| Fecha | ⟨AAAA-MM-DD⟩ |
| Autor | ⟨nombre del analista⟩ |
| Estado | ⟨Borrador / En revisión / Aprobado⟩ |

**Historial de cambios**

| Versión | Fecha | Autor | Descripción |
|---------|-------|-------|-------------|
| ⟨1.0⟩ | ⟨AAAA-MM-DD⟩ | ⟨⟩ | Versión inicial |

---

## 1. Introducción

### 1.1 Propósito
_⟨Objetivo de este documento de casos de uso.⟩_

### 1.2 Alcance
_⟨Qué funcionalidades del sistema cubre esta especificación.⟩_

### 1.3 Definiciones y acrónimos
_⟨PGN, DNP, DPIP, SIIF, SGP, bitácora, vigencia, mmm… reutilice el glosario de `ARQUITECTURA.md`.⟩_

### 1.4 Referencias
_⟨`ARQUITECTURA.md`, `README.md`, OpenAPI `/docs`, esquema `db/schema.sql`.⟩_

---

## 2. Actores del sistema

_Identifique los actores a partir de quién invoca cada funcionalidad. Sugerencia inicial para este proyecto:_

| Actor | Tipo | Descripción |
|-------|------|-------------|
| ⟨Ciudadano / Usuario visualizador⟩ | Humano / primario | Consulta la infografía en el navegador. |
| ⟨Analista DPIP / Administrador de datos⟩ | Humano / primario | Carga y actualiza las bitácoras vía ETL. |
| ⟨Sistema frontend (index.html)⟩ | Sistema | Consume la API REST. |
| ⟨Fuente externa (Excel SIIF / PIIP / SCCI / SGP)⟩ | Sistema / secundario | Provee los insumos de datos. |

**Diagrama de casos de uso** _(opcional, incluir imagen o diagrama en texto)_

```
⟨Actor⟩ ──► (CU-01 ⟨…⟩)
        ──► (CU-02 ⟨…⟩)
```

---

## 3. Lista de casos de uso

| ID | Nombre | Actor principal | Prioridad | Componente/código asociado |
|----|--------|-----------------|-----------|----------------------------|
| CU-01 | ⟨Consultar resumen/KPIs del dashboard⟩ | ⟨Usuario⟩ | ⟨Alta⟩ | ⟨`GET /api/resumen`, sección `#hero`⟩ |
| CU-02 | ⟨Visualizar transformaciones PND⟩ | ⟨Usuario⟩ | ⟨⟩ | ⟨`GET /api/transformaciones`⟩ |
| CU-03 | ⟨Explorar mapa de regionalización⟩ | ⟨Usuario⟩ | ⟨⟩ | ⟨`GET /api/regionalizacion/mapa`, Leaflet⟩ |
| CU-04 | ⟨Actualizar/cargar una nueva bitácora⟩ | ⟨Analista DPIP⟩ | ⟨⟩ | ⟨`etl/update_bitacora.py`, `load_*.py`⟩ |
| … | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |

---

## 4. Especificación detallada por caso de uso

> _Copie la ficha siguiente por cada caso de uso._

### CU-⟨NN⟩ — ⟨Nombre del caso de uso⟩

| Atributo | Descripción |
|----------|-------------|
| **Identificador** | CU-⟨NN⟩ |
| **Nombre** | ⟨verbo + objeto, p. ej. "Consultar ejecución sectorial"⟩ |
| **Actor(es)** | ⟨actor principal / actores secundarios⟩ |
| **Descripción** | ⟨resumen de una o dos frases⟩ |
| **Prioridad** | ⟨Alta / Media / Baja⟩ |
| **Frecuencia de uso** | ⟨alta / media / baja / eventual⟩ |
| **Componente de código** | ⟨endpoint(s), función(es), archivo(s), tabla(s) de BD⟩ |

**Precondiciones**
- ⟨Estado que debe cumplirse antes de iniciar. P. ej. "existe al menos una bitácora cargada".⟩

**Postcondiciones (garantía de éxito)**
- ⟨Estado del sistema tras completar exitosamente. P. ej. "se muestra el gráfico con datos de la bitácora vigente".⟩

**Disparador (trigger)**
- ⟨Evento que inicia el caso de uso. P. ej. "el usuario navega a la sección 4".⟩

**Flujo principal (camino feliz)**

| # | Actor | Sistema |
|---|-------|---------|
| 1 | ⟨acción del actor⟩ | ⟨respuesta del sistema⟩ |
| 2 | | ⟨p. ej. "la API ejecuta la consulta SQL y devuelve JSON"⟩ |
| 3 | | ⟨p. ej. "el frontend renderiza el gráfico con Chart.js"⟩ |

**Flujos alternativos**

- **CU-⟨NN⟩.A1 — ⟨nombre⟩:** _en el paso ⟨n⟩,_ ⟨condición⟩ → ⟨comportamiento alterno⟩.
  _(Ejemplo típico de este proyecto: "la API no responde → el frontend usa el conjunto de datos embebido de respaldo (función `af`)".)_

**Flujos de excepción / errores**

- **CU-⟨NN⟩.E1 — ⟨nombre⟩:** ⟨condición de error⟩ → ⟨manejo, mensaje, código HTTP⟩.

**Reglas de negocio asociadas**
- ⟨RN-⟨n⟩: p. ej. "vigencias futuras se muestran en precios constantes 2026 (deflactación en runtime)".⟩

**Requisitos de datos (entradas/salidas)**

| Parámetro | Dirección | Tipo | Obligatorio | Descripción |
|-----------|-----------|------|-------------|-------------|
| ⟨`bitacora_id`⟩ | entrada | ⟨int⟩ | ⟨No⟩ | ⟨corte a consultar; por defecto el vigente⟩ |
| ⟨`vigencia`⟩ | entrada | ⟨int⟩ | ⟨No⟩ | ⟨año fiscal⟩ |
| ⟨respuesta⟩ | salida | ⟨JSON⟩ | — | ⟨estructura devuelta⟩ |

**Requisitos especiales / no funcionales**
- ⟨rendimiento, accesibilidad, identidad visual DNP, compatibilidad de navegador, etc.⟩

**Frecuencia / notas**
- ⟨observaciones adicionales, dependencias con otros CU, pendientes.⟩

**Trazabilidad**

| Requisito | Componente de código | Prueba asociada |
|-----------|----------------------|-----------------|
| ⟨RF-⟨n⟩⟩ | ⟨`api/main.py:get_…`⟩ | ⟨caso de prueba⟩ |

---

### CU-⟨NN+1⟩ — ⟨Nombre⟩
_⟨Repita la ficha completa.⟩_

---

## 5. Matriz de trazabilidad global (casos de uso ↔ código)

| Caso de uso | Endpoint / función | Tabla(s) BD | Sección frontend |
|-------------|--------------------|-------------|------------------|
| CU-01 | ⟨`GET /api/resumen`⟩ | ⟨`metadatos_bitacora`, `ejecucion_historica`⟩ | ⟨`#hero`⟩ |
| CU-02 | ⟨⟩ | ⟨⟩ | ⟨⟩ |

---

## 6. Anexos
_⟨Diagramas, mockups, ejemplos de payload JSON, capturas de pantalla.⟩_
