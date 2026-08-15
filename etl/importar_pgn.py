#!/usr/bin/env python3
"""
importar_pgn.py — Carga el CSV de evolución presupuestal PGN (sección 2).

Uso:
    python importar_pgn.py [ruta_csv]

Ejemplo:
    python importar_pgn.py data/evolucion_presupuestal.csv

Vacía y recarga pgn_concepto y pgn_ejecucion. El esquema lo gobierna
db/mssql/001_schema.sql: el script ya no crea ni borra tablas, porque
hacerlo rompería la vista pgn_vista_crosstab y las claves foráneas.

Estas dos tablas no llevan bitacora_id: son la serie del PGN completa,
compartida por todas las bitácoras.
"""

import sys
import csv
import time
from pathlib import Path

import db as dbmod


# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_valor(raw: str) -> float | None:
    """
    Convierte el formato numérico español al float de Python.
    '350.097,955' → 350097.955   |   '0,238' → 0.238   |   '' → None
    """
    raw = raw.strip() if raw else ''
    if not raw:
        return None
    # Quitar separadores de miles (punto) y convertir decimal (coma→punto)
    return float(raw.replace('.', '').replace(',', '.'))


def leer_csv(csv_path: Path) -> list[dict]:
    """Lee el CSV manejando UTF-8 con o sin BOM y separador punto y coma."""
    with open(csv_path, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, delimiter=';')
        return [row for row in reader]


def extraer_conceptos(rows: list[dict]) -> list[tuple]:
    """
    Retorna lista ordenada de conceptos únicos en orden de primera aparición:
    (nombre, padre_nombre, nivel, unidad, orden)
    """
    seen: dict[str, int] = {}
    conceptos: list[tuple] = []
    for row in rows:
        nombre = row['Concepto'].strip()
        if nombre not in seen:
            seen[nombre] = len(conceptos)
            padre_nombre = row.get('Concepto_Padre', '').strip()
            conceptos.append((
                nombre,
                padre_nombre,           # cadena vacía si es raíz
                int(row['Nivel']),
                row['Unidad'].strip(),
                len(conceptos),         # orden 0-based
            ))
    return conceptos

# ── Main ─────────────────────────────────────────────────────────────────────

CSV_DEFECTO = Path(__file__).resolve().parent.parent / 'data' / 'evolucion_presupuestal.csv'


def main() -> None:
    if len(sys.argv) > 2:
        print(f'Uso: python {sys.argv[0]} [ruta_csv]')
        sys.exit(1)

    # La base ya no es un argumento: se toma de DNP_DPIP_CONN (ver etl/db.py).
    csv_path = Path(sys.argv[1]) if len(sys.argv) == 2 else CSV_DEFECTO

    if not csv_path.exists():
        print(f'Error: archivo CSV no encontrado: {csv_path}')
        sys.exit(1)

    t0 = time.perf_counter()

    # 1. Leer CSV
    rows = leer_csv(csv_path)
    print(f'Filas leídas del CSV: {len(rows)}')

    # 2. Extraer jerarquía de conceptos
    conceptos = extraer_conceptos(rows)
    print(f'Conceptos únicos: {len(conceptos)}')

    # 3. Conectar y vaciar (en orden de FK: primero los hechos)
    conn = dbmod.conectar()
    conn.execute('DELETE FROM dbo.pgn_ejecucion')
    conn.execute('DELETE FROM dbo.pgn_concepto')
    conn.commit()

    advertencias = 0

    with conn:
        # Paso A: insertar todos los conceptos sin padre_id (se resuelve después)
        conn.executemany(
            'INSERT INTO dbo.pgn_concepto(nombre, padre_id, nivel, unidad, orden) '
            'VALUES (?, NULL, ?, ?, ?)',
            [(nombre, nivel, unidad, orden)
             for nombre, _, nivel, unidad, orden in conceptos]
        )

        # Paso B: resolver padre_id por nombre y actualizar
        nombre_a_id: dict[str, int] = {
            r[0]: r[1]
            for r in conn.execute('SELECT nombre, id FROM dbo.pgn_concepto').fetchall()
        }
        actualizaciones: list[tuple[int, int]] = []
        for nombre, padre_nombre, *_ in conceptos:
            if not padre_nombre:
                continue
            padre_id = nombre_a_id.get(padre_nombre)
            if padre_id is None:
                print(f'  Advertencia: padre "{padre_nombre}" no encontrado '
                      f'para "{nombre}"')
                advertencias += 1
            else:
                actualizaciones.append((padre_id, nombre_a_id[nombre]))

        conn.executemany(
            'UPDATE dbo.pgn_concepto SET padre_id=? WHERE id=?',
            actualizaciones
        )

        # Paso C: insertar hechos
        hechos: list[tuple] = []
        for row in rows:
            nombre     = row['Concepto'].strip()
            concepto_id = nombre_a_id[nombre]
            valor      = parse_valor(row['Valor'])
            if valor is None:
                print(f'  Advertencia: valor nulo en fila {row}')
                advertencias += 1
                continue
            hechos.append((
                int(row['Año']),
                row['Fase'].strip(),
                concepto_id,
                valor,
            ))

        conn.upsert(
            'pgn_ejecucion',
            ['anio', 'fase', 'concepto_id', 'valor'],
            hechos, claves=['anio', 'fase', 'concepto_id'],
        )

    # 4. Verificar y reportar
    n_conceptos = conn.execute('SELECT COUNT(*) FROM dbo.pgn_concepto').fetchone()[0]
    n_hechos    = conn.execute('SELECT COUNT(*) FROM dbo.pgn_ejecucion').fetchone()[0]
    conn.close()

    t1 = time.perf_counter()

    print()
    print('-' * 40)
    print(f'Importacion completada en {t1 - t0:.3f}s')
    print(f'  pgn_concepto  : {n_conceptos:>4} registros')
    print(f'  pgn_ejecucion : {n_hechos:>4} registros')
    if advertencias:
        print(f'  Advertencias  → {advertencias}')
    print(f'  Origen CSV    : {csv_path.resolve()}')


if __name__ == '__main__':
    main()
