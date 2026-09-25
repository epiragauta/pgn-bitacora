"""
ETL Vigencias Futuras — robusto a los formatos de Marzo y Junio 2026.

Carga dos tablas:
  deflactores_pib   ← TD BITACORA (deflactor PIB base 2026, PIB corriente, PIB constante)
  vigencias_futuras ← pivot sector × año (pesos corrientes → mmm)

Fuente del pivot (autodetectada):
  A) Marzo: hoja transaccional `BASE_SIIF_2` con la columna `Valor_VF_Final (Actual)`.
     Se replica el pivot desde ahí (trazabilidad) — coincide 100% con TD BITACORA.
  B) Junio: `BASE_SIIF_2` ya no existe y las columnas de `BASE_SIIF`
     (`Valor_VF_Autorizada/Utilizada/ACTUAL_SIIF`) NO reproducen TD BITACORA
     (verificado: total 2026 BASE_SIIF≈18.690 vs TD≈28.691 mmm). En ese caso se
     lee el pivot directamente de `TD BITACORA`, que es la tabla validada por los
     analistas y de donde ya salen los deflactores.

Los deflactores/PIB siempre se leen de TD BITACORA (funciona en ambos cortes:
etiquetas `DEFLACTOR PIB ... BASE 2026`, `PIB corrientes ...`, `PIB Constantes ...`).

Uso:
    python etl/load_vigencias_futuras.py \
        --file "C:\\...\\Junio\\5. VIGENCIAS FUTURAS\\20260731 Nueva Base VF - Validada - Revisión Analistas.xlsx"
    python etl/load_vigencias_futuras.py            # usa la ruta por defecto (marzo)
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

DEFAULT_FILE = r"C:\ws\dnp\ws\BASES_BITACORA\2026\Marzo\5. VIGENCIAS FUTURAS\20260513 Nueva Base VF - Validada - Revisión Analistas.xlsx"
DEFAULT_DB   = os.path.join(os.path.dirname(__file__), '..', 'db', 'pgn.db')

# Nombres posibles de la columna de valor "final" en la hoja transaccional (Marzo).
VAL_FINAL_NAMES = ('Valor_VF_Final (Actual)', 'Valor_VF_Final (Actual) ')


def clean(v):
    return str(v).strip() if v is not None else ''


def to_f(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = clean(v).replace('\xa0', '').replace(' ', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


# ── TD BITACORA: deflactores/PIB + (opcional) pivot sector×año ────────────────
def leer_td_bitacora(ws_td):
    td_rows = []
    for i, row in enumerate(ws_td.iter_rows(values_only=True)):
        td_rows.append(list(row))
        if i >= 120:
            break

    # Cabecera de años ("Etiquetas de fila")
    year_col = {}
    hdr_idx = None
    for idx, r in enumerate(td_rows):
        if clean(r[0]).lower().startswith('etiquetas de fila'):
            hdr_idx = idx
            for c, v in enumerate(r):
                try:
                    y = int(clean(v))
                    if 2025 <= y <= 2054:
                        year_col[y] = c
                except (ValueError, TypeError):
                    pass
            break
    if not year_col:
        sys.exit("ERROR: no se encontró cabecera de años en TD BITACORA")

    deflactor, pib_corr, pib_ctes = {}, {}, {}
    for r in td_rows:
        lbl = clean(r[0]).upper()
        if 'DEFLACTOR PIB' in lbl and 'BASE' in lbl:
            for y, c in year_col.items():
                v = to_f(r[c])
                if v:
                    deflactor[y] = v
        elif lbl.startswith('PIB CORRIENTES'):
            for y, c in year_col.items():
                v = to_f(r[c])
                if v:
                    pib_corr[y] = round(v / 1000, 3)   # millones → mmm
        elif lbl.startswith('PIB CONSTANTES'):
            for y, c in year_col.items():
                v = to_f(r[c])
                if v:
                    pib_ctes[y] = v                     # ya en mmm

    # Pivot sector×año: filas entre la cabecera de años y "Total general".
    td_pivot = defaultdict(lambda: defaultdict(float))
    for r in td_rows[hdr_idx + 1:]:
        sect = clean(r[0])
        if not sect:
            continue
        if sect.lower() == 'total general':
            break
        for y, c in year_col.items():
            v = to_f(r[c])
            if v:
                td_pivot[sect][y] += v

    return year_col, deflactor, pib_corr, pib_ctes, td_pivot


# ── BASE_SIIF_2 (Marzo): pivot transaccional replicado ───────────────────────
def leer_base_siif2(wb):
    if 'BASE_SIIF_2' not in wb.sheetnames:
        return None
    ws = wb['BASE_SIIF_2']
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return None
    # Detecta fila de encabezado (la que contiene 'Nombre_Sector')
    hdr_idx = None
    for i, r in enumerate(rows[:5]):
        if 'Nombre_Sector' in [clean(x) for x in r]:
            hdr_idx = i
            break
    if hdr_idx is None:
        return None
    H = {clean(h): i for i, h in enumerate(rows[hdr_idx]) if h is not None}
    val_c = next((H[n] for n in VAL_FINAL_NAMES if n in H), None)
    if val_c is None or 'Nombre_Sector' not in H or 'Vigencia' not in H:
        return None  # sin la columna 'final' → no es replicable (caso junio)

    sect_c, vig_c = H['Nombre_Sector'], H['Vigencia']
    pivot = defaultdict(lambda: defaultdict(float))
    for r in rows[hdr_idx + 1:]:
        try:
            year = int(clean(r[vig_c]))
        except (ValueError, TypeError):
            continue
        if year < 2025 or year > 2054:
            continue
        sect = clean(r[sect_c])
        if not sect:
            continue
        v = to_f(r[val_c])
        if v:
            pivot[sect][year] += v
    return pivot


def main():
    ap = argparse.ArgumentParser(description="ETL Vigencias Futuras (Sec 5).")
    ap.add_argument('--file', default=DEFAULT_FILE, help="Archivo Excel de VF.")
    ap.add_argument('--db', default=DEFAULT_DB, help="Ruta de la base SQLite.")
    args = ap.parse_args()

    wb = openpyxl.load_workbook(args.file, read_only=True, data_only=True)
    year_col, deflactor, pib_corr, pib_ctes, td_pivot = leer_td_bitacora(wb["TD BITACORA"])

    print(f"Años encontrados: {sorted(year_col)}", file=sys.stderr)
    print(f"Deflactores: {len(deflactor)} · PIB corr: {len(pib_corr)} · PIB ctes: {len(pib_ctes)}", file=sys.stderr)

    # Fuente del pivot: BASE_SIIF_2 transaccional (marzo) o TD BITACORA (junio).
    pivot = leer_base_siif2(wb)
    if pivot is not None:
        fuente = "BASE_SIIF_2 (transaccional)"
    else:
        pivot = td_pivot
        fuente = "TD BITACORA (pivot validado)"
    wb.close()

    all_sectors = sorted(pivot.keys())
    all_years   = sorted({y for d in pivot.values() for y in d})
    print(f"Pivot desde {fuente}: {len(all_sectors)} sectores × {len(all_years)} años", file=sys.stderr)

    # Validación cruzada contra TD BITACORA (total por año)
    for y in (2026, 2027):
        tp = sum(d.get(y, 0) for d in pivot.values()) / 1e9
        tt = sum(d.get(y, 0) for d in td_pivot.values()) / 1e9
        print(f"  Validación {y}: fuente={tp:,.1f} mmm · TD BITACORA={tt:,.1f} mmm · dif={tp-tt:,.1f}", file=sys.stderr)

    # ── Cargar en BD ─────────────────────────────────────────────────────────
    conn = sqlite3.connect(args.db)
    schema_path = os.path.join(os.path.dirname(__file__), '..', 'db', 'schema.sql')
    with open(schema_path, encoding='utf-8') as f:
        schema_sql = f.read()

    for tabla in ('deflactores_pib', 'vigencias_futuras'):
        conn.execute(f"DROP TABLE IF EXISTS {tabla}")
        m = re.search(rf'(CREATE TABLE IF NOT EXISTS {tabla}[\s\S]+?;)', schema_sql)
        if not m:
            sys.exit(f"ERROR: no se encontró CREATE TABLE {tabla} en schema.sql")
        conn.execute(m.group(1))
    conn.commit()

    bid = conn.execute("SELECT id FROM metadatos_bitacora ORDER BY id DESC LIMIT 1").fetchone()[0]
    print(f"bitacora_id={bid}", file=sys.stderr)

    defl_rows = []
    for y in sorted(year_col):
        d = deflactor.get(y)
        if d is not None:
            defl_rows.append((bid, y, d, pib_corr.get(y), pib_ctes.get(y)))
    conn.executemany(
        """INSERT INTO deflactores_pib (bitacora_id, anio, deflactor, pib_corriente_mmm, pib_constante_mmm)
           VALUES (?, ?, ?, ?, ?)""", defl_rows)

    vf_rows = []
    for sect in all_sectors:
        for year in all_years:
            pesos = pivot[sect].get(year, 0.0)
            if pesos:
                vf_rows.append((bid, year, sect, round(pesos / 1e9, 3)))
    conn.executemany(
        """INSERT INTO vigencias_futuras (bitacora_id, vigencia_exec, sector, valor_corriente_mmm)
           VALUES (?, ?, ?, ?)""", vf_rows)
    conn.commit()

    n_defl = conn.execute("SELECT COUNT(*) FROM deflactores_pib WHERE bitacora_id=?", (bid,)).fetchone()[0]
    n_vf = conn.execute("SELECT COUNT(*) FROM vigencias_futuras WHERE bitacora_id=?", (bid,)).fetchone()[0]
    conn.close()

    print(f"\n✓ deflactores_pib:   {n_defl} filas")
    print(f"✓ vigencias_futuras: {n_vf} filas  ({len(all_sectors)} sectores × años) · fuente: {fuente}")


if __name__ == '__main__':
    main()
