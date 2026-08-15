# Manual de operación — Bitácora de Inversión Pública

**Para:** quien carga una bitácora nueva, despliega o atiende una incidencia
**Actualizado:** 15 de agosto de 2026

---

## 1. Qué opera este sistema

| Elemento | Dónde |
|---|---|
| Tablero público | https://dnp-btcr.skaphe.com |
| Contenedor | `dnp-dpip-bitacora`, publicado en `127.0.0.1:5080` |
| Base de datos | SQL Server `dnp_dpip`, en el contenedor `umbraco-sqlserver` |
| Proxy | Caddy en el host (`/etc/caddy/Caddyfile`) |
| Repositorio | `/data/epv/pgn-bitacora` |

Comprobación de estado en cualquier momento:

```bash
docker compose ps                                   # debe decir "healthy"
curl -s -o /dev/null -w "%{http_code}\n" https://dnp-btcr.skaphe.com/health
```

---

## 2. Cargar una bitácora nueva

Es la tarea trimestral. Toma entre 20 y 40 minutos, la mayor parte esperando a que se procesen los Excel.

### 2.1 Antes de empezar

**Respalde la base.** Es el único paso irreversible de todo el procedimiento:

```bash
docker exec umbraco-sqlserver /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P "$SA_PASSWORD" -C -Q \
  "BACKUP DATABASE dnp_dpip TO DISK='/var/opt/mssql/backup/dnp_dpip_$(date +%F).bak' WITH INIT"
```

**Coloque los archivos fuente** en `data/BASES_BITACORA/<Mes>/`, respetando las carpetas numeradas por sección (`1. INVERSIONES...`, `3. REGIONALIZACIÓN`, etc.). Verifique que estén completos:

```bash
python etl/bases.py      # lista lo que encuentra por sección
```

**Prepare el entorno:**

```bash
source .venv/bin/activate
export DNP_DPIP_CONN="DRIVER={ODBC Driver 18 for SQL Server};SERVER=127.0.0.1,1433;DATABASE=dnp_dpip;UID=dnp_dpip_app;PWD=...;TrustServerCertificate=yes"
```

### 2.2 Hojas que deben venir en los Excel

Dos cargadores dependen de hojas que **no siempre vienen** en la entrega y que alguien debe generar antes:

| Archivo | Hoja requerida | Contenido |
|---|---|---|
| `5. VIGENCIAS FUTURAS/*Base VF*.xlsx` | `BASE_SIIF_2` | Debe incluir la columna calculada `Valor_VF_Final (Actual)` |
| `3. REGIONALIZACIÓN/Consolidado Reg-Ejec-*.xlsx` | `sectores_por_region` | Tabla consolidada: región, sector, apropiación, compromisos, obligaciones, pagos, año |

Si faltan, el cargador se detiene con un mensaje que dice exactamente qué falta. **Esto es intencional**: derivar esos valores de las columnas crudas produciría cifras equivocadas, y se comprobó que ninguna reproduce la serie histórica.

### 2.3 Ejecución — el orden importa

```bash
# 1. Crea la bitácora. Debe ir PRIMERO: los demás la resuelven
python etl/load_bitacora_excel.py \
    --numero 4 --periodo 2026-II --corte 2026-06-30 \
    --notas "Segundo trimestre 2026"

python etl/importar_pgn.py                 # Sec 2 — evolución presupuestal
python etl/load_regionalizacion.py         # Sec 3 — departamentos
python etl/load_sectores_region.py         # Sec 3 — sectores por región
python etl/load_ejecucion_sectorial.py     # Sec 4 y 6 — el más lento
python etl/load_vigencias_futuras.py       # Sec 5 — DESPUÉS del primero
python etl/load_credito.py                 # Sec 7
python etl/load_sgp.py
python etl/load_sgp_componentes.py         # Sec 8
```

**Dos precedencias que no se pueden alterar:**

1. `load_bitacora_excel.py` va primero porque **crea el registro de la bitácora** que todos los demás buscan como «la más reciente».
2. `load_vigencias_futuras.py` va después de él porque ambos escriben la sección 5, y el dedicado es el autoritativo: cubre 2025-2054 con 29 sectores frente a la carga parcial del primero.

### 2.4 Avisos que puede ver, y qué significan

| Mensaje | Qué hacer |
|---|---|
| `[!] tabla: N fila(s) con clave repetida en el origen` | Informativo. El Excel trae filas duplicadas y se conserva la última, igual que siempre. Vale la pena revisarlo con el área que produce el archivo |
| `WARN: región desconocida 'X'` | La región no está en la tabla de normalización. Si es una región nueva, hay que añadirla al cargador |
| `ERROR: ... con un año fuera del rango 2000-2100` | Celda mal digitada en el Excel. **Indica la celda exacta.** Corregir en el origen y reejecutar |
| `ERROR: no se encontró la hoja ...` | Falta una de las hojas de §2.2 |

### 2.5 Verificación posterior — obligatoria

```bash
# 1. La API responde y nada se rompió
python tools/compare_apis.py --contra-linea-base

# 2. El tablero refleja el corte nuevo
curl -s https://dnp-btcr.skaphe.com/api/resumen | head -c 400
```

Sobre el primer comando: **es esperable que reporte diferencias de valores**, porque los datos cambiaron a propósito. Lo que debe revisar es que **no haya diferencias de claves ni de estado HTTP** — esas sí indicarían un problema real. Las de valores hay que revisarlas una a una contra lo esperado del nuevo corte.

Si quiere una verificación más estricta, cargue primero en una base de pruebas y compare:

```bash
python tools/compare_bd.py --a dnp_dpip --b dnp_dpip_pruebas --periodo 2026-II
```

Por último, **abra el tablero** y recorra las ocho secciones. Confirme que el selector muestra el periodo nuevo y que el mapa dibuja.

### 2.6 Si algo salió mal

Los cargadores reemplazan los datos de su bitácora, así que **volver a ejecutar el cargador corregido suele bastar**. Si la bitácora quedó inconsistente:

```bash
python etl/load_bitacora_excel.py --numero 4 --periodo 2026-II --corte 2026-06-30 --replace
```

`--replace` borra la bitácora y todos sus datos antes de recargar. Si el daño es mayor, restaure el respaldo de §2.1.

---

## 3. Despliegue

### Actualizar la aplicación

```bash
cd /data/epv/pgn-bitacora
git pull
docker compose up -d --build
docker compose ps                                    # esperar "healthy"
python tools/compare_apis.py --contra-linea-base     # verificar
```

La reconstrucción tarda 1–2 minutos y hay un corte de servicio de unos segundos al reiniciar el contenedor.

### Cambiar la configuración

La cadena de conexión y demás variables están en `.env`, **que no se versiona**. `.env.example` es la plantilla. Tras modificarlo:

```bash
docker compose up -d      # recrea el contenedor con las variables nuevas
```

### Revertir

```bash
git log --oneline -10
git checkout <commit-anterior>
docker compose up -d --build
```

Los datos viven en el volumen de SQL Server, no en la imagen: revertir la aplicación **no afecta la información cargada**.

---

## 4. Incidencias

### El tablero no carga

```bash
docker compose ps                     # ¿el contenedor está arriba?
docker compose logs --tail 50 api     # ¿qué dice?
systemctl status caddy                # ¿el proxy está activo?
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5080/health
```

Si el `/health` local responde 200 pero el dominio no, el problema está en Caddy o en el DNS, no en la aplicación.

### El tablero carga pero muestra cifras que no corresponden

Es el síntoma característico de que **el frontend cayó a sus datos de respaldo**: está diseñado para no verse roto si la API falla, de modo que un error se manifiesta como cifras viejas, no como pantalla de error.

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://dnp-btcr.skaphe.com/api/resumen
python tools/compare_apis.py --contra-linea-base
```

Revise también la consola del navegador (F12): allí aparecen las peticiones fallidas.

### El mapa se ve en blanco

Los GeoJSON no están llegando:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://dnp-btcr.skaphe.com/data/dptos.geojson
```

Debe dar 200. Si da 404, es un problema de configuración de archivos estáticos en la aplicación.

### El certificado expiró

Caddy lo renueva solo. Si algo falló:

```bash
sudo systemctl restart caddy
sudo journalctl -u caddy --since "1 hour ago" | grep -i "certificate\|error"
```

### La base no responde

```bash
docker ps | grep umbraco-sqlserver
docker exec umbraco-sqlserver /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P "$SA_PASSWORD" -C -Q "SELECT 1"
```

Ese contenedor **también aloja la base de Umbraco**: reiniciarlo afecta a otro sistema. Coordine antes de hacerlo.

---

## 5. Mantenimiento periódico

| Tarea | Frecuencia |
|---|---|
| Respaldo de `dnp_dpip` | Antes de cada cargue, y programado según la política de la entidad |
| Verificar el certificado | Automático; revisar si hay alerta |
| Actualizar imagen base de .NET | Con cada versión de parche de seguridad |
| Revisar espacio en disco | Mensual — los respaldos se acumulan |

---

## 6. Datos de contacto del entorno

| Recurso | Valor |
|---|---|
| Servidor | Entorno de **desarrollo y pruebas** — el destino productivo está pendiente de definir |
| Base | `dnp_dpip` en `umbraco-sqlserver` (compartido con Umbraco) |
| Usuario de aplicación | `dnp_dpip_app`, con permisos acotados a esa base |
| Red Docker | `sbn-ecp_umbraco-network` |
| Puerto interno | `127.0.0.1:5080` |

---

## Documentos relacionados

- `docs/MANUAL_TECNICO.md` — para modificar el código
- `docs/ARQUITECTURA.md` — visión de conjunto
- `docs/etl_uso.md` — detalle de cada cargador
- `docs/MANUAL_USUARIO.md` — uso del tablero
