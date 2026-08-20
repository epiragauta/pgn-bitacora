# Informe de cambios — 20 de agosto de 2026

**Proyecto:** Bitácora de Inversión Pública — DNP / DPIP
**Contexto:** trabajo posterior al cierre de la migración a .NET 8 / SQL Server (`v3.0.0`)
**Commits:** `c382828` · `b3165ee` · `c9682ee` · `216eb75` · `b9eabf0`

---

## Resumen

Cinco cambios, originados en dos preguntas del usuario —cómo se despliega el frontend y si el backend puede correr en un PaaS— que al verificarlas destaparon **tres defectos que no estaban a la vista**:

| # | Cambio | Origen |
|---|---|---|
| 1 | Se dejó de publicar los Excel fuente del DNP en internet | Hallazgo al explicar el despliegue |
| 2 | Las páginas web reflejan el criterio corregido de archivos estáticos | Consecuencia del #1 |
| 3 | `dotnet publish` incluye el frontend, y se documenta el despliegue en IIS | Hallazgo al preparar IIS |
| 4 | Todas las tablas llevan el prefijo `btcr_` | Requisito: base compartida |
| 5 | El nombre de la base sale de la configuración; se quitan credenciales del código | Hallazgo al revisar los ejemplos |

Los tres hallazgos comparten un patrón: **ninguno producía un error visible**. Uno exponía archivos internos, otro habría dejado el tablero en 404 y el tercero tenía una contraseña versionada.

---

## 1. Los Excel fuente estaban publicados en internet

### Qué pasaba

Los ~90 MB de `BASES_BITACORA` eran descargables desde el dominio público:

```
https://dnp-btcr.skaphe.com/data/BASES_BITACORA/.../SGP_2022-2026_Bitacora.xlsx
→ HTTP 200, 11,7 MB
```

El listado de directorio daba 404, así que no se navegaban, pero los nombres de archivo están en `docs/etl_uso.md`, que es público en el repositorio.

### Por qué

Tres causas encadenadas, dos de ellas introducidas durante la migración:

1. `backend/Dockerfile` copiaba `data/` completa para llevar los GeoJSON del mapa. Cuando `BASES_BITACORA` se colocó dentro de esa carpeta, entró en la imagen.
2. Estar en `.gitignore` no lo impidió: **`COPY` lee del disco, no del índice de git**.
3. `ServeUnknownFileTypes = true`, activado en la fase 4 para resolver el 404 de los `.geojson`, hace que se sirva *cualquier* extensión bajo el directorio publicado.

La tercera es la causa de fondo, y fue una decisión equivocada: cambió un fallo visible —un mapa en blanco— por uno invisible.

### Corrección

| Frente | Cambio |
|---|---|
| Imagen | El Dockerfile ya no copia `data/`. No hace falta: `frontend/data/` tiene los mismos GeoJSON, verificado por SHA-256 |
| Aplicación | Lista blanca de extensiones. Se registra `.geojson` y se retira `ServeUnknownFileTypes`, de modo que una extensión no reconocida devuelva 404 |
| Contexto de build | `.dockerignore` nuevo, para que esos archivos no lleguen siquiera al build |

### Verificación

| | Antes | Después |
|---|---|---|
| Excel por internet | 200, 11,7 MB | **404** |
| CSV del ETL | 200 | **404** |
| `/app/data` en la imagen | 90 MB | no existe |
| Los 11 recursos del navegador | 200 | 200, mismo tamaño |
| Paridad de 322 rutas | 318 idénticas | 318 idénticas |

Efecto colateral: el contenido de `/app` baja de ~110 MB a 18 MB y el contexto de build de 90 MB a 3,6 MB.

> **Pendiente del lado del DNP:** revisar los logs de Caddy por si alguien solicitó esas rutas durante las horas que estuvieron accesibles.

---

## 2. Páginas web actualizadas

`docs/web/arquitectura.html` describía el comportamiento anterior. Se corrigió y se añadió un llamado explicando el criterio de **lista blanca frente a `ServeUnknownFileTypes`**, con el caso real que lo motivó, para que quien toque esa parte no repita la decisión.

El manual de operación ganó una aclaración en el punto donde el operador coloca los Excel: esos archivos no llegan a la imagen. El manual de usuario no requería cambios.

---

## 3. `dotnet publish` no incluía el tablero

### Qué pasaba

`Program.cs` localiza el frontend subiendo directorios hasta encontrar `frontend/index.html`. Funciona desde el repositorio, pero **en una carpeta publicada no hay nada arriba que encontrar**.

En IIS eso habría dado la API funcionando y **404 en la raíz**, con solo una advertencia discreta en el log.

### Corrección

Un target de MSBuild en el `.csproj` copia `frontend/` al publicar. Sigue excluyendo `data/` de la raíz, para no reintroducir el problema del punto 1.

### Verificación

Se ejecutó la carpeta publicada de forma aislada, que es lo que hace IIS:

| | |
|---|---|
| Arranque | sin advertencias |
| `/`, `/api/resumen`, `/data/dptos.geojson`, `/swagger` | 200 |
| Suite de 322 rutas | 318 idénticas, cero diferencias bloqueantes |

### Documentación nueva

`docs/DESPLIEGUE_IIS.md`: requisitos, grupo de aplicaciones en «Sin código administrado», las tres formas de dar la cadena de conexión —con la autenticación integrada de Windows como recomendada—, verificación, diagnóstico de los errores 500.19 / 500.30 / 502.5 y actualizaciones con `app_offline.htm`.

> **Sobre desplegar en un PaaS:** se evaluó Vercel a petición del usuario y se descartó por dos razones independientes. La base escucha en `127.0.0.1:1433` y no es alcanzable desde fuera —el mismo motivo por el que se descartaron Fly.io y Render—, y Vercel no tiene runtime oficial de .NET. IIS es el destino natural de una aplicación ASP.NET Core.

---

## 4. Prefijo `btcr_` en todas las tablas

### Motivo

Las tablas van a instalarse en una base existente del DNP, junto a otros sistemas.

### Alcance

390 nombres en 31 archivos: DDL, backend .NET, ETL y herramientas.

```
dbo.btcr_metadatos_bitacora      PK_btcr_metadatos_bitacora
dbo.btcr_pgn_concepto            UQ_btcr_vigencias_futuras
dbo.btcr_regionalizacion         idx_btcr_sector_vigencia
dbo.btcr_pgn_vista_crosstab      FK_btcr_regionalizacion_dane
```

Se prefijaron también **restricciones e índices**: en una base compartida sus nombres deben ser únicos igual que los de las tablas. Si otro sistema ya tuviera un `PK_metadatos`, el `CREATE` habría fallado al instalar.

La base se renombró con `sp_rename`, no recreándola: **las 5.320 filas se conservaron**.

### Un error cometido y corregido

El primer intento fue un reemplazo global por nombre de tabla, y renombró también **las rutas de la API**: `/api/regionalizacion` → `/api/btcr_regionalizacion`. Eso habría roto el tablero completo y de la peor manera, haciéndolo caer a sus datos embebidos sin mostrar error.

Se detectó al revisar el resultado antes de aplicar nada, se revirtió y se rehizo acotando el reemplazo a contextos SQL (`dbo.`, `FROM`, `JOIN`, `REFERENCES`…). Después se verificó explícitamente que ninguna ruta contuviera `btcr` y que la lista de 322 rutas siguiera byte a byte igual.

**La regla quedó escrita** en `CLAUDE.md` y en el manual técnico: el prefijo es de almacenamiento, nunca del contrato público.

### Verificación

| | |
|---|---|
| Tablas con prefijo | 23 / 23 |
| Filas conservadas | 5.320 |
| Lista de 322 rutas | byte a byte idéntica |
| Paridad contra el sitio público | 318/322, cero diferencias bloqueantes |
| Los 8 cargadores ETL | todos OK contra la base renombrada |
| Datos recargados desde los Excel | **21 / 21 tablas idénticas** |

El último punto era el importante: no basta con que los cargadores no lancen excepción, sino que produzcan los mismos datos.

---

## 5. Nombre de base configurable y credenciales fuera del código

### El hallazgo

Al revisar los ejemplos para hacer configurable el nombre de la base apareció algo peor: las constantes `CONN_DEFAULT` de `etl/db.py` y `etl/migrate_sqlite_to_mssql.py` **traían la contraseña real**, versionada desde la fase 2 (`d7fa0b3`, `dfb3a5f`).

Se habían escrito como comodidad de desarrollo, y son la causa común de las dos cosas: fijaban la base y filtraban la credencial.

### Corrección

La conexión sale **únicamente** de `DNP_DPIP_CONN`. Sin valor por defecto, a propósito. Si falta, el programa termina con el formato esperado y la aclaración de que el nombre de la base es libre.

| Ámbito | Antes | Después |
|---|---|---|
| `etl/db.py` | `DATABASE=dnp_dpip` con contraseña | Solo la variable de entorno |
| `etl/migrate_sqlite_to_mssql.py` | Igual | Usa `dbmod.cadena_conexion()` |
| `tools/compare_bd.py` | Nombres fijos | `--a` desde `DNP_DPIP_DB` o exigido; `--b` obligatorio |
| Comentarios del DDL | «base dnp_dpip» | Explican que el nombre es libre y la collation no |
| Ejemplos en documentación | `dnp_dpip` / `dnp_dpip_app` | `MI_BASE` / `USUARIO` |

Los scripts de `db/mssql/` **ya eran independientes** del nombre: no llevan `USE` ni lo presuponen. El problema estaba solo en los valores por defecto y los ejemplos.

> **Acción pendiente del lado del DNP: rotar la contraseña.** Quitarla de `HEAD` no la borra del historial de git; sigue recuperable en esos dos commits. Basta con `ALTER LOGIN … WITH PASSWORD = '…'` y actualizar el `.env`. Reescribir el historial es posible pero más invasivo, y rotar es suficiente.

---

## Estado tras los cambios

El sistema sigue publicado en **https://dnp-btcr.skaphe.com**, con la misma verificación de siempre: **318 de 322 rutas idénticas a la línea base, cero diferencias de claves, valores o estado HTTP**.

Para desplegar en IIS con una base del DNP, ahora basta con:

1. Ejecutar `db/mssql/*.sql` sobre la base que entreguen — el prefijo evita colisiones.
2. `dotnet publish` y copiar la carpeta.
3. Definir la cadena de conexión.

Sin tocar código ni SQL.

### Pendientes

| Pendiente | Responsable |
|---|---|
| Rotar la contraseña de la base | DNP |
| Revisar logs de Caddy por accesos a los Excel expuestos | DNP |
| Revisión visual del tablero en navegador | DNP |
| Definir el servidor de producción y su base | DNP |

---

## Documentos relacionados

- `docs/DESPLIEGUE_IIS.md` — guía de despliegue en Windows/IIS
- `docs/ARQUITECTURA.md` — actualizado con el prefijo y el criterio de estáticos
- `docs/MANUAL_TECNICO.md` — la regla del prefijo y la de archivos estáticos
- `docs/INFORME_MIGRACION_DOTNET_SQLSERVER.md` — la migración que precede a estos cambios
