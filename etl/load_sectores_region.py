"""
ETL: detalle sector × región → regionalizacion_sectores (SQL Server, vía db.py).
Valores en pesos → /1e9 para mmm.

Dos formatos de fuente (autodetectados sobre los .xlsx de la sección 3):
  A) Hoja consolidada `sectores_por_region`
     (Región | Sector | Apropiacion | Compromisos | Obligaciones | Pagos | Año).
  B) Hojas por región (ANDINA/AMAZONAS/CARIBE/PACIFICO/ORINOQUIA) del archivo
     "Consolidado Reg-Ejec-<mes>-...-Graficasvf.xlsx": cada hoja trae Vigencia
     (fila), Region (fila), encabezado 'Etiquetas de fila' y luego
     sector | AprVigDpto | CompDpto | ObliDpto | PagosDpto hasta 'Total general'.
     El consolidado del formato A es exactamente el apilado de estas hojas
     (verificado fila por fila). La región se toma del NOMBRE de la hoja
     (en CARIBE la celda 'Region' dice '(Varios elementos)').
"""
import openpyxl

import bases
import db as dbmod

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
    if v is None or v == '':
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return 0.0
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0


def leer_consolidado(ws):
    filas = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        region_raw, sector, aprop, comp, obl, pag, vigencia = row[:7]
        if not region_raw or not sector or not vigencia:
            continue
        filas.append((region_raw, sector, aprop, comp, obl, pag, vigencia))
    return filas


def leer_hoja_region(ws):
    region_raw = ws.title
    rows = list(ws.iter_rows(min_row=1, values_only=True))

    def celda_a(r):
        return (str(r[0]).strip() if r and r[0] is not None else '')

    vigencia, hdr = None, None
    for i, r in enumerate(rows):
        a = celda_a(r).lower()
        if a == 'vigencia' and len(r) > 1:
            vigencia = r[1]
        elif a == 'etiquetas de fila':
            hdr = i
            break
    if hdr is None or vigencia is None:
        return []
    filas = []
    for r in rows[hdr + 1:]:
        sector = celda_a(r)
        if not sector or sector.lower() == 'total general':
            break
        filas.append((region_raw, sector, r[1], r[2], r[3], r[4], vigencia))
    return filas


def recolectar():
    """Recorre los .xlsx de la sección 3 y devuelve (filas, descripcion_fuente)."""
    carpeta = bases.carpeta_seccion(3)
    xlsx = sorted(carpeta.glob('*.xlsx'))
    # 1) preferir un libro con la hoja consolidada
    for f in xlsx:
        wb = openpyxl.load_workbook(f, data_only=True, read_only=True)
        if 'sectores_por_region' in wb.sheetnames:
            filas = leer_consolidado(wb['sectores_por_region'])
            wb.close()
            return filas, f"{f.name} · hoja sectores_por_region"
        wb.close()
    # 2) reconstruir desde hojas por región
    for f in xlsx:
        wb = openpyxl.load_workbook(f, data_only=True, read_only=True)
        hojas = [s for s in wb.sheetnames if normalize_region(s)]
        if hojas:
            filas = []
            for s in hojas:
                filas.extend(leer_hoja_region(wb[s]))
            wb.close()
            return filas, f"{f.name} · hojas por región {hojas}"
        wb.close()
    raise SystemExit(
        "ERROR: en la sección 3 no se encontró ni la hoja 'sectores_por_region' "
        "ni hojas por región (ANDINA/AMAZONAS/CARIBE/PACIFICO/ORINOQUIA). "
        "Solicitar el libro 'Graficasvf' del corte."
    )


def run():
    conn = dbmod.conectar()
    bid = dbmod.bitacora_reciente(conn)
    print(f"Bitácora activa: id={bid}")

    registros, fuente = recolectar()
    print(f"Fuente sectores×región: {fuente}")

    filas, skipped = [], 0
    for region_raw, sector, aprop, comp, obl, pag, vigencia in registros:
        if not region_raw or not sector or not vigencia:
            continue
        region = normalize_region(region_raw)
        if not region:
            print(f"  WARN: región desconocida '{region_raw}'")
            skipped += 1
            continue
        try:
            anio = int(vigencia)
        except (TypeError, ValueError):
            skipped += 1
            continue
        filas.append((
            bid, anio, region, str(sector).strip(),
            round(to_float(aprop) / 1e9, 3),
            round(to_float(comp) / 1e9, 3),
            round(to_float(obl) / 1e9, 3),
            round(to_float(pag) / 1e9, 3),
        ))

    conn.vaciar_bitacora(("regionalizacion_sectores",), bid)
    n = conn.upsert(
        "regionalizacion_sectores",
        ["bitacora_id", "vigencia", "region", "sector",
         "apropiacion_mmm", "compromisos_mmm", "obligaciones_mmm", "pagos_mmm"],
        filas, claves=["bitacora_id", "vigencia", "region", "sector"],
    )
    conn.commit()
    print(f"Listo: {n} registros, {skipped} omitidos.")

    print("\n--- Verificación: top 5 sectores ANDINA (año más reciente) ---")
    for r in conn.execute("""
        SELECT TOP 5 sector, apropiacion_mmm, compromisos_mmm
        FROM dbo.regionalizacion_sectores
        WHERE bitacora_id=? AND region='ANDINA'
        ORDER BY vigencia DESC, apropiacion_mmm DESC
    """, (bid,)):
        print(f"  {r[0]:<45} aprop={r[1]:>8.1f} mmm  comp={r[2]:>8.1f} mmm")
    conn.close()


if __name__ == '__main__':
    run()
