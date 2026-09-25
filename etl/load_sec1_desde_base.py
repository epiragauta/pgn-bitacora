#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETL COMPLEMENTARIO — Sección 1 (Transformaciones PND) derivada de BASE DETALLE MENSUAL.
Versión SQL Server (db.py). Ver la variante SQLite en la rama main para el detalle.

Cuando el archivo canónico de la Sec 1 (`Inversiones ... PND ...xlsx`, con las
columnas Transformación/Componente por proyecto) NO llega en un corte, la
información monetaria equivalente está en `BASE DETALLE MENSUAL INVERSIÓN ...xlsx`
(hoja `BASE`) filtrando Año + Mes del corte (universo idéntico en total y por
sector). Lo que BASE no trae es la dimensión Transformación/Componente ni BPIN;
se reconstruye de forma APROXIMADA cruzando por la llave programática
(Código, Gsto, Prog, Subp, Proy, Rec, Sit) contra un archivo catálogo
(el `Inversiones` de un corte previo, típicamente marzo).

⚠️ APROXIMACIÓN (~99,7% del vigente en junio 2026; error <1% por transformación).
   No sustituye a load_bitacora_excel.py cuando sí llega el archivo Inversiones.

Uso:
    python etl/load_sec1_desde_base.py \
        --crosswalk "C:\\...\\Marzo\\1. INVERSIONES ...\\Inversiones 2026 - PND 2022-2026.xlsx" \
        --anio 2026 --mes JUN \
        --crear-bitacora --numero 4 --periodo 2026-II --corte 2026-06-30
    # --base por defecto se resuelve con bases.excel(6, "BASE DETALLE MENSUAL*.xlsx")
"""
import argparse
import sys
import unicodedata
from collections import defaultdict

import openpyxl

import bases
import db as dbmod

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

MMM = 1_000_000_000
TOP_COMPONENTES = 5

# Índices de columna en la hoja BASE (encabezado en fila 3; datos desde fila 4)
B_ANIO, B_MES = 0, 1
B_COD, B_GSTO, B_PROG, B_SUBP, B_PROY = 4, 8, 9, 10, 11
B_REC, B_SIT = 13, 14
B_VIG, B_COM, B_OBL, B_PAG = 19, 21, 22, 23


def s_(v):
    return "" if v is None else str(v).strip()


def up(v):
    return unicodedata.normalize("NFC", s_(v)).upper()


def to_float(v):
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def llave(cod, gsto, prog, subp, proy, rec, sit):
    return (s_(cod), s_(gsto), s_(prog), s_(subp), s_(proy), s_(rec), s_(sit))


def build_crosswalk(inv_path):
    wb = openpyxl.load_workbook(inv_path, data_only=True, read_only=True)
    ws = wb["Base"]
    hdr = [s_(h) for h in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
    idx = {h: i for i, h in enumerate(hdr)}

    def gi(*names):
        for n in names:
            if n in idx:
                return idx[n]
        raise KeyError(f"columna no hallada: {names}")

    iCod = gi("Código"); iGsto = gi("Gsto"); iProg = gi("Prog"); iSubp = gi("Subp")
    iProy = gi("Proy"); iRec = gi("Rec"); iSit = gi("Sit")
    iVig = gi("Vigente"); iT = gi("Transformación", "Transformacion"); iC = gi("Componente")

    acc = defaultdict(lambda: defaultdict(float))
    tset = defaultdict(set)
    for row in ws.iter_rows(min_row=2, values_only=True):
        t = s_(row[iT])
        if not t:
            continue
        c = s_(row[iC])
        k = llave(row[iCod], row[iGsto], row[iProg], row[iSubp], row[iProy], row[iRec], row[iSit])
        acc[k][(t, c)] += to_float(row[iVig])
        tset[k].add(t)
    wb.close()
    xwalk = {k: max(opts.items(), key=lambda kv: kv[1])[0] for k, opts in acc.items()}
    n_amb = sum(1 for k, ts in tset.items() if len(ts) > 1)
    return xwalk, n_amb


def aggregate_base(base_path, anio, mes, xwalk):
    mes = mes.upper()
    wb = openpyxl.load_workbook(base_path, data_only=True, read_only=True)
    ws = wb["BASE"]
    t_acc = defaultdict(lambda: {"v": 0.0, "c": 0.0, "o": 0.0, "p": 0.0})
    tc_acc = defaultdict(lambda: defaultdict(float))
    matched = unmatched = 0.0
    n_rows = n_unm = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[B_ANIO] != anio or up(row[B_MES]) != mes:
            continue
        n_rows += 1
        v = to_float(row[B_VIG]); c = to_float(row[B_COM])
        o = to_float(row[B_OBL]); p = to_float(row[B_PAG])
        k = llave(row[B_COD], row[B_GSTO], row[B_PROG], row[B_SUBP], row[B_PROY], row[B_REC], row[B_SIT])
        tc = xwalk.get(k)
        if tc is None:
            unmatched += v; n_unm += 1
            continue
        t, comp = tc
        matched += v
        t_acc[t]["v"] += v; t_acc[t]["c"] += c; t_acc[t]["o"] += o; t_acc[t]["p"] += p
        if comp:
            tc_acc[t][comp] += v
    wb.close()
    return t_acc, tc_acc, matched, unmatched, n_rows, n_unm


def load_sec1(conn, bid, vigencia, t_acc, tc_acc):
    conn.vaciar_bitacora(
        ("btcr_inversion_transformaciones", "btcr_inversion_componentes_pnd", "btcr_ejecucion_transformaciones"), bid)
    total_v = sum(d["v"] for d in t_acc.values()) or 1

    rows = [(bid, vigencia, t, round(d["v"] / MMM, 3), round(d["v"] / total_v * 100, 2))
            for t, d in t_acc.items()]
    conn.upsert("btcr_inversion_transformaciones",
                ["bitacora_id", "vigencia", "transformador", "inversion_mmm", "peso_pct"],
                rows, claves=["bitacora_id", "vigencia", "transformador"])
    print(f"  [OK] btcr_inversion_transformaciones : {len(rows)} filas")

    rows_c = []
    for t, comps in tc_acc.items():
        t_total = t_acc[t]["v"] or 1
        sc = sorted(comps.items(), key=lambda x: -x[1])
        for comp, v in sc[:TOP_COMPONENTES]:
            rows_c.append((bid, vigencia, t, comp, round(v / MMM, 3), round(v / t_total * 100, 2)))
        otros = sum(v for _, v in sc[TOP_COMPONENTES:])
        if otros > 0:
            rows_c.append((bid, vigencia, t, "OTROS COMPONENTES", round(otros / MMM, 3),
                           round(otros / t_total * 100, 2)))
    conn.upsert("btcr_inversion_componentes_pnd",
                ["bitacora_id", "vigencia", "transformador", "componente", "vigente_mmm", "peso_pct"],
                rows_c, claves=["bitacora_id", "vigencia", "transformador", "componente"])
    print(f"  [OK] btcr_inversion_componentes_pnd  : {len(rows_c)} filas")

    rows_e = []
    for t, d in t_acc.items():
        v = d["v"] or 1
        rows_e.append((bid, vigencia, t,
                       round(d["v"] / MMM, 3), round(d["c"] / MMM, 3),
                       round(d["o"] / MMM, 3), round(d["p"] / MMM, 3),
                       round(d["c"] / v * 100, 1), round(d["o"] / v * 100, 1), round(d["p"] / v * 100, 1)))
    conn.upsert("btcr_ejecucion_transformaciones",
                ["bitacora_id", "vigencia", "transformador", "apr_vigente_mmm",
                 "compromisos_mmm", "obligaciones_mmm", "pagos_mmm", "pct_c_av", "pct_o_av", "pct_p_av"],
                rows_e, claves=["bitacora_id", "vigencia", "transformador"])
    print(f"  [OK] btcr_ejecucion_transformaciones : {len(rows_e)} filas")


def resolver_bitacora(conn, args):
    if args.crear_bitacora:
        row = conn.execute("SELECT id FROM btcr_metadatos_bitacora WHERE periodo=?", (args.periodo,)).fetchone()
        if row:
            print(f"Bitácora {args.periodo} ya existe (id={row[0]}); se reutiliza.")
            return row[0]
        nid = conn.insertar_devolviendo_id(
            """INSERT INTO dbo.btcr_metadatos_bitacora
                   (numero_bitacora, periodo, corte_fecha, fuente_principal, notas)
               VALUES (?,?,?,?,?)""",
            (args.numero, args.periodo, args.corte,
             "BASE DETALLE MENSUAL (Sec 1 aproximada por llave programática)",
             args.notas or "Sec 1 derivada de BASE — desglose por transformación aproximado."))
        conn.commit()
        print(f"Bitácora creada: {args.periodo} (id={nid}).")
        return nid
    return dbmod.bitacora_reciente(conn)


def main():
    ap = argparse.ArgumentParser(description="Sec 1 (Transformaciones PND) aproximada desde BASE.")
    ap.add_argument("--base", default=None, help="BASE DETALLE MENSUAL ....xlsx (default: bases.excel sec 6)")
    ap.add_argument("--crosswalk", required=True, help="Archivo Inversiones (catálogo llave→transf/comp).")
    ap.add_argument("--anio", type=int, default=2026)
    ap.add_argument("--mes", default="JUN")
    ap.add_argument("--crear-bitacora", action="store_true")
    ap.add_argument("--numero", default=None)
    ap.add_argument("--periodo", default=None)
    ap.add_argument("--corte", default=None)
    ap.add_argument("--notas", default=None)
    args = ap.parse_args()
    if args.crear_bitacora and not (args.numero and args.periodo and args.corte):
        raise SystemExit("--crear-bitacora requiere --numero, --periodo y --corte.")

    base = args.base or str(bases.excel(6, "BASE DETALLE MENSUAL*.xlsx"))

    print("Construyendo crosswalk llave programática → transformación/componente ...")
    xwalk, n_amb = build_crosswalk(args.crosswalk)
    print(f"  {len(xwalk)} llaves; {n_amb} ambiguas (desambiguadas por mayor vigente).")

    print(f"Agregando BASE {base} filtrada a Año={args.anio}, Mes={args.mes.upper()} ...")
    t_acc, tc_acc, matched, unmatched, n_rows, n_unm = aggregate_base(base, args.anio, args.mes, xwalk)
    tot = matched + unmatched or 1
    print(f"  Filas del corte: {n_rows} | emparejadas: {n_rows - n_unm} | sin llave: {n_unm}")
    print(f"  Vigente emparejado : {matched/MMM:,.1f} mmm ({matched/tot*100:.1f}%)")
    print(f"  Vigente SIN mapear : {unmatched/MMM:,.1f} mmm ({unmatched/tot*100:.1f}%)  ← no entra a Sec 1")

    conn = dbmod.conectar()
    bid = resolver_bitacora(conn, args)
    print(f"Bitácora destino: id={bid}, vigencia={args.anio}")
    load_sec1(conn, bid, args.anio, t_acc, tc_acc)
    conn.commit()
    conn.close()
    print("\n⚠️  Desglose por transformación APROXIMADO (cruce por llave programática).")


if __name__ == "__main__":
    main()
