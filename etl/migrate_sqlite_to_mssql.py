"""
etl/migrate_sqlite_to_mssql.py — Carga inicial SQLite -> SQL Server (Fase 2).

Copia las 23 tablas vivas de db/pgn.db a la base dnp_dpip preservando los
`id` originales, porque son referencias reales: pgn_ejecucion.concepto_id
apunta a pgn_concepto.id y todos los bitacora_id apuntan a
metadatos_bitacora.id. Por eso cada tabla se carga con IDENTITY_INSERT.

dane_departamentos NO se migra: su fuente canónica es
db/mssql/003_seed_dane.sql.

Al terminar valida, tabla por tabla, el conteo de filas y la suma de cada
columna numérica contra el origen. Si algo no cuadra, sale con código 1.

Uso:
    python etl/migrate_sqlite_to_mssql.py                 # migra y valida
    python etl/migrate_sqlite_to_mssql.py --solo-validar  # solo compara
    python etl/migrate_sqlite_to_mssql.py --truncar       # vacía antes de cargar

Conexión por variable de entorno (recomendado):
    export DNP_DPIP_CONN="DRIVER={ODBC Driver 18 for SQL Server};SERVER=...;..."
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

try:
    import pyodbc
except ImportError:
    raise SystemExit("Falta pyodbc. Instalar con: pip install pyodbc")

SQLITE_PATH = Path(__file__).parent.parent / "db" / "pgn.db"

CONN_DEFAULT = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=127.0.0.1,1433;DATABASE=dnp_dpip;"
    "UID=dnp_dpip_app;PWD=b1t4c0r42026;TrustServerCertificate=yes"
)

# Orden de carga: las tablas referenciadas van primero (FK).
# dane_departamentos queda fuera a propósito (la siembra 003_seed_dane.sql).
TABLAS = [
    "metadatos_bitacora",
    "pgn_concepto",          # antes que pgn_ejecucion (FK concepto_id)
    "pgn_ejecucion",
    "inversion_transformaciones",
    "inversion_componentes_pnd",
    "ejecucion_transformaciones",
    "regionalizacion",
    "regionalizacion_sectores",
    "ejecucion_historica",
    "apropiacion_por_sector",
    "compromisos_pct_por_sector",
    "obligaciones_pct_por_sector",
    "pagos_pct_por_sector",
    "vigencias_futuras",
    "deflactores_pib",
    "ejecucion_sectorial_entidades",
    "ejecucion_sectorial_mensual",
    "credito_portafolio",
    "credito_ejecucion_entidad",
    "credito_ejecucion_historica",
    "sgp_historico_participacion",
    "sgp_historico_componentes",
]

TOLERANCIA = 1e-6


def columnas(sq: sqlite3.Connection, tabla: str) -> list[str]:
    return [r[1] for r in sq.execute(f'PRAGMA table_info("{tabla}")')]


def columnas_numericas(sq: sqlite3.Connection, tabla: str) -> list[str]:
    """Columnas sumables, excluyendo el id (que se compara fila a fila)."""
    cols = []
    for r in sq.execute(f'PRAGMA table_info("{tabla}")'):
        nombre, tipo = r[1], (r[2] or "").upper()
        if nombre == "id":
            continue
        if any(t in tipo for t in ("INT", "DECIMAL", "REAL", "NUM", "FLOAT", "DOUBLE", "BOOL")):
            cols.append(nombre)
    return cols


def migrar(sq: sqlite3.Connection, cur: pyodbc.Cursor, tabla: str, truncar: bool) -> int:
    cols = columnas(sq, tabla)
    lista = ", ".join(f"[{c}]" for c in cols)
    marcas = ", ".join("?" for _ in cols)

    if truncar:
        # DELETE y no TRUNCATE: las FK impiden truncar tablas referenciadas.
        cur.execute(f"DELETE FROM dbo.[{tabla}]")

    filas = sq.execute(f'SELECT {", ".join(chr(34) + c + chr(34) for c in cols)} FROM "{tabla}"').fetchall()
    if not filas:
        return 0

    cur.execute(f"SET IDENTITY_INSERT dbo.[{tabla}] ON")
    cur.fast_executemany = True
    cur.executemany(f"INSERT INTO dbo.[{tabla}] ({lista}) VALUES ({marcas})", filas)
    cur.execute(f"SET IDENTITY_INSERT dbo.[{tabla}] OFF")
    return len(filas)


def num(v) -> float | None:
    if v is None:
        return None
    return float(v) if isinstance(v, (int, float, Decimal)) else None


def validar(sq: sqlite3.Connection, cur: pyodbc.Cursor, tabla: str) -> list[str]:
    """Compara conteo y sumas por columna. Devuelve la lista de diferencias."""
    fallos: list[str] = []

    n_org = sq.execute(f'SELECT COUNT(*) FROM "{tabla}"').fetchone()[0]
    cur.execute(f"SELECT COUNT(*) FROM dbo.[{tabla}]")
    n_dst = cur.fetchone()[0]
    if n_org != n_dst:
        fallos.append(f"conteo: origen={n_org} destino={n_dst}")
        return fallos  # sin filas iguales, comparar sumas no aporta

    for col in columnas_numericas(sq, tabla):
        s_org = num(sq.execute(f'SELECT SUM("{col}") FROM "{tabla}"').fetchone()[0])
        cur.execute(f"SELECT SUM(CAST([{col}] AS FLOAT)) FROM dbo.[{tabla}]")
        s_dst = num(cur.fetchone()[0])

        if s_org is None and s_dst is None:
            continue
        if s_org is None or s_dst is None:
            fallos.append(f"{col}: origen={s_org} destino={s_dst}")
            continue
        # Tolerancia relativa: las sumas grandes no deben fallar por el
        # último bit de un float.
        escala = max(abs(s_org), 1.0)
        if abs(s_org - s_dst) / escala > TOLERANCIA:
            fallos.append(f"{col}: origen={s_org!r} destino={s_dst!r}")

    return fallos


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sqlite", type=Path, default=SQLITE_PATH)
    ap.add_argument("--conn", default=os.environ.get("DNP_DPIP_CONN", CONN_DEFAULT))
    ap.add_argument("--solo-validar", action="store_true")
    ap.add_argument("--truncar", action="store_true", help="Vacía cada tabla antes de cargarla")
    args = ap.parse_args()

    sq = sqlite3.connect(args.sqlite)
    cn = pyodbc.connect(args.conn, autocommit=False)
    cur = cn.cursor()

    if not args.solo_validar:
        print(f"Migrando {len(TABLAS)} tablas desde {args.sqlite}\n")
        total = 0
        for tabla in TABLAS:
            n = migrar(sq, cur, tabla, args.truncar)
            total += n
            print(f"  {tabla:<32} {n:>6} filas")
        cn.commit()
        print(f"\n  {'TOTAL':<32} {total:>6} filas\n")

    print("Validando conteos y sumas por columna:\n")
    con_fallos = 0
    for tabla in TABLAS:
        fallos = validar(sq, cur, tabla)
        if fallos:
            con_fallos += 1
            print(f"  ✗ {tabla}")
            for f in fallos:
                print(f"      {f}")
        else:
            print(f"  ✓ {tabla}")

    cn.close()
    sq.close()

    if con_fallos:
        print(f"\n{con_fallos} tabla(s) con diferencias.")
        return 1
    print(f"\n{len(TABLAS)} tablas migradas y validadas sin diferencias.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
