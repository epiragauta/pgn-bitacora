"""
ETL SGP — Histórico por Componente — Bitácora 2026-I
Carga: sgp_historico_componentes ← hoja "8.2. Historico_Componentes"
       (tabla dinámica de componentes, columnas AE:AK, filas 1-21)
"""
import openpyxl, sys

import bases
import db as dbmod

FILE = bases.excel(7, "SGP_*_Bitacora.xlsx")

# (nombre de fila tal como aparece en la hoja, participación padre, es fila totalizadora)
# La fila 21 ("Total") se excluye: ya está disponible en sgp_historico_participacion.total_mmm
_STRUCT = [
    ('Educación',                      'Educación',                      True),
    ('Prestación Servicios',           'Educación',                      False),
    ('Calidad (Gratuidad)',            'Educación',                      False),
    ('Calidad (Matrícula)',            'Educación',                      False),
    ('Salud',                          'Salud',                          True),
    ('Régimen Subsidiado',             'Salud',                          False),
    ('Salud Pública',                  'Salud',                          False),
    ('Subsidio a la Oferta',           'Salud',                          False),
    ('Agua Potable',                   'Agua Potable',                   True),
    ('Propósito General',              'Propósito General',              True),
    ('Libre Inversión',                'Propósito General',              False),
    ('Deporte',                        'Propósito General',              False),
    ('Cultura',                        'Propósito General',              False),
    ('Libre Destinación',              'Propósito General',              False),
    ('Fonpet',                         'Propósito General',              False),
    ('Alimentación Escolar',           'Alimentación Escolar',           True),
    ('Ribereños',                      'Ribereños',                      True),
    ('Resguardos Indígenas',           'Resguardos Indígenas',           True),
    ('Fonpet Asignaciones Especiales', 'Fonpet Asignaciones Especiales', True),
]
_AÑOS = [2022, 2023, 2024, 2025, 2026]

wb = openpyxl.load_workbook(FILE, data_only=True)
ws = wb['8.2. Historico_Componentes']

# Columnas AE(31) a AK(37): etiqueta, 2022, 2023, 2024, 2025, 2026, Total general
rows = list(ws.iter_rows(min_row=1, max_row=21, min_col=31, max_col=37, values_only=True))
wb.close()

header, data_rows = rows[0], rows[1:20]  # excluye fila 21 ("Total")

if header[0] != 'Componentes / Participación' or list(header[1:6]) != _AÑOS:
    sys.exit(f"ERROR: encabezado inesperado en hoja 8.2 (AE1:AK1): {header}")
if len(data_rows) != len(_STRUCT):
    sys.exit(f"ERROR: se esperaban {len(_STRUCT)} filas de componentes, se encontraron {len(data_rows)}")

registros = []
for orden, ((nombre, padre, es_total), row) in enumerate(zip(_STRUCT, data_rows), start=1):
    if row[0] != nombre:
        sys.exit(f"ERROR: fila {orden} esperaba '{nombre}', encontró '{row[0]}'")
    for i, anio in enumerate(_AÑOS):
        valor = row[1 + i]
        registros.append((
            anio, orden, padre, nombre, int(es_total),
            round(valor / 1e9, 3) if valor is not None else None,
        ))

print(f"Componentes leídos: {len(_STRUCT)} filas x {len(_AÑOS)} vigencias = {len(registros)} registros", file=sys.stderr)

# ── Cargar en BD ──────────────────────────────────────────────────────────────
conn = dbmod.conectar()

bid = dbmod.bitacora_reciente(conn)
print(f"bitacora_id={bid}", file=sys.stderr)

# El esquema lo gobierna db/mssql/; aquí solo se reemplazan los datos de
# esta bitácora.
conn.upsert(
    "sgp_historico_componentes",
    ["bitacora_id", "vigencia", "orden", "participacion", "componente", "es_total", "valor_mmm"],
    [(bid, *r) for r in registros],
    claves=["bitacora_id", "vigencia", "orden"],
)

conn.commit()

n = conn.execute("SELECT COUNT(*) FROM sgp_historico_componentes WHERE bitacora_id=?", (bid,)).fetchone()[0]
tot2026 = conn.execute("""
    SELECT ROUND(SUM(valor_mmm),3) FROM sgp_historico_componentes
    WHERE bitacora_id=? AND vigencia=2026 AND es_total=1
""", (bid,)).fetchone()[0]

conn.close()

print(f"\n[OK] sgp_historico_componentes: {n} filas cargadas")
print(f"\n=== VERIFICACIÓN ===")
print(f"  Suma de totales de participación 2026 (miles de millones COP): {tot2026:,.3f}")
