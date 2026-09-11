# Especificación de Historias de Usuario — Plantilla

> **Instrucciones para el analista**
> Esta plantilla se diligencia a partir del código y la documentación del proyecto **Bitácora de Inversión Pública** (DNP/DPIP).
> - Reemplace todo texto entre `⟨ ⟩` por el contenido real. Elimine las notas en _cursiva_ al finalizar.
> - **Una ficha por historia de usuario.** Agrupe las historias en **épicas** (una épica por sección del tablero o por dominio: ETL, operación, API…).
> - Numere las historias como `HU-01`, `HU-02`, … y las épicas como `EP-01`, y manténgalas trazables con los endpoints (`Endpoints/*.cs`), las tablas (`db/mssql/`), la sección del `frontend/index.html` y la especificación de pruebas.
> - Los **criterios de aceptación** se escriben en formato **Gherkin** (Dado / Cuando / Entonces). Cada criterio debe ser verificable y dar origen a al menos un caso de prueba (ver `PLANTILLA_ESPECIFICACION_PRUEBAS.md`).
> - El backlog completo ya extraído del sistema está en `BACKLOG_HISTORIAS_USUARIO.md`; use esta plantilla para altas nuevas o para detallar una historia existente.

---

## Portada / control del documento

| Campo | Valor |
|-------|-------|
| Proyecto | Bitácora de Inversión Pública — DNP/DPIP |
| Documento | Especificación de Historias de Usuario |
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
_⟨Objetivo de este documento de historias de usuario.⟩_

### 1.2 Alcance
_⟨Qué funcionalidades del sistema cubre. P. ej. las 8 secciones del tablero, el selector de bitácoras, el cargue trimestral (ETL), la operación/despliegue y el consumo de la API.⟩_

### 1.3 Definiciones y acrónimos
_⟨PGN, DNP, DPIP, SIIF, SGP, bitácora, vigencia, apropiación, compromiso, obligación, pago, mmm, deflactor… reutilice el glosario de `MANUAL_USUARIO.md` y `ARQUITECTURA.md`.⟩_

### 1.4 Referencias
_⟨`ARQUITECTURA.md`, `MANUAL_USUARIO.md`, `MANUAL_OPERACION.md`, `MANUAL_TECNICO.md`, OpenAPI en `/swagger`.⟩_

---

## 2. Actores / roles

| Actor | Tipo | Descripción |
|-------|------|-------------|
| ⟨Usuario del tablero⟩ | Humano / primario | Ciudadano, directivo o analista que consulta la infografía en el navegador; no requiere autenticación. |
| ⟨Analista de datos (DPIP)⟩ | Humano / primario | Carga y actualiza las bitácoras trimestrales mediante el ETL. |
| ⟨Administrador / DevOps⟩ | Humano / secundario | Despliega, opera, respalda y monitorea el sistema. |
| ⟨Desarrollador / integrador⟩ | Humano / secundario | Consume la API pública de solo lectura para otros usos. |
| ⟨Sistema frontend / fuentes Excel⟩ | Sistema | El tablero consume la API; el ETL lee los Excel de SIIF/PIIP/SCCI/DNP. |

---

## 3. Convenciones de la historia

- **Prioridad (MoSCoW):** `Must` / `Should` / `Could` / `Won't` (por ahora).
- **Estimación:** puntos de historia (escala Fibonacci: 1, 2, 3, 5, 8, 13) o T-shirt (XS–XL); sea consistente.
- **Estado:** `Propuesta` / `Lista para desarrollo` / `En curso` / `En pruebas` / `Terminada`.
- **INVEST:** cada historia debe ser Independiente, Negociable, Valiosa, Estimable, Pequeña y Verificable.

---

## 4. Ficha de la historia de usuario

> _Copie esta ficha por cada historia._

### HU-⟨NN⟩ — ⟨Título corto: verbo + objeto⟩

| Atributo | Valor |
|----------|-------|
| **Identificador** | HU-⟨NN⟩ |
| **Épica** | ⟨EP-NN — nombre de la épica / sección⟩ |
| **Actor / rol** | ⟨actor principal⟩ |
| **Prioridad** | ⟨Must / Should / Could / Won't⟩ |
| **Estimación** | ⟨puntos⟩ |
| **Estado** | ⟨Propuesta / Lista / En curso / …⟩ |
| **Dependencias** | ⟨HU-⟨n⟩, o «ninguna»⟩ |

**Narrativa**

> **Como** ⟨rol⟩
> **quiero** ⟨funcionalidad / acción⟩
> **para** ⟨beneficio / valor de negocio⟩.

**Descripción / contexto**
_⟨Una o dos frases que aporten contexto de negocio o de la interfaz.⟩_

**Reglas de negocio asociadas**
- ⟨RN-⟨n⟩: p. ej. «las vigencias futuras se muestran en pesos constantes de 2026»; «al cambiar de bitácora se recarga todo el tablero»; «si la API falla, el tablero usa datos de respaldo sin avisar».⟩

**Criterios de aceptación (Gherkin)**

```gherkin
Escenario: ⟨nombre del escenario — camino principal⟩
  Dado ⟨precondición / estado inicial⟩
  Y ⟨otra precondición, opcional⟩
  Cuando ⟨acción del actor⟩
  Entonces ⟨resultado observable y verificable⟩
  Y ⟨resultado adicional, opcional⟩

Escenario: ⟨variante o caso límite⟩
  Dado ⟨…⟩
  Cuando ⟨…⟩
  Entonces ⟨…⟩

Escenario: ⟨manejo de error / degradación⟩
  Dado ⟨…⟩
  Cuando ⟨…⟩
  Entonces ⟨…⟩
```

**Notas / decisiones de diseño**
- ⟨Observaciones, alternativas descartadas, deuda técnica, pendientes.⟩

**Requisitos no funcionales aplicables**
- ⟨Rendimiento, accesibilidad, identidad visual DNP 2026, compatibilidad de navegador, resiliencia offline, etc.⟩

**Trazabilidad**

| Endpoint(s) / componente | Tabla(s) BD | Sección frontend | Casos de prueba |
|--------------------------|-------------|------------------|-----------------|
| ⟨`GET /api/…` · `Endpoints/….cs`⟩ | ⟨`tabla`⟩ | ⟨`#secN`⟩ | ⟨CP-⟨NN⟩⟩ |

**Definición de Listo (DoR)** — _para entrar a desarrollo_
- [ ] Narrativa y criterios de aceptación acordados con el negocio.
- [ ] Dependencias identificadas y disponibles.
- [ ] Datos de prueba / bitácora de referencia disponibles.

**Definición de Terminado (DoD)** — _para cerrar la historia_
- [ ] Todos los criterios de aceptación pasan.
- [ ] Verificación de paridad sin diferencias de claves/valores/estado (`tools/compare_apis.py`), cuando aplique.
- [ ] Documentación (`MANUAL_*`) actualizada si cambió el comportamiento.
- [ ] Revisado por QA/Documentación.

---

### HU-⟨NN+1⟩ — ⟨Título⟩
_⟨Repita la ficha completa.⟩_

---

## 5. Matriz de trazabilidad global (historias ↔ código ↔ pruebas)

| Historia | Épica | Endpoint / componente | Tabla(s) BD | Sección frontend | Casos de prueba |
|----------|-------|-----------------------|-------------|------------------|-----------------|
| HU-01 | ⟨EP-01⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨CP-01⟩ |
| HU-02 | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ |

---

## 6. Anexos
_⟨Mockups, ejemplos de payload JSON, diagramas de flujo, capturas de pantalla.⟩_
