"""
ETL: carga hoja sectores_por_region del Excel de regionalización.
Valores en pesos → divide por 1_000_000_000 para obtener mmm.

Nota: sigue apuntando al Consolidado sin sufijo de versión (no al _v_2.0)
porque la hoja "sectores_por_region" no existe en Consolidado Reg-Ejec-
Marzo-2022-2026_v_2.0.xlsx. La corrección de datos que motivó la v_2.0
solo afectó la hoja "Regionalizacion Mar-2022-2026" (ver load_regionalizacion.py).
"""
import sqlite3
import openpyxl

EXCEL = r'C:\ws\dnp\ws\BASES_BITACORA\2026\Marzo\3. REGIONALIZACIÓN\Consolidado Reg-Ejec-Marzo-2022-2026.xlsx'
DB    = r'C:\ws\dnp\ws\pgn-bitacora\db\pgn.db'

REGION_NORM = {
    'andina':    'ANDINA',
    'caribe':    'CARIBE',
    'pacifico':  'PACÍFICO',
    'pacífico':  'PACÍFICO',
    'orinoquia': 'ORINOQUÍA',
    'orinoquía': 'ORINOQUÍA',
    'amazonas':  'AMAZONIA',
    'amazonia':  'AMAZONIA',
    'insular':   'INSULAR',
}

def normalize_region(name):
    if not name:
        return None
    return REGION_NORM.get(name.strip().lower())

def run():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")

    # Aplicar migración si la tabla no existe
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS regionalizacion_sectores (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            bitacora_id INTEGER NOT NULL REFERENCES metadatos_bitacora(id),
            vigencia    INTEGER NOT NULL,
            region      TEXT    NOT NULL,
            sector      TEXT    NOT NULL,
            apropiacion_mmm  REAL,
            compromisos_mmm  REAL,
            obligaciones_mmm REAL,
            pagos_mmm        REAL,
            UNIQUE(bitacora_id, vigencia, region, sector)
        );
    """)

    bid = conn.execute(
        "SELECT id FROM metadatos_bitacora ORDER BY corte_fecha DESC LIMIT 1"
    ).fetchone()[0]
    print(f"Bitácora activa: id={bid}")

    wb = openpyxl.load_workbook(EXCEL, data_only=True)
    ws = wb['sectores_por_region']

    inserted = updated = skipped = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        region_raw, sector, aprop, comp, obl, pag, vigencia = row
        if not region_raw or not sector or not vigencia:
            continue

        region = normalize_region(region_raw)
        if not region:
            print(f"  WARN: región desconocida '{region_raw}'")
            skipped += 1
            continue

        conn.execute("""
            INSERT INTO regionalizacion_sectores
                (bitacora_id, vigencia, region, sector,
                 apropiacion_mmm, compromisos_mmm, obligaciones_mmm, pagos_mmm)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(bitacora_id, vigencia, region, sector) DO UPDATE SET
                apropiacion_mmm  = excluded.apropiacion_mmm,
                compromisos_mmm  = excluded.compromisos_mmm,
                obligaciones_mmm = excluded.obligaciones_mmm,
                pagos_mmm        = excluded.pagos_mmm
        """, (
            bid, int(vigencia), region, sector.strip(),
            round((aprop or 0) / 1e9, 3),
            round((comp  or 0) / 1e9, 3),
            round((obl   or 0) / 1e9, 3),
            round((pag   or 0) / 1e9, 3),
        ))
        inserted += 1

    conn.commit()
    conn.close()
    print(f"Listo: {inserted} registros insertados/actualizados, {skipped} omitidos.")

    # Verificación rápida
    conn2 = sqlite3.connect(DB)
    print("\n--- Verificación: top 5 sectores ANDINA 2026 ---")
    for r in conn2.execute("""
        SELECT sector, apropiacion_mmm, compromisos_mmm
        FROM regionalizacion_sectores
        WHERE region='ANDINA' AND vigencia=2026
        ORDER BY apropiacion_mmm DESC LIMIT 5
    """):
        print(f"  {r[0]:<45} aprop={r[1]:>8.1f} mmm  comp={r[2]:>8.1f} mmm")
    conn2.close()

if __name__ == '__main__':
    run()
