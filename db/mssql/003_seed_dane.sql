-- ============================================================
-- 003_seed_dane.sql — Catálogo DANE de departamentos (base dnp_dpip)
--
-- Catálogo estático de las 33 entidades territoriales. Es la fuente
-- canónica de esta tabla: la migración de datos de la Fase 2 la
-- omite deliberadamente y usa este script.
--
-- Idempotente (MERGE): re-ejecutarlo actualiza nombres/regiones sin
-- duplicar filas ni romper las FK de regionalizacion.codigo_dane.
--
-- El código es TEXTO con cero a la izquierda ('05', '08'): nunca INT.
-- Requiere N'...' en los literales por las tildes (Boyacá, Chocó,
-- Nariño, Quindío, Archipiélago...).
-- ============================================================

SET NOCOUNT ON;
GO

MERGE dbo.dane_departamentos AS destino
USING (VALUES
    (N'05', N'Antioquia',                                                    N'ANDINA'),
    (N'08', N'Atlántico',                                                    N'CARIBE'),
    (N'11', N'Bogotá, D.C.',                                                 N'ANDINA'),
    (N'13', N'Bolívar',                                                      N'CARIBE'),
    (N'15', N'Boyacá',                                                       N'ANDINA'),
    (N'17', N'Caldas',                                                       N'ANDINA'),
    (N'18', N'Caquetá',                                                      N'AMAZONIA'),
    (N'19', N'Cauca',                                                        N'PACÍFICO'),
    (N'20', N'Cesar',                                                        N'CARIBE'),
    (N'23', N'Córdoba',                                                      N'CARIBE'),
    (N'25', N'Cundinamarca',                                                 N'ANDINA'),
    (N'27', N'Chocó',                                                        N'PACÍFICO'),
    (N'41', N'Huila',                                                        N'ANDINA'),
    (N'44', N'La Guajira',                                                   N'CARIBE'),
    (N'47', N'Magdalena',                                                    N'CARIBE'),
    (N'50', N'Meta',                                                         N'ORINOQUÍA'),
    (N'52', N'Nariño',                                                       N'PACÍFICO'),
    (N'54', N'Norte de Santander',                                           N'ANDINA'),
    (N'63', N'Quindío',                                                      N'ANDINA'),
    (N'66', N'Risaralda',                                                    N'ANDINA'),
    (N'68', N'Santander',                                                    N'ANDINA'),
    (N'70', N'Sucre',                                                        N'CARIBE'),
    (N'73', N'Tolima',                                                       N'ANDINA'),
    (N'76', N'Valle del Cauca',                                              N'PACÍFICO'),
    (N'81', N'Arauca',                                                       N'ORINOQUÍA'),
    (N'85', N'Casanare',                                                     N'ORINOQUÍA'),
    (N'86', N'Putumayo',                                                     N'AMAZONIA'),
    (N'88', N'Archipiélago de San Andrés, Providencia y Santa Catalina',     N'INSULAR'),
    (N'91', N'Amazonas',                                                     N'AMAZONIA'),
    (N'94', N'Guainía',                                                      N'AMAZONIA'),
    (N'95', N'Guaviare',                                                     N'AMAZONIA'),
    (N'97', N'Vaupés',                                                       N'AMAZONIA'),
    (N'99', N'Vichada',                                                      N'ORINOQUÍA')
) AS origen (codigo, nombre, region)
    ON destino.codigo = origen.codigo
WHEN MATCHED AND (destino.nombre <> origen.nombre OR destino.region <> origen.region)
    THEN UPDATE SET nombre = origen.nombre, region = origen.region
WHEN NOT MATCHED BY TARGET
    THEN INSERT (codigo, nombre, region) VALUES (origen.codigo, origen.nombre, origen.region);
GO

SELECT CONCAT('dane_departamentos: ', COUNT(*), ' filas') AS resultado FROM dbo.dane_departamentos;
GO
