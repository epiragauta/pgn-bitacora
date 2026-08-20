-- ============================================================
-- 001_schema.sql — Esquema SQL Server (base dnp_dpip)
-- Bitácora de Inversión Pública — DNP / DPIP
--
-- Port del esquema SQLite (db/pgn.db) documentado en
-- docs/PLAN_MIGRACION_DOTNET_SQLSERVER.md §3.
--
-- Cifras monetarias en miles de millones de pesos (mmm) salvo
-- donde el nombre de la columna indique otra unidad.
--
-- Requisitos aplicados:
--   · TEXT     -> NVARCHAR  (los datos contienen tildes: ORINOQUÍA,
--                            PACÍFICO, Bogotá D.C., DEFENSA Y POLICÍA)
--   · REAL     -> DECIMAL   (precisión determinista en los ROUND)
--   · BOOLEAN  -> BIT
--   · AUTOINCREMENT -> IDENTITY(1,1)   (requiere IDENTITY_INSERT al cargar)
--   · bitacora_id NOT NULL  (verificado: cero filas NULL en el origen)
--
-- Idempotente: se puede ejecutar varias veces sin error.
-- Ejecutar sobre la base dnp_dpip (COLLATE Modern_Spanish_CS_AS).
-- ============================================================

SET NOCOUNT ON;
GO

-- ------------------------------------------------------------
-- Tabla de control: metadatos por bitácora
-- Todas las tablas de datos cuelgan de aquí vía bitacora_id.
-- ------------------------------------------------------------
IF OBJECT_ID('dbo.btcr_metadatos_bitacora', 'U') IS NULL
CREATE TABLE dbo.btcr_metadatos_bitacora (
    id               INT            IDENTITY(1,1) NOT NULL,
    numero_bitacora  NVARCHAR(10)   NOT NULL,          -- ej. '2'
    periodo          NVARCHAR(20)   NOT NULL,          -- ej. '2025-I'
    corte_fecha      DATE           NOT NULL,          -- ej. '2025-03-31'
    fuente_principal NVARCHAR(100)  NULL CONSTRAINT DF_btcr_metadatos_fuente     DEFAULT ('SIIF Nación'),
    elaborado_por    NVARCHAR(100)  NULL CONSTRAINT DF_btcr_metadatos_elaborado  DEFAULT ('DPIP - DNP'),
    fecha_carga      DATETIME2(0)   NULL CONSTRAINT DF_btcr_metadatos_fecha      DEFAULT (SYSUTCDATETIME()),
    notas            NVARCHAR(500)  NULL,
    CONSTRAINT PK_btcr_metadatos_bitacora PRIMARY KEY (id)
);
GO

-- ------------------------------------------------------------
-- Catálogo DANE de departamentos (33 entidades territoriales)
-- codigo es TEXTO con cero a la izquierda ('05', '08'): nunca INT.
-- ------------------------------------------------------------
IF OBJECT_ID('dbo.btcr_dane_departamentos', 'U') IS NULL
CREATE TABLE dbo.btcr_dane_departamentos (
    codigo  NVARCHAR(5)    NOT NULL,   -- '05', '08', ... '99'
    nombre  NVARCHAR(120)  NOT NULL,
    region  NVARCHAR(40)   NOT NULL,   -- AMAZONIA|ANDINA|CARIBE|INSULAR|ORINOQUÍA|PACÍFICO
    CONSTRAINT PK_btcr_dane_departamentos PRIMARY KEY (codigo)
);
GO

-- ============================================================
-- SECCIÓN 1 — Transformaciones del PND 2022-2026
-- ============================================================
IF OBJECT_ID('dbo.btcr_inversion_transformaciones', 'U') IS NULL
CREATE TABLE dbo.btcr_inversion_transformaciones (
    id              INT            IDENTITY(1,1) NOT NULL,
    bitacora_id     INT            NOT NULL,
    vigencia        INT            NOT NULL,
    transformador   NVARCHAR(150)  NOT NULL,
    inversion_mmm   DECIMAL(18,6)  NULL,
    peso_pct        DECIMAL(9,4)   NULL,
    CONSTRAINT PK_btcr_inversion_transformaciones PRIMARY KEY (id),
    CONSTRAINT FK_btcr_inv_transf_bitacora FOREIGN KEY (bitacora_id)
        REFERENCES dbo.btcr_metadatos_bitacora(id)
);
GO

IF OBJECT_ID('dbo.btcr_inversion_componentes_pnd', 'U') IS NULL
CREATE TABLE dbo.btcr_inversion_componentes_pnd (
    id              INT            IDENTITY(1,1) NOT NULL,
    bitacora_id     INT            NOT NULL,
    vigencia        INT            NOT NULL,
    transformador   NVARCHAR(150)  NOT NULL,
    componente      NVARCHAR(250)  NOT NULL,
    vigente_mmm     DECIMAL(18,6)  NULL,
    peso_pct        DECIMAL(9,4)   NULL,
    CONSTRAINT PK_btcr_inversion_componentes_pnd PRIMARY KEY (id),
    CONSTRAINT FK_btcr_inv_comp_bitacora FOREIGN KEY (bitacora_id)
        REFERENCES dbo.btcr_metadatos_bitacora(id)
);
GO

IF OBJECT_ID('dbo.btcr_ejecucion_transformaciones', 'U') IS NULL
CREATE TABLE dbo.btcr_ejecucion_transformaciones (
    id                  INT            IDENTITY(1,1) NOT NULL,
    bitacora_id         INT            NOT NULL,
    vigencia            INT            NOT NULL,
    transformador       NVARCHAR(150)  NOT NULL,
    apr_vigente_mmm     DECIMAL(18,6)  NULL,
    compromisos_mmm     DECIMAL(18,6)  NULL,
    obligaciones_mmm    DECIMAL(18,6)  NULL,
    pagos_mmm           DECIMAL(18,6)  NULL,
    pct_c_av            DECIMAL(9,4)   NULL,
    pct_o_av            DECIMAL(9,4)   NULL,
    pct_p_av            DECIMAL(9,4)   NULL,
    CONSTRAINT PK_btcr_ejecucion_transformaciones PRIMARY KEY (id),
    CONSTRAINT FK_btcr_ejec_transf_bitacora FOREIGN KEY (bitacora_id)
        REFERENCES dbo.btcr_metadatos_bitacora(id)
);
GO

-- ============================================================
-- SECCIÓN 2 — Evolución presupuestal del PGN (modelo pgn_*)
-- Dimensión jerárquica de conceptos + hechos por año y fase.
-- ============================================================
IF OBJECT_ID('dbo.btcr_pgn_concepto', 'U') IS NULL
CREATE TABLE dbo.btcr_pgn_concepto (
    id       INT            IDENTITY(1,1) NOT NULL,
    nombre   NVARCHAR(200)  NOT NULL,
    padre_id INT            NULL,
    nivel    INT            NOT NULL,
    unidad   NVARCHAR(20)   NOT NULL,
    orden    INT            NOT NULL,   -- posición de display
    CONSTRAINT PK_btcr_pgn_concepto     PRIMARY KEY (id),
    CONSTRAINT UQ_btcr_pgn_concepto_nombre UNIQUE (nombre),
    CONSTRAINT CK_btcr_pgn_concepto_nivel  CHECK (nivel BETWEEN 1 AND 4),
    CONSTRAINT CK_btcr_pgn_concepto_unidad CHECK (unidad IN ('Miles mm COP', '% PIB')),
    -- Autorreferencia: SQL Server prohíbe acciones en cascada sobre una FK
    -- que apunta a su propia tabla (error 1785), por lo que el
    -- "ON DELETE SET NULL" del origen SQLite se degrada a NO ACTION.
    CONSTRAINT FK_btcr_pgn_concepto_padre FOREIGN KEY (padre_id)
        REFERENCES dbo.btcr_pgn_concepto(id)
);
GO

IF OBJECT_ID('dbo.btcr_pgn_ejecucion', 'U') IS NULL
CREATE TABLE dbo.btcr_pgn_ejecucion (
    id          INT            IDENTITY(1,1) NOT NULL,
    anio        INT            NOT NULL,
    fase        NVARCHAR(20)   NOT NULL,
    concepto_id INT            NOT NULL,
    valor       DECIMAL(18,6)  NOT NULL,
    CONSTRAINT PK_btcr_pgn_ejecucion   PRIMARY KEY (id),
    CONSTRAINT UQ_btcr_pgn_ejecucion   UNIQUE (anio, fase, concepto_id),
    CONSTRAINT CK_btcr_pgn_ejecucion_anio CHECK (anio BETWEEN 2022 AND 2030),
    CONSTRAINT CK_btcr_pgn_ejecucion_fase CHECK (fase IN ('Vigente','Comprometido','Obligado','Pagado')),
    CONSTRAINT FK_btcr_pgn_ejecucion_concepto FOREIGN KEY (concepto_id)
        REFERENCES dbo.btcr_pgn_concepto(id)
);
GO

-- ============================================================
-- SECCIÓN 3 — Regionalización de la inversión (2022-2026)
-- ============================================================
IF OBJECT_ID('dbo.btcr_regionalizacion', 'U') IS NULL
CREATE TABLE dbo.btcr_regionalizacion (
    id                INT            IDENTITY(1,1) NOT NULL,
    bitacora_id       INT            NOT NULL,
    vigencia          INT            NOT NULL,
    tipo              NVARCHAR(30)   NOT NULL,   -- departamento | por_regionalizar | nacional
    region            NVARCHAR(40)   NOT NULL,
    departamento      NVARCHAR(120)  NOT NULL,
    codigo_dane       NVARCHAR(5)    NULL,       -- NULL en filas nacional/por regionalizar
    apropiacion_mmm   DECIMAL(18,6)  NULL,
    compromisos_mmm   DECIMAL(18,6)  NULL,
    obligaciones_mmm  DECIMAL(18,6)  NULL,
    pagos_mmm         DECIMAL(18,6)  NULL,
    pct_compromisos   DECIMAL(9,4)   NULL,
    pct_obligaciones  DECIMAL(9,4)   NULL,
    pct_pagos         DECIMAL(9,4)   NULL,
    pct_participacion DECIMAL(9,4)   NULL,
    CONSTRAINT PK_btcr_regionalizacion PRIMARY KEY (id),
    CONSTRAINT UQ_btcr_regionalizacion UNIQUE (bitacora_id, vigencia, region, departamento),
    CONSTRAINT FK_btcr_regionalizacion_bitacora FOREIGN KEY (bitacora_id)
        REFERENCES dbo.btcr_metadatos_bitacora(id),
    CONSTRAINT FK_btcr_regionalizacion_dane FOREIGN KEY (codigo_dane)
        REFERENCES dbo.btcr_dane_departamentos(codigo)
);
GO

IF OBJECT_ID('dbo.btcr_regionalizacion_sectores', 'U') IS NULL
CREATE TABLE dbo.btcr_regionalizacion_sectores (
    id                INT            IDENTITY(1,1) NOT NULL,
    bitacora_id       INT            NOT NULL,
    vigencia          INT            NOT NULL,
    region            NVARCHAR(40)   NOT NULL,
    sector            NVARCHAR(120)  NOT NULL,
    apropiacion_mmm   DECIMAL(18,6)  NULL,
    compromisos_mmm   DECIMAL(18,6)  NULL,
    obligaciones_mmm  DECIMAL(18,6)  NULL,
    pagos_mmm         DECIMAL(18,6)  NULL,
    CONSTRAINT PK_btcr_regionalizacion_sectores PRIMARY KEY (id),
    CONSTRAINT UQ_btcr_regionalizacion_sectores UNIQUE (bitacora_id, vigencia, region, sector),
    CONSTRAINT FK_btcr_reg_sectores_bitacora FOREIGN KEY (bitacora_id)
        REFERENCES dbo.btcr_metadatos_bitacora(id)
);
GO

-- ============================================================
-- SECCIÓN 4 — Ejecución de la inversión
-- ============================================================
IF OBJECT_ID('dbo.btcr_ejecucion_historica', 'U') IS NULL
CREATE TABLE dbo.btcr_ejecucion_historica (
    id                  INT            IDENTITY(1,1) NOT NULL,
    bitacora_id         INT            NOT NULL,
    vigencia            INT            NOT NULL,
    vigente_mmm         DECIMAL(18,6)  NULL,
    compromisos_mmm     DECIMAL(18,6)  NULL,
    obligaciones_mmm    DECIMAL(18,6)  NULL,
    pagos_mmm           DECIMAL(18,6)  NULL,
    pct_compromisos     DECIMAL(9,4)   NULL,
    pct_obligaciones    DECIMAL(9,4)   NULL,
    pct_pagos           DECIMAL(9,4)   NULL,
    inv_pct_pib         DECIMAL(9,4)   NULL,
    inv_pct_gasto_total DECIMAL(9,4)   NULL,
    CONSTRAINT PK_btcr_ejecucion_historica PRIMARY KEY (id),
    CONSTRAINT UQ_btcr_ejecucion_historica UNIQUE (bitacora_id, vigencia),
    CONSTRAINT FK_btcr_ejec_hist_bitacora FOREIGN KEY (bitacora_id)
        REFERENCES dbo.btcr_metadatos_bitacora(id)
);
GO

IF OBJECT_ID('dbo.btcr_apropiacion_por_sector', 'U') IS NULL
CREATE TABLE dbo.btcr_apropiacion_por_sector (
    id           INT            IDENTITY(1,1) NOT NULL,
    bitacora_id  INT            NOT NULL,
    vigencia     INT            NOT NULL,
    sector       NVARCHAR(120)  NOT NULL,
    vigente_mmm  DECIMAL(18,6)  NULL,
    CONSTRAINT PK_btcr_apropiacion_por_sector PRIMARY KEY (id),
    CONSTRAINT UQ_btcr_apropiacion_por_sector UNIQUE (bitacora_id, vigencia, sector),
    CONSTRAINT FK_btcr_aprop_sector_bitacora FOREIGN KEY (bitacora_id)
        REFERENCES dbo.btcr_metadatos_bitacora(id)
);
GO

IF OBJECT_ID('dbo.btcr_compromisos_pct_por_sector', 'U') IS NULL
CREATE TABLE dbo.btcr_compromisos_pct_por_sector (
    id              INT            IDENTITY(1,1) NOT NULL,
    bitacora_id     INT            NOT NULL,
    vigencia        INT            NOT NULL,
    sector          NVARCHAR(120)  NOT NULL,
    pct_compromisos DECIMAL(9,4)   NULL,
    CONSTRAINT PK_btcr_compromisos_pct_por_sector PRIMARY KEY (id),
    CONSTRAINT UQ_btcr_compromisos_pct_por_sector UNIQUE (bitacora_id, vigencia, sector),
    CONSTRAINT FK_btcr_comp_pct_bitacora FOREIGN KEY (bitacora_id)
        REFERENCES dbo.btcr_metadatos_bitacora(id)
);
GO

IF OBJECT_ID('dbo.btcr_obligaciones_pct_por_sector', 'U') IS NULL
CREATE TABLE dbo.btcr_obligaciones_pct_por_sector (
    id               INT            IDENTITY(1,1) NOT NULL,
    bitacora_id      INT            NOT NULL,
    vigencia         INT            NOT NULL,
    sector           NVARCHAR(120)  NOT NULL,
    pct_obligaciones DECIMAL(9,4)   NULL,
    CONSTRAINT PK_btcr_obligaciones_pct_por_sector PRIMARY KEY (id),
    CONSTRAINT UQ_btcr_obligaciones_pct_por_sector UNIQUE (bitacora_id, vigencia, sector),
    CONSTRAINT FK_btcr_obl_pct_bitacora FOREIGN KEY (bitacora_id)
        REFERENCES dbo.btcr_metadatos_bitacora(id)
);
GO

IF OBJECT_ID('dbo.btcr_pagos_pct_por_sector', 'U') IS NULL
CREATE TABLE dbo.btcr_pagos_pct_por_sector (
    id          INT            IDENTITY(1,1) NOT NULL,
    bitacora_id INT            NOT NULL,
    vigencia    INT            NOT NULL,
    sector      NVARCHAR(120)  NOT NULL,
    pct_pagos   DECIMAL(9,4)   NULL,
    CONSTRAINT PK_btcr_pagos_pct_por_sector PRIMARY KEY (id),
    CONSTRAINT UQ_btcr_pagos_pct_por_sector UNIQUE (bitacora_id, vigencia, sector),
    CONSTRAINT FK_btcr_pagos_pct_bitacora FOREIGN KEY (bitacora_id)
        REFERENCES dbo.btcr_metadatos_bitacora(id)
);
GO

-- ============================================================
-- SECCIÓN 5 — Vigencias futuras y deflactores
-- vigencias_futuras guarda pesos CORRIENTES; la conversión a
-- constantes 2026 la hace la API dividiendo por el deflactor.
-- ============================================================
IF OBJECT_ID('dbo.btcr_vigencias_futuras', 'U') IS NULL
CREATE TABLE dbo.btcr_vigencias_futuras (
    id                  INT            IDENTITY(1,1) NOT NULL,
    bitacora_id         INT            NOT NULL,
    vigencia_exec       INT            NOT NULL,   -- año de ejecución
    sector              NVARCHAR(120)  NOT NULL,   -- sector individual (SIIF)
    valor_corriente_mmm DECIMAL(18,6)  NULL,
    CONSTRAINT PK_btcr_vigencias_futuras PRIMARY KEY (id),
    CONSTRAINT UQ_btcr_vigencias_futuras UNIQUE (bitacora_id, vigencia_exec, sector),
    CONSTRAINT FK_btcr_vf_bitacora FOREIGN KEY (bitacora_id)
        REFERENCES dbo.btcr_metadatos_bitacora(id)
);
GO

IF OBJECT_ID('dbo.btcr_deflactores_pib', 'U') IS NULL
CREATE TABLE dbo.btcr_deflactores_pib (
    id                INT            IDENTITY(1,1) NOT NULL,
    bitacora_id       INT            NOT NULL,
    anio              INT            NOT NULL,
    deflactor         DECIMAL(18,9)  NULL,   -- DEFLACTOR PIB BASE 2026
    pib_corriente_mmm DECIMAL(18,6)  NULL,
    pib_constante_mmm DECIMAL(18,6)  NULL,
    CONSTRAINT PK_btcr_deflactores_pib PRIMARY KEY (id),
    CONSTRAINT UQ_btcr_deflactores_pib UNIQUE (bitacora_id, anio),
    CONSTRAINT FK_btcr_deflactores_bitacora FOREIGN KEY (bitacora_id)
        REFERENCES dbo.btcr_metadatos_bitacora(id)
);
GO

-- ============================================================
-- SECCIÓN 6 — Ejecución sectorial (entidades y serie mensual)
-- ============================================================
IF OBJECT_ID('dbo.btcr_ejecucion_sectorial_entidades', 'U') IS NULL
CREATE TABLE dbo.btcr_ejecucion_sectorial_entidades (
    id               INT            IDENTITY(1,1) NOT NULL,
    bitacora_id      INT            NOT NULL,
    vigencia         INT            NOT NULL,
    sector           NVARCHAR(120)  NOT NULL,
    entidad          NVARCHAR(250)  NOT NULL,
    apr_vigente_mmm  DECIMAL(18,6)  NULL,
    compromisos_mmm  DECIMAL(18,6)  NULL,
    obligaciones_mmm DECIMAL(18,6)  NULL,
    pagos_mmm        DECIMAL(18,6)  NULL,
    pct_c_av         DECIMAL(9,4)   NULL,
    pct_o_av         DECIMAL(9,4)   NULL,
    pct_p_av         DECIMAL(9,4)   NULL,
    CONSTRAINT PK_btcr_ejecucion_sectorial_entidades PRIMARY KEY (id),
    CONSTRAINT UQ_btcr_ejecucion_sectorial_entidades UNIQUE (bitacora_id, vigencia, entidad),
    CONSTRAINT FK_btcr_ejec_sect_ent_bitacora FOREIGN KEY (bitacora_id)
        REFERENCES dbo.btcr_metadatos_bitacora(id)
);
GO

IF OBJECT_ID('dbo.btcr_ejecucion_sectorial_mensual', 'U') IS NULL
CREATE TABLE dbo.btcr_ejecucion_sectorial_mensual (
    id                     INT            IDENTITY(1,1) NOT NULL,
    bitacora_id            INT            NOT NULL,
    vigencia               INT            NOT NULL,
    sector                 NVARCHAR(120)  NOT NULL,
    mes                    INT            NOT NULL,
    pct_compromisos_2025   DECIMAL(9,4)   NULL,
    pct_compromisos_2024   DECIMAL(9,4)   NULL,
    pct_compromisos_prom   DECIMAL(9,4)   NULL,
    pct_compromisos_mejor  DECIMAL(9,4)   NULL,
    pct_obligaciones_2025  DECIMAL(9,4)   NULL,
    pct_obligaciones_2024  DECIMAL(9,4)   NULL,
    pct_obligaciones_prom  DECIMAL(9,4)   NULL,
    pct_obligaciones_mejor DECIMAL(9,4)   NULL,
    CONSTRAINT PK_btcr_ejecucion_sectorial_mensual PRIMARY KEY (id),
    CONSTRAINT CK_btcr_ejec_sect_mensual_mes CHECK (mes BETWEEN 1 AND 12),
    CONSTRAINT FK_btcr_ejec_sect_men_bitacora FOREIGN KEY (bitacora_id)
        REFERENCES dbo.btcr_metadatos_bitacora(id)
);
GO

-- ============================================================
-- SECCIÓN 7 — Crédito externo (SCCI)
-- ============================================================
IF OBJECT_ID('dbo.btcr_credito_portafolio', 'U') IS NULL
CREATE TABLE dbo.btcr_credito_portafolio (
    id               INT            IDENTITY(1,1) NOT NULL,
    bitacora_id      INT            NOT NULL,
    nombre           NVARCHAR(300)  NOT NULL,
    nombre_corto     NVARCHAR(150)  NULL,
    fuente           NVARCHAR(20)   NOT NULL,   -- BID, BM, CAF
    contrato         NVARCHAR(50)   NULL,
    sector           NVARCHAR(120)  NOT NULL,
    monto_usd        DECIMAL(18,2)  NULL,
    desembolsado_usd DECIMAL(18,2)  NULL,
    CONSTRAINT PK_btcr_credito_portafolio PRIMARY KEY (id),
    CONSTRAINT FK_btcr_credito_port_bitacora FOREIGN KEY (bitacora_id)
        REFERENCES dbo.btcr_metadatos_bitacora(id)
);
GO

IF OBJECT_ID('dbo.btcr_credito_ejecucion_entidad', 'U') IS NULL
CREATE TABLE dbo.btcr_credito_ejecucion_entidad (
    id              INT            IDENTITY(1,1) NOT NULL,
    bitacora_id     INT            NOT NULL,
    entidad         NVARCHAR(250)  NOT NULL,
    sector          NVARCHAR(120)  NOT NULL,
    apr_inicial_mmm DECIMAL(18,6)  NULL,
    apr_vigente_mmm DECIMAL(18,6)  NULL,
    compromiso_mmm  DECIMAL(18,6)  NULL,
    obligacion_mmm  DECIMAL(18,6)  NULL,
    pago_mmm        DECIMAL(18,6)  NULL,
    pct_com         DECIMAL(9,4)   NULL,
    pct_ejec        DECIMAL(9,4)   NULL,
    pct_pago        DECIMAL(9,4)   NULL,
    CONSTRAINT PK_btcr_credito_ejecucion_entidad PRIMARY KEY (id),
    CONSTRAINT UQ_btcr_credito_ejecucion_entidad UNIQUE (bitacora_id, entidad),
    CONSTRAINT FK_btcr_credito_ent_bitacora FOREIGN KEY (bitacora_id)
        REFERENCES dbo.btcr_metadatos_bitacora(id)
);
GO

IF OBJECT_ID('dbo.btcr_credito_ejecucion_historica', 'U') IS NULL
CREATE TABLE dbo.btcr_credito_ejecucion_historica (
    id               INT            IDENTITY(1,1) NOT NULL,
    bitacora_id      INT            NOT NULL,
    anio             INT            NOT NULL,
    pct_comprometido DECIMAL(9,4)   NULL,
    pct_ejecutado    DECIMAL(9,4)   NULL,
    pct_pagado       DECIMAL(9,4)   NULL,
    vigente_mmm      DECIMAL(18,6)  NULL,
    comprometido_mmm DECIMAL(18,6)  NULL,
    ejecutado_mmm    DECIMAL(18,6)  NULL,
    pagado_mmm       DECIMAL(18,6)  NULL,
    CONSTRAINT PK_btcr_credito_ejecucion_historica PRIMARY KEY (id),
    CONSTRAINT UQ_btcr_credito_ejecucion_historica UNIQUE (bitacora_id, anio),
    CONSTRAINT FK_btcr_credito_hist_bitacora FOREIGN KEY (bitacora_id)
        REFERENCES dbo.btcr_metadatos_bitacora(id)
);
GO

-- ============================================================
-- SECCIÓN 8 — Sistema General de Participaciones (SGP)
-- ============================================================
IF OBJECT_ID('dbo.btcr_sgp_historico_participacion', 'U') IS NULL
CREATE TABLE dbo.btcr_sgp_historico_participacion (
    id                       INT            IDENTITY(1,1) NOT NULL,
    bitacora_id              INT            NOT NULL,
    vigencia                 INT            NOT NULL,
    educacion_mmm            DECIMAL(18,6)  NULL,
    salud_mmm                DECIMAL(18,6)  NULL,
    agua_potable_mmm         DECIMAL(18,6)  NULL,
    proposito_general_mmm    DECIMAL(18,6)  NULL,
    alimentacion_escolar_mmm DECIMAL(18,6)  NULL,
    riberenos_mmm            DECIMAL(18,6)  NULL,
    resguardos_indigenas_mmm DECIMAL(18,6)  NULL,
    fonpet_ae_mmm            DECIMAL(18,6)  NULL,
    total_mmm                DECIMAL(18,6)  NULL,
    CONSTRAINT PK_btcr_sgp_historico_participacion PRIMARY KEY (id),
    CONSTRAINT UQ_btcr_sgp_historico_participacion UNIQUE (bitacora_id, vigencia),
    CONSTRAINT FK_btcr_sgp_part_bitacora FOREIGN KEY (bitacora_id)
        REFERENCES dbo.btcr_metadatos_bitacora(id)
);
GO

IF OBJECT_ID('dbo.btcr_sgp_historico_componentes', 'U') IS NULL
CREATE TABLE dbo.btcr_sgp_historico_componentes (
    id            INT            IDENTITY(1,1) NOT NULL,
    bitacora_id   INT            NOT NULL,
    vigencia      INT            NOT NULL,
    orden         INT            NOT NULL,   -- orden de la fila en la hoja fuente
    participacion NVARCHAR(120)  NOT NULL,   -- participación padre
    componente    NVARCHAR(120)  NOT NULL,
    es_total      BIT            NULL CONSTRAINT DF_btcr_sgp_comp_es_total DEFAULT (0),
    valor_mmm     DECIMAL(18,6)  NULL,
    CONSTRAINT PK_btcr_sgp_historico_componentes PRIMARY KEY (id),
    CONSTRAINT UQ_btcr_sgp_historico_componentes UNIQUE (bitacora_id, vigencia, orden),
    CONSTRAINT FK_btcr_sgp_comp_bitacora FOREIGN KEY (bitacora_id)
        REFERENCES dbo.btcr_metadatos_bitacora(id)
);
GO

-- ============================================================
-- Índices para las consultas frecuentes de la API
-- (equivalentes a los del origen SQLite; se normaliza el nombre
--  idx_btcr_vigencias_futuras_año -> _anio para evitar tildes)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_btcr_ejecucion_historica_vigencia' AND object_id = OBJECT_ID('dbo.btcr_ejecucion_historica'))
    CREATE INDEX idx_btcr_ejecucion_historica_vigencia ON dbo.btcr_ejecucion_historica(vigencia);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_btcr_sector_vigencia' AND object_id = OBJECT_ID('dbo.btcr_apropiacion_por_sector'))
    CREATE INDEX idx_btcr_sector_vigencia ON dbo.btcr_apropiacion_por_sector(vigencia, sector);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_btcr_sectorial_entidad' AND object_id = OBJECT_ID('dbo.btcr_ejecucion_sectorial_entidades'))
    CREATE INDEX idx_btcr_sectorial_entidad ON dbo.btcr_ejecucion_sectorial_entidades(vigencia, sector, entidad);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_btcr_vigencias_futuras_anio' AND object_id = OBJECT_ID('dbo.btcr_vigencias_futuras'))
    CREATE INDEX idx_btcr_vigencias_futuras_anio ON dbo.btcr_vigencias_futuras(vigencia_exec);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_btcr_credito_entidad' AND object_id = OBJECT_ID('dbo.btcr_credito_ejecucion_entidad'))
    CREATE INDEX idx_btcr_credito_entidad ON dbo.btcr_credito_ejecucion_entidad(entidad);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_btcr_sgp_historico_vigencia' AND object_id = OBJECT_ID('dbo.btcr_sgp_historico_participacion'))
    CREATE INDEX idx_btcr_sgp_historico_vigencia ON dbo.btcr_sgp_historico_participacion(vigencia);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_btcr_sgp_componentes_orden' AND object_id = OBJECT_ID('dbo.btcr_sgp_historico_componentes'))
    CREATE INDEX idx_btcr_sgp_componentes_orden ON dbo.btcr_sgp_historico_componentes(orden, vigencia);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_btcr_regionalizacion_vigencia' AND object_id = OBJECT_ID('dbo.btcr_regionalizacion'))
    CREATE INDEX idx_btcr_regionalizacion_vigencia ON dbo.btcr_regionalizacion(vigencia, region);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_btcr_regionalizacion_dane' AND object_id = OBJECT_ID('dbo.btcr_regionalizacion'))
    CREATE INDEX idx_btcr_regionalizacion_dane ON dbo.btcr_regionalizacion(codigo_dane, vigencia);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_btcr_pgn_ej_anio_fase' AND object_id = OBJECT_ID('dbo.btcr_pgn_ejecucion'))
    CREATE INDEX idx_btcr_pgn_ej_anio_fase ON dbo.btcr_pgn_ejecucion(anio, fase);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_btcr_pgn_ej_concepto' AND object_id = OBJECT_ID('dbo.btcr_pgn_ejecucion'))
    CREATE INDEX idx_btcr_pgn_ej_concepto ON dbo.btcr_pgn_ejecucion(concepto_id);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_btcr_pgn_co_padre' AND object_id = OBJECT_ID('dbo.btcr_pgn_concepto'))
    CREATE INDEX idx_btcr_pgn_co_padre ON dbo.btcr_pgn_concepto(padre_id);
GO
