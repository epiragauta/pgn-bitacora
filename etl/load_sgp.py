"""
ETL Sistema General de Participaciones (SGP) — Bitácora 2026-I
Carga: sgp_historico_participacion ← hoja "8.1. Historico_Participacion"
       (tabla dinámica de participaciones por año, columnas T:U)
"""
import openpyxl, sqlite3, sys, os, re

FILE = r"C:\ws\dnp\ws\BASES_BITACORA\2026\Marzo\7. SDRT\SGP_2022-2026_Bitacora.xlsx"
DB   = os.path.join(os.path.dirname(__file__), '..', 'db', 'pgn.db')

# Etiqueta de la tabla dinámica -> clave de la serie
_SERIES_MAP = {
    'Total_SGP':                       'total',
    'Suma de Educación':               'educacion',
    'Suma de Salud':                   'salud',
    'Suma de Agua Potable':            'agua_potable',
    'Suma de Propósito General':       'proposito_general',
    'Suma de Alimentación Escolar':    'alimentacion_escolar',
    'Suma de Ribereños':               'riberenos',
    'Suma de Resguardos Indígenas':    'resguardos_indigenas',
    'Fonpet AE':                       'fonpet_ae',
}

wb = openpyxl.load_workbook(FILE, data_only=True)
ws = wb['8.1. Historico_Participacion']

# Las tablas dinámicas de esta hoja están en las columnas T (etiqueta/año) y U (serie/valor).
# Estructura: fila "Etiquetas de fila" | <nombre serie>  seguida de filas <año> | <valor>
# hasta una fila "Total general" | <total serie>.
series: dict = {}
current_key = None
for row in ws.iter_rows(min_row=1, max_row=100, min_col=20, max_col=21, values_only=True):
    label, value = row
    if label == 'Etiquetas de fila':
        current_key = _SERIES_MAP.get(value)
        if current_key:
            series[current_key] = {}
        continue
    if current_key is None:
        continue
    if isinstance(label, int) and 2022 <= label <= 2026:
        series[current_key][label] = value
    elif label == 'Total general':
        current_key = None

wb.close()

faltantes = [k for k in _SERIES_MAP.values() if k not in series]
if faltantes:
    sys.exit(f"ERROR: no se encontraron todas las series esperadas en la hoja. Faltan: {faltantes}")

print(f"Series leídas: {sorted(series.keys())}", file=sys.stderr)

# Valores en la hoja están en millones de pesos corrientes -> convertir a miles de millones (÷1000)
años = [2022, 2023, 2024, 2025, 2026]
hist_rows = []
for anio in años:
    hist_rows.append((
        anio,
        round(series['educacion'][anio] / 1000, 3),
        round(series['salud'][anio] / 1000, 3),
        round(series['agua_potable'][anio] / 1000, 3),
        round(series['proposito_general'][anio] / 1000, 3),
        round(series['alimentacion_escolar'][anio] / 1000, 3),
        round(series['riberenos'][anio] / 1000, 3),
        round(series['resguardos_indigenas'][anio] / 1000, 3),
        round(series['fonpet_ae'][anio] / 1000, 3),
        round(series['total'][anio] / 1000, 3),
    ))

print(f"Histórico SGP: {len(hist_rows)} vigencias leídas (2022-2026)", file=sys.stderr)

# ── Cargar en BD ──────────────────────────────────────────────────────────────
conn = sqlite3.connect(DB)

schema_path = os.path.join(os.path.dirname(__file__), '..', 'db', 'schema.sql')
with open(schema_path, encoding='utf-8') as f:
    schema_sql = f.read()

conn.execute("DROP TABLE IF EXISTS sgp_historico_participacion")
m = re.search(r'(CREATE TABLE IF NOT EXISTS sgp_historico_participacion[\s\S]+?;)', schema_sql)
if not m:
    sys.exit("ERROR: no se encontró CREATE TABLE sgp_historico_participacion en schema.sql")
conn.execute(m.group(1))
conn.commit()

bid = conn.execute("SELECT id FROM metadatos_bitacora ORDER BY id DESC LIMIT 1").fetchone()[0]
print(f"bitacora_id={bid}", file=sys.stderr)

conn.executemany("""
    INSERT INTO sgp_historico_participacion
        (bitacora_id, vigencia, educacion_mmm, salud_mmm, agua_potable_mmm, proposito_general_mmm,
         alimentacion_escolar_mmm, riberenos_mmm, resguardos_indigenas_mmm, fonpet_ae_mmm, total_mmm)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", [(bid, *r) for r in hist_rows])

conn.commit()

n = conn.execute("SELECT COUNT(*) FROM sgp_historico_participacion WHERE bitacora_id=?", (bid,)).fetchone()[0]
tot = conn.execute("""
    SELECT ROUND(SUM(total_mmm),3) FROM sgp_historico_participacion WHERE bitacora_id=?
""", (bid,)).fetchone()[0]

conn.close()

print(f"\n[OK] sgp_historico_participacion: {n} filas cargadas")
print(f"\n=== VERIFICACIÓN ===")
print(f"  Total SGP 2022-2026 (miles de millones COP): {tot:,.3f}")
