/* ==========================================================================
   REVERSA — elimina la Bitácora 2026-II (esquema btcr_).
   Transaccional e idempotente. NO restaura la Evolución PGN previa (global).
   ========================================================================== */
SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRAN;

DECLARE @periodo nvarchar(20) = N'2026-II';
DECLARE @bid INT;
SELECT @bid = id FROM dbo.btcr_metadatos_bitacora WHERE periodo = @periodo;

IF @bid IS NULL
BEGIN
    PRINT 'La bitacora 2026-II no existe; nada que revertir.';
END
ELSE
BEGIN
    DELETE FROM dbo.btcr_inversion_transformaciones     WHERE bitacora_id = @bid;
    DELETE FROM dbo.btcr_inversion_componentes_pnd       WHERE bitacora_id = @bid;
    DELETE FROM dbo.btcr_ejecucion_transformaciones      WHERE bitacora_id = @bid;
    DELETE FROM dbo.btcr_apropiacion_por_sector          WHERE bitacora_id = @bid;
    DELETE FROM dbo.btcr_compromisos_pct_por_sector      WHERE bitacora_id = @bid;
    DELETE FROM dbo.btcr_obligaciones_pct_por_sector     WHERE bitacora_id = @bid;
    DELETE FROM dbo.btcr_pagos_pct_por_sector            WHERE bitacora_id = @bid;
    DELETE FROM dbo.btcr_ejecucion_historica             WHERE bitacora_id = @bid;
    DELETE FROM dbo.btcr_ejecucion_sectorial_entidades   WHERE bitacora_id = @bid;
    DELETE FROM dbo.btcr_ejecucion_sectorial_mensual     WHERE bitacora_id = @bid;
    DELETE FROM dbo.btcr_regionalizacion                 WHERE bitacora_id = @bid;
    DELETE FROM dbo.btcr_regionalizacion_sectores        WHERE bitacora_id = @bid;
    DELETE FROM dbo.btcr_vigencias_futuras               WHERE bitacora_id = @bid;
    DELETE FROM dbo.btcr_deflactores_pib                 WHERE bitacora_id = @bid;
    DELETE FROM dbo.btcr_credito_portafolio              WHERE bitacora_id = @bid;
    DELETE FROM dbo.btcr_credito_ejecucion_entidad       WHERE bitacora_id = @bid;
    DELETE FROM dbo.btcr_credito_ejecucion_historica     WHERE bitacora_id = @bid;
    DELETE FROM dbo.btcr_sgp_historico_participacion      WHERE bitacora_id = @bid;
    DELETE FROM dbo.btcr_sgp_historico_componentes        WHERE bitacora_id = @bid;
    DELETE FROM dbo.btcr_metadatos_bitacora              WHERE id = @bid;
    PRINT 'Bitacora 2026-II (id=' + CAST(@bid AS varchar(10)) + ') eliminada.';
END

COMMIT;
