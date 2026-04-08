"""
seed_data.py  —  Carga inicial de datos Bitácora PGN 2025-I
Fuente: DNP/DPIP – Corte 31 de marzo de 2025
Cifras en miles de millones de pesos corrientes salvo vigencias futuras (constantes 2025)
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "pgn.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def seed():
    conn = get_conn()
    schema = (Path(__file__).parent.parent / "db" / "schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)

    # ----------------------------------------------------------
    # Metadatos
    # ----------------------------------------------------------
    conn.execute("""
        INSERT OR IGNORE INTO metadatos_bitacora
            (numero_bitacora, periodo, corte_fecha, fuente_principal, elaborado_por, notas)
        VALUES (?,?,?,?,?,?)
    """, ("2", "2025-I", "2025-03-31", "SIIF Nación / DPIP",
          "Dirección de Programación de Inversiones Públicas - DNP",
          "PND 2022-2026 'Colombia potencia mundial de la vida'"))
    bid = conn.execute("SELECT id FROM metadatos_bitacora WHERE periodo='2025-I'").fetchone()["id"]

    # ----------------------------------------------------------
    # SECCIÓN 1 – Inversiones PND (Transformaciones) 2025
    # ----------------------------------------------------------
    transformaciones = [
        ("SEGURIDAD HUMANA Y JUSTICIA SOCIAL",                              32.149, 38.29),
        ("CONVERGENCIA REGIONAL",                                           25.544, 30.42),
        ("OTRAS TRANSFORMACIONES Y EJES TRANSVERSALES",                     10.725, 12.77),
        ("TRANSFORMACIÓN PRODUCTIVA, INTERNACIONALIZACIÓN Y ACCIÓN CLIMÁTICA", 9.552, 11.38),
        ("ORDENAMIENTO DEL TERRITORIO ALREDEDOR DEL AGUA Y JUSTICIA AMBIENTAL", 3.529,  4.20),
        ("DERECHO HUMANO A LA ALIMENTACIÓN",                                 2.462,  2.93),
    ]
    conn.executemany("""
        INSERT OR IGNORE INTO inversion_transformaciones
            (bitacora_id, vigencia, transformador, inversion_mmm, peso_pct)
        VALUES (?,?,?,?,?)
    """, [(bid, 2025, t[0], t[1], t[2]) for t in transformaciones])

    componentes = [
        # (transformador, componente, vigente_mmm, peso_pct)
        # Seguridad Humana y Justicia Social
        ("SEGURIDAD HUMANA Y JUSTICIA SOCIAL", "OPORTUNIDADES DE EDUCACIÓN, FORMACIÓN, Y DE INSERCIÓN Y RECONVERSIÓN LABORAL", 4.978, 15),
        ("SEGURIDAD HUMANA Y JUSTICIA SOCIAL", "EDUCACIÓN SUPERIOR COMO UN DERECHO", 4.968, 15),
        ("SEGURIDAD HUMANA Y JUSTICIA SOCIAL", "SISTEMA DE TRANSFERENCIAS Y PROGRAMA RENTA CIUDADANA", 4.526, 14),
        ("SEGURIDAD HUMANA Y JUSTICIA SOCIAL", "FINANCIACIÓN SOSTENIBLE DE LOS SISTEMAS DE TRANSPORTE PÚBLICO", 2.663, 8),
        ("SEGURIDAD HUMANA Y JUSTICIA SOCIAL", "PROGRAMA DE ALIMENTACIÓN ESCOLAR (PAE)", 2.106, 7),
        ("SEGURIDAD HUMANA Y JUSTICIA SOCIAL", "OTROS COMPONENTES", 12.908, 40),
        # Convergencia Regional
        ("CONVERGENCIA REGIONAL", "INTEGRACIÓN DE TERRITORIOS BAJO EL PRINCIPIO DE LA CONECTIVIDAD FÍSICA Y LA MULTIMODALIDAD", 9.212, 36),
        ("CONVERGENCIA REGIONAL", "ENTIDADES PÚBLICAS TERRITORIALES Y NACIONALES FORTALECIDAS", 3.702, 14),
        ("CONVERGENCIA REGIONAL", "ACCESO EFECTIVO DE LAS VÍCTIMAS DEL CONFLICTO ARMADO A LAS MEDIDAS DE REPARACIÓN INTEGRAL", 2.398, 9),
        ("CONVERGENCIA REGIONAL", "ACCESO A SERVICIOS PÚBLICOS A PARTIR DE LAS CAPACIDADES Y NECESIDADES DE LOS TERRITORIOS", 1.801, 7),
        ("CONVERGENCIA REGIONAL", "INFRAESTRUCTURA Y SERVICIOS LOGÍSTICOS", 1.763, 7),
        ("CONVERGENCIA REGIONAL", "OTROS COMPONENTES", 6.668, 26),
        # Otras transformaciones
        ("OTRAS TRANSFORMACIONES Y EJES TRANSVERSALES", "UNIVERSALIZACIÓN DE LA ATENCIÓN INTEGRAL A LA PRIMERA INFANCIA", 6.126, 57),
        ("OTRAS TRANSFORMACIONES Y EJES TRANSVERSALES", "FORTALECIMIENTO DE LAS FAMILIAS Y LAS COMUNIDADES", 1.600, 15),
        ("OTRAS TRANSFORMACIONES Y EJES TRANSVERSALES", "ICBF COMO IMPULSOR DE PROYECTOS DE VIDA", 1.024, 10),
        ("OTRAS TRANSFORMACIONES Y EJES TRANSVERSALES", "ADMINISTRACIÓN EFICIENTE DE LOS RECURSOS PÚBLICOS", 678, 6),
        ("OTRAS TRANSFORMACIONES Y EJES TRANSVERSALES", "CONSTRUCCION DE TEJIDO SOCIAL DIVERSO CON GARANTIA DE DERECHOS", 499, 5),
        ("OTRAS TRANSFORMACIONES Y EJES TRANSVERSALES", "OTROS COMPONENTES", 798, 7),
        # Transformación Productiva
        ("TRANSFORMACIÓN PRODUCTIVA, INTERNACIONALIZACIÓN Y ACCIÓN CLIMÁTICA", "CIERRE DE BRECHAS ENERGÉTICAS", 4.904, 51),
        ("TRANSFORMACIÓN PRODUCTIVA, INTERNACIONALIZACIÓN Y ACCIÓN CLIMÁTICA", "GENERACIÓN DE ENERGÍA A PARTIR DE FUENTES NO CONVENCIONALES (FNCER)", 1.184, 12),
        ("TRANSFORMACIÓN PRODUCTIVA, INTERNACIONALIZACIÓN Y ACCIÓN CLIMÁTICA", "REDUCCIÓN DE LA VULNERABILIDAD FISCAL Y FINANCIERA ANTE RIESGOS CLIMÁTICOS", 568, 6),
        ("TRANSFORMACIÓN PRODUCTIVA, INTERNACIONALIZACIÓN Y ACCIÓN CLIMÁTICA", "DIVERSIFICACIÓN PRODUCTIVA ASOCIADA A LAS ACTIVIDADES EXTRACTIVAS", 469, 5),
        ("TRANSFORMACIÓN PRODUCTIVA, INTERNACIONALIZACIÓN Y ACCIÓN CLIMÁTICA", "SEGURIDAD Y CONFIABILIDAD ENERGÉTICA", 460, 5),
        ("TRANSFORMACIÓN PRODUCTIVA, INTERNACIONALIZACIÓN Y ACCIÓN CLIMÁTICA", "OTROS COMPONENTES", 1.966, 21),
        # Ordenamiento Territorio
        ("ORDENAMIENTO DEL TERRITORIO ALREDEDOR DEL AGUA Y JUSTICIA AMBIENTAL", "ACCESO Y FORMALIZACIÓN DE LA PROPIEDAD", 1.835, 52),
        ("ORDENAMIENTO DEL TERRITORIO ALREDEDOR DEL AGUA Y JUSTICIA AMBIENTAL", "ACTUALIZACIÓN CATASTRAL MULTIPROPÓSITO", 641, 18),
        ("ORDENAMIENTO DEL TERRITORIO ALREDEDOR DEL AGUA Y JUSTICIA AMBIENTAL", "COORDINACIÓN INSTITUCIONAL PARA OPTIMIZAR LA FORMALIZACIÓN", 166, 5),
        ("ORDENAMIENTO DEL TERRITORIO ALREDEDOR DEL AGUA Y JUSTICIA AMBIENTAL", "DEMOCRATIZACIÓN DEL CONOCIMIENTO, LA INFORMACIÓN AMBIENTAL Y DE RIESGO DE DESASTRES", 154, 4),
        ("ORDENAMIENTO DEL TERRITORIO ALREDEDOR DEL AGUA Y JUSTICIA AMBIENTAL", "SISTEMA DE ADMINISTRACIÓN DEL TERRITORIO (SAT)", 149, 4),
        ("ORDENAMIENTO DEL TERRITORIO ALREDEDOR DEL AGUA Y JUSTICIA AMBIENTAL", "OTROS COMPONENTES", 583, 17),
        # Derecho Humano Alimentación
        ("DERECHO HUMANO A LA ALIMENTACIÓN", "PROVEER ACCESO A FACTORES PRODUCTIVOS EN FORMA OPORTUNA Y SIMULTÁNEA", 1.411, 57),
        ("DERECHO HUMANO A LA ALIMENTACIÓN", "ENTORNOS DE DESARROLLO QUE INCENTIVEN LA ALIMENTACIÓN SALUDABLE Y ADECUADA", 455, 18),
        ("DERECHO HUMANO A LA ALIMENTACIÓN", "POLÍTICA DE INOCUIDAD DE LOS ALIMENTOS PARA EL PAÍS", 203, 8),
        ("DERECHO HUMANO A LA ALIMENTACIÓN", "OTROS COMPONENTES", 393, 16),
    ]
    conn.executemany("""
        INSERT OR IGNORE INTO inversion_componentes_pnd
            (bitacora_id, vigencia, transformador, componente, vigente_mmm, peso_pct)
        VALUES (?,?,?,?,?,?)
    """, [(bid, 2025, c[0], c[1], c[2], c[3]) for c in componentes])

    ejec_transf = [
        ("SEGURIDAD HUMANA Y JUSTICIA SOCIAL",                               32.149, 10.096, 3.047, 3.000, 31, 9, 9),
        ("CONVERGENCIA REGIONAL",                                            25.544, 14.336, 1.912, 1.884, 56, 7, 7),
        ("OTRAS TRANSFORMACIONES Y EJES TRANSVERSALES",                      10.725,  7.948, 1.440, 1.438, 74,13,13),
        ("TRANSFORMACIÓN PRODUCTIVA, INTERNACIONALIZACIÓN Y ACCIÓN CLIMÁTICA", 9.552, 2.277,    57,    55, 24, 1, 1),
        ("ORDENAMIENTO DEL TERRITORIO ALREDEDOR DEL AGUA Y JUSTICIA AMBIENTAL", 3.529, 1.037,  133,   127, 29, 4, 4),
        ("DERECHO HUMANO A LA ALIMENTACIÓN",                                  2.462,   668,    39,    28, 27, 2, 1),
    ]
    conn.executemany("""
        INSERT OR IGNORE INTO ejecucion_transformaciones
            (bitacora_id, vigencia, transformador, apr_vigente_mmm, compromisos_mmm,
             obligaciones_mmm, pagos_mmm, pct_c_av, pct_o_av, pct_p_av)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, [(bid, 2025, e[0], e[1], e[2], e[3], e[4], e[5], e[6], e[7]) for e in ejec_transf])

    # ----------------------------------------------------------
    # SECCIÓN 2 – Evolución presupuestal 2022-2025
    # ----------------------------------------------------------
    # Datos tabla general PGN (cifras en miles de millones)
    evolucion = [
        # (vigencia, rubro, sub_rubro, vigente, comp, obl, pago, pct_pgn)
        (2022, "TOTAL PGN",     None,         352281, 109234, 60610, 59528, None),
        (2022, "Funcionamiento",None,          210990,  63934, 40598, 39805, 14.3),
        (2022, "Inversión",     None,           69626,  36610, 11380, 11143,  4.7),
        (2022, "Servicio Deuda",None,           71665,   8690,  8632,  8580,  4.9),
        (2023, "TOTAL PGN",     None,         405655, 130548, 84833, 79631, None),
        (2023, "Funcionamiento",None,          253434,  66941, 44722, 43044, 16.0),
        (2023, "Inversión",     None,           74222,  31580,  8506,  8419,  4.7),
        (2023, "Servicio Deuda",None,           77998,  32027, 31606, 28168,  4.9),
        (2024, "TOTAL PGN",     None,         502624, 129714, 83214, 79036, None),
        (2024, "Funcionamiento",None,          308251,  72863, 55949, 54369, 18.1),
        (2024, "Inversión",     None,           99851,  38582,  9082,  8679,  5.9),
        (2024, "Servicio Deuda",None,           94522,  18268, 18184, 15988,  5.5),
        (2025, "TOTAL PGN",     None,         525803, 144809, 84466, 80791, None),
        (2025, "Funcionamiento",None,          329237,  89948, 60116, 58924, 18.1),
        (2025, "Inversión",     None,           83961,  36363,  6628,  6532,  4.6),
        (2025, "Servicio Deuda",None,          112605,  18499, 17722, 15335,  6.2),
        # Sub-rubros transferencias
        (2025, "Funcionamiento","Gastos de personal",   60243, 12170, 11045, 11025, None),
        (2025, "Funcionamiento","Adquisición de Bienes y Servicios", 16805, 8261, 2035, 1934, None),
        (2025, "Funcionamiento","Transferencias",       247741, 68100, 46577, 45578, None),
        (2025, "Funcionamiento","SGP",                  81984, 17597, 17563, 17562, None),
        (2025, "Funcionamiento","Pensiones",            77396, 22786, 12306, 12306, None),
    ]
    conn.executemany("""
        INSERT OR IGNORE INTO evolucion_presupuestal
            (bitacora_id, vigencia, rubro, sub_rubro, vigente_mmm, compromisos_mmm,
             obligaciones_mmm, pagos_mmm, pct_pgn)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, [(bid,)+e for e in evolucion])

    # ----------------------------------------------------------
    # SECCIÓN 3 – Regionalización 2025 (corte marzo 2025)
    # cifras en millones de pesos
    # ----------------------------------------------------------
    regional_2025 = [
        # (region, departamento, vigente, comp, obl, pagos, pct_c, pct_o, pct_p, pct_part, sectores_json)
        ("AMAZONAS",   "Amazonas",   2124156, 410848,  49078,  49048, 19.3, 11.9, 99.9, 100.0,
         '[{"sector":"Transporte","pct":19},{"sector":"Minas y Energía","pct":19},{"sector":"Igualdad y Equidad","pct":13}]'),
        ("AMAZONAS",   "Putumayo",    741980, 149701,  11657,  11644, 20.2,  7.8, 99.9,  34.9, "[]"),
        ("AMAZONAS",   "Caquetá",     612970, 101677,  17013,  17001, 16.6, 16.7, 99.9,  28.9, "[]"),
        ("AMAZONAS",   "Amazonas Dpto",255827,  55769,  11920,  11918, 21.8, 21.4,100.0,  12.0, "[]"),
        ("AMAZONAS",   "Guainía",     207716,  29624,   2276,   2275, 14.3,  7.7,100.0,   9.8, "[]"),
        ("AMAZONAS",   "Guaviare",    175386,  40991,   4526,   4524, 23.4, 11.0,100.0,   8.3, "[]"),
        ("AMAZONAS",   "Vaupés",      130278,  33085,   1686,   1686, 25.4,  5.1,100.0,   6.1, "[]"),
        ("ANDINA",     "Andina",    22904919,7928802,1872802,1862732, 34.6, 23.6, 99.5, 100.0,
         '[{"sector":"Transporte","pct":23},{"sector":"Trabajo","pct":19},{"sector":"Igualdad y Equidad","pct":14}]'),
        ("ANDINA",     "Bogotá",    5906100,1515429, 484913, 479668, 25.7, 32.0, 98.9,  25.8, "[]"),
        ("ANDINA",     "Antioquia", 5850587,2720526, 712060, 708497, 46.5, 26.2, 99.5,  25.5, "[]"),
        ("ANDINA",     "Santander", 1973363, 929552,  59065,  58943, 47.1,  6.4, 99.8,   8.6, "[]"),
        ("ANDINA",     "Cundinamarca",1916068,676206,110890, 110863, 35.3, 16.4,100.0,   8.4, "[]"),
        ("ANDINA",     "Norte de Santander",1887266,586558,156822,156234,31.1,26.7,99.6,  8.2, "[]"),
        ("ANDINA",     "Huila",     1172395, 351761,  41436,  41331, 30.0, 11.8, 99.7,   5.1, "[]"),
        ("ANDINA",     "Boyacá",    1170401, 275970,  73214,  73154, 23.6, 26.5, 99.9,   5.1, "[]"),
        ("ANDINA",     "Tolima",    1162263, 236534,  49829,  49788, 20.4, 21.1, 99.9,   5.1, "[]"),
        ("ANDINA",     "Caldas",     865289, 317173, 110348, 110332, 36.7, 34.8,100.0,   3.8, "[]"),
        ("ANDINA",     "Risaralda",  608335, 213512,  53158,   3136, 35.1, 24.9,100.0,   2.7, "[]"),
        ("ANDINA",     "Quindío",    392852, 105581,  21068,  20786, 26.9, 20.0, 98.7,   1.7, "[]"),
        ("CARIBE",     "Caribe - Insular",11509903,2540747,370302,361051,22.1,14.6,97.5,100.0,
         '[{"sector":"Igualdad y Equidad","pct":22},{"sector":"Minas y Energía","pct":17},{"sector":"Inclusión Social","pct":16}]'),
        ("CARIBE",     "Bolívar",   2179043, 682265,  98710,  89883, 31.3, 14.5, 91.1,  18.9, "[]"),
        ("CARIBE",     "La Guajira",1848604, 178638,  23917,  23869,  9.7, 13.4, 99.8,  16.1, "[]"),
        ("CARIBE",     "Atlántico", 1755505, 352176,  91927,  91845, 20.1, 26.1, 99.9,  15.3, "[]"),
        ("CARIBE",     "Magdalena", 1419850, 279647,  39550,  39502, 19.7, 14.1, 99.9,  12.3, "[]"),
        ("CARIBE",     "Córdoba",   1400778, 229702,  40088,  39942, 16.4, 17.5, 99.6,  12.2, "[]"),
        ("CARIBE",     "Cesar",     1351380, 332547,  41682,  41658, 24.6, 12.5, 99.9,  11.7, "[]"),
        ("CARIBE",     "Sucre",     1198110, 436899,  31039,  30971, 36.5,  7.1, 99.8,  10.4, "[]"),
        ("CARIBE",     "Archipiélago San Andrés",356632,48873,3389,3381,13.7,6.9,99.7,  3.1, "[]"),
        ("ORINOQUÍA",  "Orinoquía", 2133287, 606828, 113196, 113199, 28.4, 18.7,100.0, 100.0,
         '[{"sector":"Transporte","pct":26},{"sector":"Igualdad y Equidad","pct":15},{"sector":"Minas y Energía","pct":14}]'),
        ("ORINOQUÍA",  "Meta",       843372, 214049,  39547,  39522, 25.4, 18.5, 99.9,  39.7, "[]"),
        ("ORINOQUÍA",  "Casanare",   620242, 247133,  56531,  56521, 39.8, 22.9,100.0,  29.2, "[]"),
        ("ORINOQUÍA",  "Arauca",     376178,  53071,  10119,  10165, 14.1, 19.1,100.5,  17.7, "[]"),
        ("ORINOQUÍA",  "Vichada",    293496,  92574,   6999,   6992, 31.5,  7.6, 99.9,  13.8, "[]"),
        ("PACÍFICO",   "Pacifico",  8652873,1951833, 348764, 346719, 22.6, 17.9, 99.4, 100.0,
         '[{"sector":"Transporte","pct":21},{"sector":"Inclusión Social y Reconciliación","pct":16},{"sector":"Igualdad y Equidad","pct":16}]'),
        ("PACÍFICO",   "Valle del Cauca",3112431,461582,96862,96435,14.8,21.0,99.6,  36.0, "[]"),
        ("PACÍFICO",   "Nariño",    2227965, 744089, 167635, 166807, 33.4, 22.5, 99.5,  25.7, "[]"),
        ("PACÍFICO",   "Cauca",     2045318, 587799,  46919,  46368, 28.7,  8.0, 98.8,  23.6, "[]"),
        ("NACIONAL",   "Nacional", 25623712,8407022,1165186,1121509,  None,None,None,  None,
         '[]'),
    ]
    conn.executemany("""
        INSERT OR IGNORE INTO regionalizacion_detalle_2025
            (bitacora_id, region, departamento, vigente_mm, compromisos_mm,
             obligaciones_mm, pagos_mm, pct_ejec_compromisos, pct_ejec_obligaciones,
             pct_ejec_pagos, pct_participacion, principales_sectores)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, [(bid,)+r for r in regional_2025])

    # ----------------------------------------------------------
    # SECCIÓN 4 – Ejecución histórica 2022-2025
    # ----------------------------------------------------------
    ejecucion = [
        (2022, 69626, 36610, 11380, 11143, 53, 16, 16.0, 4.7, 20),
        (2023, 74222, 31580,  8506,  8419, 43, 11, 11.3, 5.3, 20),
        (2024, 99851, 38582,  9082,  8679, 39,  9,  8.7, 5.3, 19),
        (2025, 83961, 36363,  6628,  6532, 43,  8,  7.8, 4.6, 16),
    ]
    conn.executemany("""
        INSERT OR IGNORE INTO ejecucion_historica
            (bitacora_id, vigencia, vigente_mmm, compromisos_mmm, obligaciones_mmm,
             pagos_mmm, pct_compromisos, pct_obligaciones, pct_pagos, inv_pct_pib, inv_pct_gasto_total)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, [(bid,)+e for e in ejecucion])

    # Apropiación por sector 2015-2025 (muestra más representativa)
    sectores_aprop = [
        # (vigencia, sector, vigente_mmm)
        (2015, "Educación", 2.465), (2022, "Educación", 5.535), (2023, "Educación", 7.404), (2024, "Educación", 8.081), (2025, "Educación", 8.267),
        (2015, "Minas y Energía", 2.668), (2022, "Minas y Energía", 4.787), (2023, "Minas y Energía", 7.287), (2024, "Minas y Energía", 7.526), (2025, "Minas y Energía", 7.419),
        (2015, "Trabajo", 4.413), (2022, "Trabajo", 4.333), (2023, "Trabajo", 5.121), (2024, "Trabajo", 5.663), (2025, "Trabajo", 6.642),
        (2015, "Vivienda, Ciudad y Territorio", 2.286), (2022, "Vivienda, Ciudad y Territorio", 3.165), (2023, "Vivienda, Ciudad y Territorio", 5.008), (2024, "Vivienda, Ciudad y Territorio", 5.367), (2025, "Vivienda, Ciudad y Territorio", 4.377),
        (2015, "Agricultura y desarrollo Rural", 3.288), (2022, "Agricultura y desarrollo Rural", 1.824), (2023, "Agricultura y desarrollo Rural", 4.445), (2024, "Agricultura y desarrollo Rural", 6.821), (2025, "Agricultura y desarrollo Rural", 4.288),
        (2015, "Salud y Protección Social", 4.669), (2022, "Salud y Protección Social", 1.183), (2023, "Salud y Protección Social", 2.125), (2024, "Salud y Protección Social", 2.057), (2025, "Salud y Protección Social", 2.144),
        (2015, "Transporte", 6.628), (2022, "Transporte", 11.233), (2023, "Transporte", 11.304), (2024, "Transporte", 12.777), (2025, "Transporte", 13.748),
        (2022, "Igualdad y Equidad", None), (2023, "Igualdad y Equidad", None), (2024, "Igualdad y Equidad", 9.968), (2025, "Igualdad y Equidad", 10.151),
        (2022, "Inclusión Social y Reconciliación", 9.788), (2023, "Inclusión Social y Reconciliación", 21.728), (2024, "Inclusión Social y Reconciliación", 11.152), (2025, "Inclusión Social y Reconciliación", 8.243),
        (2022, "Hacienda", 3.129), (2023, "Hacienda", 2.614), (2024, "Hacienda", 4.831), (2025, "Hacienda", 4.406),
        (2022, "Defensa y Policía", 1.471), (2023, "Defensa y Policía", 2.083), (2024, "Defensa y Policía", 3.103), (2025, "Defensa y Policía", 2.493),
        (2022, "Tecnologías de la Información y las Comunicaciones", 1.129), (2023, "Tecnologías de la Información y las Comunicaciones", 1.566), (2024, "Tecnologías de la Información y las Comunicaciones", 3.260), (2025, "Tecnologías de la Información y las Comunicaciones", 1.921),
    ]
    conn.executemany("""
        INSERT OR IGNORE INTO apropiacion_por_sector
            (bitacora_id, vigencia, sector, vigente_mmm)
        VALUES (?,?,?,?)
    """, [(bid, s[0], s[1], s[2]) for s in sectores_aprop])

    # ----------------------------------------------------------
    # SECCIÓN 5 – Vigencias Futuras 2026-2040 (constantes 2025)
    # ----------------------------------------------------------
    vf_sectores = {
        "TRANSPORTE":             [9651, 9172, 8777, 8373, 8542, 7208, 6921, 6452, 4067, 2495, 2401, 1958, 1939, 1205, 656],
        "HACIENDA":               [4433, 3545, 5057, 4302, 2827, 2796, 2766, 2852, 2236, 2209, 2183, 2157, 1741, 1412, 1397],
        "IGUALDAD Y EQUIDAD":     [1291,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0],
        "DEFENSA Y POLICÍA":      [1170,  983,  983,  983,  983,  983,  983,    0,    0,    0,    0,    0,    0,    0,    0],
        "VIVIENDA, CIUDAD Y TERRITORIO":[391, 524, 548, 571, 226,  75,    0,    0,    0,    0,    0,    0,    0,    0,    0],
        "OTROS SECTORES":         [ 911,  314,   52,   52,   52,   52,   52,   52,   52,   52,   52,   52,   52,   52,   52],
    }
    vf_pib = [1.01, 0.80, 0.81, 0.72, 0.61, 0.52, 0.48, 0.41, 0.27, 0.19, 0.18, 0.16, 0.14, 0.10, 0.07]
    años_vf = list(range(2026, 2041))
    vf_rows = []
    for sector, valores in vf_sectores.items():
        for i, (año, val) in enumerate(zip(años_vf, valores)):
            vf_rows.append((bid, año, sector, val, vf_pib[i]))
    conn.executemany("""
        INSERT OR IGNORE INTO vigencias_futuras
            (bitacora_id, vigencia_exec, sector, valor_mmm_ctes, pct_pib)
        VALUES (?,?,?,?,?)
    """, vf_rows)

    # ----------------------------------------------------------
    # SECCIÓN 6 – Ejecución Sectorial por entidades (muestra sectores principales)
    # Datos corte marzo 2025 (cifras en miles de millones)
    # ----------------------------------------------------------
    sectorial = [
        # (vigencia, sector, entidad, apr_vig, comp, obl, pct_c_av, pct_o_av)
        (2025, "EDUCACIÓN", "SECTOR EDUCACIÓN", 8.267, None, None, None, None),
        (2025, "TRANSPORTE", "SECTOR TRANSPORTE", 13.748, 9.079, 1.311, 66, 10),
        (2025, "TRANSPORTE", "Agencia Nacional de Infraestructura - ANI", 7.382, 5.859, 1.085, 79, 15),
        (2025, "TRANSPORTE", "Instituto Nacional de Vías - INVIAS", 3.724, 1.859,  90, 50, 2),
        (2025, "TRANSPORTE", "Aeronáutica Civil", 2.285, 1.202,  25, 53, 1),
        (2025, "TRANSPORTE", "Ministerio de Transporte - Gestión General", 130, 38, 4, 29, 3),
        (2025, "HACIENDA", "SECTOR HACIENDA", 4.406, 1.623, 152, 37, 3),
        (2025, "HACIENDA", "Ministerio de Hacienda y Crédito Público", 3.611, 928, 144, 26, 4),
        (2025, "HACIENDA", "Fondo Adaptación", 624, 590, 0, 95, 0),
        (2025, "DEFENSA Y POLICÍA", "SECTOR DEFENSA Y POLICÍA", 2.493, 1.042, 321, 42, 13),
        (2025, "DEFENSA Y POLICÍA", "Ministerio de Defensa Nacional", 2.109, 948, 316, 45, 15),
        (2025, "DEFENSA Y POLICÍA", "Policía Nacional", 253, 58, 0, 23, 0),
        (2025, "VIVIENDA, CIUDAD Y TERRITORIO", "SECTOR VIVIENDA", 4.377, 2.993, 194, 68, 4),
        (2025, "VIVIENDA, CIUDAD Y TERRITORIO", "FONVIVIENDA", 2.701, 2.474, 111, 92, 4),
        (2025, "VIVIENDA, CIUDAD Y TERRITORIO", "Ministerio de Vivienda - Gestión General", 1.661, 511, 82, 31, 5),
        (2025, "AGRICULTURA Y DESARROLLO RURAL", "SECTOR AGRICULTURA", 4.288, 1.028, 125, 24, 3),
        (2025, "AGRICULTURA Y DESARROLLO RURAL", "Minagricultura", 1.636, 338, 32, 21, 2),
        (2025, "AGRICULTURA Y DESARROLLO RURAL", "UPRA", 1.108, 258, 5, 23, 0),
        (2025, "AGRICULTURA Y DESARROLLO RURAL", "Agencia Nacional de Tierras - ANT", 704, 52, 11, 7, 2),
        (2025, "INTERIOR", "SECTOR INTERIOR", 483, 50, 3, 10, 1),
        (2025, "PRESIDENCIA DE LA REPÚBLICA", "SECTOR PRESIDENCIA", 604, 43, 3, 7, 0),
        (2025, "PRESIDENCIA DE LA REPÚBLICA", "Presidencia de la República", 205, 15, 1, 7, 1),
        (2025, "PRESIDENCIA DE LA REPÚBLICA", "Dirección de Sustitución de Cultivos Ilícitos", 185, 0, 0, 0, 0),
        (2025, "MINAS Y ENERGÍA", "SECTOR MINAS Y ENERGÍA", 7.419, None, None, None, None),
        (2025, "TRABAJO", "SECTOR TRABAJO", 6.642, None, None, None, None),
        (2025, "IGUALDAD Y EQUIDAD", "SECTOR IGUALDAD Y EQUIDAD", 10.151, None, None, None, None),
    ]
    conn.executemany("""
        INSERT OR IGNORE INTO ejecucion_sectorial_entidades
            (bitacora_id, vigencia, sector, entidad, apr_vigente_mmm, compromisos_mmm,
             obligaciones_mmm, pct_c_av, pct_o_av)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, [(bid,)+s for s in sectorial])

    # Ejecución sectorial mensual 2025 (Ene-Mar)
    sectorial_mensual = [
        # (vigencia, sector, mes, pct_2025, pct_2024, pct_prom, pct_mejor)
        (2025, "TRANSPORTE",               1, 3, 0, 1, 3),
        (2025, "TRANSPORTE",               2, 5, 12, 5, 12),
        (2025, "TRANSPORTE",               3, 10, 14, 8, 14),
        (2025, "VIVIENDA, CIUDAD Y TERRITORIO", 1, 0, 0, 0, 4),
        (2025, "VIVIENDA, CIUDAD Y TERRITORIO", 2, 1, 1, 2, 4),
        (2025, "VIVIENDA, CIUDAD Y TERRITORIO", 3, 4, 2, 5, 11),
        (2025, "HACIENDA",                 1, 0, 0, 0, 2),
        (2025, "HACIENDA",                 2, 3, 2, 1, 2),
        (2025, "HACIENDA",                 3, 3, 3, 2, 3),
        (2025, "DEFENSA Y POLICÍA",        1, 1, 10, 6, 13),
        (2025, "DEFENSA Y POLICÍA",        2, 1, 11, 7, 15),
        (2025, "DEFENSA Y POLICÍA",        3, 13, 15, 15, 26),
        (2025, "INTERIOR",                 1, 0, 0, 0, 0),
        (2025, "INTERIOR",                 2, 0, 0, 2, 7),
        (2025, "INTERIOR",                 3, 1, 1, 3, 8),
        (2025, "PRESIDENCIA DE LA REPÚBLICA", 1, 0, 0, 0, 0),
        (2025, "PRESIDENCIA DE LA REPÚBLICA", 2, 0, 0, 0, 1),
        (2025, "PRESIDENCIA DE LA REPÚBLICA", 3, 0, 1, 2, 4),
        (2025, "AGRICULTURA Y DESARROLLO RURAL", 1, 0, 0, 0, 0),
        (2025, "AGRICULTURA Y DESARROLLO RURAL", 2, 1, 1, 3, 7),
        (2025, "AGRICULTURA Y DESARROLLO RURAL", 3, 3, 3, 6, 13),
    ]
    conn.executemany("""
        INSERT OR IGNORE INTO ejecucion_sectorial_mensual
            (bitacora_id, vigencia, sector, mes, pct_compromisos_2025,
             pct_compromisos_2024, pct_compromisos_prom, pct_compromisos_mejor)
        VALUES (?,?,?,?,?,?,?,?)
    """, [(bid,)+s for s in sectorial_mensual])

    conn.commit()
    print(f"✅  Base de datos cargada: {DB_PATH}")
    print(f"   Bitácora id={bid}")

    # Verificación rápida
    for tbl in ["inversion_transformaciones","evolucion_presupuestal",
                "regionalizacion_detalle_2025","ejecucion_historica",
                "vigencias_futuras","ejecucion_sectorial_entidades"]:
        n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"   {tbl}: {n} filas")
    conn.close()

if __name__ == "__main__":
    seed()
