"""
api/main.py  —  API REST Bitácora PGN
FastAPI · SQLite
Ejecutar: uvicorn api.main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import sqlite3
import json
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "db" / "pgn.db"

app = FastAPI(
    title="API Bitácora PGN",
    description="Inversión pública Colombia 2022-2026 – DNP/DPIP",
    version="2.0.0",
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


def resolve_bitacora(conn, bitacora_id: Optional[int] = None):
    """Devuelve (id, vigencia_año). Sin parámetro usa la bitácora más reciente."""
    sql = "SELECT id, CAST(strftime('%Y', corte_fecha) AS INT) AS vigencia FROM metadatos_bitacora"
    if bitacora_id:
        row = conn.execute(sql + " WHERE id=?", (bitacora_id,)).fetchone()
    else:
        row = conn.execute(sql + " ORDER BY corte_fecha DESC LIMIT 1").fetchone()
    if not row:
        raise HTTPException(404, "Bitácora no encontrada")
    return row["id"], row["vigencia"]


# ──────────────────────────────────────────────
# METADATOS
# ──────────────────────────────────────────────
@app.get("/api/bitacoras", tags=["Metadatos"])
def list_bitacoras():
    """Lista todas las bitácoras cargadas (más reciente primero)."""
    db = get_db()
    rows = db.execute("""
        SELECT *, CAST(strftime('%Y', corte_fecha) AS INT) AS vigencia
        FROM metadatos_bitacora ORDER BY corte_fecha DESC
    """).fetchall()
    return rows_to_list(rows)


@app.get("/api/bitacoras/{periodo}", tags=["Metadatos"])
def get_bitacora(periodo: str):
    db = get_db()
    row = db.execute(
        "SELECT *, CAST(strftime('%Y', corte_fecha) AS INT) AS vigencia "
        "FROM metadatos_bitacora WHERE periodo=?", (periodo,)
    ).fetchone()
    if not row:
        raise HTTPException(404, f"Bitácora periodo '{periodo}' no encontrada")
    return dict(row)


# ──────────────────────────────────────────────
# SECCIÓN 1 – TRANSFORMACIONES PND
# ──────────────────────────────────────────────
@app.get("/api/transformaciones", tags=["Sec 1 - Transformaciones PND"])
def get_transformaciones(bitacora_id: Optional[int] = None):
    """Distribución de inversión por transformadores del PND 2022-2026."""
    db = get_db()
    bid, vigencia = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT t.transformador, t.inversion_mmm, t.peso_pct,
               e.compromisos_mmm, e.obligaciones_mmm, e.pagos_mmm,
               e.pct_c_av, e.pct_o_av, e.pct_p_av
        FROM inversion_transformaciones t
        LEFT JOIN ejecucion_transformaciones e
               ON t.bitacora_id=e.bitacora_id AND t.vigencia=e.vigencia
              AND t.transformador=e.transformador
        WHERE t.bitacora_id=? AND t.vigencia=?
        ORDER BY t.inversion_mmm DESC
    """, (bid, vigencia)).fetchall()
    return rows_to_list(rows)


@app.get("/api/transformaciones/{transformador}/componentes", tags=["Sec 1 - Transformaciones PND"])
def get_componentes(transformador: str, bitacora_id: Optional[int] = None):
    """Componentes de un transformador PND."""
    db = get_db()
    bid, vigencia = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT componente, vigente_mmm, peso_pct
        FROM inversion_componentes_pnd
        WHERE bitacora_id=? AND vigencia=? AND transformador=?
        ORDER BY vigente_mmm DESC
    """, (bid, vigencia, transformador)).fetchall()
    return rows_to_list(rows)


# ──────────────────────────────────────────────
# SECCIÓN 2 – EVOLUCIÓN PRESUPUESTAL
# ──────────────────────────────────────────────
@app.get("/api/evolucion", tags=["Sec 2 - Evolución Presupuestal"])
def get_evolucion(
    bitacora_id: Optional[int] = None,
    rubro: Optional[str] = Query(None, description="Filtra por rubro: Funcionamiento, Inversión, Servicio Deuda, TOTAL PGN")
):
    """Evolución del PGN por rubro principal."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    sql = """
        SELECT vigencia, rubro, sub_rubro, vigente_mmm,
               compromisos_mmm, obligaciones_mmm, pagos_mmm, pct_pgn
        FROM evolucion_presupuestal
        WHERE bitacora_id=? AND sub_rubro IS NULL
    """
    params: list = [bid]
    if rubro:
        sql += " AND rubro=?"
        params.append(rubro)
    sql += " ORDER BY vigencia, rubro"
    return rows_to_list(db.execute(sql, params).fetchall())


@app.get("/api/evolucion/inversion_historica", tags=["Sec 2 - Evolución Presupuestal"])
def get_inversion_historica(bitacora_id: Optional[int] = None):
    """Serie histórica de inversión con indicadores macroeconómicos."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT vigencia, vigente_mmm, compromisos_mmm, obligaciones_mmm, pagos_mmm,
               pct_compromisos, pct_obligaciones, pct_pagos, inv_pct_pib, inv_pct_gasto_total
        FROM ejecucion_historica WHERE bitacora_id=? ORDER BY vigencia
    """, (bid,)).fetchall()
    return rows_to_list(rows)


# ──────────────────────────────────────────────
# SECCIÓN 3 – REGIONALIZACIÓN
# ──────────────────────────────────────────────
@app.get("/api/regionalizacion", tags=["Sec 3 - Regionalización"])
def get_regionalizacion(bitacora_id: Optional[int] = None, region: Optional[str] = None):
    """Regionalización por región y departamento."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    sql = """
        SELECT region, departamento, vigente_mm, compromisos_mm, obligaciones_mm, pagos_mm,
               pct_ejec_compromisos, pct_ejec_obligaciones, pct_ejec_pagos,
               pct_participacion, principales_sectores
        FROM regionalizacion_detalle_2025
        WHERE bitacora_id=?
    """
    params: list = [bid]
    if region:
        sql += " AND region=?"
        params.append(region.upper())
    sql += " ORDER BY region, pct_participacion DESC NULLS LAST"
    result = []
    for r in db.execute(sql, params).fetchall():
        d = dict(r)
        if d.get("principales_sectores"):
            try:
                d["principales_sectores"] = json.loads(d["principales_sectores"])
            except Exception:
                pass
        result.append(d)
    return result


@app.get("/api/regionalizacion/historico", tags=["Sec 3 - Regionalización"])
def get_regionalizacion_historico(bitacora_id: Optional[int] = None):
    """Histórico regionalización (totales regionales)."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT vigencia, region, departamento, apropiacion_mm, compromisos_mm,
               obligaciones_mm, pagos_mm
        FROM regionalizacion_resumen WHERE bitacora_id=? ORDER BY vigencia, region
    """, (bid,)).fetchall()
    return rows_to_list(rows)


# ──────────────────────────────────────────────
# SECCIÓN 4 – EJECUCIÓN
# ──────────────────────────────────────────────
@app.get("/api/ejecucion", tags=["Sec 4 - Ejecución"])
def get_ejecucion(bitacora_id: Optional[int] = None):
    """Ejecución presupuestal histórica de inversión."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT vigencia, vigente_mmm, compromisos_mmm, obligaciones_mmm, pagos_mmm,
               pct_compromisos, pct_obligaciones, pct_pagos, inv_pct_pib, inv_pct_gasto_total
        FROM ejecucion_historica WHERE bitacora_id=? ORDER BY vigencia
    """, (bid,)).fetchall()
    return rows_to_list(rows)


@app.get("/api/ejecucion/sectores/apropiacion", tags=["Sec 4 - Ejecución"])
def get_apropiacion_sectores(bitacora_id: Optional[int] = None):
    """Apropiación vigente por sector."""
    db = get_db()
    bid, vigencia = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT vigencia, sector, vigente_mmm FROM apropiacion_por_sector
        WHERE bitacora_id=? AND vigencia=?
        ORDER BY vigente_mmm DESC NULLS LAST
    """, (bid, vigencia)).fetchall()
    return rows_to_list(rows)


@app.get("/api/ejecucion/sectores/compromisos_pct", tags=["Sec 4 - Ejecución"])
def get_compromisos_pct(bitacora_id: Optional[int] = None):
    """% de compromisos sobre apropiación por sector."""
    db = get_db()
    bid, vigencia = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT vigencia, sector, pct_compromisos
        FROM compromisos_pct_por_sector
        WHERE bitacora_id=? AND vigencia=?
        ORDER BY pct_compromisos DESC
    """, (bid, vigencia)).fetchall()
    return rows_to_list(rows)


# ──────────────────────────────────────────────
# SECCIÓN 5 – VIGENCIAS FUTURAS
# ──────────────────────────────────────────────
@app.get("/api/vigencias_futuras", tags=["Sec 5 - Vigencias Futuras"])
def get_vigencias_futuras(bitacora_id: Optional[int] = None, sector: Optional[str] = None):
    """Vigencias futuras comprometidas (miles de millones COP corrientes)."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    sql = "SELECT vigencia_exec, sector, valor_mmm_ctes, pct_pib FROM vigencias_futuras WHERE bitacora_id=?"
    params: list = [bid]
    if sector:
        sql += " AND sector=?"
        params.append(sector.upper())
    sql += " ORDER BY vigencia_exec, valor_mmm_ctes DESC"
    return rows_to_list(db.execute(sql, params).fetchall())


@app.get("/api/vigencias_futuras/totales", tags=["Sec 5 - Vigencias Futuras"])
def get_vigencias_totales(bitacora_id: Optional[int] = None):
    """Total vigencias futuras por año."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT vigencia_exec,
               ROUND(SUM(valor_mmm_ctes), 3) AS total_mmm,
               MAX(pct_pib) AS pct_pib
        FROM vigencias_futuras WHERE bitacora_id=?
        GROUP BY vigencia_exec ORDER BY vigencia_exec
    """, (bid,)).fetchall()
    return rows_to_list(rows)


# ──────────────────────────────────────────────
# SECCIÓN 6 – EJECUCIÓN SECTORIAL
# ──────────────────────────────────────────────
@app.get("/api/sectorial", tags=["Sec 6 - Ejecución Sectorial"])
def get_sectorial(bitacora_id: Optional[int] = None, sector: Optional[str] = None):
    """Ejecución sectorial por entidad."""
    db = get_db()
    bid, vigencia = resolve_bitacora(db, bitacora_id)
    sql = """
        SELECT vigencia, sector, entidad, apr_vigente_mmm,
               compromisos_mmm, obligaciones_mmm, pct_c_av, pct_o_av
        FROM ejecucion_sectorial_entidades
        WHERE bitacora_id=? AND vigencia=?
    """
    params: list = [bid, vigencia]
    if sector:
        sql += " AND sector=?"
        params.append(sector.upper())
    sql += " ORDER BY sector, apr_vigente_mmm DESC NULLS LAST"
    return rows_to_list(db.execute(sql, params).fetchall())


@app.get("/api/sectorial/mensual", tags=["Sec 6 - Ejecución Sectorial"])
def get_sectorial_mensual(bitacora_id: Optional[int] = None, sector: Optional[str] = None):
    """Ejecución mensual sectorial comparada con años anteriores."""
    db = get_db()
    bid, vigencia = resolve_bitacora(db, bitacora_id)
    sql = """
        SELECT vigencia, sector, mes,
               pct_compromisos_2025, pct_compromisos_2024,
               pct_compromisos_prom, pct_compromisos_mejor
        FROM ejecucion_sectorial_mensual
        WHERE bitacora_id=? AND vigencia=?
    """
    params: list = [bid, vigencia]
    if sector:
        sql += " AND sector=?"
        params.append(sector.upper())
    sql += " ORDER BY sector, mes"
    return rows_to_list(db.execute(sql, params).fetchall())


# ──────────────────────────────────────────────
# ENDPOINT RESUMEN
# ──────────────────────────────────────────────
@app.get("/api/resumen", tags=["Dashboard"])
def get_resumen(bitacora_id: Optional[int] = None):
    """KPIs principales para el dashboard de la infografía."""
    db = get_db()
    bid, vigencia = resolve_bitacora(db, bitacora_id)

    meta = db.execute(
        "SELECT periodo, corte_fecha, numero_bitacora FROM metadatos_bitacora WHERE id=?", (bid,)
    ).fetchone()

    inv = db.execute(
        "SELECT * FROM ejecucion_historica WHERE bitacora_id=? AND vigencia=?", (bid, vigencia)
    ).fetchone()

    # Si no hay ejecucion_historica, derivar totales desde ejecucion_transformaciones
    if not inv:
        totals = db.execute("""
            SELECT ROUND(SUM(apr_vigente_mmm),3) AS vigente_mmm,
                   ROUND(SUM(compromisos_mmm),3)  AS compromisos_mmm,
                   ROUND(SUM(obligaciones_mmm),3) AS obligaciones_mmm,
                   ROUND(SUM(pagos_mmm),3)         AS pagos_mmm
            FROM ejecucion_transformaciones WHERE bitacora_id=? AND vigencia=?
        """, (bid, vigencia)).fetchone()
        inv_data: dict = dict(totals) if totals else {}
        v = inv_data.get("vigente_mmm") or 0
        c = inv_data.get("compromisos_mmm") or 0
        o = inv_data.get("obligaciones_mmm") or 0
        p = inv_data.get("pagos_mmm") or 0
        inv_data["pct_compromisos"]   = round(c / v * 100, 1) if v else None
        inv_data["pct_obligaciones"]  = round(o / v * 100, 1) if v else None
        inv_data["pct_pagos"]         = round(p / v * 100, 1) if v else None
        inv_data["inv_pct_pib"]       = None
        inv_data["inv_pct_gasto_total"] = None
    else:
        inv_data = dict(inv)

    total_transf = db.execute(
        "SELECT SUM(inversion_mmm) AS total FROM inversion_transformaciones WHERE bitacora_id=? AND vigencia=?",
        (bid, vigencia)
    ).fetchone()
    vf_total = db.execute(
        "SELECT ROUND(SUM(valor_mmm_ctes),1) AS total FROM vigencias_futuras WHERE bitacora_id=?",
        (bid,)
    ).fetchone()

    meta_d = dict(meta) if meta else {}
    return {
        "bitacora_id":   bid,
        "vigencia":      vigencia,
        "periodo":       meta_d.get("periodo"),
        "numero_bitacora": meta_d.get("numero_bitacora"),
        "corte_fecha":   meta_d.get("corte_fecha"),
        "inversion_vigente_mmm":     inv_data.get("vigente_mmm"),
        "inversion_compromisos_mmm": inv_data.get("compromisos_mmm"),
        "inversion_obligaciones_mmm": inv_data.get("obligaciones_mmm"),
        "inversion_pagos_mmm":       inv_data.get("pagos_mmm"),
        "pct_compromisos":    inv_data.get("pct_compromisos"),
        "pct_obligaciones":   inv_data.get("pct_obligaciones"),
        "pct_pagos":          inv_data.get("pct_pagos"),
        "inv_pct_pib":        inv_data.get("inv_pct_pib"),
        "inv_pct_gasto_total": inv_data.get("inv_pct_gasto_total"),
        "total_transformaciones_mmm":    dict(total_transf)["total"] if total_transf else None,
        "vigencias_futuras_total_mmm":   dict(vf_total)["total"]     if vf_total    else None,
        "fuente": "SIIF Nación / DPIP - DNP",
    }


# ──────────────────────────────────────────────
# ARCHIVOS ESTÁTICOS
# Debe ir al final, después de todas las rutas /api
# ──────────────────────────────────────────────
DATA_DIR     = Path(__file__).parent.parent / "data"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

app.mount("/data", StaticFiles(directory=str(DATA_DIR)),     name="data")
app.mount("/",     StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
