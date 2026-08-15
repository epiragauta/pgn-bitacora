"""
etl/bases.py — Localiza los Excel fuente de la bitácora.

Los cargadores tenían la ruta absoluta del equipo de quien los escribió
(`C:\\ws\\dnp\\ws\\BASES_BITACORA\\2026\\Marzo\\...`), lo que impedía
ejecutarlos en cualquier otra máquina. Aquí se resuelve en orden:

  1. variable de entorno BASES_BITACORA
  2. data/BASES_BITACORA/<periodo>/ dentro del repositorio
  3. las rutas históricas de Windows, por si se corre en el equipo original

Los archivos se buscan por patrón dentro de la carpeta de cada sección, no
por nombre exacto: los nombres traen fechas y sufijos ("vf", "Validada",
"Revisión Analistas") que cambian en cada corte.
"""

from __future__ import annotations

import os
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parent.parent

_CANDIDATAS = [
    RAIZ_REPO / "data" / "BASES_BITACORA",
    Path(r"D:\ws\Bases Bitácora"),
    Path(r"C:\ws\dnp\ws\BASES_BITACORA"),
]


def raiz_bases(periodo: str | None = None) -> Path:
    """Carpeta con las subcarpetas numeradas por sección (1., 2., ...).

    `periodo` es el nombre de la subcarpeta del corte ('Marzo'). Si no se
    indica y hay una sola, se usa esa.
    """
    if (env := os.environ.get("BASES_BITACORA")):
        base = Path(env)
        if not base.exists():
            raise SystemExit(f"BASES_BITACORA apunta a una ruta inexistente: {base}")
    else:
        base = next((c for c in _CANDIDATAS if c.exists()), None)
        if base is None:
            raise SystemExit(
                "No se encontró la carpeta BASES_BITACORA. Definir la variable "
                "de entorno BASES_BITACORA o colocarla en data/BASES_BITACORA/."
            )

    # Si ya apunta a la carpeta del corte, no hay que descender.
    if _tiene_secciones(base):
        return base

    if periodo:
        destino = base / periodo
        if not _tiene_secciones(destino):
            raise SystemExit(f"No hay carpetas de sección en {destino}")
        return destino

    cortes = [d for d in sorted(base.iterdir()) if d.is_dir() and _tiene_secciones(d)]
    if len(cortes) == 1:
        return cortes[0]
    if not cortes:
        # Puede haber un nivel de año: BASES_BITACORA/2026/Marzo
        for anio in sorted(base.iterdir(), reverse=True):
            if anio.is_dir():
                internos = [d for d in sorted(anio.iterdir()) if d.is_dir() and _tiene_secciones(d)]
                if len(internos) == 1:
                    return internos[0]
                if internos:
                    raise SystemExit(
                        f"Varios cortes en {anio}: {[d.name for d in internos]}. "
                        "Indicar cuál con --periodo-carpeta."
                    )
        raise SystemExit(f"No se encontraron carpetas de sección bajo {base}")
    raise SystemExit(
        f"Varios cortes disponibles en {base}: {[d.name for d in cortes]}. "
        "Indicar cuál con --periodo-carpeta."
    )


def _tiene_secciones(directorio: Path) -> bool:
    if not directorio.is_dir():
        return False
    return any(d.is_dir() and d.name[:1].isdigit() for d in directorio.iterdir())


def carpeta_seccion(numero: int, periodo: str | None = None) -> Path:
    """Carpeta de una sección por su número ('3' -> '3. REGIONALIZACIÓN')."""
    raiz = raiz_bases(periodo)
    for d in sorted(raiz.iterdir()):
        if d.is_dir() and d.name.startswith(f"{numero}."):
            return d
    raise SystemExit(f"No se encontró la carpeta de la sección {numero} en {raiz}")


def excel(numero: int, patron: str, periodo: str | None = None) -> Path:
    """Único .xlsx de una sección que coincide con el patrón glob.

    Ignora los temporales de Excel (`~$...`), que aparecen cuando alguien
    dejó el archivo abierto y no son libros válidos.
    """
    carpeta = carpeta_seccion(numero, periodo)
    encontrados = [p for p in sorted(carpeta.glob(patron)) if not p.name.startswith("~$")]

    if not encontrados:
        disponibles = [p.name for p in sorted(carpeta.glob("*.xlsx")) if not p.name.startswith("~$")]
        raise SystemExit(
            f"Ningún archivo coincide con '{patron}' en {carpeta}.\n"
            f"Disponibles: {disponibles}"
        )
    if len(encontrados) > 1:
        raise SystemExit(
            f"'{patron}' coincide con varios archivos en {carpeta}: "
            f"{[p.name for p in encontrados]}. Precisar el patrón o pasar la ruta."
        )
    return encontrados[0]


if __name__ == "__main__":
    raiz = raiz_bases()
    print(f"Raíz de bases: {raiz}\n")
    for d in sorted(raiz.iterdir()):
        if d.is_dir():
            archivos = [p.name for p in sorted(d.glob("*.xlsx")) if not p.name.startswith("~$")]
            print(f"  {d.name}")
            for a in archivos:
                print(f"      {a}")
