"""
tools/compare_apis.py — Verificación de no regresión de la API.

Recorre las 322 rutas de tools/endpoints.py y compara cada respuesta
contra la línea base congelada, clasificando las diferencias por tipo.
Esa línea base se capturó de la API FastAPI antes de migrar, así que
sigue siendo la vara con la que se mide cualquier cambio del backend.

También puede comparar dos instancias en vivo (--base-a), útil para
contrastar un despliegue contra otro.

Las diferencias NO son todas iguales, y mezclarlas oculta las que
importan:

  · claves   — el conjunto de campos del JSON cambió. Es lo más grave:
               el frontend lee claves snake_case exactas y ante una que
               falte cae en silencio a sus datos embebidos, sin error.
  · valores  — mismas claves, distinto dato. Error de traducción de SQL.
  · orden    — mismas filas, distinta secuencia. Ocurre donde el original
               ordena por un campo con empates y no define desempate; ahí
               su orden es arbitrario (ver §3.9 del plan de migración).
  · estado   — códigos HTTP distintos.

Uso:
    # Contra la línea base congelada (lo habitual)
    python tools/compare_apis.py --contra-linea-base

    # Entre dos instancias en vivo
    python tools/compare_apis.py --base-a http://otra:5080 --base-b http://127.0.0.1:5080

Código de salida: 0 si no hay diferencias de claves, valores ni estado
(las de orden se reportan pero no hacen fallar).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from endpoints import build_urls, slug  # noqa: E402

BASELINE_DIR = Path(__file__).parent / "baseline"
TOLERANCIA_DECIMALES = 6


def normalizar(x):
    """Ordena claves y recorta la precisión para que la comparación sea
    numérica y no textual: 43 y 43.0 son el mismo dato."""
    if isinstance(x, dict):
        return {k: normalizar(v) for k, v in sorted(x.items())}
    if isinstance(x, list):
        return [normalizar(v) for v in x]
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        return round(float(x), TOLERANCIA_DECIMALES)
    return x


def obtener(base: str, ruta: str, timeout: float) -> tuple[int, object]:
    req = urllib.request.Request(base.rstrip("/") + ruta, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, None


def claves(dato) -> set[str]:
    """Conjunto de claves presentes, mirando dentro de las listas."""
    if isinstance(dato, dict):
        return set(dato.keys())
    if isinstance(dato, list):
        return {k for fila in dato if isinstance(fila, dict) for k in fila}
    return set()


def como_multiconjunto(dato) -> list[str] | None:
    if not isinstance(dato, list):
        return None
    return sorted(json.dumps(f, sort_keys=True, ensure_ascii=False) for f in dato)


def primera_fila_distinta(a, b) -> str | None:
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"número de filas: A={len(a)} B={len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                return (f"fila [{i}]\n        A: {json.dumps(x, ensure_ascii=False)[:220]}"
                        f"\n        B: {json.dumps(y, ensure_ascii=False)[:220]}")
        return None
    return (f"\n        A: {json.dumps(a, ensure_ascii=False)[:220]}"
            f"\n        B: {json.dumps(b, ensure_ascii=False)[:220]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-a", default="http://127.0.0.1:5080", help="API de referencia")
    ap.add_argument("--base-b", default="http://127.0.0.1:5080", help="API a verificar (.NET)")
    ap.add_argument("--contra-linea-base", action="store_true",
                    help="Usa tools/baseline/ como referencia en lugar de otra API")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--detalle", type=int, default=10, help="Cuántas diferencias detallar por tipo")
    args = ap.parse_args()

    urls = build_urls()
    referencia = "línea base congelada" if args.contra_linea_base else args.base_a
    print(f"Comparando {len(urls)} rutas\n  A (referencia): {referencia}\n  B (verificado): {args.base_b}\n")

    identicas = 0
    dif: dict[str, list] = {"claves": [], "valores": [], "orden": [], "estado": []}

    for i, url in enumerate(urls, 1):
        if args.contra_linea_base:
            archivo = BASELINE_DIR / f"{slug(url)}.json"
            if not archivo.exists():
                dif["estado"].append((url, "sin archivo en la línea base"))
                continue
            estado_a, cuerpo_a = 200, json.loads(archivo.read_text(encoding="utf-8"))
        else:
            estado_a, cuerpo_a = obtener(args.base_a, url, args.timeout)

        estado_b, cuerpo_b = obtener(args.base_b, url, args.timeout)

        if estado_a != estado_b:
            dif["estado"].append((url, f"A={estado_a} B={estado_b}"))
            continue

        a, b = normalizar(cuerpo_a), normalizar(cuerpo_b)

        if a == b:
            identicas += 1
        elif claves(a) != claves(b):
            falta = claves(a) - claves(b)
            sobra = claves(b) - claves(a)
            detalle = []
            if falta:
                detalle.append(f"faltan en B: {sorted(falta)}")
            if sobra:
                detalle.append(f"sobran en B: {sorted(sobra)}")
            dif["claves"].append((url, "; ".join(detalle)))
        elif (ma := como_multiconjunto(a)) is not None and ma == como_multiconjunto(b):
            dif["orden"].append((url, "mismas filas, distinta secuencia"))
        else:
            dif["valores"].append((url, primera_fila_distinta(a, b)))

        if i % 50 == 0 or i == len(urls):
            print(f"  {i}/{len(urls)}", flush=True)

    print(f"\n{'='*64}")
    print(f"  idénticas            {identicas:>4} / {len(urls)}")
    print(f"  dif. de claves       {len(dif['claves']):>4}   <- rompe el frontend")
    print(f"  dif. de valores      {len(dif['valores']):>4}   <- error de traducción")
    print(f"  dif. de estado HTTP  {len(dif['estado']):>4}")
    print(f"  dif. solo de orden   {len(dif['orden']):>4}   <- empates sin desempate en el original")
    print(f"{'='*64}")

    for tipo in ("claves", "valores", "estado", "orden"):
        if not dif[tipo]:
            continue
        print(f"\n[{tipo}]")
        for url, detalle in dif[tipo][: args.detalle]:
            print(f"  {url}")
            if detalle:
                print(f"        {detalle}")
        if len(dif[tipo]) > args.detalle:
            print(f"  ... y {len(dif[tipo]) - args.detalle} más")

    bloqueantes = len(dif["claves"]) + len(dif["valores"]) + len(dif["estado"])
    if bloqueantes:
        print(f"\nFALLO: {bloqueantes} diferencia(s) bloqueante(s).")
        return 1

    print("\nParidad verificada: sin diferencias de claves, valores ni estado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
