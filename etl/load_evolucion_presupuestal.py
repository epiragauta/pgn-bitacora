#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETL Sección 2 — Evolución Presupuestal PGN, directo desde el Excel.

Lee la hoja `Evolucion PGN` del archivo de estructura de evolución
(`...Estructura_Evolución PGN y Reg-Ejec-<mes>.xlsx`) y carga las tablas
`pgn_concepto` / `pgn_ejecucion` (+ vista `pgn_vista_crosstab`), reemplazando
la carga por CSV de `importar_pgn.py`. Reutiliza su DDL para no divergir del
esquema que consume la API.

La hoja es un crosstab: 28 conceptos (jerarquía de 4 niveles, incluidas 4 filas
"% del PIB") × 5 años × 4 fases. Unidades ya en miles de millones (mmm), no se
convierten. Detalles de la fuente (ver docs/2. Integracion_datos_evolucion_presupuestal.md §7):
  - Fila de años (2022–2026) con celdas combinadas; cada año = 4 columnas
    (Vigente, Comp., Obl., Pago).
  - Una fila sub-encabezado de fases que se omite.
  - La fila "Inversión" está duplicada al final; se ignora la segunda.
  - En el Excel cada fila "% PIB" precede a su concepto base; el mapeo usa una
    plantilla en el mismo orden del Excel, con verificación de alineación por texto.

Uso:
    python etl/load_evolucion_presupuestal.py \
        --file "C:\\...\\Junio\\2. EVOLUCIÓN PRESUPUESTAL\\2026-08-14Estructura_Evolución PGN y Reg-Ejec-junio-.xlsx"
    python etl/load_evolucion_presupuestal.py            # ruta por defecto (marzo)
"""
import argparse
import os
import sqlite3
import sys
import unicodedata

import openpyxl

sys.path.insert(0, os.path.dirname(__file__))
from importar_pgn import DDL   # reutiliza el mismo esquema/DDL

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DEFAULT_FILE = r"C:\ws\dnp\ws\BASES_BITACORA\2026\Marzo\2. EVOLUCIÓN PRESUPUESTAL\2026-03-31Estructura_Evolución PGN y Reg-Ejec-marzo.xlsx"
DEFAULT_DB   = os.path.join(os.path.dirname(__file__), '..', 'db', 'pgn.db')
SHEET = 'Evolucion PGN'

FASES = ['Vigente', 'Comprometido', 'Obligado', 'Pagado']  # offsets 0..3 dentro del bloque del año
MMM = 'Miles mm COP'
PCT = '% PIB'

# Plantilla en el ORDEN EN QUE APARECEN LAS FILAS DEL EXCEL (28 conceptos).
# (nombre_canonico, nivel, padre_canonico, unidad, pista_texto_excel)
# La pista es un substring normalizado esperado en la etiqueta del Excel; sirve
# para detectar desalineación estructural (no para el mapeo, que es posicional).
TEMPLATE = [
    ("PGN como % del PIB",                              1, "Total PGN",                            PCT, "pgn como"),
    ("Total PGN",                                       1, "",                                     MMM, "total pgn"),
    ("Funcionamiento como % del PIB",                   2, "Funcionamiento",                       PCT, "funcionamiento como"),
    ("Funcionamiento",                                  2, "Total PGN",                            MMM, "funcionamiento"),
    ("Gastos de Personal",                              3, "Funcionamiento",                       MMM, "gastos de personal"),
    ("Adquisición de Bienes y Servicios",               3, "Funcionamiento",                       MMM, "bienes y servicios"),
    ("Transferencias",                                  3, "Funcionamiento",                       MMM, "transferencias"),
    ("SGP",                                             4, "Transferencias",                       MMM, "sgp"),
    ("Pensiones",                                       4, "Transferencias",                       MMM, "pensiones"),
    ("IES Pública sin Pensiones",                       4, "Transferencias",                       MMM, "educaci"),
    ("Resto",                                           4, "Transferencias",                       MMM, "resto"),
    ("Gastos de Comercialización y Producción",         3, "Funcionamiento",                       MMM, "comercializaci"),
    ("Adquisición de Activos Financieros",              3, "Funcionamiento",                       MMM, "activos financieros"),
    ("Disminución de Pasivos",                          3, "Funcionamiento",                       MMM, "disminuci"),
    ("Gastos por Tributos, Multas, Sanciones e Intereses de Mora", 3, "Funcionamiento",            MMM, "tributos"),
    ("Servicio de la Deuda como % del PIB",             2, "Servicio de la Deuda",                 PCT, "deuda como"),
    ("Servicio de la Deuda",                            2, "Total PGN",                            MMM, "servicio de la deuda"),
    ("Servicio de la Deuda Pública Externa",            3, "Servicio de la Deuda",                 MMM, "externa"),
    ("Principal - Deuda Externa",                       4, "Servicio de la Deuda Pública Externa", MMM, "principal"),
    ("Intereses - Deuda Externa",                       4, "Servicio de la Deuda Pública Externa", MMM, "intereses"),
    ("Comisiones y Otros Gastos - Deuda Externa",       4, "Servicio de la Deuda Pública Externa", MMM, "comisiones"),
    ("Servicio de la Deuda Pública Interna",            3, "Servicio de la Deuda",                 MMM, "interna"),
    ("Principal - Deuda Interna",                       4, "Servicio de la Deuda Pública Interna", MMM, "principal"),
    ("Intereses - Deuda Interna",                       4, "Servicio de la Deuda Pública Interna", MMM, "intereses"),
    ("Comisiones y Otros Gastos - Deuda Interna",       4, "Servicio de la Deuda Pública Interna", MMM, "comisiones"),
    ("Fondo de Contingencias",                          3, "Servicio de la Deuda",                 MMM, "contingencia"),
    ("Inversión como % del PIB",                        2, "Inversión",                            PCT, "inversi"),
    ("Inversión",                                       2, "Total PGN",                            MMM, "inversi"),
]


# Orden canónico de los conceptos en la BD (base antes que su fila "% del PIB"),
# para reproducir exactamente el ordenamiento que usa la app (vista/drilldown).
ORDEN_CANONICO = [
    "Total PGN", "PGN como % del PIB",
    "Funcionamiento", "Funcionamiento como % del PIB",
    "Gastos de Personal", "Adquisición de Bienes y Servicios", "Transferencias",
    "SGP", "Pensiones", "IES Pública sin Pensiones", "Resto",
    "Gastos de Comercialización y Producción", "Adquisición de Activos Financieros",
    "Disminución de Pasivos", "Gastos por Tributos, Multas, Sanciones e Intereses de Mora",
    "Servicio de la Deuda", "Servicio de la Deuda como % del PIB",
    "Servicio de la Deuda Pública Externa",
    "Principal - Deuda Externa", "Intereses - Deuda Externa", "Comisiones y Otros Gastos - Deuda Externa",
    "Servicio de la Deuda Pública Interna",
    "Principal - Deuda Interna", "Intereses - Deuda Interna", "Comisiones y Otros Gastos - Deuda Interna",
    "Fondo de Contingencias",
    "Inversión", "Inversión como % del PIB",
]
ORDEN = {n: i for i, n in enumerate(ORDEN_CANONICO)}


def norm(v):
    s = unicodedata.normalize('NFKD', str(v) if v is not None else '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return ' '.join(s.lower().split())


def es_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def main():
    ap = argparse.ArgumentParser(description="ETL Sec 2 Evolución Presupuestal (pgn_*).")
    ap.add_argument('--file', default=DEFAULT_FILE)
    ap.add_argument('--db', default=DEFAULT_DB)
    args = ap.parse_args()

    wb = openpyxl.load_workbook(args.file, data_only=True, read_only=True)
    ws = wb[SHEET]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()

    # 1) Fila de años → columna inicial (Vigente) de cada año.
    #    Las celdas de año pueden venir como número o como texto ('2022').
    def como_anio(v):
        try:
            y = int(float(str(v).strip()))
            return y if 2022 <= y <= 2035 else None
        except (ValueError, TypeError):
            return None

    year_col = {}
    hdr_idx = None
    for i, r in enumerate(rows[:12]):
        for c, v in enumerate(r):
            y = como_anio(v)
            if y is not None:
                year_col[y] = c
        if year_col:
            hdr_idx = i
            break
    if not year_col:
        sys.exit("ERROR: no se encontró la fila de años (2022–2026) en 'Evolucion PGN'")
    anios = sorted(year_col)
    print(f"Años: {anios}  (columnas Vigente {[year_col[y] for y in anios]})", file=sys.stderr)

    # 2) Recolectar las 28 filas de datos (etiqueta no vacía + algún valor numérico),
    #    omitiendo el sub-encabezado (etiqueta vacía) y la fila "Inversión" duplicada.
    data_rows = []
    for r in rows[hdr_idx + 1:]:
        label = str(r[0]).strip() if r and r[0] is not None else ''
        if not label:
            continue
        tiene_valor = any(es_num(r[year_col[y]]) for y in anios
                          if year_col[y] < len(r))
        if not tiene_valor:
            continue
        data_rows.append(r)
        if len(data_rows) == len(TEMPLATE):
            break

    if len(data_rows) != len(TEMPLATE):
        sys.exit(f"ERROR: se esperaban {len(TEMPLATE)} filas de datos, se hallaron {len(data_rows)}")

    # 3) Mapear posicionalmente contra la plantilla, verificando alineación por texto
    conceptos = []   # (nombre, padre, nivel, unidad, orden)
    hechos = []      # (anio, fase, nombre_concepto, valor)
    orden_db = {}    # nombre -> orden final (según jerarquía BD: base antes que su %)
    for idx, (row, (nombre, nivel, padre, unidad, hint)) in enumerate(zip(data_rows, TEMPLATE)):
        label = norm(row[0])
        if hint not in label:
            print(f"  ADVERTENCIA: fila {idx} '{row[0]}' no coincide con la pista '{hint}' "
                  f"del concepto '{nombre}'. Verifica la estructura del Excel.", file=sys.stderr)
        for y in anios:
            base = year_col[y]
            for off, fase in enumerate(FASES):
                col = base + off
                val = row[col] if col < len(row) else None
                if es_num(val):
                    hechos.append((y, fase, nombre, float(val)))
        conceptos.append((nombre, padre, nivel, unidad))

    # Orden final: canónico de la BD (no el de aparición en el Excel).
    conceptos = [(n, p, lv, u, ORDEN[n]) for (n, p, lv, u) in conceptos]

    # 4) Cargar en BD (mismo DDL que importar_pgn.py)
    conn = sqlite3.connect(args.db)
    conn.executescript(DDL)
    with conn:
        conn.executemany(
            'INSERT INTO pgn_concepto(nombre, padre_id, nivel, unidad, orden) VALUES (?, NULL, ?, ?, ?)',
            [(n, lv, u, o) for n, p, lv, u, o in conceptos])
        nombre_id = dict(conn.execute('SELECT nombre, id FROM pgn_concepto').fetchall())
        conn.executemany('UPDATE pgn_concepto SET padre_id=? WHERE id=?',
                          [(nombre_id[p], nombre_id[n]) for n, p, lv, u, o in conceptos if p])
        conn.executemany(
            'INSERT OR REPLACE INTO pgn_ejecucion(anio, fase, concepto_id, valor) VALUES (?, ?, ?, ?)',
            [(a, f, nombre_id[n], v) for a, f, n, v in hechos])

    nc = conn.execute('SELECT COUNT(*) FROM pgn_concepto').fetchone()[0]
    ne = conn.execute('SELECT COUNT(*) FROM pgn_ejecucion').fetchone()[0]
    # Reporte de control: nivel 1 y rubros nivel 2, fase Vigente, por año
    print(f"\n[OK] pgn_concepto: {nc} · pgn_ejecucion: {ne}")
    print("\nVigente por año (mmm) — rubros principales:")
    for nombre in ('Total PGN', 'Funcionamiento', 'Servicio de la Deuda', 'Inversión'):
        vals = dict(conn.execute("""
            SELECT e.anio, e.valor FROM pgn_ejecucion e JOIN pgn_concepto c ON c.id=e.concepto_id
            WHERE c.nombre=? AND e.fase='Vigente' ORDER BY e.anio""", (nombre,)).fetchall())
        serie = '  '.join(f"{y}={vals.get(y, 0):,.0f}" for y in anios)
        print(f"  {nombre:<22} {serie}")
    conn.close()


if __name__ == '__main__':
    main()
