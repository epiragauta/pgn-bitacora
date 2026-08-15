"""
tools/endpoints.py — Enumeración de todas las rutas de la API.

Fuente única de verdad de "qué hay que probar". La usan:
  · tools/capture_baseline.py — congela las respuestas de referencia
  · tools/compare_apis.py     — verifica la API contra esa referencia

Los parámetros no se inventan: se derivan de los datos reales de la base,
de modo que al cargar una bitácora nueva la cobertura crece sola en lugar
de quedarse obsoleta.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent.parent / "etl"))

FASES = ["Vigente", "Comprometido", "Obligado", "Pagado"]


def _conectar():
    """Conexión a SQL Server, con la misma convención que los ETL.

    Antes esto leía db/pgn.db. Al retirarse SQLite en la fase 7, los
    parámetros se derivan de la base viva: es la que define qué vigencias,
    regiones y sectores existen realmente.
    """
    import pyodbc  # se importa aquí para no exigirlo si solo se lee el módulo

    cadena = os.environ.get("DNP_DPIP_CONN")
    if not cadena:
        from db import CONN_DEFAULT  # etl/db.py
        cadena = CONN_DEFAULT
    return pyodbc.connect(cadena)


def _col(conn, sql: str) -> list:
    """Primera columna de una consulta, sin NULLs."""
    return [r[0] for r in conn.cursor().execute(sql).fetchall() if r[0] is not None]


def _distintos(conn, expr: str, tabla: str, where: str = "") -> list:
    """Valores distintos de una columna de texto, en orden binario.

    El orden importa: define la secuencia de rutas y, con ella, la
    comparabilidad entre ejecuciones. SQL Server ordena por diccionario y
    SQLite lo hacía por bytes, así que se fuerza Latin1_General_BIN2 para
    que la lista no cambie respecto de la línea base. Hace falta la
    subconsulta porque SELECT DISTINCT no admite ordenar por una expresión
    que no esté en la lista de selección.
    """
    filtro = f" WHERE {where}" if where else ""
    return _col(conn, (
        f"SELECT v FROM (SELECT DISTINCT {expr} AS v FROM {tabla}{filtro}) t "
        f"ORDER BY v COLLATE Latin1_General_BIN2"
    ))


def build_urls(conn=None) -> list[str]:
    """Devuelve todas las rutas a verificar, en orden estable."""
    conn = conn or _conectar()

    bitacoras = _col(conn, "SELECT id FROM metadatos_bitacora ORDER BY id")
    periodos = _col(conn, "SELECT periodo FROM metadatos_bitacora ORDER BY id")
    # Cada bitácora usa su propia convención de nombres ('CONVERGENCIA
    # REGIONAL' en la 1, '5. CONVERGENCIA REGIONAL' en la 2), así que el
    # transformador se empareja con su bitácora: consultarlo contra otra
    # devuelve vacío y no verifica nada.
    transformadores = conn.cursor().execute(
        "SELECT bitacora_id, t FROM ("
        "  SELECT DISTINCT bitacora_id, transformador AS t FROM inversion_transformaciones"
        ") x ORDER BY bitacora_id, t COLLATE Latin1_General_BIN2"
    ).fetchall()
    conceptos = _col(conn, "SELECT nombre FROM pgn_concepto ORDER BY orden")
    anios_pgn = _col(conn, "SELECT DISTINCT anio FROM pgn_ejecucion ORDER BY anio")
    rubros = _distintos(conn, "REPLACE(nombre,'Servicio de la Deuda','Servicio Deuda')",
                        "pgn_concepto", "nivel=2 AND unidad='Miles mm COP'")
    vig_reg = _col(conn, "SELECT DISTINCT vigencia FROM regionalizacion ORDER BY vigencia")
    regiones = _distintos(conn, "region", "regionalizacion")
    vig_reg_sec = _col(conn, "SELECT DISTINCT vigencia FROM regionalizacion_sectores ORDER BY vigencia")
    reg_sec = _distintos(conn, "region", "regionalizacion_sectores")
    danes = _distintos(conn, "codigo_dane", "regionalizacion", "codigo_dane IS NOT NULL")
    sect_vf = _distintos(conn, "sector", "vigencias_futuras")
    sect_ent = _distintos(conn, "sector", "ejecucion_sectorial_entidades")
    sect_men = _distintos(conn, "sector", "ejecucion_sectorial_mensual")
    cred_fuentes = _distintos(conn, "fuente", "credito_portafolio")
    cred_sectores = _distintos(conn, "sector", "credito_portafolio")

    conn.close()

    urls: list[str] = []

    def add(path: str, **params) -> None:
        """Agrega una ruta; los parámetros None se omiten."""
        qs = "&".join(f"{k}={quote(str(v))}" for k, v in params.items() if v is not None)
        urls.append(f"{path}?{qs}" if qs else path)

    # ── Metadatos ──────────────────────────────────────────
    add("/api/bitacoras")
    for p in periodos:
        add(f"/api/bitacoras/{quote(p)}")

    # Endpoints que aceptan bitacora_id: se prueban sin parámetro
    # (bitácora más reciente) y con cada id explícito.
    bids = [None] + bitacoras

    # ── Sec 1 · Transformaciones PND ───────────────────────
    for b in bids:
        add("/api/transformaciones", bitacora_id=b)
    for b, t in transformadores:
        add(f"/api/transformaciones/{quote(t)}/componentes", bitacora_id=b)

    # ── Sec 2 · Evolución presupuestal ─────────────────────
    add("/api/evolucion")
    for r in rubros:
        add("/api/evolucion", rubro=r)
    for a in anios_pgn:
        for f in FASES:
            add("/api/evolucion/composicion", anio=a, fase=f)
    add("/api/evolucion/tasa_ejecucion")
    add("/api/evolucion/pct_pib")
    for c in conceptos:
        add("/api/evolucion/drilldown", concepto=c, anio=max(anios_pgn), fase="Vigente")
    add("/api/evolucion/tabla_completa")
    add("/api/evolucion/inversion_historica")

    # ── Sec 3 · Regionalización ────────────────────────────
    for v in vig_reg:
        add("/api/regionalizacion", vigencia=v)
        for r in regiones:
            add("/api/regionalizacion", vigencia=v, region=r)
        add("/api/regionalizacion/mapa", vigencia=v)
    add("/api/regionalizacion/historico")
    for v in vig_reg_sec:
        add("/api/regionalizacion/sectores", vigencia=v)
        for r in reg_sec:
            add("/api/regionalizacion/sectores", vigencia=v, region=r)
    for d in danes:
        add(f"/api/regionalizacion/departamento/{quote(d)}")

    # ── Sec 4 · Ejecución ──────────────────────────────────
    for b in bids:
        add("/api/ejecucion", bitacora_id=b)
    add("/api/ejecucion/sectores/apropiacion")
    add("/api/ejecucion/sectores/compromisos_pct")
    add("/api/ejecucion/sectores/obligaciones_pct")
    add("/api/ejecucion/sectores/pagos_pct")
    add("/api/ejecucion/sectores/matriz")

    # ── Sec 5 · Vigencias futuras ──────────────────────────
    add("/api/vigencias_futuras")
    for s in sect_vf:
        add("/api/vigencias_futuras", sector=s)
    add("/api/vigencias_futuras/totales")
    add("/api/vigencias_futuras/chart")

    # ── Sec 6 · Ejecución sectorial ────────────────────────
    add("/api/sectorial")
    add("/api/sectorial/historico")
    add("/api/sectorial/mensual")
    for s in sect_ent:
        add("/api/sectorial", sector=s)
        add("/api/sectorial/historico", sector=s)
    for s in sect_men:
        add("/api/sectorial/mensual", sector=s)

    # ── Sec 7 · Crédito externo ────────────────────────────
    add("/api/credito")
    for f in cred_fuentes:
        add("/api/credito", fuente=f)
    for s in cred_sectores:
        add("/api/credito", sector=s)
    add("/api/credito/fuentes")
    add("/api/credito/sectores")
    add("/api/credito/resumen")
    add("/api/credito/ejecucion_entidad")
    add("/api/credito/ejecucion_historica")

    # ── Sec 8 · SGP ────────────────────────────────────────
    add("/api/sgp/historico")
    add("/api/sgp/historico_componentes")
    add("/api/sgp/resumen")

    # ── Dashboard ──────────────────────────────────────────
    for b in bids:
        add("/api/resumen", bitacora_id=b)

    return urls


def slug(url: str) -> str:
    """Nombre de archivo seguro y estable para una ruta."""
    s = url.removeprefix("/api/").replace("/", "__")
    return "".join(ch if ch.isalnum() or ch in "._-=&%" else "_" for ch in s) or "root"


if __name__ == "__main__":
    for u in build_urls():
        print(u)
