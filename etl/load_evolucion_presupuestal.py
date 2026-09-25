#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETL Sección 2 — Evolución Presupuestal PGN desde Excel (SQL Server, db.py).

Lee la hoja `Evolucion PGN` del archivo de estructura de evolución y carga
`pgn_concepto` / `pgn_ejecucion` (reemplaza la carga por CSV de importar_pgn.py).
Mismo esquema/tablas que consume la API .NET; el esquema vive en db/mssql/.

La hoja es un crosstab: 28 conceptos (jerarquía de 4 niveles, incl. 4 filas
"% del PIB") × 5 años × 4 fases. Unidades ya en mmm. En el Excel cada fila
"% PIB" precede a su concepto base; el mapeo usa una plantilla en el orden del
Excel con verificación por texto, y el `orden` final sigue el canónico de la BD.
"""
import sys
import unicodedata

import openpyxl

import bases
import db as dbmod

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SHEET = "Evolucion PGN"
FASES = ["Vigente", "Comprometido", "Obligado", "Pagado"]
MMM = "Miles mm COP"
PCT = "% PIB"

# Plantilla en el ORDEN EN QUE APARECEN LAS FILAS DEL EXCEL (28 conceptos).
# (nombre_canonico, nivel, padre_canonico, unidad, pista_texto_excel)
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

# Orden canónico de la BD (base antes que su fila "% del PIB").
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
    s = unicodedata.normalize("NFKD", str(v) if v is not None else "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def es_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def como_anio(v):
    try:
        y = int(float(str(v).strip()))
        return y if 2022 <= y <= 2035 else None
    except (ValueError, TypeError):
        return None


def main():
    file = str(bases.excel(2, "*Estructura*.xlsx"))
    print(f"Archivo Sec 2: {file}", file=sys.stderr)
    wb = openpyxl.load_workbook(file, data_only=True, read_only=True)
    ws = wb[SHEET]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()

    # 1) Fila de años → columna inicial (Vigente) de cada año
    year_col, hdr_idx = {}, None
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
    print(f"Años: {anios} (col Vigente {[year_col[y] for y in anios]})", file=sys.stderr)

    # 2) Recolectar 28 filas de datos (etiqueta no vacía + algún valor numérico)
    data_rows = []
    for r in rows[hdr_idx + 1:]:
        label = str(r[0]).strip() if r and r[0] is not None else ""
        if not label:
            continue
        if not any(es_num(r[year_col[y]]) for y in anios if year_col[y] < len(r)):
            continue
        data_rows.append(r)
        if len(data_rows) == len(TEMPLATE):
            break
    if len(data_rows) != len(TEMPLATE):
        sys.exit(f"ERROR: se esperaban {len(TEMPLATE)} filas de datos, se hallaron {len(data_rows)}")

    # 3) Mapear posicionalmente contra la plantilla (verificando alineación por texto)
    conceptos, hechos = [], []
    for idx, (row, (nombre, nivel, padre, unidad, hint)) in enumerate(zip(data_rows, TEMPLATE)):
        if hint not in norm(row[0]):
            print(f"  ADVERTENCIA: fila {idx} '{row[0]}' no casa con pista '{hint}' de '{nombre}'.",
                  file=sys.stderr)
        for y in anios:
            base = year_col[y]
            for off, fase in enumerate(FASES):
                col = base + off
                val = row[col] if col < len(row) else None
                if es_num(val):
                    hechos.append((y, fase, nombre, float(val)))
        conceptos.append((nombre, padre, nivel, unidad, ORDEN[nombre]))

    # 4) Cargar en BD (SQL Server): vaciar (orden FK) → conceptos → padres → hechos
    conn = dbmod.conectar()
    conn.execute("DELETE FROM dbo.pgn_ejecucion")
    conn.execute("DELETE FROM dbo.pgn_concepto")
    conn.commit()
    with conn:
        conn.executemany(
            "INSERT INTO dbo.pgn_concepto(nombre, padre_id, nivel, unidad, orden) VALUES (?, NULL, ?, ?, ?)",
            [(n, lv, u, o) for n, p, lv, u, o in conceptos])
        nombre_id = {r[0]: r[1] for r in conn.execute("SELECT nombre, id FROM dbo.pgn_concepto").fetchall()}
        conn.executemany("UPDATE dbo.pgn_concepto SET padre_id=? WHERE id=?",
                          [(nombre_id[p], nombre_id[n]) for n, p, lv, u, o in conceptos if p])
        conn.upsert("pgn_ejecucion", ["anio", "fase", "concepto_id", "valor"],
                    [(a, f, nombre_id[n], v) for a, f, n, v in hechos],
                    claves=["anio", "fase", "concepto_id"])

    nc = conn.execute("SELECT COUNT(*) FROM dbo.pgn_concepto").fetchone()[0]
    ne = conn.execute("SELECT COUNT(*) FROM dbo.pgn_ejecucion").fetchone()[0]
    print(f"\n[OK] pgn_concepto: {nc} · pgn_ejecucion: {ne}")
    print("\nVigente por año (mmm) — rubros principales:")
    for nombre in ("Total PGN", "Funcionamiento", "Servicio de la Deuda", "Inversión"):
        vals = {r[0]: r[1] for r in conn.execute(
            "SELECT e.anio, e.valor FROM dbo.pgn_ejecucion e JOIN dbo.pgn_concepto c ON c.id=e.concepto_id "
            "WHERE c.nombre=? AND e.fase='Vigente' ORDER BY e.anio", (nombre,)).fetchall()}
        serie = "  ".join(f"{y}={vals.get(y, 0):,.0f}" for y in anios)
        print(f"  {nombre:<22} {serie}")
    conn.close()


if __name__ == "__main__":
    main()
