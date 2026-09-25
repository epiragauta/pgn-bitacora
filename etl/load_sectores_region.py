"""
ETL: carga el detalle sector × región (hoja de la Sección 3) → regionalizacion_sectores.
Valores en pesos → divide por 1_000_000_000 para obtener mmm.

Dos formatos de fuente soportados (autodetectados):

  A) Hoja consolidada `sectores_por_region`
     Columnas: Región | Sector | Apropiacion | Compromisos | Obligaciones | Pagos | Año
     (así venía el Consolidado "sin sufijo" de Marzo).

  B) Hojas por región (una hoja por cada región: ANDINA, AMAZONAS, CARIBE,
     PACIFICO, ORINOQUIA), tal como aparecen en
     `Consolidado Reg-Ejec-<mes>-2022-2026-Graficasvf.xlsx`.
     Cada hoja tiene:
        fila con 'Vigencia' en col A  → año
        fila con 'Region'   en col A  → nombre de la región
        fila con 'Etiquetas de fila' en col A → encabezado; debajo van
           sector | Suma de AprVigDpto | Suma de CompDpto | Suma de ObliDpto | Suma de PagosDpto
        hasta la fila 'Total general' (se omite).
     El consolidado del formato A es exactamente el apilado de estas hojas
     (verificado fila por fila contra `sectores_por_region` de Marzo).

Cuando el archivo del período no trae la hoja `sectores_por_region` pero sí
las hojas por región, este ETL reconstruye el detalle a partir de ellas.

Uso:
    python etl/load_sectores_region.py \
        --excel "ruta/Consolidado Reg-Ejec-Junio-2022-2026-Graficasvf.xlsx" \
        --db db/pgn.db
    python etl/load_sectores_region.py            # usa los valores por defecto
"""
import argparse
import sqlite3
from pathlib import Path

import openpyxl

# Ruta por defecto: el archivo "Graficasvf" es el que trae las hojas por región.
DEFAULT_EXCEL = r'C:\ws\dnp\ws\BASES_BITACORA\2026\Marzo\3. REGIONALIZACIÓN\Consolidado Reg-Ejec-Marzo-2022-2026-Graficasvf.xlsx'
DEFAULT_DB    = str(Path(__file__).resolve().parent.parent / 'db' / 'pgn.db')

REGION_NORM = {
    'andina':    'ANDINA',
    'caribe':    'CARIBE - INSULAR',
    'pacifico':  'PACÍFICO',
    'pacífico':  'PACÍFICO',
    'orinoquia': 'ORINOQUÍA',
    'orinoquía': 'ORINOQUÍA',
    'amazonas':  'AMAZONIA',
    'amazonia':  'AMAZONIA',
    'insular':   'CARIBE - INSULAR',
}


def normalize_region(name):
    if not name:
        return None
    return REGION_NORM.get(str(name).strip().lower())


def to_float(v):
    """Acepta número o texto (incl. formato colombiano '1.234.567,89'). Devuelve float o 0.0."""
    if v is None or v == '':
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return 0.0
    # Formato regional: si tiene coma decimal, quita puntos de miles y cambia coma por punto.
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0


def leer_consolidado(ws):
    """Formato A: hoja `sectores_por_region`. Devuelve filas (region_raw, sector, ap, co, ob, pa, año)."""
    filas = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        region_raw, sector, aprop, comp, obl, pag, vigencia = row[:7]
        if not region_raw or not sector or not vigencia:
            continue
        filas.append((region_raw, sector, aprop, comp, obl, pag, vigencia))
    return filas


def leer_hoja_region(ws):
    """Formato B: una hoja de región. Devuelve filas (region_raw, sector, ap, co, ob, pa, año).

    La región se toma del NOMBRE de la hoja (ANDINA/AMAZONAS/CARIBE/PACIFICO/ORINOQUIA),
    no de la celda 'Region' de la fila 3: en la hoja CARIBE esa celda dice
    '(Varios elementos)' porque el filtro de la tabla dinámica agrupa Caribe + Insular.
    """
    region_raw = ws.title
    rows = list(ws.iter_rows(min_row=1, values_only=True))

    def celda_a(r):
        return (str(r[0]).strip() if r and r[0] is not None else '')

    vigencia = None
    hdr_idx = None
    for i, r in enumerate(rows):
        a = celda_a(r).lower()
        if a == 'vigencia' and len(r) > 1:
            vigencia = r[1]
        elif a == 'etiquetas de fila':
            hdr_idx = i
            break

    if hdr_idx is None or vigencia is None:
        return []

    filas = []
    for r in rows[hdr_idx + 1:]:
        sector = celda_a(r)
        if not sector or sector.lower() == 'total general':
            break
        filas.append((region_raw, sector, r[1], r[2], r[3], r[4], vigencia))
    return filas


def recolectar_filas(wb):
    """Autodetecta el formato del libro y devuelve todas las filas de detalle sector×región."""
    if 'sectores_por_region' in wb.sheetnames:
        print("Fuente: hoja 'sectores_por_region' (formato consolidado).")
        return leer_consolidado(wb['sectores_por_region'])

    hojas_region = [sh for sh in wb.sheetnames if normalize_region(sh)]
    if hojas_region:
        print(f"Fuente: hojas por región {hojas_region} (reconstruyendo consolidado).")
        filas = []
        for sh in hojas_region:
            filas.extend(leer_hoja_region(wb[sh]))
        return filas

    raise SystemExit(
        "No se encontró ni la hoja 'sectores_por_region' ni hojas por región "
        f"(ANDINA/AMAZONAS/CARIBE/PACIFICO/ORINOQUIA) en el libro. Hojas: {wb.sheetnames}"
    )


def run(excel=DEFAULT_EXCEL, db=DEFAULT_DB, bitacora_id=None):
    conn = sqlite3.connect(db)
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

    if bitacora_id is None:
        bid = conn.execute(
            "SELECT id FROM metadatos_bitacora ORDER BY corte_fecha DESC LIMIT 1"
        ).fetchone()[0]
    else:
        bid = bitacora_id
    print(f"Bitácora activa: id={bid}")
    print(f"Excel: {excel}")

    wb = openpyxl.load_workbook(excel, data_only=True, read_only=True)
    filas = recolectar_filas(wb)
    wb.close()

    inserted = skipped = 0
    for region_raw, sector, aprop, comp, obl, pag, vigencia in filas:
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
            bid, int(vigencia), region, str(sector).strip(),
            round(to_float(aprop) / 1e9, 3),
            round(to_float(comp)  / 1e9, 3),
            round(to_float(obl)   / 1e9, 3),
            round(to_float(pag)   / 1e9, 3),
        ))
        inserted += 1

    conn.commit()
    conn.close()
    print(f"Listo: {inserted} registros insertados/actualizados, {skipped} omitidos.")

    # Verificación rápida
    conn2 = sqlite3.connect(db)
    print("\n--- Verificación: top 5 sectores ANDINA (año más reciente) ---")
    for r in conn2.execute("""
        SELECT sector, apropiacion_mmm, compromisos_mmm
        FROM regionalizacion_sectores
        WHERE region='ANDINA' AND bitacora_id=?
        ORDER BY vigencia DESC, apropiacion_mmm DESC LIMIT 5
    """, (bid,)):
        print(f"  {r[0]:<45} aprop={r[1]:>8.1f} mmm  comp={r[2]:>8.1f} mmm")
    conn2.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description="Carga detalle sector×región (Sec 3).")
    ap.add_argument('--excel', default=DEFAULT_EXCEL, help="Ruta del Excel de regionalización.")
    ap.add_argument('--db', default=DEFAULT_DB, help="Ruta de la base SQLite.")
    ap.add_argument('--bitacora-id', type=int, default=None,
                    help="ID de bitácora destino (por defecto, la más reciente).")
    args = ap.parse_args()
    run(excel=args.excel, db=args.db, bitacora_id=args.bitacora_id)
