"""
etl/update_bitacora.py  —  Script de carga de nuevas bitácoras
Uso:
  python3 etl/update_bitacora.py --periodo 2025-II --corte 2025-06-30

El script:
  1. Crea el registro en metadatos_bitacora
  2. Lee un CSV por tabla (generado manualmente o via extracción)
  3. Inserta o actualiza los registros en la BD

Estructura de CSV esperada por tabla:
  - data/inversion_transformaciones.csv
  - data/ejecucion_historica.csv
  - data/apropiacion_sectores.csv
  - data/ejecucion_sectorial.csv

Secciones que este script YA NO carga:
  · Regionalización — escribía en regionalizacion_detalle_2025, tabla
    retirada en la migración. Usar etl/load_regionalizacion.py.
  · Vigencias futuras — su CSV trae valor_mmm_ctes y pct_pib, columnas
    que dejaron de existir hace tiempo (la tabla guarda pesos corrientes
    en valor_corriente_mmm). Usar etl/load_vigencias_futuras.py.
"""

import csv
import argparse
from pathlib import Path

import db as dbmod

DATA_DIR = Path(__file__).parent / "data"


def get_conn():
    return dbmod.conectar()


def create_bitacora(conn, numero, periodo, corte, fuente, notas):
    nuevo_id = conn.insertar_devolviendo_id("""
        INSERT INTO dbo.metadatos_bitacora
            (numero_bitacora, periodo, corte_fecha, fuente_principal, notas)
        VALUES (?,?,?,?,?)
    """, (numero, periodo, corte, fuente, notas))
    conn.commit()
    return nuevo_id


def load_csv(path, required_cols=None):
    """Lee un CSV y retorna lista de dicts. Valida columnas si se pasan."""
    if not path.exists():
        print(f"  ⚠️  No existe {path.name}, se omite")
        return []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if required_cols:
        missing = required_cols - set(reader.fieldnames or [])
        if missing:
            print(f"  ❌  {path.name}: faltan columnas {missing}")
            return []
    return rows


def load_inversion_transformaciones(conn, bid, rows):
    for r in rows:
        conn.execute("""
            INSERT INTO dbo.inversion_transformaciones
                (bitacora_id, vigencia, transformador, inversion_mmm, peso_pct)
            VALUES (?,?,?,?,?)
        """, (bid, int(r["vigencia"]), r["transformador"],
              float(r["inversion_mmm"]) if r.get("inversion_mmm") else None,
              float(r["peso_pct"])      if r.get("peso_pct")      else None))
    print(f"  ✅  inversion_transformaciones: {len(rows)} filas")


def load_ejecucion_historica(conn, bid, rows):
    for r in rows:
        conn.execute("""
            INSERT INTO dbo.ejecucion_historica
                (bitacora_id, vigencia, vigente_mmm, compromisos_mmm,
                 obligaciones_mmm, pagos_mmm, pct_compromisos, pct_obligaciones,
                 pct_pagos, inv_pct_pib, inv_pct_gasto_total)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (bid,
              int(r["vigencia"]),
              float(r["vigente_mmm"]),
              float(r["compromisos_mmm"]),
              float(r["obligaciones_mmm"]),
              float(r["pagos_mmm"]),
              float(r.get("pct_compromisos", 0)),
              float(r.get("pct_obligaciones", 0)),
              float(r.get("pct_pagos", 0)),
              float(r.get("inv_pct_pib", 0)),
              float(r.get("inv_pct_gasto_total", 0))))
    print(f"  ✅  ejecucion_historica: {len(rows)} filas")


def load_apropiacion_sectores(conn, bid, rows):
    for r in rows:
        conn.execute("""
            INSERT INTO dbo.apropiacion_por_sector
                (bitacora_id, vigencia, sector, vigente_mmm)
            VALUES (?,?,?,?)
        """, (bid, int(r["vigencia"]), r["sector"],
              float(r["vigente_mmm"]) if r.get("vigente_mmm") else None))
    print(f"  ✅  apropiacion_por_sector: {len(rows)} filas")


def load_ejecucion_sectorial(conn, bid, rows):
    for r in rows:
        conn.execute("""
            INSERT INTO dbo.ejecucion_sectorial_entidades
                (bitacora_id, vigencia, sector, entidad,
                 apr_vigente_mmm, compromisos_mmm, obligaciones_mmm,
                 pct_c_av, pct_o_av)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (bid, int(r["vigencia"]), r["sector"], r["entidad"],
              float(r.get("apr_vigente_mmm") or 0),
              float(r["compromisos_mmm"]) if r.get("compromisos_mmm") else None,
              float(r["obligaciones_mmm"]) if r.get("obligaciones_mmm") else None,
              float(r["pct_c_av"]) if r.get("pct_c_av") else None,
              float(r["pct_o_av"]) if r.get("pct_o_av") else None))
    print(f"  ✅  ejecucion_sectorial_entidades: {len(rows)} filas")


def main():
    parser = argparse.ArgumentParser(description="Carga nueva bitácora PGN")
    parser.add_argument("--numero",  default="3",          help="Número de bitácora")
    parser.add_argument("--periodo", required=True,         help="Período ej. 2025-II")
    parser.add_argument("--corte",   required=True,         help="Fecha corte YYYY-MM-DD")
    parser.add_argument("--fuente",  default="SIIF Nación", help="Fuente de datos")
    parser.add_argument("--notas",   default="",            help="Notas adicionales")
    parser.add_argument("--data-dir", default=str(DATA_DIR),help="Directorio de CSVs")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    conn = get_conn()

    # Verificar si ya existe
    exists = conn.execute(
        "SELECT id FROM metadatos_bitacora WHERE periodo=?", (args.periodo,)
    ).fetchone()
    if exists:
        print(f"⚠️  Ya existe bitácora para período {args.periodo} (id={exists[0]})")
        print("   Si quieres recargar, primero elimina el registro manualmente.")
        return

    bid = create_bitacora(conn, args.numero, args.periodo, args.corte, args.fuente, args.notas)
    print(f"\n✅  Bitácora creada: {args.periodo} (id={bid})")
    print(f"   Leyendo CSVs desde: {data_dir}\n")

    loaders = [
        ("inversion_transformaciones.csv", load_inversion_transformaciones),
        ("ejecucion_historica.csv",        load_ejecucion_historica),
        ("apropiacion_sectores.csv",       load_apropiacion_sectores),
        ("ejecucion_sectorial.csv",        load_ejecucion_sectorial),
    ]
    for fname, fn in loaders:
        rows = load_csv(data_dir / fname)
        if rows:
            fn(conn, bid, rows)

    conn.commit()
    print(f"\n🎉  Carga completada para {args.periodo}")


if __name__ == "__main__":
    main()
