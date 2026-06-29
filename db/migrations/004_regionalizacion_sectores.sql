CREATE TABLE IF NOT EXISTS regionalizacion_sectores (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    bitacora_id INTEGER NOT NULL REFERENCES metadatos_bitacora(id),
    vigencia    INTEGER NOT NULL,
    region      TEXT    NOT NULL,
    sector      TEXT    NOT NULL,
    apropiacion_mmm  REAL,
    compromisos_mmm  REAL,
    obligaciones_mmm REAL,
    pagos_mmm        REAL,
    UNIQUE(bitacora_id, vigencia, region, sector)
);
