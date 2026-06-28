#!/usr/bin/env python3
"""
importar_pgn.py — Carga el CSV de evolución presupuestal PGN en SQLite.

Uso:
    python importar_pgn.py <ruta_csv> <ruta_db>

Ejemplo:
    python importar_pgn.py data/evolucion_presupuestal.csv db/pgn.db

El script ejecuta DROP + CREATE de las tablas pgn_concepto y pgn_ejecucion.
El resto del schema (otras secciones de la app) no se modifica.
"""

import sys
import csv
import sqlite3
import time
from pathlib import Path

# ── DDL ──────────────────────────────────────────────────────────────────────

DDL = """
PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS pgn_ejecucion;
DROP TABLE IF EXISTS pgn_concepto;
DROP VIEW  IF EXISTS pgn_vista_crosstab;

CREATE TABLE pgn_concepto (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre   TEXT    NOT NULL UNIQUE,
    padre_id INTEGER REFERENCES pgn_concepto(id) ON DELETE SET NULL,
    nivel    INTEGER NOT NULL CHECK(nivel BETWEEN 1 AND 4),
    unidad   TEXT    NOT NULL CHECK(unidad IN ('Miles mm COP','% PIB')),
    orden    INTEGER NOT NULL
);

CREATE TABLE pgn_ejecucion (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    anio        INTEGER NOT NULL CHECK(anio BETWEEN 2022 AND 2030),
    fase        TEXT    NOT NULL CHECK(fase IN ('Vigente','Comprometido','Obligado','Pagado')),
    concepto_id INTEGER NOT NULL REFERENCES pgn_concepto(id),
    valor       REAL    NOT NULL,
    UNIQUE(anio, fase, concepto_id)
);

CREATE INDEX idx_pgn_ej_anio_fase ON pgn_ejecucion(anio, fase);
CREATE INDEX idx_pgn_ej_concepto  ON pgn_ejecucion(concepto_id);
CREATE INDEX idx_pgn_co_padre     ON pgn_concepto(padre_id);

CREATE VIEW pgn_vista_crosstab AS
SELECT
    c.id, c.nombre, c.nivel, c.unidad, c.orden,
    MAX(CASE WHEN e.anio=2022 AND e.fase='Vigente'       THEN e.valor END) AS vigente_2022,
    MAX(CASE WHEN e.anio=2022 AND e.fase='Comprometido'  THEN e.valor END) AS comprometido_2022,
    MAX(CASE WHEN e.anio=2022 AND e.fase='Obligado'      THEN e.valor END) AS obligado_2022,
    MAX(CASE WHEN e.anio=2022 AND e.fase='Pagado'        THEN e.valor END) AS pagado_2022,
    MAX(CASE WHEN e.anio=2023 AND e.fase='Vigente'       THEN e.valor END) AS vigente_2023,
    MAX(CASE WHEN e.anio=2023 AND e.fase='Comprometido'  THEN e.valor END) AS comprometido_2023,
    MAX(CASE WHEN e.anio=2023 AND e.fase='Obligado'      THEN e.valor END) AS obligado_2023,
    MAX(CASE WHEN e.anio=2023 AND e.fase='Pagado'        THEN e.valor END) AS pagado_2023,
    MAX(CASE WHEN e.anio=2024 AND e.fase='Vigente'       THEN e.valor END) AS vigente_2024,
    MAX(CASE WHEN e.anio=2024 AND e.fase='Comprometido'  THEN e.valor END) AS comprometido_2024,
    MAX(CASE WHEN e.anio=2024 AND e.fase='Obligado'      THEN e.valor END) AS obligado_2024,
    MAX(CASE WHEN e.anio=2024 AND e.fase='Pagado'        THEN e.valor END) AS pagado_2024,
    MAX(CASE WHEN e.anio=2025 AND e.fase='Vigente'       THEN e.valor END) AS vigente_2025,
    MAX(CASE WHEN e.anio=2025 AND e.fase='Comprometido'  THEN e.valor END) AS comprometido_2025,
    MAX(CASE WHEN e.anio=2025 AND e.fase='Obligado'      THEN e.valor END) AS obligado_2025,
    MAX(CASE WHEN e.anio=2025 AND e.fase='Pagado'        THEN e.valor END) AS pagado_2025,
    MAX(CASE WHEN e.anio=2026 AND e.fase='Vigente'       THEN e.valor END) AS vigente_2026,
    MAX(CASE WHEN e.anio=2026 AND e.fase='Comprometido'  THEN e.valor END) AS comprometido_2026,
    MAX(CASE WHEN e.anio=2026 AND e.fase='Obligado'      THEN e.valor END) AS obligado_2026,
    MAX(CASE WHEN e.anio=2026 AND e.fase='Pagado'        THEN e.valor END) AS pagado_2026
FROM pgn_concepto c
LEFT JOIN pgn_ejecucion e ON e.concepto_id = c.id
GROUP BY c.id
ORDER BY c.orden;

PRAGMA foreign_keys = ON;
"""

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

def main() -> None:
    if len(sys.argv) != 3:
        print(f'Uso: python {sys.argv[0]} <ruta_csv> <ruta_db>')
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    db_path  = Path(sys.argv[2])

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

    # 3. Conectar a la BD y ejecutar DDL
    conn = sqlite3.connect(db_path)
    conn.executescript(DDL)

    advertencias = 0

    with conn:
        # Paso A: insertar todos los conceptos sin padre_id (se resuelve después)
        conn.executemany(
            'INSERT INTO pgn_concepto(nombre, padre_id, nivel, unidad, orden) '
            'VALUES (?, NULL, ?, ?, ?)',
            [(nombre, nivel, unidad, orden)
             for nombre, _, nivel, unidad, orden in conceptos]
        )

        # Paso B: resolver padre_id por nombre y actualizar
        nombre_a_id: dict[str, int] = dict(
            conn.execute('SELECT nombre, id FROM pgn_concepto').fetchall()
        )
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
            'UPDATE pgn_concepto SET padre_id=? WHERE id=?',
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

        conn.executemany(
            'INSERT OR REPLACE INTO pgn_ejecucion(anio, fase, concepto_id, valor) '
            'VALUES (?, ?, ?, ?)',
            hechos
        )

    # 4. Verificar y reportar
    n_conceptos = conn.execute('SELECT COUNT(*) FROM pgn_concepto').fetchone()[0]
    n_hechos    = conn.execute('SELECT COUNT(*) FROM pgn_ejecucion').fetchone()[0]
    conn.close()

    t1 = time.perf_counter()

    print()
    print('-' * 40)
    print(f'Importacion completada en {t1 - t0:.3f}s')
    print(f'  pgn_concepto  : {n_conceptos:>4} registros')
    print(f'  pgn_ejecucion : {n_hechos:>4} registros')
    if advertencias:
        print(f'  Advertencias  → {advertencias}')
    print(f'  Base de datos : {db_path.resolve()}')


if __name__ == '__main__':
    main()
