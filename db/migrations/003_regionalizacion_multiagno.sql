-- ============================================================
-- Migración 003: Regionalización multi-año
-- Reemplaza regionalizacion_resumen y regionalizacion_detalle_2025
-- por dane_departamentos + regionalizacion (cubre 2022-2026)
-- ============================================================

PRAGMA foreign_keys = OFF;

-- Renombrar tablas legacy
ALTER TABLE regionalizacion_resumen      RENAME TO legacy_regionalizacion_resumen;
ALTER TABLE regionalizacion_detalle_2025 RENAME TO legacy_regionalizacion_detalle_2025;

-- ------------------------------------------------------------
-- Catálogo de departamentos DANE (32 entidades territoriales)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dane_departamentos (
    codigo  TEXT PRIMARY KEY,   -- '05', '08', ... '99'
    nombre  TEXT NOT NULL,      -- nombre normalizado
    region  TEXT NOT NULL       -- AMAZONIA|ANDINA|CARIBE|INSULAR|ORINOQUÍA|PACÍFICO
);

INSERT OR IGNORE INTO dane_departamentos (codigo, nombre, region) VALUES
    ('05', 'Antioquia',                                           'ANDINA'),
    ('08', 'Atlántico',                                           'CARIBE'),
    ('11', 'Bogotá, D.C.',                                        'ANDINA'),
    ('13', 'Bolívar',                                             'CARIBE'),
    ('15', 'Boyacá',                                              'ANDINA'),
    ('17', 'Caldas',                                              'ANDINA'),
    ('18', 'Caquetá',                                             'AMAZONIA'),
    ('19', 'Cauca',                                               'PACÍFICO'),
    ('20', 'Cesar',                                               'CARIBE'),
    ('23', 'Córdoba',                                             'CARIBE'),
    ('25', 'Cundinamarca',                                        'ANDINA'),
    ('27', 'Chocó',                                               'PACÍFICO'),
    ('41', 'Huila',                                               'ANDINA'),
    ('44', 'La Guajira',                                          'CARIBE'),
    ('47', 'Magdalena',                                           'CARIBE'),
    ('50', 'Meta',                                                'ORINOQUÍA'),
    ('52', 'Nariño',                                              'PACÍFICO'),
    ('54', 'Norte de Santander',                                  'ANDINA'),
    ('63', 'Quindío',                                             'ANDINA'),
    ('66', 'Risaralda',                                           'ANDINA'),
    ('68', 'Santander',                                           'ANDINA'),
    ('70', 'Sucre',                                               'CARIBE'),
    ('73', 'Tolima',                                              'ANDINA'),
    ('76', 'Valle del Cauca',                                     'PACÍFICO'),
    ('81', 'Arauca',                                              'ORINOQUÍA'),
    ('85', 'Casanare',                                            'ORINOQUÍA'),
    ('86', 'Putumayo',                                            'AMAZONIA'),
    ('88', 'Archipiélago de San Andrés, Providencia y Santa Catalina', 'INSULAR'),
    ('91', 'Amazonas',                                            'AMAZONIA'),
    ('94', 'Guainía',                                             'AMAZONIA'),
    ('95', 'Guaviare',                                            'AMAZONIA'),
    ('97', 'Vaupés',                                              'AMAZONIA'),
    ('99', 'Vichada',                                             'ORINOQUÍA');

-- ------------------------------------------------------------
-- Tabla unificada de regionalización (2022-2026)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS regionalizacion (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id      INTEGER REFERENCES metadatos_bitacora(id),
    vigencia         INTEGER NOT NULL,
    tipo             TEXT    NOT NULL,   -- 'departamento' | 'por_regionalizar' | 'nacional'
    region           TEXT    NOT NULL,   -- AMAZONIA | ANDINA | CARIBE | INSULAR | ORINOQUÍA | PACÍFICO | POR_REGIONALIZAR | NACIONAL
    departamento     TEXT    NOT NULL,
    codigo_dane      TEXT    REFERENCES dane_departamentos(codigo),
    apropiacion_mmm  REAL,              -- miles de millones pesos corrientes
    compromisos_mmm  REAL,
    obligaciones_mmm REAL,
    pagos_mmm        REAL,
    pct_compromisos  REAL,              -- % comp/aprop
    pct_obligaciones REAL,
    pct_pagos        REAL,
    pct_participacion REAL,             -- % del total general del año
    UNIQUE(bitacora_id, vigencia, region, departamento)
);

CREATE INDEX IF NOT EXISTS idx_regionalizacion_vigencia
    ON regionalizacion(vigencia, region);
CREATE INDEX IF NOT EXISTS idx_regionalizacion_dane
    ON regionalizacion(codigo_dane, vigencia);

PRAGMA foreign_keys = ON;
