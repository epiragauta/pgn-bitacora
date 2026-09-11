# Plan de actividades por rol — Integración a producción en SICODIS

**Proyecto:** Bitácora de Inversión Pública (DNP/DPIP)
**Documento:** listado de actividades para tres perfiles profesionales
**Fecha:** 2026-08-24
**Estado del sistema:** migración FastAPI/SQLite → .NET 8/SQL Server **completa en entorno de desarrollo y pruebas** (instancia `dnp_dpip` sobre una instancia SQL Server de desarrollo/pruebas ya existente). Este plan cubre el **paso a producción integrando la base de datos en SICODIS** (pendiente abierto #9 del `PLAN_MIGRACION_DOTNET_SQLSERVER.md`).

---

## 1. Propósito y alcance

Este documento traduce el trabajo de migración —ya ejecutado y verificado en dev/test— en un **listado de actividades asignadas por rol** para llevar la aplicación a **producción**, integrando sus tablas en la base de datos de **SICODIS** (*Sistema de Información y Consulta de Distribuciones* del DNP) o en otra base institucional que se defina.

Es un plan **híbrido**:
- Cada fase abre con un recuadro **«Base ya construida (dev/test)»** que resume lo hecho, con referencia a la fase del plan de migración original.
- A continuación se detallan las **actividades pendientes** hacia producción, cada una con entregable, criterio de aceptación, dependencias y esfuerzo.

**Fuera de alcance:** modificar `frontend/index.html` (se mantiene la premisa del plan original: el frontend no se toca). Cualquier cambio funcional del tablero es otro proyecto.

---

## 2. Perfiles y responsabilidades

| Rol | Profesional | Ámbito principal |
|---|---|---|
| **Ingeniero de Bases de Datos** | **Andrés Pachón** | Evaluación e integración en SICODIS, configuración de la base de datos, mayúsculas/tildes, permisos, adaptación de funciones entre las dos bases de datos, cargadores de datos (ETL), carga y validación de datos, respaldos. Además, por reparto de las actividades de desarrollo: ajuste de los cálculos del backend y verificación de los archivos de datos. |
| **DevOps** | **Edwin Piragauta** | Conectividad y red, secretos, **publicación y despliegue del servicio .NET (sin contenedores)**, acceso público con seguridad (proxy/TLS), monitoreo, manual de operación. Además, por reparto de las actividades de desarrollo: configuración de producción del backend y automatización de la verificación. |
| **Pruebas y Documentación** | **Ivonne Serrano** | Pruebas funcionales y de comparación, verificación del formato de datos y de los recursos del tablero, revisión visual del tablero, consolidación de evidencias y actualización de manuales y documentación de cierre. |

> **Reparto de las actividades de desarrollo.** El perfil de Ivonne se orienta a pruebas y documentación; las actividades técnicas de desarrollo que antes recaían en ese perfil se distribuyen entre Edwin y Andrés en proporción **≈ 65 % Edwin / 35 % Andrés** (ver §15).

> Nomenclatura de identificadores de actividad: **`BD-`** (Andrés), **`DO-`** (Edwin), **`SI-`** (Ivonne, pruebas/documentación), **`ALL-`** (transversal/compartida).

---

## 3. Cómo leer cada actividad

Cada actividad se describe con cinco campos:

- **Entregable** — producto verificable (script, documento, objeto de BD, artefacto publicado, reporte).
- **Criterio de aceptación (CA)** — condición objetiva de «terminado».
- **Depende de** — actividad(es) que deben completarse antes (handoff entre roles cuando aplica).
- **Esfuerzo** — estimación en **días-persona (d)**. Es el campo más incierto; úsese como orden de magnitud para el cronograma, no como compromiso contractual.
- **Apoyo** — rol secundario que colabora, cuando corresponde.

> El nombre de cada actividad se redacta en lenguaje llano; el detalle técnico vive en el **entregable** y el **criterio de aceptación**.

---

## 4. Supuestos (por confirmar con el área de SICODIS)

Estos supuestos condicionan varias actividades. **Cada uno debe confirmarse en la Fase 0**; si cambian, se ajusta el plan.

| # | Supuesto | Riesgo si es falso |
|---|---|---|
| S1 | SICODIS corre **SQL Server** (edición y versión ≥ 2019), motor análogo al de dev/test. | Si es otro motor (Oracle, PostgreSQL), la adaptación y el DDL se rehacen; el backend Dapper requiere ajustes. |
| S2 | Es viable crear una **BD dedicada** (p. ej. `dnp_dpip`) en la instancia de SICODIS, sin tocar las tablas de SICODIS, igual que se hizo en dev/test sobre una instancia compartida. | Si obligan a integrar dentro del esquema de SICODIS, se añade análisis de colisiones y colación heredada (ver BD-A2/A3). |
| S3 | El host de despliegue tiene **conectividad de red** hacia la instancia de SICODIS (puerto, firewall, DNS/VPN). | Bloquea todo el despliegue; hay que gestionar red antes. |
| S4 | Se permite fijar la **colación `Modern_Spanish_CS_AS`** a nivel de BD destino (anula la del servidor, como en dev/test). | Sin ella, `PACÍFICO`/`PACIFICO` se fusionan y se corrompen los `GROUP BY` (regla 2 del proyecto). |
| S5 | Las **credenciales y cadenas de conexión** se gestionan fuera del repositorio (variable de entorno / secreto). | Exposición de credenciales. |
| S6 | El **frontend no se modifica**; se sirve tal cual desde el backend .NET. | Fuera de alcance. |

---

## 5. Reglas de negocio que ninguna actividad puede violar

Heredadas del `CLAUDE.md` y del plan de migración. Se repiten aquí porque **fallan en silencio** si se rompen y varias actividades las verifican:

1. **Toda aritmética SQL calculada va en `CAST(... AS FLOAT)`** (almacenamiento en `DECIMAL(18,6)`). — verifica BD-C1.
2. **La colación de la BD debe ser `Modern_Spanish_CS_AS`** (case- y accent-sensitive). — verifica BD-A3 / BD-B1.
3. **Los alias de columna del SQL son las claves JSON**; Dapper devuelve diccionarios. Nunca introducir una política de nombres. — verifica SI-E1.
4. **La línea base congelada (`tools/baseline/`) no se regenera** para hacer desaparecer una diferencia. — gobierna SI-G2.

---

## 6. Fase 0 — Gobernanza, accesos y línea base de producción

> **Base ya construida (dev/test):** la línea base de 322 rutas está congelada en `tools/baseline/` (Fase 0 del plan original). Sigue siendo la vara de medición.

| ID | Actividad | Rol | Apoyo | Entregable | CA | Depende de | Esfuerzo |
|---|---|---|---|---|---|---|---|
| ALL-00.1 | Acordar con el equipo de SICODIS el alcance, los tiempos, los responsables y la política de cambios. | DevOps | BD, QA/Doc | Acta firmada | Acta aprobada por DNP y por el custodio de SICODIS | — | 1.0 |
| ALL-00.2 | Gestionar y obtener los accesos: usuario de base de datos, red y permisos de despliegue. | DevOps | BD | Accesos activos | Conexión de prueba (`sqlcmd`/`telnet`) exitosa desde el host de despliegue | ALL-00.1 | 1.0 |
| SI-00.3 | Confirmar que la referencia de comparación (línea base) sigue vigente para verificar más adelante que nada cambie. | QA/Doc | — | Nota de vigencia de línea base | `compare_apis.py --contra-linea-base` corre sobre dev/test sin diferencias bloqueantes | — | 0.5 |

---

## 7. Fase A — Evaluación de integración en SICODIS

> **Base ya construida (dev/test):** el esquema real (23 tablas + 1 vista) está extraído de `db/pgn.db` y materializado en `db/mssql/`; se descartaron 5 tablas muertas (§2.1 del plan). En dev/test convive con otra aplicación en la misma instancia sin interferencia. **Pendiente:** repetir esa evaluación contra el entorno de SICODIS y decidir la estrategia de coexistencia.

| ID | Actividad | Rol | Apoyo | Entregable | CA | Depende de | Esfuerzo |
|---|---|---|---|---|---|---|---|
| BD-A1 | Levantar las características de la base de datos de SICODIS (versión, configuración regional, capacidad, ventanas de mantenimiento). | BD | DevOps | Ficha técnica de la instancia | Documento con edición, versión y colación confirmadas | ALL-00.2 | 1.5 |
| BD-A2 | Decidir cómo convivirán los datos de la aplicación con SICODIS (base propia o dentro de SICODIS) y revisar posibles choques de nombres. | BD | QA/Doc | ADR (registro de decisión) + matriz de colisiones | Decisión firmada; 0 colisiones de nombres sin resolver | BD-A1 | 2.0 |
| BD-A3 | Revisar el manejo de mayúsculas y tildes en el destino para que las regiones y sectores no se mezclen. | BD | — | Nota técnica de colación | `WHERE region = N'PACIFICO'` devuelve 0 filas vs 3 con `N'PACÍFICO'` en el destino | BD-A2 | 1.0 |
| BD-A4 | Definir el usuario de la aplicación y sus permisos mínimos, aislado de los datos de SICODIS. | BD | DevOps | Matriz de permisos + script de creación de login | El usuario de prueba lee/escribe solo objetos propios y **no** accede a tablas de SICODIS | BD-A2 | 1.0 |
| DO-A5 | Comprobar la conexión de red hacia SICODIS desde donde correrá la aplicación (puertos, firewall, VPN, DNS). | DevOps | BD | Diagrama de red + prueba de conectividad | `sqlcmd` conecta a la instancia desde el host de despliegue; latencia documentada | ALL-00.2 | 1.0 |
| SI-A6 | Documentar el listado de tablas y vistas que la aplicación necesita y confirmar que no chocan con SICODIS. | QA/Doc | BD | Checklist de objetos requeridos | Lista validada contra §2.1 del plan de migración | BD-A2 | 0.5 |

---

## 8. Fase B — Configuración de la base de datos

> **Base ya construida (dev/test):** BD `dnp_dpip` creada con `Modern_Spanish_CS_AS`; DDL idempotente en `db/mssql/001_schema.sql`, `002_views.sql`, `003_seed_dane.sql` (Fase 1); login con `CHECK_POLICY = OFF` para la contraseña de dev. **Pendiente:** parametrizar todo esto para producción y endurecer la contraseña.

| ID | Actividad | Rol | Apoyo | Entregable | CA | Depende de | Esfuerzo |
|---|---|---|---|---|---|---|---|
| BD-B1 | Definir los parámetros de la base de datos de destino (configuración regional, tamaños, modo de recuperación). | BD | — | Documento de parámetros + script `000_database.sql` | Script idempotente ejecuta sin error; parámetros verificados con `sys.databases` | BD-A3 | 1.0 |
| BD-B2 | Aplicar los scripts de creación de tablas en el destino y comprobar que se pueden re-ejecutar sin errores. | BD | QA/Doc | Scripts DDL versionados para producción | Doble ejecución completa sin errores ni duplicados (como Fase 1) | BD-B1 | 1.0 |
| BD-B3 | Definir la conexión y las credenciales de producción (cadena de conexión y contraseña conforme a la política, con su rotación). | BD | DevOps | Plantilla `.env.example` de producción + política de credenciales | Cadena probada de extremo a extremo; contraseña conforme a política (`CHECK_POLICY = ON`) | BD-A4 | 1.0 |
| DO-B4 | Guardar de forma segura la contraseña y la cadena de conexión, fuera del código. | DevOps | BD | Secreto configurado en el host | El servicio arranca leyendo la cadena; 0 credenciales en el artefacto o el repo | BD-B3 | 1.0 |
| BD-B6 | Acordar con SICODIS la política de copias de seguridad y probar una restauración. | BD | DevOps | Plan de backup + evidencia de restore | Primer ciclo backup→restore de prueba exitoso | BD-B1 | 1.0 |

---

## 9. Fase C — Adaptación de funciones entre las dos bases de datos

> **Base ya construida (dev/test):** el **catálogo completo de incompatibilidades** está resuelto y verificado (§3 del plan): sintaxis (`strftime`→`YEAR`, `NULLS LAST`, `COLLATE NOCASE`, recursividad, `GROUP BY`, `ORDER BY` en vistas), **división por cero** (error 8134 → `NULLIF` sistemático), tipos (`REAL`→`DECIMAL(18,6)`, `TEXT`→`NVARCHAR` con `N`) y la **regla de precisión** (`CAST AS FLOAT` en aritmética). Los cargadores del ETL ya tienen sus equivalencias. **Pendiente:** re-verificar todo esto contra la versión exacta de SICODIS.

| ID | Actividad | Rol | Apoyo | Entregable | CA | Depende de | Esfuerzo |
|---|---|---|---|---|---|---|---|
| BD-C1 | Revisar las diferencias de funcionamiento entre la base actual y SQL Server y comprobar que los cálculos dan los mismos resultados. | BD | QA/Doc | Informe de conformidad (§3.1/§3.2) + nota de precisión numérica | Cada diferencia del catálogo resuelta en el motor destino; cálculos iguales a la línea base dentro de 1e-6 (caso testigo `pct_pib` = 1.2368) | BD-B2 | 2.5 |
| BD-C3 | Adaptar los cargadores de datos (ETL) para que funcionen contra la nueva base. | BD | QA/Doc | `etl/db.py` validado + registro de duplicados | Carga en BD de pruebas del destino reproduce sumas vía `tools/compare_bd.py` | BD-B2 | 1.5 |
| BD-C4 | Ajustar los cálculos del backend que replican la lógica anterior y probarlos. *(Actividad de desarrollo reasignada a Andrés.)* | BD | QA/Doc | Pruebas unitarias de los 4 servicios de cálculo | Salidas idénticas a la línea base para las rutas que dependen de estos servicios | DO-D1 | 1.0 |

---

## 10. Fase D — Preparación del backend para producción

> **Base ya construida (dev/test):** los **30 endpoints** están portados a .NET 8 con Dapper; los 4 servicios de cálculo, implementados; el formato de datos JSON se preserva; las fechas se formatean en SQL; los mapas (`.geojson`) se sirven bien. Paridad verificada: **318/322 idénticas, 0 diferencias de datos** (Fases 3–4). **Pendiente:** configuración de producción y ajustes. *(Actividades de desarrollo repartidas entre Edwin y Andrés.)*

| ID | Actividad | Rol | Apoyo | Entregable | CA | Depende de | Esfuerzo |
|---|---|---|---|---|---|---|---|
| DO-D1 | Configurar el backend para el ambiente de producción (registro de eventos, chequeo de salud, permisos de acceso). *(Desarrollo → Edwin.)* | DevOps | BD | Configuración de producción | `/health` y `/swagger` responden; CORS restringido a `GET` verificado | BD-B3 | 1.0 |
| BD-D2 | Comprobar que los mapas y archivos de datos se sirven correctamente. *(Desarrollo → Andrés.)* | BD | DevOps | Verificación de estáticos de datos | `dptos.geojson` y `regiones.geojson` responden 200 con SHA-256 idéntico | DO-D1 | 0.5 |
| DO-D3 | Reforzar la seguridad y revisar que ningún reporte falle por errores de datos. *(Desarrollo → Edwin.)* | DevOps | BD | Checklist de seguridad del backend | Ningún endpoint devuelve 500 sobre las 322 rutas contra la BD destino | BD-C1, DO-D1 | 1.0 |
| DO-D4 | Ajustar las herramientas de comparación para que apunten a la base de SICODIS. *(Desarrollo → Edwin.)* | DevOps | BD | Herramientas de paridad apuntando a producción | Enumera 322 rutas derivadas de la BD destino sin error | BD-B2 | 1.0 |

---

## 11. Fase E — Integración con el tablero (frontend)

> **Base ya construida (dev/test):** el tablero se sirve sin una sola modificación; los 8 recursos que referencia y los 13 de segundo nivel se compararon byte a byte y son idénticos. **Pendiente:** repetir la verificación contra producción y completar la **revisión visual en navegador**, que quedó pendiente en la Fase 4 del plan.

| ID | Actividad | Rol | Apoyo | Entregable | CA | Depende de | Esfuerzo |
|---|---|---|---|---|---|---|---|
| SI-E1 | Verificar que el tablero recibe los datos con el mismo formato de siempre. | QA/Doc | — | Informe de contrato JSON | 0 diferencias de **claves** vs línea base | DO-D1 | 0.5 |
| SI-E2 | Verificar que los archivos y recursos del tablero se sirven idénticos a los actuales. | QA/Doc | DevOps | Reporte SHA-256 | Todos los recursos idénticos al original | BD-D2, DO-F3 | 0.5 |
| SI-E3 | Revisar visualmente el tablero en el navegador (8 secciones, mapa, ventanas de información, selector de bitácoras). | QA/Doc | DevOps | Checklist de revisión visual + capturas | Sin regresiones visuales; el mapa renderiza sus capas | DO-F3 | 1.0 |
| DO-E4 | Confirmar que el servidor intermedio (proxy) no altera la información entregada. | DevOps | QA/Doc | Reporte de paridad vía proxy | 318/322 idénticas, 0 diferencias de datos a través del proxy | DO-F3 | 0.5 |

---

## 12. Fase F — Despliegue (sin contenedores)

> **Base ya construida (dev/test):** el backend .NET se publica y sirve tras un reverse proxy con TLS de Let's Encrypt, escuchando solo en loopback; publicado en `https://dnp-btcr.skaphe.com` (Fase 6). **Pendiente:** desplegar el servicio .NET **directamente en el entorno de producción de SICODIS, sin contenedores**, con acceso seguro, monitoreo y runbook.

> **Nota de despliegue (sin contenedores):** el backend se entrega como publicación de .NET (`dotnet publish`) y se ejecuta como **servicio gestionado del sistema operativo** —`systemd` en Linux o *Windows Service* / IIS en Windows— con Kestrel escuchando en loopback detrás del reverse proxy institucional (Nginx, IIS/ARR o Caddy). No se usan Docker, imágenes ni orquestadores.

| ID | Actividad | Rol | Apoyo | Entregable | CA | Depende de | Esfuerzo |
|---|---|---|---|---|---|---|---|
| DO-F1 | Publicar e instalar el backend como servicio del sistema, con versión y forma de reversa (sin contenedores). | DevOps | BD | Artefacto publicado y versionado + definición de servicio + procedimiento de despliegue/reversa | Servicio activo conectando a SICODIS; se relanza tras reinicio del host; artefacto versionado y reversible | DO-B4, DO-A5 | 2.5 |
| DO-F3 | Configurar el acceso público con seguridad (dirección web y certificado). | DevOps | — | Bloque de proxy + certificado | HTTPS 200 en la raíz y en `/api/resumen`; redirección HTTP→HTTPS activa | DO-F1, pregunta abierta #7 | 1.0 |
| DO-F4 | Poner en marcha el monitoreo y el manual de operación (arranque, parada, respaldo, reversa). | DevOps | BD, QA/Doc | Monitoreo/alertas + `MANUAL_OPERACION.md` actualizado | Una caída del servicio genera alerta; runbook revisado y aprobado por los tres roles | DO-F1 | 2.0 |

---

## 13. Fase G — Carga de datos, verificación y cierre

> **Base ya construida (dev/test):** el traslado de datos cargó 5.320 filas en 22 tablas **sin una sola diferencia**; el ETL desde Excel reproduce la base (21/21 tablas idénticas). **Pendiente:** ejecutar la carga en producción y comparar contra la línea base.

| ID | Actividad | Rol | Apoyo | Entregable | CA | Depende de | Esfuerzo |
|---|---|---|---|---|---|---|---|
| BD-G1 | Cargar los datos en la base de destino y verificar que las cifras coinciden. | BD | QA/Doc | BD de producción poblada + reporte `compare_bd.py` | Conteos y sumas iguales dentro de 1e-6; identificadores preservados; 0 huérfanos | BD-B2, BD-C3 | 1.5 |
| SI-G2 | Comparar las respuestas de la aplicación contra la referencia para confirmar que todo quedó igual. | QA/Doc | DevOps | Reporte de paridad de producción | 0 diferencias de **claves/valores/estado**; solo divergencias de orden entre filas empatadas (§3.9) | BD-G1, DO-D4, DO-F3 | 1.0 |
| BD-G3 | Definir el procedimiento para cargar cada nueva bitácora trimestral. | BD | DevOps | Procedimiento de actualización trimestral | Ensayo de carga de una bitácora sin downtime perceptible y con paridad post-carga | BD-G1 | 1.0 |
| SI-G4 | Reunir las evidencias, actualizar la documentación y entregar a operación. | QA/Doc | BD, DevOps | Documento de cierre + evidencias | Firmado por los tres roles; pendientes abiertos actualizados | Todas | 1.0 |

---

## 14. Matriz RACI (resumen)

> **R** = Responsable de ejecutar · **A** = Aprueba/rinde cuentas · **C** = Consultado · **I** = Informado.

| Bloque de trabajo | Andrés (BD) | Edwin (DevOps) | Ivonne (Pruebas/Doc) |
|---|---|---|---|
| Gobernanza y accesos (Fase 0) | C | **A/R** | C |
| Evaluación de integración SICODIS (A) | **A/R** | C | C |
| Configuración de la base de datos (B) | **A/R** | C | I |
| Adaptación de funciones (C) | **A/R** | I | C |
| Backend .NET producción (D) | **R** | **A/R** | C |
| Integración con el tablero (E) | C | **A** | **R** |
| Despliegue (F) | C | **A/R** | C |
| Datos, verificación y cierre (G) | **R** (datos) | C | **R** (verificación/doc) |

---

## 15. Resumen de esfuerzo estimado por rol

> Estimación de orden de magnitud en días-persona. Excluye tiempos de espera por accesos o coordinación externa.

| Rol | Actividades | Esfuerzo (d) |
|---|---|---|
| **Andrés Pachón — Bases de Datos** | A1, A2, A3, A4, B1, B2, B3, B6, C1, C3, **C4**, **D2**, G1, G3 | **17.5** |
| **Edwin Piragauta — DevOps** | 00.1, 00.2, A5, B4, **D1**, **D3**, **D4**, E4, F1, F3, F4 | **13.0** |
| **Ivonne Serrano — Pruebas y Documentación** | 00.3, A6, E1, E2, E3, G2, G4 | **5.0** |
| | **Total** | **35.5 días-persona** |

**Reparto de las actividades de desarrollo reasignadas** (las que antes recaían en el perfil de Ivonne): C4, D1, D2, D3, D4 = **4.5 d**.

| Rol | Actividades de desarrollo | Esfuerzo (d) | Proporción |
|---|---|---|---|
| Edwin | D1, D3, D4 | 3.0 | **≈ 67 %** |
| Andrés | C4, D2 | 1.5 | **≈ 33 %** |

El plan se ejecuta en una **ventana fija de 4 semanas** (20 días hábiles por persona), con los tres roles trabajando en paralelo y respetando las dependencias (la BD habilita a DevOps y a pruebas). El detalle semana a semana está en §16.

> **Nota de capacidad.** Las cargas caben holgadamente en la ventana de 4 semanas: Andrés (17.5 d), Edwin (13.0 d) e Ivonne (5.0 d) quedan por debajo de los 20 días hábiles por persona. Ningún rol supera 5 días-persona en ninguna semana. La holgura de Pruebas/Documentación (Ivonne) permite además apoyar las validaciones intensivas de BD (BD-C1, BD-C3, BD-G1). Si los accesos de la Fase 0 se retrasan, la Semana 1 se comprime y el resto se corre en bloque.

---

## 16. Cronograma (4 semanas)

Ventana fija de **4 semanas** (20 días hábiles por persona). Los tres roles trabajan en paralelo; el orden respeta las dependencias de §17. El detalle de cada actividad está en las fases §6–§13.

| Semana | Andrés — Bases de Datos | Edwin — DevOps | Ivonne — Pruebas y Documentación |
|---|---|---|---|
| **Semana 1**<br>Gobernanza y evaluación | A1, A2, A3 *(características de SICODIS, decisión de coexistencia, mayúsculas/tildes)* — 4.5 d | 00.1, 00.2, A5 *(acta, accesos, red)* — 3.0 d | 00.3, A6 *(vigencia de línea base, inventario de objetos)* — 1.0 d |
| **Semana 2**<br>Base de datos y adaptación | A4, B1, B2, B3, B6 *(permisos, parámetros, tablas creadas, conexión, respaldos)* — 5.0 d | B4, D1, D4 *(secretos, backend prod, herramientas de comparación)* — 3.0 d | E1 *(formato de datos)* + apoyo a validación de BD — 0.5 d |
| **Semana 3**<br>Adaptación, ajustes y despliegue | C1, C3, C4 *(diferencias y cálculos, ETL, servicios de cálculo)* — 5.0 d | D3, F1, F3 *(refuerzo de seguridad, servicio desplegado, acceso público)* — 4.5 d | Apoyo a BD-C1/BD-C3 *(validación)* — holgura |
| **Semana 4**<br>Datos, verificación y cierre | D2, G1, G3 *(archivos de datos, carga de datos, procedimiento trimestral)* — 3.0 d | F4, E4 *(monitoreo y manual, paridad vía proxy)* — 2.5 d | E2, E3, G2, G4 *(recursos, revisión visual, verificación final, cierre documental)* — 3.5 d |

**Hitos de cierre de semana:**

| Fin de | Hito |
|---|---|
| **Semana 1** | Fase 0 cerrada (accesos y línea base vigente); base de SICODIS caracterizada; **estrategia de coexistencia decidida**. |
| **Semana 2** | Permisos y parámetros de BD definidos; **tablas creadas en el destino**; backend configurado para producción; credenciales protegidas. |
| **Semana 3** | Adaptación de funciones verificada; **servicio .NET desplegado (sin contenedores)**; acceso público publicado; herramientas de comparación apuntando al destino. |
| **Semana 4** | **Datos cargados y validados**; **verificación final 322/322** contra la línea base; tablero revisado; monitoreo y manual; **documentación de cierre** y traspaso a operación. |

> **Carga semanal (días-persona):** S1 → Andrés 4.5 · Edwin 3.0 · Ivonne 1.0. S2 → Andrés 5.0 · Edwin 3.0 · Ivonne 0.5. S3 → Andrés 5.0 · Edwin 4.5 · Ivonne (apoyo). S4 → Andrés 3.0 · Edwin 2.5 · Ivonne 3.5. Ningún rol supera 5 días-persona por semana.

---

## 17. Ruta crítica y dependencias clave

```
ALL-00.1 → ALL-00.2 ─┬─→ BD-A1 → BD-A2 → BD-A3 → BD-B1 → BD-B2 ─┬─→ BD-C1
                     │                                          ├─→ BD-C3 → BD-G1 → SI-G2 → SI-G4
                     └─→ DO-A5 ───────────────→ DO-F1 → DO-F3 ───┘        (verificación + cierre)
                                   BD-B3 → DO-B4 ↑        ↓
                                                     DO-D1 → DO-D3 / BD-C4 / SI-E1 / SI-E3
```

- **Nada avanza sin la Fase 0** (accesos). Es el bloqueo más probable y depende de terceros.
- **La BD es la que habilita** al resto: `BD-B2` (tablas en el destino) desbloquea adaptación, backend y datos.
- **`DO-F3` (acceso público)** habilita toda la verificación del tablero y la comparación de extremo a extremo; depende de la pregunta abierta #7.
- **`SI-G2` (verificación final)** es el criterio de aceptación global del paso a producción; `SI-G4` cierra y documenta.

---

## 18. Riesgos específicos del entorno SICODIS

| Riesgo | Impacto | Mitigación | Rol |
|---|---|---|---|
| SICODIS no es SQL Server (S1 falso) | Alto — rehacer DDL, ETL y capa Dapper | Confirmar en BD-A1 **antes** de comprometer cronograma | BD |
| Obligan a integrar en el esquema de SICODIS (S2 falso) | Alto — colisiones y colación heredada | Análisis de colisiones (BD-A2) + `COLLATE` por columna (BD-A3) | BD |
| Colación de servidor CI/AI impuesta (S4 falso) | Alto — fusión silenciosa de regiones/sectores | Fijar colación a nivel de BD/columna; prueba `PACÍFICO` vs `PACIFICO` | BD |
| Sin conectividad de red al día del despliegue (S3 falso) | Alto — bloquea despliegue | Prueba de red temprana (DO-A5) | DevOps |
| Política de contraseñas/cifrado más estricta | Medio — ajustar cadena de conexión y login | `CHECK_POLICY = ON` (BD-B3) + `Encrypt=True` según política | BD/DevOps |
| Subdominio de producción sin definir | Medio — retrasa publicación | Escalar la pregunta abierta #7 en Fase 0 | DevOps |
| ETL sin `BASES_BITACORA` disponibles | Medio — impide la carga real | Confirmar disponibilidad de archivos fuente antes de BD-G1 | BD |

---

## 19. Preguntas abiertas a resolver en la Fase 0

1. **Motor y versión exacta** de la instancia de SICODIS (confirma o refuta S1).
2. **Estrategia de coexistencia**: ¿BD dedicada nueva o integración en el esquema de SICODIS? (S2)
3. **Colación**: ¿se permite `Modern_Spanish_CS_AS` a nivel de BD? (S4)
4. **Topología de despliegue**: ¿el servicio .NET corre en el mismo host que SICODIS o en otro host de la red interna? ¿Linux (`systemd`) o Windows (*Windows Service*/IIS)? ¿Cuál es el reverse proxy institucional (Nginx, IIS/ARR, Caddy)? (S3)
5. **Acceso público y subdominio** de producción (pendiente abierto #7 del plan de migración).
6. **Gestión de secretos** en producción: ¿variable de entorno, archivo protegido o gestor institucional? (S5)
7. **Responsable de respaldos**: ¿los asume el DBA de SICODIS o el equipo del proyecto? (BD-B6)
8. **Disponibilidad de `BASES_BITACORA`** para la carga real y las actualizaciones trimestrales.

---

*Documento base en formato Markdown, con su equivalente en Excel (`PLAN_ACTIVIDADES_ROLES_INTEGRACION_SICODIS.xlsx`). Una vez validado el contenido y el reparto, puede convertirse a una presentación, a un tablero de proyecto (con estas mismas IDs de actividad) o a un cronograma con fechas.*
