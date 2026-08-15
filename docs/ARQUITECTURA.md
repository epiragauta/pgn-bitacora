# Arquitectura — Bitácora de Inversión Pública

**Sistema:** Tablero web de seguimiento a la inversión pública de Colombia
**Entidad:** DNP / DPIP — Dirección de Programación de Inversiones Públicas
**Versión:** 3.0.0 · **Actualizado:** 15 de agosto de 2026

---

## 1. Qué es el sistema

La Bitácora publica el seguimiento del **Presupuesto General de la Nación** en materia de inversión, con tres ámbitos adicionales que se administran por fuera del PGN: crédito externo, Sistema General de Participaciones y vigencias futuras.

Su unidad de trabajo es la **bitácora**: un corte trimestral de información. Cada bitácora es un conjunto coherente de cifras a una fecha determinada, y el sistema conserva todas las cargadas, de modo que se puede consultar el histórico sin que una carga nueva pise a la anterior.

Se alimenta de archivos Excel producidos por SIIF Nación, PIIP, SCCI y las áreas técnicas del DNP. **No consume ninguna API externa en tiempo real**: la información entra por un proceso de cargue controlado, trimestral.

---

## 2. Arquitectura en tres capas

```
   Internet
      │
      ▼  HTTPS · certificado automático
┌─────────────────────────────────────────────┐
│  Caddy  (host)                              │
│  dnp-btcr.skaphe.com → localhost:5080       │
└─────────────────────────────────────────────┘
      │  HTTP plano, solo por loopback
      ▼
┌─────────────────────────────────────────────┐
│  Contenedor  dnp-dpip-bitacora              │
│  ┌───────────────────────────────────────┐  │
│  │  API .NET 8 (Minimal API + Dapper)    │  │
│  │  · 30 endpoints REST bajo /api        │  │
│  │  · sirve el frontend y los GeoJSON    │  │
│  └───────────────────────────────────────┘  │
│      publicado en 127.0.0.1:5080            │
└─────────────────────────────────────────────┘
      │  red sbn-ecp_umbraco-network
      ▼  alias interno: sqlserver
┌─────────────────────────────────────────────┐
│  SQL Server 2022 — base dnp_dpip            │
│  23 tablas · 1 vista · Modern_Spanish_CS_AS │
└─────────────────────────────────────────────┘
      ▲
      │  cargue trimestral
┌─────────────────────────────────────────────┐
│  ETL Python (openpyxl + pyodbc)             │
│  ← Excel de SIIF, PIIP, SCCI, DNP           │
└─────────────────────────────────────────────┘
```

**Tres propiedades de este diseño merecen atención:**

1. **La API no está expuesta a la red.** El contenedor publica en `127.0.0.1:5080`; la única puerta desde internet es Caddy. Aunque se abriera un puerto por error en el firewall, no habría nada escuchando en la interfaz pública.
2. **La API alcanza la base por red interna de Docker**, usando el alias de servicio `sqlserver`, no el puerto 1433 publicado. Reduce superficie y no depende de que ese puerto siga expuesto.
3. **El ETL no pasa por la API.** Escribe directo en la base. La API es estrictamente de lectura.

---

## 3. Capa de datos

### Modelo

El eje del modelo es `metadatos_bitacora`: cada corte trimestral tiene un registro allí, y **toda tabla de datos cuelga de él por `bitacora_id`**. Eso es lo que permite conservar varios cortes simultáneos sin mezclarlos.

Los prefijos de tabla funcionan como espacio de nombres por dominio:

| Prefijo | Dominio | Tablas |
|---|---|---|
| *(sin prefijo)* | Inversión PGN | `inversion_transformaciones`, `ejecucion_historica`, `apropiacion_por_sector`, … |
| `pgn_` | Evolución presupuestal | `pgn_concepto`, `pgn_ejecucion` + vista `pgn_vista_crosstab` |
| `credito_` | Crédito externo | `credito_portafolio`, `credito_ejecucion_entidad`, … |
| `sgp_` | Participaciones | `sgp_historico_participacion`, `sgp_historico_componentes` |

El esquema admite un futuro `sgr_` (Sistema General de Regalías) sin cambios estructurales.

### El modelo jerárquico de la sección 2

`pgn_concepto` es una **dimensión autorreferenciada**: cada concepto presupuestal apunta a su padre, formando un árbol de hasta cuatro niveles. `pgn_ejecucion` guarda el hecho —un valor por año, fase y concepto—. Esa forma es la que permite el desglose interactivo del tablero mediante una consulta recursiva.

Estas dos tablas **no llevan `bitacora_id`**: son la serie completa del PGN, compartida por todos los cortes.

### Tres reglas que no son negociables

Cada una nació de un defecto real durante la migración, y las tres fallan **en silencio**:

| Regla | Qué pasa si se rompe |
|---|---|
| Collation `Modern_Spanish_CS_AS` | `PACÍFICO` y `PACIFICO` se vuelven el mismo valor y las agrupaciones por región fusionan filas |
| Toda aritmética calculada va con `CAST(... AS FLOAT)` | Los porcentajes difieren en el último decimal frente a la serie histórica |
| Texto en `NVARCHAR`, nunca `VARCHAR` | Se pierden las tildes de regiones, sectores y entidades |

### Unidades

Los valores monetarios están en **miles de millones de pesos** (mmm) salvo indicación en el nombre de la columna. Las vigencias futuras se almacenan en **pesos corrientes** y la API las convierte a constantes de 2026 al vuelo, dividiendo por el deflactor del PIB del año correspondiente. Se guarda el dato crudo, no el derivado: si cambia la serie de deflactores, no hay que recargar nada.

---

## 4. Capa de API

### Organización

.NET 8 Minimal API con **Dapper** sobre SQL crudo. Se descartó un ORM completo deliberadamente: las consultas son analíticas —CTEs recursivas, agregados, pivots— y expresarlas en LINQ habría añadido una capa de traducción sin beneficio.

```
backend/src/PgnBitacora.Api/
├── Program.cs          Cableado: DI, CORS, Swagger, archivos estáticos
├── Endpoints/          Una clase por sección del tablero
├── Services/           Lógica que no cabe en SQL
├── Data/               Conexión, resolución de bitácora
└── Json/               Serialización a medida
```

### La decisión de diseño central: el SQL define el contrato

`Data/Db.cs` devuelve **diccionarios**, no objetos tipados. Los alias de columna del SQL se convierten literalmente en las claves del JSON.

Puede parecer una renuncia al tipado, pero responde a un riesgo concreto: **el frontend lee claves snake_case exactas y, si falta una, cae a sus datos embebidos sin mostrar ningún error**. Con DTOs tipados, un renombre inocente en refactorización dejaría el tablero mostrando cifras obsoletas sin que nadie se enterara. Con diccionarios, el SQL *es* el contrato y no hay dónde equivocarse.

Por la misma razón, la serialización JSON no aplica ninguna política de nombres y escribe los nulos de forma explícita.

### Resolución de bitácora

Todo endpoint acepta `bitacora_id` opcional. Sin él, `BitacoraResolver` devuelve la bitácora más reciente por fecha de corte. Eso es lo que permite que el tablero funcione sin parámetros y que el selector de periodos funcione con uno solo.

### Servicios

Cuatro cálculos no se resuelven bien en SQL y viven en C#:

| Servicio | Qué hace |
|---|---|
| `VigenciasFuturasChart` | Agrupa 29 sectores en 6 series, convierte a constantes y calcula el % del PIB |
| `MatrizSectores` | Pivot sector × vigencia a partir de cuatro consultas |
| `Resumen` | KPIs del encabezado, con respaldo si falta la fila de ejecución histórica |
| `SgpResumen` | Crecimiento interanual y acumulado del SGP |

### Contenido estático

La misma aplicación sirve el frontend y los GeoJSON. El tipo `application/geo+json` está registrado explícitamente: sin eso el middleware de .NET devuelve 404 para esas extensiones y **el mapa queda en blanco sin error alguno**.

---

## 5. Capa de presentación

El frontend es **un único archivo HTML autónomo** con CSS y JavaScript embebidos, más las librerías vendorizadas localmente (Chart.js, Leaflet, tipografías). No hay build, ni empaquetador, ni dependencias que resolver en tiempo de despliegue.

Consume la API por `fetch` y tiene una característica que condiciona todo el backend: **si una petición falla, usa datos embebidos en el propio archivo y no avisa**. Es una decisión de resiliencia razonable para una infografía —la página nunca se ve rota— pero significa que un error del backend se manifiesta como cifras desactualizadas, no como una pantalla de error. De ahí la insistencia del proyecto en la verificación automática de paridad.

---

## 6. Cargue de datos

```
Excel (SIIF · PIIP · SCCI · DNP)
        │
        │  openpyxl
        ▼
   Cargadores por sección
        │
        │  etl/db.py  (pyodbc)
        ▼
      dnp_dpip
```

`etl/bases.py` localiza los archivos por patrón dentro de cada carpeta de sección, porque los nombres traen fechas y sufijos que cambian cada trimestre. `etl/db.py` concentra las equivalencias con el motor anterior, de modo que los cargadores conservan intacta su lógica de lectura de Excel — que es donde vive el conocimiento del negocio y lo más costoso de reescribir.

**El orden de ejecución importa** y está documentado en el manual de operación: un cargador crea la bitácora que los demás resuelven, y otro debe correr después porque reemplaza una carga parcial.

---

## 7. Verificación

El sistema incluye su propia red de seguridad, y es parte de la arquitectura, no un accesorio:

| Herramienta | Función |
|---|---|
| `tools/endpoints.py` | Enumera las 322 rutas derivándolas de los datos reales de la base, de modo que la cobertura crece sola al cargar una bitácora nueva |
| `tools/baseline/` | Captura congelada del comportamiento de la API previa a la migración |
| `tools/compare_apis.py` | Compara y **clasifica las diferencias por tipo**: claves, valores, estado HTTP y orden. Solo las tres primeras bloquean |
| `tools/compare_bd.py` | Contrasta dos bases tabla por tabla: conteos y suma de cada columna numérica |

La distinción por tipo es lo que hace útil la herramienta: una diferencia de orden entre filas empatadas es inocua, mientras que una clave faltante rompe el tablero sin ruido. Mezclarlas ocultaría la que importa.

---

## 8. Despliegue

| Elemento | Valor |
|---|---|
| URL pública | `https://dnp-btcr.skaphe.com` |
| Proxy inverso | Caddy en el host, TLS automático de Let's Encrypt |
| Contenedor | `dnp-dpip-bitacora`, imagen multi-etapa `sdk:8.0` → `aspnet:8.0` |
| Publicación | `127.0.0.1:5080` — solo loopback |
| Red | `sbn-ecp_umbraco-network`, alias `sqlserver` |
| Reinicio | `unless-stopped`, con `HEALTHCHECK` contra `/health` |
| Configuración | Cadena de conexión por variable de entorno desde `.env`, fuera del control de versiones |

Los datos viven en el volumen de SQL Server, no en la imagen: reconstruir o reiniciar el contenedor no pierde nada.

**Nota:** este servidor es un entorno de desarrollo y pruebas. El destino productivo definitivo está pendiente de definición.

---

## 9. Seguridad

| Aspecto | Estado |
|---|---|
| Transporte | HTTPS con certificado renovado automáticamente; HTTP redirige por 308 |
| Exposición | Solo Caddy alcanza la API; el contenedor no escucha en la interfaz pública |
| Autenticación | **No hay**, por decisión explícita: la API es pública y de solo lectura |
| Credenciales | Fuera del repositorio, inyectadas por entorno |
| Permisos de base | Login dedicado con alcance a `dnp_dpip`, sin acceso a otras bases de la instancia |
| Inyección SQL | Todas las consultas usan parámetros; ningún valor de usuario se concatena |

Los endpoints están agrupados con `MapGroup("/api")` precisamente para que introducir autenticación más adelante sea un cambio de una línea.

---

## 10. Decisiones descartadas y por qué

| Alternativa | Motivo del descarte |
|---|---|
| Entity Framework Core | Las consultas son analíticas; habrían terminado en SQL crudo igual, con una capa de más |
| DTOs tipados por endpoint | El frontend depende de claves exactas y falla en silencio; los diccionarios eliminan la clase entera de error |
| Fly.io / Render | Ninguno alcanza la instancia de SQL Server, que escucha en loopback |
| Reescribir el ETL en .NET | Habría exigido rehacer ~2.500 líneas de parsing de Excel ya probadas, con riesgo alto y beneficio nulo |
| Collation insensible a tildes | Fusiona regiones y sectores en las agrupaciones |
| Almacenar vigencias futuras ya deflactadas | Ata el dato a una serie de deflactores concreta; se guarda el valor crudo y se convierte al vuelo |

---

## Documentos relacionados

- `docs/MANUAL_TECNICO.md` — detalle de implementación para desarrolladores
- `docs/MANUAL_OPERACION.md` — cargue trimestral y despliegue
- `docs/MANUAL_USUARIO.md` — uso del tablero
- `docs/PLAN_MIGRACION_DOTNET_SQLSERVER.md` — bitácora técnica de la migración, con el catálogo completo de incompatibilidades entre motores
