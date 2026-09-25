"""
ETL Crédito Externo (SCCI) — robusto a los formatos de Marzo y Junio 2026.

Carga tres tablas (SQL Server, vía db.py):
  btcr_credito_portafolio          ← hoja "Portafolio"
  btcr_credito_ejecucion_entidad   ← ejecución por entidad (COP → mmm)
  btcr_credito_ejecucion_historica ← comparativo anual (COP → mmm)

Formatos soportados (autodetectados):
  A) Marzo (`Datos informe II 2026.xlsx`): Portafolio (8 col posicionales),
     "Ejecución Entidad", "Comp Ejección Anual Marzo".
  B) Junio (`Datos_Bitacora_SCCI.xlsx`): archivo reestructurado
     Portafolio (17 col, encabezado en fila 2, por nombre),
     "Presupuestal_junio" (por crédito) → agregado por (Sigla, Sector),
     "PresupuestalXAño" → comparativo anual.
"""
import openpyxl, sys

import bases
import db as dbmod

FILE = bases.excel(8, "Datos*.xlsx")   # cubre "Datos informe*.xlsx" y "Datos_Bitacora_SCCI.xlsx"


def clean(v):
    return str(v).strip() if v is not None else ''


def to_f(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = clean(v).replace('\xa0', '').replace(' ', '')
    if s in ('', '-', '—'):
        return None
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def find_header_row(rows, key, limit=6):
    for i, r in enumerate(rows[:limit]):
        if key in [clean(x) for x in r]:
            return i
    return None


# ─────────────────────────── Formato MARZO ───────────────────────────────────
def leer_marzo(wb):
    port, ent, hist = [], [], []
    for r in list(wb['Portafolio'].iter_rows(values_only=True))[1:]:
        if not r[0]:
            continue
        nombre, nombre_corto, fuente, contrato, monto, desembolsado, contratante, sector = r
        port.append((nombre, nombre_corto, clean(fuente),
                     str(contrato) if contrato is not None else None,
                     clean(sector), to_f(monto), to_f(desembolsado) or 0.0))
    for r in list(wb['Ejecución Entidad'].iter_rows(values_only=True))[1:]:
        if not r[0]:
            continue
        entidad, sector, apr_ini, apr_vig, comp, obl, pago, pct_com, pct_eje, pct_pag = r
        ent.append((clean(entidad), clean(sector),
                    round(apr_ini/1e9, 3) if apr_ini else None,
                    round(apr_vig/1e9, 3) if apr_vig else None,
                    round(comp/1e9, 3) if comp else None,
                    round(obl/1e9, 3) if obl else None,
                    round(pago/1e9, 3) if pago else None,
                    round(pct_com*100, 2) if pct_com is not None else None,
                    round(pct_eje*100, 2) if pct_eje is not None else None,
                    round(pct_pag*100, 2) if pct_pag is not None else None))
    for r in list(wb['Comp Ejección Anual Marzo'].iter_rows(values_only=True))[1:]:
        if not r[0]:
            continue
        anio, comp_pct, ejec_pct, pag_pct, vig, comp_v, ejec_v, pag_v = r[:8]
        hist.append((int(anio),
                     round(comp_pct*100, 2) if comp_pct is not None else None,
                     round(ejec_pct*100, 2) if ejec_pct is not None else None,
                     round(pag_pct*100, 2) if pag_pct is not None else None,
                     round(vig/1e9, 3) if vig else None,
                     round(comp_v/1e9, 3) if comp_v else None,
                     round(ejec_v/1e9, 3) if ejec_v else None,
                     round(pag_v/1e9, 3) if pag_v else None))
    return port, ent, hist


# ─────────────────────────── Formato JUNIO ───────────────────────────────────
def leer_junio(wb):
    # 1) Portafolio (encabezado en fila 2; por nombre de columna)
    rows = list(wb['Portafolio'].iter_rows(values_only=True))
    hi = find_header_row(rows, 'NOMBRE PROYECTO')
    H = {clean(h): i for i, h in enumerate(rows[hi]) if clean(h)}
    def g(r, name):
        i = H.get(name)
        return r[i] if i is not None and i < len(r) else None
    port = []
    for r in rows[hi+1:]:
        nombre = clean(g(r, 'NOMBRE PROYECTO'))
        sector = clean(g(r, 'SECTOR'))
        banco = clean(g(r, 'BANCO'))
        if not nombre or not sector or not banco:   # descarta filas TOTAL/resumen
            continue
        port.append((nombre, clean(g(r, 'NOMBRE CORTO')), banco,
                     clean(g(r, 'NO. CRÉDITO')) or None, sector,
                     to_f(g(r, 'MONTO ACTUAL (USD)')),
                     to_f(g(r, 'MONTO DESEMBOLSADO (USD)')) or 0.0))

    # 2) Ejecución por entidad: agrega "Presupuestal_junio" por (Sigla, Sector)
    rows = list(wb['Presupuestal_junio'].iter_rows(values_only=True))
    hi = find_header_row(rows, 'Sector')
    H = {clean(h): i for i, h in enumerate(rows[hi]) if clean(h)}
    def gp(r, name):
        i = H.get(name)
        return r[i] if i is not None and i < len(r) else None
    acc = {}
    for r in rows[hi+1:]:
        sigla = clean(gp(r, 'Sigla'))
        sector = clean(gp(r, 'Sector'))
        if not sigla and not sector:
            continue
        key = (sigla or clean(gp(r, 'Unidad Ejecutora')), sector)
        a = acc.setdefault(key, {'v': 0.0, 'c': 0.0, 'o': 0.0, 'p': 0.0})
        a['v'] += to_f(gp(r, 'Vigente_Jun')) or 0.0
        a['c'] += to_f(gp(r, 'Comprometido_Jun')) or 0.0
        a['o'] += to_f(gp(r, 'Obligado_Jun')) or 0.0
        a['p'] += to_f(gp(r, 'Pagado_Jun')) or 0.0
    ent = []
    for (entidad, sector), a in acc.items():
        v = a['v']
        ent.append((entidad, sector, None,
                    round(v/1e9, 3) if v else None,
                    round(a['c']/1e9, 3) if a['c'] else None,
                    round(a['o']/1e9, 3) if a['o'] else None,
                    round(a['p']/1e9, 3) if a['p'] else None,
                    round(a['c']/v*100, 2) if v else None,
                    round(a['o']/v*100, 2) if v else None,
                    round(a['p']/v*100, 2) if v else None))

    # 3) Comparativo anual: "PresupuestalXAño" (encabezado en fila 1)
    rows = list(wb['PresupuestalXAño'].iter_rows(values_only=True))
    hi = find_header_row(rows, 'AÑO')
    H = {clean(h): i for i, h in enumerate(rows[hi]) if clean(h)}
    def gh(r, name):
        i = H.get(name)
        return r[i] if i is not None and i < len(r) else None
    hist = []
    for r in rows[hi+1:]:
        anio = to_f(gh(r, 'AÑO'))
        if anio is None:
            continue
        v = to_f(gh(r, 'Vigente')); cmp_ = to_f(gh(r, 'Comprometido'))
        obl = to_f(gh(r, 'Obligado')); pag = to_f(gh(r, 'Pagado'))
        pc = to_f(gh(r, '%Comp')); pe = to_f(gh(r, '%Ejec')); pp = to_f(gh(r, '%Pag'))
        hist.append((int(anio),
                     round(pc*100, 2) if pc is not None else None,
                     round(pe*100, 2) if pe is not None else None,
                     round(pp*100, 2) if pp is not None else None,
                     round(v/1e9, 3) if v else None,
                     round(cmp_/1e9, 3) if cmp_ else None,
                     round(obl/1e9, 3) if obl else None,
                     round(pag/1e9, 3) if pag else None))
    return port, ent, hist


# ── Lectura autodetectada ─────────────────────────────────────────────────────
wb = openpyxl.load_workbook(FILE, data_only=True)
if 'Presupuestal_junio' in wb.sheetnames or 'PresupuestalXAño' in wb.sheetnames:
    fmt = 'junio'; port_rows, ent_rows, hist_rows = leer_junio(wb)
else:
    fmt = 'marzo'; port_rows, ent_rows, hist_rows = leer_marzo(wb)
wb.close()
print(f"Formato SCCI: {fmt} | Portafolio {len(port_rows)} · Entidades {len(ent_rows)} · Años {len(hist_rows)}", file=sys.stderr)

# ── Carga en BD (SQL Server) ──────────────────────────────────────────────────
conn = dbmod.conectar()
bid = dbmod.bitacora_reciente(conn)
print(f"bitacora_id={bid}", file=sys.stderr)

conn.vaciar_bitacora(
    ("btcr_credito_portafolio", "btcr_credito_ejecucion_entidad", "btcr_credito_ejecucion_historica"), bid)

conn.executemany("""
    INSERT INTO dbo.btcr_credito_portafolio
        (bitacora_id, nombre, nombre_corto, fuente, contrato, sector, monto_usd, desembolsado_usd)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", [(bid, *r) for r in port_rows])

conn.upsert(
    "btcr_credito_ejecucion_entidad",
    ["bitacora_id", "entidad", "sector", "apr_inicial_mmm", "apr_vigente_mmm",
     "compromiso_mmm", "obligacion_mmm", "pago_mmm", "pct_com", "pct_ejec", "pct_pago"],
    [(bid, *r) for r in ent_rows], claves=["bitacora_id", "entidad"])

conn.upsert(
    "btcr_credito_ejecucion_historica",
    ["bitacora_id", "anio", "pct_comprometido", "pct_ejecutado", "pct_pagado",
     "vigente_mmm", "comprometido_mmm", "ejecutado_mmm", "pagado_mmm"],
    [(bid, *r) for r in hist_rows], claves=["bitacora_id", "anio"])

conn.commit()

n1 = conn.execute("SELECT COUNT(*) FROM btcr_credito_portafolio WHERE bitacora_id=?", (bid,)).fetchone()[0]
n2 = conn.execute("SELECT COUNT(*) FROM btcr_credito_ejecucion_entidad WHERE bitacora_id=?", (bid,)).fetchone()[0]
n3 = conn.execute("SELECT COUNT(*) FROM btcr_credito_ejecucion_historica WHERE bitacora_id=?", (bid,)).fetchone()[0]
tot = conn.execute("""
    SELECT COUNT(*), ROUND(SUM(monto_usd),2), ROUND(SUM(desembolsado_usd),2)
    FROM btcr_credito_portafolio WHERE bitacora_id=?""", (bid,)).fetchone()
conn.close()

print(f"\n[OK] btcr_credito_portafolio:          {n1} filas cargadas")
print(f"[OK] btcr_credito_ejecucion_entidad:   {n2} filas cargadas")
print(f"[OK] btcr_credito_ejecucion_historica: {n3} filas cargadas")
print(f"  Operaciones: {tot[0]} · Total USD: {tot[1]:,.2f} · Desembolsado: {tot[2]:,.2f}")
