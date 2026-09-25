"""
tools/generar_seed_sql.py — Genera el script SQL de datos iniciales.

Vuelca el contenido de la base en `db/mssql/004_datos_iniciales.sql`, como
sentencias INSERT que sqlcmd puede ejecutar sin ninguna otra dependencia.

Para qué: el servidor de IIS del DNP no tiene —ni debería tener— Python,
pyodbc ni el ODBC Driver. Con este archivo, el despliegue solo necesita
`sqlcmd`, que viene con SQL Server. Los ETL siguen corriendo desde otra
máquina para los cargues trimestrales.

Detalles que el volcado respeta:

  · **IDENTITY_INSERT** por tabla: los `id` son referencias reales
    (`btcr_pgn_ejecucion.concepto_id`, todos los `bitacora_id`), así que
    se conservan tal cual.
  · **Orden de claves foráneas** al insertar, y el inverso al borrar.
  · **N'...' en todo texto**, porque los datos llevan tildes.
  · Lotes de 1.000 filas, que es el máximo de un INSERT ... VALUES.

Uso:
    export DNP_DPIP_CONN="..."
    python tools/generar_seed_sql.py
    python tools/generar_seed_sql.py --salida otra_ruta.sql
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "etl"))

try:
    import pyodbc
except ImportError:
    raise SystemExit("Falta pyodbc. Instalar con: pip install pyodbc")

from db import cadena_conexion  # noqa: E402

SALIDA = Path(__file__).parent.parent / "db" / "mssql" / "004_datos_iniciales.sql"

# Orden de inserción: las tablas referenciadas primero.
# btcr_dane_departamentos queda fuera: la siembra 003_seed_dane.sql.
TABLAS = [
    "btcr_metadatos_bitacora",
    "btcr_pgn_concepto",
    "btcr_pgn_ejecucion",
    "btcr_inversion_transformaciones",
    "btcr_inversion_componentes_pnd",
    "btcr_ejecucion_transformaciones",
    "btcr_regionalizacion",
    "btcr_regionalizacion_sectores",
    "btcr_ejecucion_historica",
    "btcr_apropiacion_por_sector",
    "btcr_compromisos_pct_por_sector",
    "btcr_obligaciones_pct_por_sector",
    "btcr_pagos_pct_por_sector",
    "btcr_vigencias_futuras",
    "btcr_deflactores_pib",
    "btcr_ejecucion_sectorial_entidades",
    "btcr_ejecucion_sectorial_mensual",
    "btcr_credito_portafolio",
    "btcr_credito_ejecucion_entidad",
    "btcr_credito_ejecucion_historica",
    "btcr_sgp_historico_participacion",
    "btcr_sgp_historico_componentes",
]

POR_LOTE = 1000   # máximo de filas en un INSERT ... VALUES de SQL Server


def literal(v) -> str:
    """Valor de Python a literal de T-SQL."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float, Decimal)):
        return str(v)
    if isinstance(v, datetime):
        return f"'{v:%Y-%m-%d %H:%M:%S}'"
    if isinstance(v, date):
        return f"'{v:%Y-%m-%d}'"
    # N'...' siempre: los datos llevan tildes y la collation es CS_AS
    return "N'" + str(v).replace("'", "''") + "'"


def columnas(cur, tabla: str) -> list[str]:
    return [r[0] for r in cur.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=? ORDER BY ORDINAL_POSITION
        """, tabla).fetchall()]


def tiene_identidad(cur, tabla: str) -> bool:
    return cur.execute(
        "SELECT COUNT(*) FROM sys.identity_columns WHERE object_id=OBJECT_ID(?)",
        f"dbo.{tabla}").fetchone()[0] > 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", type=Path, default=SALIDA)
    args = ap.parse_args()

    cn = pyodbc.connect(cadena_conexion())
    cur = cn.cursor()

    partes: list[str] = ["""-- ============================================================
-- 004_datos_iniciales.sql — Datos de la Bitácora
--
-- GENERADO por tools/generar_seed_sql.py — no editar a mano.
--
-- Carga el contenido completo de la Bitácora sin más dependencia que
-- sqlcmd, para no exigir Python ni el driver ODBC en el servidor de IIS.
--
-- Conserva los `id` originales con IDENTITY_INSERT: no son decorativos,
-- son las referencias que usan concepto_id y bitacora_id.
--
-- **Reemplaza los datos existentes** de estas tablas. Va todo en una
-- transacción: si algo falla, no queda a medias.
--
-- Ejecutar DESPUÉS de 001_schema.sql, 002_views.sql y 003_seed_dane.sql.
-- El nombre de la base es libre; este script no lleva USE.
-- ============================================================

SET NOCOUNT ON;
SET XACT_ABORT ON;   -- cualquier error aborta la transacción entera
GO

BEGIN TRANSACTION;
GO
"""]

    # Borrado en orden inverso al de las claves foráneas
    partes.append("-- ── Limpieza (orden inverso al de las FK) ──────────────────\n")
    for tabla in reversed(TABLAS):
        partes.append(f"DELETE FROM dbo.{tabla};\n")
    partes.append("GO\n\n")

    total = 0
    for tabla in TABLAS:
        cols = columnas(cur, tabla)
        filas = cur.execute(
            f"SELECT {', '.join('[' + c + ']' for c in cols)} FROM dbo.{tabla} ORDER BY 1"
        ).fetchall()
        total += len(filas)

        partes.append(f"-- ── {tabla} ({len(filas)} filas) " + "─" * max(0, 32 - len(tabla)) + "\n")
        if not filas:
            partes.append("-- (sin datos)\n\n")
            continue

        ident = tiene_identidad(cur, tabla)
        if ident:
            partes.append(f"SET IDENTITY_INSERT dbo.{tabla} ON;\n")

        lista = ", ".join(f"[{c}]" for c in cols)
        for i in range(0, len(filas), POR_LOTE):
            lote = filas[i:i + POR_LOTE]
            partes.append(f"INSERT INTO dbo.{tabla} ({lista}) VALUES\n")
            partes.append(",\n".join(
                "  (" + ", ".join(literal(v) for v in fila) + ")" for fila in lote))
            partes.append(";\n")

        if ident:
            partes.append(f"SET IDENTITY_INSERT dbo.{tabla} OFF;\n")
        partes.append("GO\n\n")

    partes.append("""COMMIT TRANSACTION;
GO

-- Resumen de lo cargado
SELECT CONCAT('bitácoras: ', COUNT(*)) AS resultado FROM dbo.btcr_metadatos_bitacora
UNION ALL SELECT CONCAT('entidades sectoriales: ', COUNT(*)) FROM dbo.btcr_ejecucion_sectorial_entidades
UNION ALL SELECT CONCAT('regionalización: ', COUNT(*)) FROM dbo.btcr_regionalizacion
UNION ALL SELECT CONCAT('vigencias futuras: ', COUNT(*)) FROM dbo.btcr_vigencias_futuras;
GO
""")

    args.salida.write_text("".join(partes), encoding="utf-8")
    cn.close()

    kb = args.salida.stat().st_size / 1024
    print(f"{args.salida}")
    print(f"  {len(TABLAS)} tablas · {total} filas · {kb:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
