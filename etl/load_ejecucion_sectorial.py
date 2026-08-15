#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETL: BASE DETALLE MENSUAL INVERSIÓN 2018-2026.xlsx → pgn.db

Carga datos de ejecución de inversión (Secciones 4 y 6) desde el archivo
detallado de SIIF Nación. Filtra al mes de corte indicado (por defecto MAR).

Uso:
    python etl/load_ejecucion_sectorial.py \\
        --excel "ruta/BASE DETALLE MENSUAL INVERSIÓN 2018-2026.xlsx" \\
        --db db/pgn.db \\
        --bitacora-id 1 \\
        --mes-corte MAR
"""

import argparse
import unicodedata
from collections import defaultdict
from pathlib import Path

import bases
import db as dbmod
import openpyxl


# ── Índices de columnas en la hoja BASE ─────────────────────────────────────
COL_ANIO      = 0
COL_MES       = 1
COL_SECTOR    = 2   # Sector (no homologado, fallback)
COL_SEC_HOMO  = 3   # Sector Homologado  ← fuente principal
COL_ENT       = 6   # U. Ejec. (fallback)
COL_ENT_HOMO  = 7   # U. Ejec.-Homo      ← fuente principal
COL_VIGENTE   = 19
COL_COMPROMISO = 21
COL_OBLIGACION = 22
COL_PAGO      = 23

# ── Orden de meses ───────────────────────────────────────────────────────────
MES_ORD = {
    'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4,
    'MAY': 5, 'JUN': 6, 'JUL': 7, 'AGO': 8,
    'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12,
}

# ── Mapa de nombres históricos → nombre canónico (claves en MAYÚSCULAS) ─────
SECTOR_MAP = {
    'AGROPECUARIO':
        'AGRICULTURA Y DESARROLLO RURAL',
    'CIENCIA Y TECNOLOGÍA':
        'CIENCIA, TECNOLOGÍA E INNOVACIÓN',
    'CIENCIA Y TECNOLOGIA':
        'CIENCIA, TECNOLOGÍA E INNOVACIÓN',
    'COMUNICACIONES':
        'TECNOLOGÍAS DE LA INFORMACIÓN Y LAS COMUNICACIONES',
    'EMPLEO PUBLICO':
        'EMPLEO PÚBLICO',
    'PRESIDENCIA DE LA REPUBLICA':
        'PRESIDENCIA DE LA REPÚBLICA',
    'CONGRESO DE LA REPUBLICA':
        'CONGRESO DE LA REPÚBLICA',
    'JURISDICCION ESPECIAL PARA LA PAZ':
        'SISTEMA INTEGRAL DE VERDAD, JUSTICIA, REPARACIÓN Y NO REPETICIÓN',
    'JURISDICCIÓN ESPECIAL PARA LA PAZ':
        'SISTEMA INTEGRAL DE VERDAD, JUSTICIA, REPARACIÓN Y NO REPETICIÓN',
    'FISCALIA':
        'FISCALÍA',
    'REGISTRADURIA':
        'REGISTRADURÍA',
    'PLANEACION':
        'PLANEACIÓN',
    'INFORMACION ESTADISTICA':
        'INFORMACIÓN ESTADÍSTICA',
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def norm_str(raw):
    """NFC-normaliza y hace strip para comparación consistente."""
    return unicodedata.normalize('NFC', str(raw).strip())


def norm_sector(raw):
    if not raw:
        return None
    s = norm_str(raw).upper()
    if not s or s in ('0', 'NONE'):
        return None
    return SECTOR_MAP.get(s, s)


def norm_entidad(raw):
    if not raw:
        return ''
    return norm_str(raw)


def norm_mes(raw):
    if not raw:
        return None
    return str(raw).strip().upper()


def pct(num, den, d=1):
    if not den:
        return None
    return round(num / den * 100, d)


def to_mmm(pesos, d=3):
    """Pesos corrientes → miles de millones."""
    return round(pesos / 1_000_000_000, d)


# ── Lectura del Excel ────────────────────────────────────────────────────────

def load_excel(path, mes_corte):
    """
    Devuelve dos listas:
      records_corte   — filas del mes de corte (Mes == mes_corte)
                        (anio, sector, entidad, vig, comp, obl, pago)
      records_mensual — filas de todos los meses <= mes_corte
                        (anio, mes_num, sector, vig, comp, obl, pago)
    """
    mes_corte_upper = mes_corte.upper()
    mes_corte_num   = MES_ORD[mes_corte_upper]

    print(f"Leyendo {Path(path).name} ...")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb['BASE']

    records_corte   = []   # solo mes == mes_corte (comparación punto-en-tiempo)
    records_mensual = []   # TODOS los meses (curva mensual completa)
    skipped = 0

    for row in ws.iter_rows(min_row=2, values_only=True):
        anio = row[COL_ANIO]
        mes  = norm_mes(row[COL_MES])
        if anio is None or mes is None:
            continue
        if mes not in MES_ORD:
            continue
        mes_num = MES_ORD[mes]

        sec = norm_sector(row[COL_SEC_HOMO] or row[COL_SECTOR])
        if not sec:
            skipped += 1
            continue

        ent_raw = row[COL_ENT_HOMO] or row[COL_ENT]
        ent = norm_entidad(ent_raw)

        vig  = float(row[COL_VIGENTE]    or 0)
        comp = float(row[COL_COMPROMISO] or 0)
        obl  = float(row[COL_OBLIGACION] or 0)
        pago = float(row[COL_PAGO]       or 0)

        # Todos los meses → series mensuales históricas
        records_mensual.append((int(anio), mes_num, sec, vig, comp, obl, pago))

        # Solo el mes de corte → comparaciones punto-en-tiempo
        if mes == mes_corte_upper:
            records_corte.append((int(anio), sec, ent, vig, comp, obl, pago))

    wb.close()
    print(f"  Filas corte ({mes_corte}):          {len(records_corte):>7,}")
    print(f"  Filas total (todos los meses): {len(records_mensual):>7,}")
    if skipped:
        print(f"  Filas ignoradas (sin sector):  {skipped:>7,}")
    return records_corte, records_mensual


# ── Agregaciones ─────────────────────────────────────────────────────────────

def agg_totales(records_corte):
    """SUM por año → [vig, comp, obl, pago]."""
    tot = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    for anio, sec, ent, v, c, o, p in records_corte:
        t = tot[anio]
        t[0] += v; t[1] += c; t[2] += o; t[3] += p
    return tot


def agg_sectores(records_corte):
    """SUM por (año, sector) → [vig, comp, obl, pago]."""
    sec = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    for anio, sector, ent, v, c, o, p in records_corte:
        t = sec[(anio, sector)]
        t[0] += v; t[1] += c; t[2] += o; t[3] += p
    return sec


def agg_entidades(records_corte):
    """SUM por (año, sector, entidad) para todos los años → [vig, comp, obl, pago]."""
    ent = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    for anio, sector, entidad, v, c, o, p in records_corte:
        if not entidad:
            continue
        t = ent[(anio, sector, entidad)]
        t[0] += v; t[1] += c; t[2] += o; t[3] += p
    return ent


def _accent_score(s):
    """Cuenta caracteres con tilde/diacrítico (para preferir la grafía correcta)."""
    return sum(1 for ch in s if len(unicodedata.normalize('NFD', ch)) > 1)


def canonicalize_entidades(ent_agg):
    """
    El histórico de 'U. Ejec.-Homo' trae, para una misma entidad, años con
    tildes y años sin tildes (p. ej. 'COMISIÓN...' vs 'COMISION...'). Eso
    fragmenta la serie histórica en el frontend, que agrupa por texto exacto
    de entidad. Se agrupa por (sector, nombre sin tildes en mayúsculas) y se
    reescribe todo el grupo a la grafía con más tildes (ortografía correcta).
    """
    def norm_key(s):
        s2 = unicodedata.normalize('NFD', s)
        s2 = ''.join(ch for ch in s2 if unicodedata.category(ch) != 'Mn')
        return ' '.join(s2.upper().split())

    variants_by_group = defaultdict(set)
    for (anio, sector, entidad) in ent_agg:
        variants_by_group[(sector, norm_key(entidad))].add(entidad)

    canonical_for = {}
    for (sector, _key), variants in variants_by_group.items():
        canonical = max(variants, key=_accent_score).upper()
        for v in variants:
            canonical_for[(sector, v)] = canonical

    merged = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    for (anio, sector, entidad), (v, c, o, p) in ent_agg.items():
        canon = canonical_for[(sector, entidad)]
        t = merged[(anio, sector, canon)]
        t[0] += v; t[1] += c; t[2] += o; t[3] += p
    return merged


def agg_mensual(records_mensual):
    """SUM por (año, mes, sector) → [vig, comp, obl, pago]."""
    mens = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    for anio, mes_num, sector, v, c, o, p in records_mensual:
        t = mens[(anio, mes_num, sector)]
        t[0] += v; t[1] += c; t[2] += o; t[3] += p
    return mens


# ── Carga a SQLite ────────────────────────────────────────────────────────────

def verificar_columnas(conn):
    """Comprueba que el esquema tenga las columnas que este ETL escribe.

    Antes esta función parcheaba la base con ALTER TABLE cuando venía del
    esquema viejo. Ya no: el esquema es responsabilidad de db/mssql/ y una
    columna que falte es un error de despliegue, no algo que el cargador
    deba arreglar por su cuenta.
    """
    requeridas = {
        'ejecucion_sectorial_entidades': {'pagos_mmm', 'pct_p_av'},
        'ejecucion_sectorial_mensual': {
            'pct_obligaciones_2025', 'pct_obligaciones_2024',
            'pct_obligaciones_prom', 'pct_obligaciones_mejor',
        },
    }
    for tabla, columnas in requeridas.items():
        presentes = {
            r[0] for r in conn.execute(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=?", (tabla,)
            ).fetchall()
        }
        faltan = columnas - presentes
        if faltan:
            raise SystemExit(
                f"ERROR: a la tabla {tabla} le faltan columnas: {sorted(faltan)}.\n"
                "Aplicar db/mssql/001_schema.sql antes de cargar."
            )


def load_db(conn, bid, anio_max, mes_corte, tot, sec_agg, ent_agg, mens_agg, pib_prev, gasto_prev):

    # ── 3A: ejecucion_historica ──────────────────────────────────────────────
    print("\n→ ejecucion_historica")
    hist = []
    for anio in sorted(tot):
        v, c, o, p = tot[anio]
        hist.append((
            bid, anio,
            to_mmm(v), to_mmm(c), to_mmm(o), to_mmm(p),
            pct(c, v), pct(o, v), pct(p, v),
            pib_prev.get(anio),
            gasto_prev.get(anio),
        ))

    conn.vaciar_bitacora(("ejecucion_historica",), bid)
    conn.upsert(
        "ejecucion_historica",
        ["bitacora_id", "vigencia", "vigente_mmm", "compromisos_mmm",
         "obligaciones_mmm", "pagos_mmm", "pct_compromisos", "pct_obligaciones",
         "pct_pagos", "inv_pct_pib", "inv_pct_gasto_total"],
        hist, claves=["bitacora_id", "vigencia"],
    )
    for r in hist:
        print(f"  {r[1]}: vig={r[2]:>10,.0f} mmm  "
              f"comp={r[3]:>10,.0f}  obl={r[4]:>10,.0f}  "
              f"pct_c={r[6]}%  pct_o={r[7]}%  pct_p={r[8]}%")

    # ── 3B: apropiacion_por_sector y tablas *_pct_por_sector ─────────────────
    print("\n→ apropiacion_por_sector / *_pct_por_sector")
    apr_rows  = []
    comp_rows = []
    obl_rows  = []
    pago_rows = []

    for (anio, sector), (v, c, o, p) in sec_agg.items():
        apr_rows.append( (bid, anio, sector, to_mmm(v)))
        comp_rows.append((bid, anio, sector, pct(c, v)))
        obl_rows.append( (bid, anio, sector, pct(o, v)))
        pago_rows.append((bid, anio, sector, pct(p, v)))

    conn.vaciar_bitacora((
        "apropiacion_por_sector", "compromisos_pct_por_sector",
        "obligaciones_pct_por_sector", "pagos_pct_por_sector",
    ), bid)

    claves_sector = ["bitacora_id", "vigencia", "sector"]
    conn.upsert("apropiacion_por_sector",
                claves_sector + ["vigente_mmm"], apr_rows, claves=claves_sector)
    conn.upsert("compromisos_pct_por_sector",
                claves_sector + ["pct_compromisos"], comp_rows, claves=claves_sector)
    conn.upsert("obligaciones_pct_por_sector",
                claves_sector + ["pct_obligaciones"], obl_rows, claves=claves_sector)
    conn.upsert("pagos_pct_por_sector",
                claves_sector + ["pct_pagos"], pago_rows, claves=claves_sector)
    print(f"  {len(apr_rows)} registros (sector × vigencia)")

    # ── 3C: ejecucion_sectorial_entidades (todos los años) ───────────────────
    print("\n→ ejecucion_sectorial_entidades (todos los años)")
    ent_agg = canonicalize_entidades(ent_agg)
    ent_rows = []
    for (anio, sector, entidad), (v, c, o, p) in ent_agg.items():
        ent_rows.append((
            bid, anio, sector, entidad,
            to_mmm(v), to_mmm(c), to_mmm(o), to_mmm(p),
            pct(c, v), pct(o, v), pct(p, v),
        ))

    conn.vaciar_bitacora(("ejecucion_sectorial_entidades",), bid)
    conn.upsert(
        "ejecucion_sectorial_entidades",
        ["bitacora_id", "vigencia", "sector", "entidad",
         "apr_vigente_mmm", "compromisos_mmm", "obligaciones_mmm", "pagos_mmm",
         "pct_c_av", "pct_o_av", "pct_p_av"],
        ent_rows, claves=["bitacora_id", "vigencia", "entidad"],
    )
    anios_ent = sorted({r[1] for r in ent_rows})
    print(f"  {len(ent_rows)} registros (entidad × vigencia) · años: {anios_ent}")

    # ── 3D: ejecucion_sectorial_mensual ───────────────────────────────────────
    # Carga los 12 meses del año:
    #   - año actual (anio_max): meses 1..mes_corte_num  → datos reales
    #                            meses mes_corte_num+1..12 → NULL (aún no ocurridos)
    #   - año anterior (anio_max-1): todos los meses disponibles en el Excel
    #   - histórico (2022..anio_max-2): promedio y mejor por mes — el promedio se
    #     limita al cuatrienio del PND vigente (2022-2026), no a la serie completa
    #     desde 2018, para que la referencia comparativa sea del gobierno actual.
    print(f"\n→ ejecucion_sectorial_mensual (vigencia={anio_max})")

    # Mes de corte del año actual (columna 'pct_compromisos_2025')
    anio_corte_num = MES_ORD[mes_corte.upper()]

    # Sectores activos en el año de corte
    sectores_act = sorted({sec for (ay, sec) in sec_agg if ay == anio_max})

    mens_rows = []
    for sector in sectores_act:
        for mes_num in range(1, 13):
            # Año actual: solo hasta el mes de corte
            if mes_num <= anio_corte_num:
                va, ca, oa, pa = mens_agg.get((anio_max, mes_num, sector), [0, 0, 0, 0])
                pct_comp_actual = pct(ca, va)
                pct_obl_actual  = pct(oa, va)
            else:
                pct_comp_actual = None
                pct_obl_actual  = None

            # Año anterior: datos reales hasta donde llega el Excel
            vb, cb, ob, pb = mens_agg.get((anio_max - 1, mes_num, sector), [0, 0, 0, 0])

            # Promedio y mejor sobre años históricos (2022 … anio_max-2)
            hist_comp = []
            hist_obl  = []
            for ay in range(2022, anio_max - 1):
                vh, ch, oh, ph = mens_agg.get((ay, mes_num, sector), [0, 0, 0, 0])
                if vh > 0:
                    hist_comp.append(ch / vh * 100)
                    hist_obl.append(oh / vh * 100)

            prom_comp  = round(sum(hist_comp) / len(hist_comp), 1) if hist_comp else None
            mejor_comp = round(max(hist_comp), 1)                  if hist_comp else None
            prom_obl   = round(sum(hist_obl)  / len(hist_obl),  1) if hist_obl  else None
            mejor_obl  = round(max(hist_obl),  1)                  if hist_obl  else None

            mens_rows.append((
                bid, anio_max, sector, mes_num,
                pct_comp_actual,  # pct_compromisos_2025 (año actual)
                pct(cb, vb),      # pct_compromisos_2024 (año anterior)
                prom_comp,
                mejor_comp,
                pct_obl_actual,   # pct_obligaciones_2025 (año actual)
                pct(ob, vb),      # pct_obligaciones_2024 (año anterior)
                prom_obl,
                mejor_obl,
            ))

    conn.execute(
        "DELETE FROM dbo.ejecucion_sectorial_mensual WHERE bitacora_id=? AND vigencia=?",
        (bid, anio_max)
    )
    # Esta tabla no tiene clave natural única (un sector puede repetir mes),
    # así que se inserta directo tras el borrado, sin upsert.
    conn.executemany("""
        INSERT INTO dbo.ejecucion_sectorial_mensual
            (bitacora_id, vigencia, sector, mes,
             pct_compromisos_2025, pct_compromisos_2024,
             pct_compromisos_prom, pct_compromisos_mejor,
             pct_obligaciones_2025, pct_obligaciones_2024,
             pct_obligaciones_prom, pct_obligaciones_mejor)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, mens_rows)
    print(f"  {len(mens_rows)} filas (sectores × meses)")


# ── Verificación ──────────────────────────────────────────────────────────────

def verificar(conn, bid):
    print("\n=== Verificación ===")
    rows = conn.execute("""
        SELECT vigencia, vigente_mmm, compromisos_mmm,
               pct_compromisos, pct_obligaciones
        FROM dbo.ejecucion_historica WHERE bitacora_id=?
        ORDER BY vigencia
    """, (bid,)).fetchall()
    print(f"{'Año':>6}  {'Vigente mmm':>12}  {'Comp mmm':>12}  {'%Comp':>6}  {'%Obl':>6}")
    for r in rows:
        print(f"  {r[0]:>4}  {r[1]:>12,.0f}  {r[2]:>12,.0f}  {r[3]:>6}%  {r[4]:>6}%")

    n_sec = conn.execute(
        "SELECT COUNT(*) FROM dbo.apropiacion_por_sector WHERE bitacora_id=?", (bid,)
    ).fetchone()[0]
    n_ent = conn.execute(
        "SELECT COUNT(*) FROM dbo.ejecucion_sectorial_entidades WHERE bitacora_id=?", (bid,)
    ).fetchone()[0]
    n_men = conn.execute(
        "SELECT COUNT(*) FROM dbo.ejecucion_sectorial_mensual WHERE bitacora_id=?", (bid,)
    ).fetchone()[0]
    print(f"\n  apropiacion_por_sector:        {n_sec:>5} registros")
    print(f"  ejecucion_sectorial_entidades: {n_ent:>5} registros")
    print(f"  ejecucion_sectorial_mensual:   {n_men:>5} registros")


# ── Entry point ───────────────────────────────────────────────────────────────

def run(args):
    conn = dbmod.conectar()

    bid = args.bitacora_id if args.bitacora_id else dbmod.bitacora_reciente(conn)
    row = conn.execute(
        "SELECT periodo, corte_fecha FROM dbo.metadatos_bitacora WHERE id=?", (bid,)
    ).fetchone()
    if not row:
        print(f"ERROR: bitacora_id={bid} no existe en metadatos_bitacora")
        conn.close()
        return

    print(f"\n=== ETL ejecucion_sectorial -> bitacora_id={bid} ({row[0]}) ===\n")

    # Agregar columnas nuevas si la BD viene del schema anterior
    verificar_columnas(conn)

    excel = Path(args.excel) if args.excel else bases.excel(6, "BASE DETALLE MENSUAL*.xlsx")
    print(f"  Excel: {excel.name}")
    records_corte, records_mensual = load_excel(excel, args.mes_corte)

    # El Excel maestro es un archivo acumulativo que crece cada bitácora (p. ej.
    # "BASE DETALLE MENSUAL INVERSIÓN 2018-2026.xlsx"). Si se recarga una
    # bitácora antigua usando una copia más nueva del archivo, éste ya trae
    # filas de vigencias posteriores al corte de esa bitácora. Sin este tope,
    # 'anio_max' (usado como año "actual" en toda la carga) terminaba siendo el
    # año más reciente del Excel en vez del año propio de la bitácora,
    # colando vigencias futuras en tablas de bitácoras ya publicadas.
    vigencia_bitacora = int(str(row[1])[:4])
    n_antes = len(records_corte) + len(records_mensual)
    records_corte   = [r for r in records_corte   if r[0] <= vigencia_bitacora]
    records_mensual = [r for r in records_mensual if r[0] <= vigencia_bitacora]
    n_descartadas = n_antes - len(records_corte) - len(records_mensual)
    if n_descartadas:
        print(f"  ⚠ {n_descartadas} filas posteriores a {vigencia_bitacora} "
              f"descartadas (no corresponden a esta bitácora)")

    # Preservar inv_pct_pib e inv_pct_gasto_total para vigencias que ya las tienen
    pib_prev   = {}
    gasto_prev = {}
    for r in conn.execute(
        "SELECT vigencia, inv_pct_pib, inv_pct_gasto_total "
        "FROM dbo.ejecucion_historica WHERE bitacora_id=?",
        (bid,)
    ).fetchall():
        pib_prev[r[0]]   = r[1]
        gasto_prev[r[0]] = r[2]

    # Agregaciones
    tot      = agg_totales(records_corte)
    sec_agg  = agg_sectores(records_corte)
    anio_max = max(tot.keys())
    ent_agg  = agg_entidades(records_corte)
    mens_agg = agg_mensual(records_mensual)

    # Cargar
    load_db(conn, bid, anio_max, args.mes_corte, tot, sec_agg, ent_agg, mens_agg,
            pib_prev, gasto_prev)

    conn.commit()

    verificar(conn, bid)
    conn.close()

    print("\n✅  ETL completado")


if __name__ == '__main__':
    ap = argparse.ArgumentParser(
        description='Carga ejecución sectorial desde BASE DETALLE MENSUAL'
    )
    ap.add_argument('--excel', default=None,
                    help='Ruta al .xlsx (por defecto, el de la sección 6)')
    ap.add_argument('--bitacora-id', type=int, default=None, dest='bitacora_id',
                    help='Por defecto, la bitácora más reciente')
    ap.add_argument('--mes-corte',    default='MAR',  dest='mes_corte',
                    help='Mes del corte (ENE, FEB, MAR, …)')
    run(ap.parse_args())
