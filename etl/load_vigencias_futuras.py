"""
ETL Vigencias Futuras — robusto a los formatos de Marzo y Junio 2026 (SQL Server).

Carga dos tablas:
  btcr_deflactores_pib   ← TD BITACORA (deflactor PIB base 2026, PIB corriente/constante)
  btcr_vigencias_futuras ← pivot sector × año (pesos corrientes → mmm)

Fuente del pivot (autodetectada):
  A) Hoja transaccional `BASE_SIIF_2`/`BASE_SIIF` con la columna calculada
     `Valor_VF_Final (Actual)` → se replica el pivot desde ahí (trazabilidad).
  B) Si esa columna no existe (entrega de junio 2026: BASE_SIIF trae solo las
     columnas crudas Autorizada/Utilizada/ACTUAL, que NO reproducen los totales
     de la bitácora), se usa el pivot ya validado de `TD BITACORA`, de donde
     además salen los deflactores.
"""
import openpyxl, sys
from collections import defaultdict

import bases
import db as dbmod

# Puede haber varias entregas del mismo corte ('20260709...', '20260731...');
# se toma la más reciente (el nombre empieza por la fecha AAAAMMDD).
_vf = sorted(bases.carpeta_seccion(5).glob("*Base VF*.xlsx"))
if not _vf:
    sys.exit("No se encontró archivo de Vigencias Futuras (*Base VF*.xlsx) en la sección 5.")
FILE = _vf[-1]

def clean(v):
    return str(v).strip() if v is not None else ''

def to_f(v):
    if v is None: return None
    if isinstance(v, (int, float)): return float(v)
    s = clean(v).replace('\xa0', '').replace(' ', '').replace(',', '.')
    try: return float(s)
    except: return None

# ── 1. TD BITACORA: deflactores/PIB + pivot sector×año ────────────────────────
wb = openpyxl.load_workbook(FILE, read_only=True, data_only=True)
ws_td = wb["TD BITACORA"]

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
            except:
                pass
        break

if not year_col:
    sys.exit("ERROR: no se encontró cabecera de años en TD BITACORA")

print(f"Años encontrados: {sorted(year_col)}", file=sys.stderr)

deflactor, pib_corr, pib_ctes = {}, {}, {}
for r in td_rows:
    lbl = clean(r[0]).upper()
    if 'DEFLACTOR PIB' in lbl and 'BASE' in lbl:
        for y, c in year_col.items():
            v = to_f(r[c])
            if v: deflactor[y] = v
    elif lbl.startswith('PIB CORRIENTES'):
        for y, c in year_col.items():
            v = to_f(r[c])
            if v: pib_corr[y] = round(v / 1000, 3)   # millones → mmm
    elif lbl.startswith('PIB CONSTANTES'):
        for y, c in year_col.items():
            v = to_f(r[c])
            if v: pib_ctes[y] = v

# Pivot sector×año desde TD BITACORA (filas entre la cabecera y "Total general")
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

print(f"Deflactores: {len(deflactor)} · PIB corr: {len(pib_corr)} · PIB ctes: {len(pib_ctes)}", file=sys.stderr)

# ── 2. Fuente del pivot: BASE_SIIF_2 transaccional (marzo) o TD BITACORA (junio) ──
_HOJAS_BASE = ("BASE_SIIF_2", "BASE_SIIF")
_hoja = next((h for h in _HOJAS_BASE if h in wb.sheetnames), None)

def _fila_encabezado(filas, requeridas=('Nombre_Sector', 'Vigencia'), maximo=10):
    for i, fila in enumerate(filas[:maximo]):
        etiquetas = {clean(c) for c in fila if c is not None}
        if all(r in etiquetas for r in requeridas):
            return i
    return None

pivot = None
fuente = None
if _hoja is not None:
    ws_src = wb[_hoja]
    src_rows = list(ws_src.iter_rows(values_only=True))
    _i = _fila_encabezado(src_rows)
    if _i is not None:
        SC = {clean(h): i for i, h in enumerate(src_rows[_i]) if h is not None}
        VIG_C = SC.get('Vigencia')
        VAL_C = SC.get('Valor_VF_Final (Actual)') or SC.get('Valor_VF_Final (Actual) ')
        SECT_C = SC.get('Nombre_Sector')
        if None not in (VIG_C, VAL_C, SECT_C):
            pivot = defaultdict(lambda: defaultdict(float))
            for r in src_rows[_i + 1:]:
                try: year = int(clean(r[VIG_C]))
                except: continue
                if year < 2025 or year > 2054: continue
                sect = clean(r[SECT_C])
                if not sect: continue
                val = to_f(r[VAL_C])
                if val: pivot[sect][year] += val
            fuente = f"{_hoja} (transaccional)"

wb.close()

if pivot is None:
    # Junio: la hoja transaccional no trae 'Valor_VF_Final (Actual)'; se usa el
    # pivot validado de TD BITACORA (verificado: coincide 100% con los totales).
    pivot = td_pivot
    fuente = "TD BITACORA (pivot validado)"

all_sectors = sorted(pivot.keys())
all_years   = sorted({y for d in pivot.values() for y in d})
print(f"Pivot desde {fuente}: {len(all_sectors)} sectores × {len(all_years)} años", file=sys.stderr)
for y in (2026, 2027):
    tp = sum(d.get(y, 0) for d in pivot.values()) / 1e9
    tt = sum(d.get(y, 0) for d in td_pivot.values()) / 1e9
    print(f"  Validación {y}: fuente={tp:,.1f} · TD BITACORA={tt:,.1f} · dif={tp-tt:,.1f}", file=sys.stderr)

# ── 3. Cargar en BD (SQL Server) ──────────────────────────────────────────────
conn = dbmod.conectar()
bid = dbmod.bitacora_reciente(conn)
print(f"bitacora_id={bid}", file=sys.stderr)

conn.vaciar_bitacora(("btcr_vigencias_futuras", "btcr_deflactores_pib"), bid)

defl_rows = []
for y in sorted(year_col):
    d = deflactor.get(y)
    if d is not None:
        defl_rows.append((bid, y, d, pib_corr.get(y), pib_ctes.get(y)))
conn.upsert(
    "btcr_deflactores_pib",
    ["bitacora_id", "anio", "deflactor", "pib_corriente_mmm", "pib_constante_mmm"],
    defl_rows, claves=["bitacora_id", "anio"])

vf_rows = []
for sect in all_sectors:
    for year in all_years:
        pesos = pivot[sect].get(year, 0.0)
        if pesos:
            vf_rows.append((bid, year, sect, round(pesos / 1e9, 3)))
conn.upsert(
    "btcr_vigencias_futuras",
    ["bitacora_id", "vigencia_exec", "sector", "valor_corriente_mmm"],
    vf_rows, claves=["bitacora_id", "vigencia_exec", "sector"])

conn.commit()

n_defl = conn.execute("SELECT COUNT(*) FROM btcr_deflactores_pib WHERE bitacora_id=?", (bid,)).fetchone()[0]
n_vf = conn.execute("SELECT COUNT(*) FROM btcr_vigencias_futuras WHERE bitacora_id=?", (bid,)).fetchone()[0]
conn.close()

print(f"\n[OK] btcr_deflactores_pib:   {n_defl} filas")
print(f"[OK] btcr_vigencias_futuras: {n_vf} filas  ({len(all_sectors)} sectores × años) · fuente: {fuente}")
