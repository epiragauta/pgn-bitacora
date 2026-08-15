"""
tools/compare_bd.py — Compara dos bases dnp_dpip tabla por tabla.

Sirve para validar el ETL: se cargan los Excel en una base de pruebas y se
contrasta contra la base buena (la que salió de la migración desde SQLite).
Si el ETL adaptado a SQL Server reproduce los mismos datos, la adaptación
no cambió resultados.

Compara, por bitácora, el número de filas y la suma de cada columna
numérica. No compara `id`: las identidades se regeneran en cada carga y
son un detalle de almacenamiento, no un dato.

Uso:
    python tools/compare_bd.py --a dnp_dpip --b dnp_dpip_pruebas
    python tools/compare_bd.py --a dnp_dpip --b dnp_dpip_pruebas --periodo 2026-I
"""

from __future__ import annotations

import argparse
import os
import sys

try:
    import pyodbc
except ImportError:
    raise SystemExit("Falta pyodbc. Instalar con: pip install pyodbc")

TOLERANCIA = 1e-6

PLANTILLA = (
    "DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={servidor};DATABASE={base};"
    "UID={usuario};PWD={clave};TrustServerCertificate=yes"
)


def conectar(base: str, args) -> pyodbc.Connection:
    return pyodbc.connect(PLANTILLA.format(
        servidor=args.servidor, base=base, usuario=args.usuario, clave=args.clave))


def tablas_con_bitacora(cur) -> list[str]:
    return [r[0] for r in cur.execute("""
        SELECT t.TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES t
        JOIN INFORMATION_SCHEMA.COLUMNS c
          ON c.TABLE_NAME = t.TABLE_NAME AND c.COLUMN_NAME = 'bitacora_id'
        WHERE t.TABLE_TYPE = 'BASE TABLE'
        ORDER BY t.TABLE_NAME
    """).fetchall()]


def columnas_numericas(cur, tabla: str) -> list[str]:
    # Se excluyen id y bitacora_id: son identificadores, no datos. El id se
    # regenera en cada carga y el bitacora_id difiere legítimamente entre
    # bases, así que sumarlos solo produce ruido.
    return [r[0] for r in cur.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = ? AND COLUMN_NAME NOT IN ('id', 'bitacora_id', 'concepto_id', 'padre_id')
          AND DATA_TYPE IN ('int','bigint','smallint','decimal','numeric','float','real','bit')
        ORDER BY ORDINAL_POSITION
    """, tabla).fetchall()]


def resolver_bitacora(cur, periodo: str | None) -> int | None:
    if periodo:
        fila = cur.execute(
            "SELECT id FROM dbo.metadatos_bitacora WHERE periodo = ?", periodo).fetchone()
        if not fila:
            raise SystemExit(f"No existe la bitácora de periodo '{periodo}'")
        return fila[0]
    fila = cur.execute(
        "SELECT TOP 1 id FROM dbo.metadatos_bitacora ORDER BY corte_fecha DESC, id DESC"
    ).fetchone()
    return fila[0] if fila else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="dnp_dpip", help="Base de referencia")
    ap.add_argument("--b", default="dnp_dpip_pruebas", help="Base a verificar")
    ap.add_argument("--periodo", default=None, help="Periodo a comparar (ej. 2026-I)")
    ap.add_argument("--servidor", default=os.environ.get("DNP_DPIP_SERVER", "127.0.0.1,1433"))
    ap.add_argument("--usuario", default=os.environ.get("DNP_DPIP_USER", "dnp_dpip_app"))
    ap.add_argument("--clave", default=os.environ.get("DNP_DPIP_PASSWORD", ""))
    args = ap.parse_args()

    if not args.clave:
        raise SystemExit("Definir la contraseña con --clave o DNP_DPIP_PASSWORD.")

    ca, cb = conectar(args.a, args).cursor(), conectar(args.b, args).cursor()

    bid_a = resolver_bitacora(ca, args.periodo)
    bid_b = resolver_bitacora(cb, args.periodo)
    print(f"Comparando la bitácora {args.periodo or '(más reciente)'}:")
    print(f"  A {args.a:<22} id={bid_a}")
    print(f"  B {args.b:<22} id={bid_b}\n")

    tablas = tablas_con_bitacora(ca)
    # pgn_* no llevan bitacora_id: son la serie completa del PGN.
    tablas += ["pgn_concepto", "pgn_ejecucion"]

    iguales, distintas = 0, []
    print(f"{'tabla':<34}{'A':>8}{'B':>8}")
    for tabla in tablas:
        tiene_bid = tabla not in ("pgn_concepto", "pgn_ejecucion")
        filtro = " WHERE bitacora_id = ?" if tiene_bid else ""

        def contar(cur, bid):
            sql = f"SELECT COUNT(*) FROM dbo.[{tabla}]{filtro}"
            return (cur.execute(sql, bid) if tiene_bid else cur.execute(sql)).fetchone()[0]

        na, nb = contar(ca, bid_a), contar(cb, bid_b)
        problemas = [] if na == nb else [f"filas: A={na} B={nb}"]

        if na == nb:
            for col in columnas_numericas(ca, tabla):
                sql = f"SELECT SUM(CAST([{col}] AS FLOAT)) FROM dbo.[{tabla}]{filtro}"
                sa = (ca.execute(sql, bid_a) if tiene_bid else ca.execute(sql)).fetchone()[0]
                sb = (cb.execute(sql, bid_b) if tiene_bid else cb.execute(sql)).fetchone()[0]
                if sa is None and sb is None:
                    continue
                if sa is None or sb is None:
                    problemas.append(f"{col}: A={sa} B={sb}")
                elif abs(sa - sb) / max(abs(sa), 1.0) > TOLERANCIA:
                    problemas.append(f"{col}: A={sa!r} B={sb!r}")

        marca = "igual" if not problemas else "DIFIERE"
        print(f"{tabla:<34}{na:>8}{nb:>8}  {marca}")
        for p in problemas:
            print(f"      {p}")
        if problemas:
            distintas.append(tabla)
        else:
            iguales += 1

    print(f"\n{iguales}/{len(tablas)} tablas idénticas")
    if distintas:
        print(f"Con diferencias: {', '.join(distintas)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
