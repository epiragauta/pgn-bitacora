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
# Fuente: tablas pgn_concepto + pgn_ejecucion (2022-2026)
# ──────────────────────────────────────────────
@app.get("/api/evolucion", tags=["Sec 2 - Evolución Presupuestal"])
def get_evolucion(
    bitacora_id: Optional[int] = None,
    rubro: Optional[str] = Query(None, description="Filtra por rubro: Funcionamiento, Inversión, Servicio Deuda")
):
    """Apropiación vigente por rubro principal (2022-2026). Nivel 2, Miles mm COP."""
    db = get_db()
    # Alias corto para compatibilidad con el frontend
    sql = """
        SELECT
            e.anio                                          AS vigencia,
            REPLACE(c.nombre, 'Servicio de la Deuda',
                              'Servicio Deuda')             AS rubro,
            e.valor                                         AS vigente_mmm
        FROM pgn_ejecucion  e
        JOIN pgn_concepto   c ON c.id = e.concepto_id
        WHERE c.nivel  = 2
          AND c.unidad = 'Miles mm COP'
          AND e.fase   = 'Vigente'
    """
    params: list = []
    if rubro:
        sql += " AND REPLACE(c.nombre,'Servicio de la Deuda','Servicio Deuda') = ?"
        params.append(rubro)
    sql += " ORDER BY e.anio, c.orden"
    return rows_to_list(db.execute(sql, params).fetchall())


@app.get("/api/evolucion/composicion", tags=["Sec 2 - Evolución Presupuestal"])
def get_evolucion_composicion(anio: int = Query(..., description="Año (2022-2026)"), fase: str = "Vigente"):
    """Composición porcentual del PGN por categoría principal para un año dado."""
    db = get_db()
    rows = db.execute("""
        WITH total AS (
            SELECT e.valor
            FROM   pgn_ejecucion e
            JOIN   pgn_concepto  c ON c.id = e.concepto_id
            WHERE  c.nombre = 'Total PGN' AND c.unidad = 'Miles mm COP'
              AND  e.anio = ? AND e.fase = ?
        )
        SELECT c.nombre AS concepto, e.valor,
               ROUND(e.valor * 100.0 / total.valor, 2) AS pct_total
        FROM pgn_ejecucion e
        JOIN pgn_concepto  c ON c.id = e.concepto_id
        CROSS JOIN total
        WHERE c.nivel = 2 AND c.unidad = 'Miles mm COP'
          AND e.anio = ? AND e.fase = ?
        ORDER BY c.orden
    """, (anio, fase, anio, fase)).fetchall()
    return rows_to_list(rows)


@app.get("/api/evolucion/tasa_ejecucion", tags=["Sec 2 - Evolución Presupuestal"])
def get_tasa_ejecucion():
    """Tasa de ejecución (Pagado/Vigente) del Total PGN por año."""
    db = get_db()
    rows = db.execute("""
        SELECT v.anio, v.valor AS vigente, p.valor AS pagado,
               ROUND(p.valor * 100.0 / v.valor, 2) AS tasa_ejecucion_pct
        FROM pgn_ejecucion v
        JOIN pgn_ejecucion p
             ON  p.anio = v.anio AND p.concepto_id = v.concepto_id AND p.fase = 'Pagado'
        JOIN pgn_concepto  c ON c.id = v.concepto_id
        WHERE c.nombre = 'Total PGN' AND c.unidad = 'Miles mm COP' AND v.fase = 'Vigente'
        ORDER BY v.anio
    """).fetchall()
    return rows_to_list(rows)


@app.get("/api/evolucion/pct_pib", tags=["Sec 2 - Evolución Presupuestal"])
def get_evolucion_pct_pib():
    """Evolución de grandes rubros como % del PIB (Vigente, nivel 2)."""
    db = get_db()
    rows = db.execute("""
        SELECT e.anio, c.nombre AS concepto,
               ROUND(e.valor * 100, 4) AS valor_pct_pib
        FROM pgn_ejecucion e
        JOIN pgn_concepto  c ON c.id = e.concepto_id
        WHERE c.nivel = 2 AND c.unidad = '% PIB' AND e.fase = 'Vigente'
        ORDER BY e.anio, c.orden
    """).fetchall()
    return rows_to_list(rows)


@app.get("/api/evolucion/drilldown", tags=["Sec 2 - Evolución Presupuestal"])
def get_evolucion_drilldown(
    concepto: str = Query(..., description="Nombre del concepto raíz"),
    anio: int = Query(..., description="Año"),
    fase: str = "Vigente"
):
    """Árbol jerárquico completo de un concepto y sus descendientes."""
    db = get_db()
    rows = db.execute("""
        WITH RECURSIVE arbol AS (
            SELECT id, nombre, nivel, padre_id, orden FROM pgn_concepto WHERE nombre = ?
            UNION ALL
            SELECT c.id, c.nombre, c.nivel, c.padre_id, c.orden
            FROM pgn_concepto c JOIN arbol a ON c.padre_id = a.id
        )
        SELECT a.nivel, a.nombre, e.valor, COALESCE(p.nombre,'') AS padre
        FROM   arbol a
        JOIN   pgn_ejecucion  e ON e.concepto_id = a.id
        LEFT JOIN pgn_concepto p ON p.id = a.padre_id
        WHERE  e.anio = ? AND e.fase = ?
        ORDER BY a.orden
    """, (concepto, anio, fase)).fetchall()
    return rows_to_list(rows)


@app.get("/api/evolucion/tabla_completa", tags=["Sec 2 - Evolución Presupuestal"])
def get_tabla_completa():
    """Todos los conceptos × años × fases en formato pivot (pgn_vista_crosstab)."""
    db = get_db()
    rows = db.execute("SELECT * FROM pgn_vista_crosstab ORDER BY orden").fetchall()
    return rows_to_list(rows)


@app.get("/api/evolucion/inversion_historica", tags=["Sec 2 - Evolución Presupuestal"])
def get_inversion_historica(bitacora_id: Optional[int] = None):
    """Serie histórica de inversión con indicadores macroeconómicos (2022-2026)."""
    db = get_db()
    rows = db.execute("""
        SELECT
            v.anio                                              AS vigencia,
            v.valor                                             AS vigente_mmm,
            com.valor                                           AS compromisos_mmm,
            obl.valor                                           AS obligaciones_mmm,
            pag.valor                                           AS pagados_mmm,
            ROUND(com.valor * 100.0 / v.valor, 2)              AS pct_compromisos,
            ROUND(obl.valor * 100.0 / v.valor, 2)              AS pct_obligaciones,
            ROUND(pag.valor * 100.0 / v.valor, 2)              AS pct_pagos,
            ROUND(pib.valor * 100, 1)                          AS inv_pct_pib,
            ROUND(v.valor * 100.0 / tot.valor, 1)              AS inv_pct_gasto_total
        FROM pgn_ejecucion v
        JOIN pgn_ejecucion com ON com.anio=v.anio AND com.concepto_id=v.concepto_id AND com.fase='Comprometido'
        JOIN pgn_ejecucion obl ON obl.anio=v.anio AND obl.concepto_id=v.concepto_id AND obl.fase='Obligado'
        JOIN pgn_ejecucion pag ON pag.anio=v.anio AND pag.concepto_id=v.concepto_id AND pag.fase='Pagado'
        JOIN pgn_ejecucion pib ON pib.anio=v.anio AND pib.fase='Vigente'
        JOIN pgn_concepto  cpib ON cpib.id=pib.concepto_id AND cpib.nombre='Inversión como % del PIB'
        JOIN pgn_ejecucion tot ON tot.anio=v.anio AND tot.fase='Vigente'
        JOIN pgn_concepto  ctot ON ctot.id=tot.concepto_id AND ctot.nombre='Total PGN' AND ctot.unidad='Miles mm COP'
        JOIN pgn_concepto  c    ON c.id=v.concepto_id AND c.nombre='Inversión' AND c.unidad='Miles mm COP'
        WHERE v.fase = 'Vigente'
        ORDER BY v.anio
    """).fetchall()
    return rows_to_list(rows)


# ──────────────────────────────────────────────
# SECCIÓN 3 – REGIONALIZACIÓN
# ──────────────────────────────────────────────
@app.get("/api/regionalizacion", tags=["Sec 3 - Regionalización"])
def get_regionalizacion(
    vigencia: int = Query(2025, description="Año de corte"),
    region: Optional[str] = Query(None, description="Filtrar por región"),
    bitacora_id: Optional[int] = None,
):
    """
    Departamentos regionalizados para un año dado.
    Incluye código DANE para integración con capas GeoJSON.
    Nota: datos 2023 tienen compromisos muy bajos por diferencia en fecha de corte.
    """
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    sql = """
        SELECT r.vigencia, r.tipo, r.region, r.departamento,
               r.codigo_dane, d.nombre AS nombre_dane,
               r.apropiacion_mmm, r.compromisos_mmm, r.obligaciones_mmm, r.pagos_mmm,
               r.pct_compromisos, r.pct_obligaciones, r.pct_pagos, r.pct_participacion
        FROM regionalizacion r
        LEFT JOIN dane_departamentos d ON d.codigo = r.codigo_dane
        WHERE r.bitacora_id=? AND r.vigencia=?
    """
    params: list = [bid, vigencia]
    if region:
        sql += " AND r.region=?"
        params.append(region.upper())
    sql += " ORDER BY r.region, r.departamento COLLATE NOCASE"
    return rows_to_list(db.execute(sql, params).fetchall())


@app.get("/api/regionalizacion/historico", tags=["Sec 3 - Regionalización"])
def get_regionalizacion_historico(bitacora_id: Optional[int] = None):
    """
    Totales por región, todos los años 2022-2026.
    Agrupa sumando todos los departamentos de cada región.
    Excluye 'POR_REGIONALIZAR' y 'NACIONAL'.
    """
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT vigencia, region, tipo,
               ROUND(SUM(apropiacion_mmm), 3)  AS apropiacion_mmm,
               ROUND(SUM(compromisos_mmm), 3)  AS compromisos_mmm,
               ROUND(SUM(obligaciones_mmm), 3) AS obligaciones_mmm,
               ROUND(SUM(pagos_mmm), 3)        AS pagos_mmm,
               ROUND(SUM(compromisos_mmm)*100.0/NULLIF(SUM(apropiacion_mmm),0), 2) AS pct_compromisos
        FROM regionalizacion
        WHERE bitacora_id=? AND tipo IN ('departamento','por_regionalizar','nacional')
        GROUP BY vigencia, region
        ORDER BY vigencia, region
    """, (bid,)).fetchall()
    return rows_to_list(rows)


@app.get("/api/regionalizacion/sectores", tags=["Sec 3 - Regionalización"])
def get_regionalizacion_sectores(
    vigencia: int = Query(2026, description="Año de corte"),
    region: Optional[str] = None,
    bitacora_id: Optional[int] = None,
):
    """Sectores por región. Filtra por vigencia y opcionalmente por región."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    sql = """
        SELECT vigencia, region, sector,
               apropiacion_mmm, compromisos_mmm, obligaciones_mmm, pagos_mmm
        FROM regionalizacion_sectores
        WHERE bitacora_id=? AND vigencia=?
    """
    params: list = [bid, vigencia]
    if region:
        sql += " AND region=?"
        params.append(region.upper())
    sql += " ORDER BY region, apropiacion_mmm DESC"
    return rows_to_list(db.execute(sql, params).fetchall())


@app.get("/api/regionalizacion/mapa", tags=["Sec 3 - Regionalización"])
def get_regionalizacion_mapa(
    vigencia: int = Query(2025, description="Año de corte"),
    bitacora_id: Optional[int] = None,
):
    """
    Datos para coloreado del mapa GeoJSON por departamento.
    Devuelve codigo_dane + métricas de ejecución.
    """
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT r.codigo_dane, r.departamento, r.region,
               r.apropiacion_mmm, r.compromisos_mmm,
               r.pct_compromisos, r.pct_participacion
        FROM regionalizacion r
        WHERE r.bitacora_id=? AND r.vigencia=? AND r.tipo='departamento'
        ORDER BY r.region, r.departamento
    """, (bid, vigencia)).fetchall()
    return rows_to_list(rows)


@app.get("/api/regionalizacion/departamento/{codigo_dane}", tags=["Sec 3 - Regionalización"])
def get_regionalizacion_departamento(codigo_dane: str, bitacora_id: Optional[int] = None):
    """Serie histórica 2022-2026 para un departamento específico (código DANE)."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT r.vigencia, r.departamento, r.region,
               r.apropiacion_mmm, r.compromisos_mmm, r.obligaciones_mmm, r.pagos_mmm,
               r.pct_compromisos, r.pct_obligaciones, r.pct_participacion
        FROM regionalizacion r
        WHERE r.bitacora_id=? AND r.codigo_dane=?
        ORDER BY r.vigencia
    """, (bid, codigo_dane)).fetchall()
    if not rows:
        raise HTTPException(404, f"Departamento con código DANE '{codigo_dane}' no encontrado")
    return rows_to_list(rows)


# ──────────────────────────────────────────────
# SECCIÓN 4 – EJECUCIÓN
# ──────────────────────────────────────────────
@app.get("/api/ejecucion", tags=["Sec 4 - Ejecución"])
def get_ejecucion(bitacora_id: Optional[int] = None):
    """Ejecución histórica de inversión 2022-2026 (pgn_ejecucion)."""
    db = get_db()
    rows = db.execute("""
        SELECT
            v.anio                                          AS vigencia,
            v.valor                                         AS vigente_mmm,
            com.valor                                       AS compromisos_mmm,
            obl.valor                                       AS obligaciones_mmm,
            pag.valor                                       AS pagos_mmm,
            ROUND(com.valor * 100.0 / v.valor, 2)          AS pct_compromisos,
            ROUND(obl.valor * 100.0 / v.valor, 2)          AS pct_obligaciones,
            ROUND(pag.valor * 100.0 / v.valor, 2)          AS pct_pagos,
            ROUND(pib.valor * 100, 1)                      AS inv_pct_pib,
            ROUND(v.valor * 100.0 / tot.valor, 1)          AS inv_pct_gasto_total
        FROM pgn_ejecucion v
        JOIN pgn_ejecucion com ON com.anio=v.anio AND com.concepto_id=v.concepto_id AND com.fase='Comprometido'
        JOIN pgn_ejecucion obl ON obl.anio=v.anio AND obl.concepto_id=v.concepto_id AND obl.fase='Obligado'
        JOIN pgn_ejecucion pag ON pag.anio=v.anio AND pag.concepto_id=v.concepto_id AND pag.fase='Pagado'
        JOIN pgn_ejecucion pib ON pib.anio=v.anio AND pib.fase='Vigente'
        JOIN pgn_concepto  cpib ON cpib.id=pib.concepto_id AND cpib.nombre='Inversión como % del PIB'
        JOIN pgn_ejecucion tot ON tot.anio=v.anio AND tot.fase='Vigente'
        JOIN pgn_concepto  ctot ON ctot.id=tot.concepto_id AND ctot.nombre='Total PGN' AND ctot.unidad='Miles mm COP'
        JOIN pgn_concepto  c    ON c.id=v.concepto_id AND c.nombre='Inversión' AND c.unidad='Miles mm COP'
        WHERE v.fase = 'Vigente'
        ORDER BY v.anio
    """).fetchall()
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


@app.get("/api/ejecucion/sectores/obligaciones_pct", tags=["Sec 4 - Ejecución"])
def get_obligaciones_pct(bitacora_id: Optional[int] = None):
    """% de obligaciones sobre apropiación por sector."""
    db = get_db()
    bid, vigencia = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT vigencia, sector, pct_obligaciones
        FROM obligaciones_pct_por_sector
        WHERE bitacora_id=? AND vigencia=?
        ORDER BY pct_obligaciones DESC
    """, (bid, vigencia)).fetchall()
    return rows_to_list(rows)


@app.get("/api/ejecucion/sectores/pagos_pct", tags=["Sec 4 - Ejecución"])
def get_pagos_pct(bitacora_id: Optional[int] = None):
    """% de pagos sobre apropiación por sector."""
    db = get_db()
    bid, vigencia = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT vigencia, sector, pct_pagos
        FROM pagos_pct_por_sector
        WHERE bitacora_id=? AND vigencia=?
        ORDER BY pct_pagos DESC
    """, (bid, vigencia)).fetchall()
    return rows_to_list(rows)


@app.get("/api/ejecucion/sectores/matriz", tags=["Sec 4 - Ejecución"])
def get_sectores_matriz(bitacora_id: Optional[int] = None):
    """Matriz completa por sector y vigencia: apropiación (mmm), %C, %O, %P."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)

    apr = db.execute(
        "SELECT vigencia, sector, vigente_mmm FROM apropiacion_por_sector WHERE bitacora_id=? ORDER BY vigencia, sector",
        (bid,)
    ).fetchall()
    cmp = db.execute(
        "SELECT vigencia, sector, pct_compromisos FROM compromisos_pct_por_sector WHERE bitacora_id=? ORDER BY vigencia, sector",
        (bid,)
    ).fetchall()
    obl = db.execute(
        "SELECT vigencia, sector, pct_obligaciones FROM obligaciones_pct_por_sector WHERE bitacora_id=? ORDER BY vigencia, sector",
        (bid,)
    ).fetchall()
    pag = db.execute(
        "SELECT vigencia, sector, pct_pagos FROM pagos_pct_por_sector WHERE bitacora_id=? ORDER BY vigencia, sector",
        (bid,)
    ).fetchall()

    vigencias = sorted(set(r["vigencia"] for r in apr))
    sectores  = sorted(set(r["sector"]   for r in apr))

    apr_m = {(r["vigencia"], r["sector"]): r["vigente_mmm"]      for r in apr}
    cmp_m = {(r["vigencia"], r["sector"]): r["pct_compromisos"]  for r in cmp}
    obl_m = {(r["vigencia"], r["sector"]): r["pct_obligaciones"] for r in obl}
    pag_m = {(r["vigencia"], r["sector"]): r["pct_pagos"]        for r in pag}

    result = []
    for sector in sectores:
        result.append({
            "sector": sector,
            "apr":   [apr_m.get((v, sector)) for v in vigencias],
            "pct_c": [cmp_m.get((v, sector)) for v in vigencias],
            "pct_o": [obl_m.get((v, sector)) for v in vigencias],
            "pct_p": [pag_m.get((v, sector)) for v in vigencias],
        })

    return {"vigencias": vigencias, "sectores": result}


# ──────────────────────────────────────────────
# SECCIÓN 5 – VIGENCIAS FUTURAS
# ──────────────────────────────────────────────

# Sectores individuales que se muestran solos; el resto se agrupa como OTROS
_VF_SECT_NAMED = [
    "TRANSPORTE",
    "IGUALDAD Y EQUIDAD",
    "HACIENDA",
    "DEFENSA Y POLICÍA",
    "SALUD Y PROTECCIÓN SOCIAL",
]
_VF_AÑOS = list(range(2027, 2041))


@app.get("/api/vigencias_futuras", tags=["Sec 5 - Vigencias Futuras"])
def get_vigencias_futuras(bitacora_id: Optional[int] = None, sector: Optional[str] = None):
    """Vigencias futuras por sector en pesos corrientes (mmm)."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    sql = "SELECT vigencia_exec, sector, valor_corriente_mmm FROM vigencias_futuras WHERE bitacora_id=?"
    params: list = [bid]
    if sector:
        sql += " AND sector=?"
        params.append(sector.upper())
    sql += " ORDER BY vigencia_exec, valor_corriente_mmm DESC"
    return rows_to_list(db.execute(sql, params).fetchall())


@app.get("/api/vigencias_futuras/totales", tags=["Sec 5 - Vigencias Futuras"])
def get_vigencias_totales(bitacora_id: Optional[int] = None):
    """Total de vigencias futuras por año (corrientes mmm + deflactor + % PIB)."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT v.vigencia_exec,
               ROUND(SUM(v.valor_corriente_mmm), 3)          AS total_corriente_mmm,
               d.deflactor,
               ROUND(SUM(v.valor_corriente_mmm) / d.deflactor, 3) AS total_constante_mmm,
               CASE WHEN d.pib_constante_mmm > 0
                    THEN ROUND(SUM(v.valor_corriente_mmm) / d.deflactor / d.pib_constante_mmm * 100, 4)
                    ELSE NULL END AS pct_pib
        FROM vigencias_futuras v
        LEFT JOIN deflactores_pib d
               ON d.bitacora_id = v.bitacora_id AND d.anio = v.vigencia_exec
        WHERE v.bitacora_id = ?
          AND v.vigencia_exec BETWEEN 2027 AND 2040
        GROUP BY v.vigencia_exec
        ORDER BY v.vigencia_exec
    """, (bid,)).fetchall()
    return rows_to_list(rows)


@app.get("/api/vigencias_futuras/chart", tags=["Sec 5 - Vigencias Futuras"])
def get_vigencias_chart(bitacora_id: Optional[int] = None):
    """Datos del gráfico: 6 series en constantes 2026 + % PIB (2027-2040)."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)

    # Leer pivot crudo + deflactores en un solo query
    rows = db.execute("""
        SELECT v.vigencia_exec,
               v.sector,
               ROUND(v.valor_corriente_mmm / d.deflactor, 3) AS valor_ctes
        FROM vigencias_futuras v
        JOIN deflactores_pib d
          ON d.bitacora_id = v.bitacora_id AND d.anio = v.vigencia_exec
        WHERE v.bitacora_id = ?
          AND v.vigencia_exec BETWEEN 2027 AND 2040
        ORDER BY v.vigencia_exec, v.sector
    """, (bid,)).fetchall()

    # PIB constante por año (para % PIB)
    pib_rows = db.execute("""
        SELECT anio, pib_constante_mmm FROM deflactores_pib
        WHERE bitacora_id = ? AND anio BETWEEN 2027 AND 2040
        ORDER BY anio
    """, (bid,)).fetchall()
    pib_map = {r["anio"]: r["pib_constante_mmm"] for r in pib_rows}

    # Agrupar en 6 series
    from collections import defaultdict
    pivot: dict = {s: defaultdict(float) for s in _VF_SECT_NAMED}
    pivot["OTROS SECTORES"] = defaultdict(float)

    for r in rows:
        sect = r["sector"]
        year = r["vigencia_exec"]
        val  = r["valor_ctes"] or 0.0
        if sect in _VF_SECT_NAMED:
            pivot[sect][year] += val
        else:
            pivot["OTROS SECTORES"][year] += val

    series = []
    for s in _VF_SECT_NAMED + ["OTROS SECTORES"]:
        series.append({
            "sector":  s,
            "valores": [round(pivot[s].get(y, 0.0), 1) for y in _VF_AÑOS],
        })

    totales = [
        round(sum(pivot[s].get(y, 0.0) for s in _VF_SECT_NAMED + ["OTROS SECTORES"]), 1)
        for y in _VF_AÑOS
    ]
    pct_pib = [
        round(totales[i] / pib_map[y] * 100, 4) if pib_map.get(y) else None
        for i, y in enumerate(_VF_AÑOS)
    ]

    return {
        "anios":   _VF_AÑOS,
        "series":  series,
        "totales": totales,
        "pct_pib": pct_pib,
    }


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
    """Ejecución mensual sectorial comparada con años anteriores (compromisos y obligaciones)."""
    db = get_db()
    bid, vigencia = resolve_bitacora(db, bitacora_id)
    sql = """
        SELECT vigencia, sector, mes,
               pct_compromisos_2025, pct_compromisos_2024,
               pct_compromisos_prom, pct_compromisos_mejor,
               pct_obligaciones_2025, pct_obligaciones_2024,
               pct_obligaciones_prom, pct_obligaciones_mejor
        FROM ejecucion_sectorial_mensual
        WHERE bitacora_id=? AND vigencia=?
    """
    params: list = [bid, vigencia]
    if sector:
        sql += " AND sector=?"
        params.append(sector.upper())
    sql += " ORDER BY sector, mes"
    return rows_to_list(db.execute(sql, params).fetchall())


@app.get("/api/sectorial/historico", tags=["Sec 6 - Ejecución Sectorial"])
def get_sectorial_historico(bitacora_id: Optional[int] = None, sector: Optional[str] = None):
    """Entidades por sector con todas las vigencias disponibles (para tabla multi-año)."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    sql = """
        SELECT vigencia, sector, entidad,
               apr_vigente_mmm, compromisos_mmm, obligaciones_mmm,
               pct_c_av, pct_o_av
        FROM ejecucion_sectorial_entidades
        WHERE bitacora_id=? AND vigencia >= 2022
    """
    params: list = [bid]
    if sector:
        sql += " AND sector=?"
        params.append(sector.upper())
    sql += " ORDER BY sector, entidad, vigencia"
    return rows_to_list(db.execute(sql, params).fetchall())


# ──────────────────────────────────────────────
# SECCIÓN 7 – CRÉDITO EXTERNO (SCCI)
# ──────────────────────────────────────────────
@app.get("/api/credito", tags=["Sec 7 - Crédito Externo"])
def get_credito(bitacora_id: Optional[int] = None, fuente: Optional[str] = None, sector: Optional[str] = None):
    """Portafolio de créditos externos vigentes (BID, BM, CAF). Montos en USD."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    sql = """
        SELECT nombre, nombre_corto, fuente, contrato, sector, monto_usd, desembolsado_usd
        FROM credito_portafolio WHERE bitacora_id=?
    """
    params: list = [bid]
    if fuente:
        sql += " AND fuente=?"
        params.append(fuente.upper())
    if sector:
        sql += " AND sector=?"
        params.append(sector)
    sql += " ORDER BY monto_usd DESC"
    return rows_to_list(db.execute(sql, params).fetchall())


@app.get("/api/credito/fuentes", tags=["Sec 7 - Crédito Externo"])
def get_credito_fuentes(bitacora_id: Optional[int] = None):
    """Operaciones de crédito agrupadas por fuente de financiación (BID/BM/CAF), para el donut."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT fuente,
               COUNT(*) AS n_creditos,
               ROUND(SUM(monto_usd), 2)        AS monto_usd,
               ROUND(SUM(desembolsado_usd), 2) AS desembolsado_usd
        FROM credito_portafolio WHERE bitacora_id=?
        GROUP BY fuente ORDER BY monto_usd DESC
    """, (bid,)).fetchall()
    return rows_to_list(rows)


@app.get("/api/credito/sectores", tags=["Sec 7 - Crédito Externo"])
def get_credito_sectores(bitacora_id: Optional[int] = None):
    """Créditos y desembolsos agrupados por sector."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT sector,
               COUNT(*) AS n_creditos,
               ROUND(SUM(monto_usd), 2)        AS monto_usd,
               ROUND(SUM(desembolsado_usd), 2) AS desembolsado_usd,
               ROUND(SUM(desembolsado_usd) * 100.0 / SUM(monto_usd), 2) AS pct_desembolsado
        FROM credito_portafolio WHERE bitacora_id=?
        GROUP BY sector ORDER BY monto_usd DESC
    """, (bid,)).fetchall()
    return rows_to_list(rows)


@app.get("/api/credito/resumen", tags=["Sec 7 - Crédito Externo"])
def get_credito_resumen(bitacora_id: Optional[int] = None):
    """KPIs del portafolio de crédito externo (cartera vigente, montos, % desembolsado)."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    row = db.execute("""
        SELECT COUNT(*) AS n_creditos,
               ROUND(SUM(monto_usd), 2)        AS monto_total_usd,
               ROUND(SUM(desembolsado_usd), 2) AS desembolsado_total_usd,
               ROUND(SUM(desembolsado_usd) * 100.0 / SUM(monto_usd), 2) AS pct_desembolsado
        FROM credito_portafolio WHERE bitacora_id=?
    """, (bid,)).fetchone()
    return dict(row) if row else {}


@app.get("/api/credito/ejecucion_entidad", tags=["Sec 7 - Crédito Externo"])
def get_credito_ejecucion_entidad(bitacora_id: Optional[int] = None):
    """Ejecución presupuestal por entidad de los recursos de crédito externo (recurso 13 y 14). Cifras en mmm COP."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT entidad, sector, apr_inicial_mmm, apr_vigente_mmm, compromiso_mmm,
               obligacion_mmm, pago_mmm, pct_com, pct_ejec, pct_pago
        FROM credito_ejecucion_entidad
        WHERE bitacora_id=? ORDER BY apr_vigente_mmm DESC
    """, (bid,)).fetchall()
    return rows_to_list(rows)


@app.get("/api/credito/ejecucion_historica", tags=["Sec 7 - Crédito Externo"])
def get_credito_ejecucion_historica(bitacora_id: Optional[int] = None):
    """Comparativo histórico de ejecución presupuestal de crédito externo (% y valores por año)."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT anio, pct_comprometido, pct_ejecutado, pct_pagado,
               vigente_mmm, comprometido_mmm, ejecutado_mmm, pagado_mmm
        FROM credito_ejecucion_historica
        WHERE bitacora_id=? ORDER BY anio
    """, (bid,)).fetchall()
    return rows_to_list(rows)


# ──────────────────────────────────────────────
# SECCIÓN 8 – SISTEMA GENERAL DE PARTICIPACIONES (SGP)
# ──────────────────────────────────────────────
@app.get("/api/sgp/historico", tags=["Sec 8 - SGP"])
def get_sgp_historico(bitacora_id: Optional[int] = None):
    """Serie histórica 2022-2026 del SGP por participación. Miles de millones COP corrientes."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT vigencia, educacion_mmm, salud_mmm, agua_potable_mmm, proposito_general_mmm,
               alimentacion_escolar_mmm, riberenos_mmm, resguardos_indigenas_mmm, fonpet_ae_mmm, total_mmm
        FROM sgp_historico_participacion
        WHERE bitacora_id=?
        ORDER BY vigencia
    """, (bid,)).fetchall()
    return rows_to_list(rows)


@app.get("/api/sgp/historico_componentes", tags=["Sec 8 - SGP"])
def get_sgp_historico_componentes(bitacora_id: Optional[int] = None):
    """Histórico 2022-2026 del SGP desagregado por componente interno de cada participación."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT vigencia, orden, participacion, componente, es_total, valor_mmm
        FROM sgp_historico_componentes
        WHERE bitacora_id=?
        ORDER BY orden, vigencia
    """, (bid,)).fetchall()
    return rows_to_list(rows)


@app.get("/api/sgp/resumen", tags=["Sec 8 - SGP"])
def get_sgp_resumen(bitacora_id: Optional[int] = None):
    """KPIs del SGP: total último año, crecimiento vs año anterior, total acumulado 2022-2026."""
    db = get_db()
    bid, _ = resolve_bitacora(db, bitacora_id)
    rows = db.execute("""
        SELECT vigencia, total_mmm FROM sgp_historico_participacion
        WHERE bitacora_id=? ORDER BY vigencia
    """, (bid,)).fetchall()
    if not rows:
        return {}
    ultimo = rows[-1]
    anterior = rows[-2] if len(rows) > 1 else None
    total_acumulado = sum(r["total_mmm"] or 0 for r in rows)
    return {
        "vigencia_reciente": ultimo["vigencia"],
        "total_reciente_mmm": ultimo["total_mmm"],
        "vigencia_anterior": anterior["vigencia"] if anterior else None,
        "total_anterior_mmm": anterior["total_mmm"] if anterior else None,
        "crecimiento_pct": round((ultimo["total_mmm"] / anterior["total_mmm"] - 1) * 100, 2)
                            if anterior and anterior["total_mmm"] else None,
        "total_acumulado_mmm": round(total_acumulado, 3),
    }


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
        """SELECT ROUND(SUM(v.valor_corriente_mmm / d.deflactor), 1) AS total
           FROM vigencias_futuras v
           JOIN deflactores_pib d ON d.bitacora_id=v.bitacora_id AND d.anio=v.vigencia_exec
           WHERE v.bitacora_id=? AND v.vigencia_exec BETWEEN 2027 AND 2040""",
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
