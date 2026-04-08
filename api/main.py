"""
api/main.py  —  API REST Bitácora PGN
FastAPI · SQLite
Ejecutar: uvicorn api.main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import sqlite3
import json
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "db" / "pgn.db"

app = FastAPI(
    title="API Bitácora PGN",
    description="Inversión pública Colombia 2022-2025 – DNP/DPIP",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_list(rows):
    return [dict(r) for r in rows]


# ──────────────────────────────────────────────
# METADATOS
# ──────────────────────────────────────────────
@app.get("/api/bitacoras", tags=["Metadatos"])
def list_bitacoras():
    """Lista todas las bitácoras cargadas."""
    db = get_db()
    rows = db.execute("SELECT * FROM metadatos_bitacora ORDER BY corte_fecha DESC").fetchall()
    return rows_to_list(rows)


@app.get("/api/bitacoras/{periodo}", tags=["Metadatos"])
def get_bitacora(periodo: str):
    db = get_db()
    row = db.execute(
        "SELECT * FROM metadatos_bitacora WHERE periodo=?", (periodo,)
    ).fetchone()
    if not row:
        raise HTTPException(404, f"Bitácora periodo '{periodo}' no encontrada")
    return dict(row)


# ──────────────────────────────────────────────
# SECCIÓN 1 – TRANSFORMACIONES PND
# ──────────────────────────────────────────────
@app.get("/api/transformaciones", tags=["Sec 1 - Transformaciones PND"])
def get_transformaciones(vigencia: int = 2025):
    """Distribución de inversión por transformadores del PND 2022-2026."""
    db = get_db()
    rows = db.execute("""
        SELECT t.transformador, t.inversion_mmm, t.peso_pct,
               e.compromisos_mmm, e.obligaciones_mmm, e.pagos_mmm,
               e.pct_c_av, e.pct_o_av, e.pct_p_av
        FROM inversion_transformaciones t
        LEFT JOIN ejecucion_transformaciones e
               ON t.bitacora_id=e.bitacora_id AND t.vigencia=e.vigencia
              AND t.transformador=e.transformador
        WHERE t.vigencia=?
        ORDER BY t.inversion_mmm DESC
    """, (vigencia,)).fetchall()
    return rows_to_list(rows)


@app.get("/api/transformaciones/{transformador}/componentes", tags=["Sec 1 - Transformaciones PND"])
def get_componentes(transformador: str, vigencia: int = 2025):
    """Componentes de un transformador PND."""
    db = get_db()
    rows = db.execute("""
        SELECT componente, vigente_mmm, peso_pct
        FROM inversion_componentes_pnd
        WHERE vigencia=? AND transformador=?
        ORDER BY vigente_mmm DESC
    """, (vigencia, transformador)).fetchall()
    return rows_to_list(rows)


# ──────────────────────────────────────────────
# SECCIÓN 2 – EVOLUCIÓN PRESUPUESTAL
# ──────────────────────────────────────────────
@app.get("/api/evolucion", tags=["Sec 2 - Evolución Presupuestal"])
def get_evolucion(
    rubro: Optional[str] = Query(None, description="Filtra por rubro: Funcionamiento, Inversión, Servicio Deuda, TOTAL PGN")
):
    """Evolución del PGN 2022-2025 por rubro principal."""
    db = get_db()
    sql = """
        SELECT vigencia, rubro, sub_rubro, vigente_mmm,
               compromisos_mmm, obligaciones_mmm, pagos_mmm, pct_pgn
        FROM evolucion_presupuestal
        WHERE sub_rubro IS NULL
    """
    params = []
    if rubro:
        sql += " AND rubro=?"
        params.append(rubro)
    sql += " ORDER BY vigencia, rubro"
    rows = db.execute(sql, params).fetchall()
    return rows_to_list(rows)


@app.get("/api/evolucion/inversion_historica", tags=["Sec 2 - Evolución Presupuestal"])
def get_inversion_historica():
    """Serie histórica de inversión 2022-2025 con indicadores macroeconómicos."""
    db = get_db()
    rows = db.execute("""
        SELECT vigencia, vigente_mmm, compromisos_mmm, obligaciones_mmm, pagos_mmm,
               pct_compromisos, pct_obligaciones, pct_pagos, inv_pct_pib, inv_pct_gasto_total
        FROM ejecucion_historica
        ORDER BY vigencia
    """).fetchall()
    return rows_to_list(rows)


# ──────────────────────────────────────────────
# SECCIÓN 3 – REGIONALIZACIÓN
# ──────────────────────────────────────────────
@app.get("/api/regionalizacion", tags=["Sec 3 - Regionalización"])
def get_regionalizacion(region: Optional[str] = None):
    """Regionalización 2025 por región y departamento."""
    db = get_db()
    sql = """
        SELECT region, departamento, vigente_mm, compromisos_mm, obligaciones_mm, pagos_mm,
               pct_ejec_compromisos, pct_ejec_obligaciones, pct_ejec_pagos,
               pct_participacion, principales_sectores
        FROM regionalizacion_detalle_2025
        WHERE 1=1
    """
    params = []
    if region:
        sql += " AND region=?"
        params.append(region.upper())
    sql += " ORDER BY region, pct_participacion DESC NULLS LAST"
    rows = db.execute(sql, params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("principales_sectores"):
            try:
                d["principales_sectores"] = json.loads(d["principales_sectores"])
            except Exception:
                pass
        result.append(d)
    return result


@app.get("/api/regionalizacion/historico", tags=["Sec 3 - Regionalización"])
def get_regionalizacion_historico():
    """Histórico regionalización 2022-2025 (totales regionales)."""
    db = get_db()
    rows = db.execute("""
        SELECT vigencia, region, departamento, apropiacion_mm, compromisos_mm,
               obligaciones_mm, pagos_mm
        FROM regionalizacion_resumen
        ORDER BY vigencia, region
    """).fetchall()
    return rows_to_list(rows)


# ──────────────────────────────────────────────
# SECCIÓN 4 – EJECUCIÓN
# ──────────────────────────────────────────────
@app.get("/api/ejecucion", tags=["Sec 4 - Ejecución"])
def get_ejecucion():
    """Ejecución presupuestal histórica de inversión 2022-2025."""
    db = get_db()
    rows = db.execute("""
        SELECT vigencia, vigente_mmm, compromisos_mmm, obligaciones_mmm, pagos_mmm,
               pct_compromisos, pct_obligaciones, pct_pagos, inv_pct_pib, inv_pct_gasto_total
        FROM ejecucion_historica ORDER BY vigencia
    """).fetchall()
    return rows_to_list(rows)


@app.get("/api/ejecucion/sectores/apropiacion", tags=["Sec 4 - Ejecución"])
def get_apropiacion_sectores(vigencia: Optional[int] = None):
    """Apropiación vigente por sector y año."""
    db = get_db()
    sql = "SELECT vigencia, sector, vigente_mmm FROM apropiacion_por_sector WHERE 1=1"
    params = []
    if vigencia:
        sql += " AND vigencia=?"
        params.append(vigencia)
    sql += " ORDER BY vigencia, vigente_mmm DESC NULLS LAST"
    rows = db.execute(sql, params).fetchall()
    return rows_to_list(rows)


@app.get("/api/ejecucion/sectores/compromisos_pct", tags=["Sec 4 - Ejecución"])
def get_compromisos_pct():
    """% de compromisos sobre apropiación por sector 2022-2025."""
    db = get_db()
    rows = db.execute("""
        SELECT vigencia, sector, pct_compromisos
        FROM compromisos_pct_por_sector ORDER BY vigencia, pct_compromisos DESC
    """).fetchall()
    return rows_to_list(rows)


# ──────────────────────────────────────────────
# SECCIÓN 5 – VIGENCIAS FUTURAS
# ──────────────────────────────────────────────
@app.get("/api/vigencias_futuras", tags=["Sec 5 - Vigencias Futuras"])
def get_vigencias_futuras(sector: Optional[str] = None):
    """Vigencias futuras comprometidas 2026-2040 (miles de millones COP constantes 2025)."""
    db = get_db()
    sql = """
        SELECT vigencia_exec, sector, valor_mmm_ctes, pct_pib
        FROM vigencias_futuras WHERE 1=1
    """
    params = []
    if sector:
        sql += " AND sector=?"
        params.append(sector.upper())
    sql += " ORDER BY vigencia_exec, valor_mmm_ctes DESC"
    rows = db.execute(sql, params).fetchall()
    return rows_to_list(rows)


@app.get("/api/vigencias_futuras/totales", tags=["Sec 5 - Vigencias Futuras"])
def get_vigencias_totales():
    """Total vigencias futuras por año 2026-2040."""
    db = get_db()
    rows = db.execute("""
        SELECT vigencia_exec,
               ROUND(SUM(valor_mmm_ctes), 3) AS total_mmm,
               MAX(pct_pib) AS pct_pib
        FROM vigencias_futuras
        GROUP BY vigencia_exec
        ORDER BY vigencia_exec
    """).fetchall()
    return rows_to_list(rows)


# ──────────────────────────────────────────────
# SECCIÓN 6 – EJECUCIÓN SECTORIAL
# ──────────────────────────────────────────────
@app.get("/api/sectorial", tags=["Sec 6 - Ejecución Sectorial"])
def get_sectorial(
    vigencia: int = 2025,
    sector: Optional[str] = None
):
    """Ejecución sectorial por entidad."""
    db = get_db()
    sql = """
        SELECT vigencia, sector, entidad, apr_vigente_mmm,
               compromisos_mmm, obligaciones_mmm, pct_c_av, pct_o_av
        FROM ejecucion_sectorial_entidades
        WHERE vigencia=?
    """
    params = [vigencia]
    if sector:
        sql += " AND sector=?"
        params.append(sector.upper())
    sql += " ORDER BY sector, apr_vigente_mmm DESC NULLS LAST"
    rows = db.execute(sql, params).fetchall()
    return rows_to_list(rows)


@app.get("/api/sectorial/mensual", tags=["Sec 6 - Ejecución Sectorial"])
def get_sectorial_mensual(sector: Optional[str] = None, vigencia: int = 2025):
    """Ejecución mensual sectorial Ene-Mar comparada con años anteriores."""
    db = get_db()
    sql = """
        SELECT vigencia, sector, mes,
               pct_compromisos_2025, pct_compromisos_2024,
               pct_compromisos_prom, pct_compromisos_mejor
        FROM ejecucion_sectorial_mensual
        WHERE vigencia=?
    """
    params = [vigencia]
    if sector:
        sql += " AND sector=?"
        params.append(sector.upper())
    sql += " ORDER BY sector, mes"
    rows = db.execute(sql, params).fetchall()
    return rows_to_list(rows)


# ──────────────────────────────────────────────
# ENDPOINT RESUMEN (útil para el dashboard)
# ──────────────────────────────────────────────
@app.get("/api/resumen", tags=["Dashboard"])
def get_resumen():
    """KPIs principales para el dashboard de la infografía."""
    db = get_db()
    inv = db.execute(
        "SELECT * FROM ejecucion_historica WHERE vigencia=2025"
    ).fetchone()
    total_transf = db.execute(
        "SELECT SUM(inversion_mmm) as total FROM inversion_transformaciones WHERE vigencia=2025"
    ).fetchone()
    vf_total = db.execute(
        "SELECT ROUND(SUM(valor_mmm_ctes),1) as total FROM vigencias_futuras"
    ).fetchone()
    return {
        "vigencia": 2025,
        "corte": "31 de marzo de 2025",
        "inversion_vigente_mmm": dict(inv)["vigente_mmm"] if inv else None,
        "inversion_compromisos_mmm": dict(inv)["compromisos_mmm"] if inv else None,
        "inversion_obligaciones_mmm": dict(inv)["obligaciones_mmm"] if inv else None,
        "inversion_pagos_mmm": dict(inv)["pagos_mmm"] if inv else None,
        "pct_compromisos": dict(inv)["pct_compromisos"] if inv else None,
        "pct_obligaciones": dict(inv)["pct_obligaciones"] if inv else None,
        "pct_pagos": dict(inv)["pct_pagos"] if inv else None,
        "inv_pct_pib": dict(inv)["inv_pct_pib"] if inv else None,
        "total_transformaciones_mmm": dict(total_transf)["total"],
        "vigencias_futuras_total_mmm_ctes": dict(vf_total)["total"],
        "fuente": "SIIF Nación / DPIP - DNP",
    }


# ──────────────────────────────────────────────
# FRONTEND ESTÁTICO
# Debe ir al final, después de todas las rutas /api
# ──────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
