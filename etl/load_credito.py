"""
ETL Crédito Externo (SCCI) — robusto a los formatos de Marzo y Junio 2026.

Carga tres tablas:
  credito_portafolio          ← hoja "Portafolio" (créditos BID/BM/CAF, USD)
  credito_ejecucion_entidad   ← ejecución por entidad (COP → mmm)
  credito_ejecucion_historica ← comparativo anual (COP → mmm)

Formatos soportados (autodetectados):
  A) Marzo (`Datos informe II 2026.xlsx`):
       Portafolio (8 col posicionales) · "Ejecución Entidad" · "Comp Ejección Anual Marzo"
  B) Junio (`Datos_Bitacora_SCCI.xlsx`): archivo reestructurado
       Portafolio (17 col, encabezado en fila 2, se lee por nombre)
       "Presupuestal_junio" (por crédito) → se agrega por (Sigla, Sector) para la ejecución por entidad
       "PresupuestalXAño" → comparativo anual

Uso:
    python etl/load_credito.py --file "C:\\...\\Junio\\8. SCCI\\Datos_Bitacora_SCCI.xlsx"
    python etl/load_credito.py            # ruta por defecto (marzo)
"""
import argparse
import openpyxl, sqlite3, sys, os, re
from collections import defaultdict

# Consola Windows (cp1252) no imprime ✓/✗; forzamos UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

DEFAULT_FILE = r"C:\ws\dnp\ws\BASES_BITACORA\2026\Marzo\8. SCCI\Datos informe II 2026.xlsx"
DEFAULT_DB   = os.path.join(os.path.dirname(__file__), '..', 'db', 'pgn.db')


def clean(v):
    return str(v).strip() if v is not None else ''


def to_f(v):
    """Número o texto ('35300000', ' -   ', '1.234,56') → float o None."""
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
    ws = wb['Portafolio']
    rows = list(ws.iter_rows(values_only=True))
    port = []
    for r in rows[1:]:
        if not r[0]:
            continue
        nombre, nombre_corto, fuente, contrato, monto, desembolsado, contratante, sector = r
        port.append((nombre, nombre_corto, clean(fuente),
                     str(contrato) if contrato is not None else None,
                     clean(sector), to_f(monto), to_f(desembolsado) or 0.0))

    ws2 = wb['Ejecución Entidad']
    ent = []
    for r in list(ws2.iter_rows(values_only=True))[1:]:
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

    ws3 = wb['Comp Ejección Anual Marzo']
    hist = []
    for r in list(ws3.iter_rows(values_only=True))[1:]:
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
    # 1) Portafolio (encabezado en fila 2; se lee por nombre de columna)
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
        banco  = clean(g(r, 'BANCO'))
        # Un crédito real tiene sector y banco; así se descartan filas de TOTAL/resumen.
        if not nombre or not sector or not banco:
            continue
        port.append((nombre, clean(g(r, 'NOMBRE CORTO')),
                     banco,                                      # fuente = banco (BID/BM/CAF)
                     clean(g(r, 'NO. CRÉDITO')) or None,
                     sector,
                     to_f(g(r, 'MONTO ACTUAL (USD)')),
                     to_f(g(r, 'MONTO DESEMBOLSADO (USD)')) or 0.0))

    # 2) Ejecución por entidad: agregar "Presupuestal_junio" por (Sigla, Sector)
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
        ent.append((entidad, sector,
                    None,                                   # apr_inicial no existe en junio
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


def main():
    ap = argparse.ArgumentParser(description="ETL Crédito Externo (Sec 7).")
    ap.add_argument('--file', default=DEFAULT_FILE)
    ap.add_argument('--db', default=DEFAULT_DB)
    args = ap.parse_args()

    wb = openpyxl.load_workbook(args.file, data_only=True)
    if 'Presupuestal_junio' in wb.sheetnames or 'PresupuestalXAño' in wb.sheetnames:
        fmt = 'junio'
        port, ent, hist = leer_junio(wb)
    else:
        fmt = 'marzo'
        port, ent, hist = leer_marzo(wb)
    wb.close()

    print(f"Formato detectado: {fmt}", file=sys.stderr)
    print(f"Portafolio: {len(port)} · Entidades: {len(ent)} · Años históricos: {len(hist)}", file=sys.stderr)

    conn = sqlite3.connect(args.db)
    schema_path = os.path.join(os.path.dirname(__file__), '..', 'db', 'schema.sql')
    with open(schema_path, encoding='utf-8') as f:
        schema_sql = f.read()
    for tabla in ('credito_portafolio', 'credito_ejecucion_entidad', 'credito_ejecucion_historica'):
        conn.execute(f"DROP TABLE IF EXISTS {tabla}")
        m = re.search(rf'(CREATE TABLE IF NOT EXISTS {tabla}[\s\S]+?;)', schema_sql)
        if not m:
            sys.exit(f"ERROR: no se encontró CREATE TABLE {tabla} en schema.sql")
        conn.execute(m.group(1))
    conn.commit()

    bid = conn.execute("SELECT id FROM metadatos_bitacora ORDER BY id DESC LIMIT 1").fetchone()[0]
    print(f"bitacora_id={bid}", file=sys.stderr)

    conn.executemany("""INSERT INTO credito_portafolio
        (bitacora_id, nombre, nombre_corto, fuente, contrato, sector, monto_usd, desembolsado_usd)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", [(bid, *r) for r in port])
    conn.executemany("""INSERT INTO credito_ejecucion_entidad
        (bitacora_id, entidad, sector, apr_inicial_mmm, apr_vigente_mmm, compromiso_mmm,
         obligacion_mmm, pago_mmm, pct_com, pct_ejec, pct_pago)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", [(bid, *r) for r in ent])
    conn.executemany("""INSERT INTO credito_ejecucion_historica
        (bitacora_id, anio, pct_comprometido, pct_ejecutado, pct_pagado,
         vigente_mmm, comprometido_mmm, ejecutado_mmm, pagado_mmm)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", [(bid, *r) for r in hist])
    conn.commit()

    tot = conn.execute("""SELECT COUNT(*), ROUND(SUM(monto_usd),2), ROUND(SUM(desembolsado_usd),2)
                          FROM credito_portafolio WHERE bitacora_id=?""", (bid,)).fetchone()
    conn.close()

    print(f"\n[OK] credito_portafolio:          {len(port)} filas")
    print(f"[OK] credito_ejecucion_entidad:   {len(ent)} filas")
    print(f"[OK] credito_ejecucion_historica: {len(hist)} filas")
    print(f"\n=== VERIFICACIÓN ===")
    print(f"  Operaciones: {tot[0]} · Total USD: {tot[1]:,.2f} · Desembolsado: {tot[2]:,.2f}")


if __name__ == '__main__':
    main()
