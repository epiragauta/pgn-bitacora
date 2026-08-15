"""
tools/capture_baseline.py — Congela las respuestas de referencia.

Guarda en tools/baseline/ la respuesta JSON de cada una de las rutas que
enumera tools/endpoints.py. Ese conjunto es contra el que compara
tools/compare_apis.py: si un cambio en el backend altera un valor, la
comparación lo delata.

La referencia actual se capturó de la API FastAPI antes de migrar, y por
eso sirve de red de seguridad. **Regenerarla solo cuando los datos
cambien a propósito** (una bitácora nueva), nunca para "arreglar" una
diferencia: eso borraría justamente la evidencia que se busca.

Uso:
    python tools/capture_baseline.py [--base http://127.0.0.1:5080]
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

OUT_DIR = Path(__file__).parent / "baseline"


def fetch(base: str, path: str, timeout: float) -> tuple[int, object]:
    req = urllib.request.Request(base.rstrip("/") + path, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # Un 404 puede ser la respuesta correcta y también debe congelarse.
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5080")
    ap.add_argument("--timeout", type=float, default=30.0)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.json"):
        old.unlink()

    urls = build_urls()
    index: list[dict] = []
    errores: list[str] = []
    vacios: list[str] = []

    for i, url in enumerate(urls, 1):
        status, body = fetch(args.base, url, args.timeout)
        nombre = f"{slug(url)}.json"
        (OUT_DIR / nombre).write_text(
            json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        n = len(body) if isinstance(body, (list, dict)) else 0
        index.append({"url": url, "status": status, "archivo": nombre, "elementos": n})

        if status != 200:
            errores.append(f"  HTTP {status}  {url}")
        elif n == 0:
            vacios.append(f"  vacío     {url}")

        if i % 50 == 0 or i == len(urls):
            print(f"  {i}/{len(urls)} rutas capturadas", flush=True)

    (OUT_DIR / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"\nLínea base: {len(urls)} rutas en {OUT_DIR}")
    if errores:
        print(f"\n{len(errores)} respuestas con estado distinto de 200:")
        print("\n".join(errores))
    if vacios:
        print(f"\n{len(vacios)} respuestas vacías (revisar si es lo esperado):")
        print("\n".join(vacios[:20]))
        if len(vacios) > 20:
            print(f"  ... y {len(vacios) - 20} más")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
