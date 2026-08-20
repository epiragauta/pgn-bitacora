"""
etl/db.py — Capa de conexión común de los ETL (SQL Server).

Los cargadores estaban escritos contra sqlite3 y usaban su API de
conveniencia: `conn.execute(...)`, `conn.executemany(...)`, `cur.lastrowid`.
pyodbc no ofrece nada de eso a nivel de conexión, así que aquí va un
envoltorio delgado con la misma forma. El objetivo es que cada cargador
cambie solo su línea de conexión y sus sentencias no portables, no toda su
lógica de lectura de Excel, que es donde vive el conocimiento del negocio.

Diferencias con SQLite que este módulo resuelve:

  · `INSERT OR REPLACE`  -> no existe en SQL Server. `upsert()` lo emula
    borrando por clave natural e insertando, dentro de la misma
    transacción.
  · `cur.lastrowid`      -> `SCOPE_IDENTITY()` sobre la misma sesión.
  · `PRAGMA foreign_keys`-> innecesario: las FK están siempre activas.
  · `CREATE TABLE`       -> el esquema es responsabilidad de db/mssql/.
    Los cargadores ya no crean ni borran tablas: vacían por bitácora.

Conexión: **obligatoriamente** por la variable de entorno DNP_DPIP_CONN.

    export DNP_DPIP_CONN="DRIVER={ODBC Driver 18 for SQL Server};\
SERVER=servidor,1433;DATABASE=la_base;UID=usuario;PWD=clave;TrustServerCertificate=yes"

No hay valor por defecto a propósito. Antes existía uno con credenciales
reales incrustadas, que terminaron versionadas en el repositorio; y de
paso fijaba el nombre de la base, cuando el esquema está pensado para
instalarse en cualquiera (todas las tablas llevan el prefijo btcr_).
"""

from __future__ import annotations

import os
import sys
from typing import Any, Iterable, Sequence

try:
    import pyodbc
except ImportError:  # pragma: no cover
    raise SystemExit(
        "Falta pyodbc. Instalar con: pip install pyodbc\n"
        "Requiere el paquete del sistema 'ODBC Driver 18 for SQL Server'."
    )

VARIABLE = "DNP_DPIP_CONN"

AYUDA = f"""Falta la variable de entorno {VARIABLE}.

    export {VARIABLE}="DRIVER={{ODBC Driver 18 for SQL Server}};\\
SERVER=servidor,1433;DATABASE=la_base;UID=usuario;PWD=clave;TrustServerCertificate=yes"

El nombre de la base es libre: el esquema no lo presupone y todas las
tablas llevan el prefijo btcr_ para convivir con otros sistemas."""


def cadena_conexion() -> str:
    cadena = os.environ.get(VARIABLE)
    if not cadena:
        raise SystemExit(AYUDA)
    return cadena


class Cursor:
    """Cursor de pyodbc con la superficie que usan los ETL."""

    def __init__(self, cursor: "pyodbc.Cursor"):
        self._cursor = cursor

    @property
    def lastrowid(self):
        raise NotImplementedError(
            "SQL Server no expone lastrowid. Usar conn.insertar_devolviendo_id(sql, params), "
            "que ejecuta el INSERT y SCOPE_IDENTITY() en el mismo lote."
        )

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def __iter__(self):
        return iter(self._cursor)


class Conexion:
    """Envoltorio con la forma de sqlite3.Connection que usan los ETL."""

    def __init__(self, cadena: str | None = None):
        self._conn = pyodbc.connect(cadena or cadena_conexion(), autocommit=False)

    def execute(self, sql: str, params: Sequence[Any] = ()) -> Cursor:
        cur = self._conn.cursor()
        cur.execute(sql, tuple(params))
        return Cursor(cur)

    def executemany(self, sql: str, filas: Iterable[Sequence[Any]]) -> Cursor:
        filas = [tuple(f) for f in filas]
        cur = self._conn.cursor()
        if filas:
            cur.fast_executemany = True
            cur.executemany(sql, filas)
        return Cursor(cur)

    def insertar_devolviendo_id(self, sql: str, params: Sequence[Any] = ()) -> int:
        """INSERT que devuelve el id generado (sustituye a `cur.lastrowid`).

        SCOPE_IDENTITY() está acotado al ámbito del lote, no a la sesión:
        consultado en un `execute` posterior devuelve NULL. Por eso las dos
        sentencias van juntas. `SET NOCOUNT ON` evita que el recuento del
        INSERT se interponga como primer conjunto de resultados.
        """
        cur = self._conn.cursor()
        cur.execute(f"SET NOCOUNT ON; {sql}; SELECT CAST(SCOPE_IDENTITY() AS INT);", tuple(params))
        fila = cur.fetchone()
        if fila is None or fila[0] is None:
            raise RuntimeError(f"El INSERT no devolvió identidad: {sql[:80]}")
        return int(fila[0])

    def upsert(self, tabla: str, columnas: Sequence[str],
               filas: Iterable[Sequence[Any]], claves: Sequence[str]) -> int:
        """Equivalente a INSERT OR REPLACE.

        Borra por clave natural y vuelve a insertar. Se prefiere a MERGE
        por ser más simple de leer y auditar; el volumen de estas cargas
        (miles de filas, no millones) no justifica nada más elaborado.

        SQLite aplicaba INSERT OR REPLACE fila a fila, así que dos filas
        del mismo lote con la misma clave no chocaban: la última pisaba a
        la anterior. Aquí se inserta en bloque, de modo que hay que
        deduplicar antes o la restricción UNIQUE aborta la carga. Se
        conserva la última, que es lo que hacía el original, pero se avisa
        por stderr: un duplicado suele significar que la hoja de origen
        trae dos filas para la misma clave y una se está descartando.
        """
        filas = [tuple(f) for f in filas]
        if not filas:
            return 0

        posiciones = [list(columnas).index(k) for k in claves]

        unicas: dict[tuple, tuple] = {}
        for fila in filas:
            unicas[tuple(fila[i] for i in posiciones)] = fila
        if len(unicas) != len(filas):
            print(
                f"  [!] {tabla}: {len(filas) - len(unicas)} fila(s) con clave repetida "
                f"en el origen; se conserva la última de cada clave.",
                file=sys.stderr,
            )
            filas = list(unicas.values())
        condicion = " AND ".join(f"[{k}] = ?" for k in claves)
        self.executemany(
            f"DELETE FROM dbo.[{tabla}] WHERE {condicion}",
            [tuple(f[i] for i in posiciones) for f in filas],
        )

        lista = ", ".join(f"[{c}]" for c in columnas)
        marcas = ", ".join("?" for _ in columnas)
        self.executemany(f"INSERT INTO dbo.[{tabla}] ({lista}) VALUES ({marcas})", filas)
        return len(filas)

    def vaciar_bitacora(self, tablas: Iterable[str], bitacora_id: int) -> None:
        """Borra los datos de una bitácora en las tablas indicadas.

        Reemplaza al DROP TABLE + CREATE TABLE que hacían varios
        cargadores: ahora el esquema lo gobierna db/mssql/ y borrar la
        tabla rompería las claves foráneas.
        """
        for tabla in tablas:
            self.execute(f"DELETE FROM dbo.[{tabla}] WHERE bitacora_id = ?", (bitacora_id,))

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Conexion":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # Misma semántica que sqlite3: el bloque `with` confirma o revierte
        # la transacción, pero NO cierra la conexión. Los cargadores siguen
        # consultando después del bloque para imprimir su verificación.
        if exc_type is None:
            self.commit()
        else:
            self.rollback()


def conectar(cadena: str | None = None) -> Conexion:
    return Conexion(cadena)


def bitacora_reciente(conn: Conexion) -> int:
    """id de la bitácora más reciente, que es contra la que cargan los ETL."""
    fila = conn.execute(
        "SELECT TOP 1 id FROM dbo.btcr_metadatos_bitacora ORDER BY corte_fecha DESC, id DESC"
    ).fetchone()
    if not fila:
        raise SystemExit("No hay ninguna bitácora en metadatos_bitacora.")
    return int(fila[0])
