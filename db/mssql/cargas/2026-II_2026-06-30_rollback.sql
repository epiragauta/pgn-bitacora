/* ==========================================================================
   REVERSA — elimina la Bitácora 2026-II de dnp_dpip.
   Transaccional e idempotente. NO restaura la Evolución PGN previa (global).
   ========================================================================== */
SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRAN;

DECLARE @periodo nvarchar(20) = N'2026-II';
DECLARE @bid INT;
SELECT @bid = id FROM dbo.metadatos_bitacora WHERE periodo = @periodo;

IF @bid IS NULL
BEGIN
    PRINT 'La bitacora 2026-II no existe; nada que revertir.';
END
ELSE
BEGIN
    DELETE FROM dbo.inversion_transformaciones     WHERE bitacora_id = @bid;
    DELETE FROM dbo.inversion_componentes_pnd       WHERE bitacora_id = @bid;
    DELETE FROM dbo.ejecucion_transformaciones      WHERE bitacora_id = @bid;
    DELETE FROM dbo.apropiacion_por_sector          WHERE bitacora_id = @bid;
    DELETE FROM dbo.compromisos_pct_por_sector      WHERE bitacora_id = @bid;
    DELETE FROM dbo.obligaciones_pct_por_sector     WHERE bitacora_id = @bid;
    DELETE FROM dbo.pagos_pct_por_sector            WHERE bitacora_id = @bid;
    DELETE FROM dbo.ejecucion_historica             WHERE bitacora_id = @bid;
    DELETE FROM dbo.ejecucion_sectorial_entidades   WHERE bitacora_id = @bid;
    DELETE FROM dbo.ejecucion_sectorial_mensual     WHERE bitacora_id = @bid;
    DELETE FROM dbo.regionalizacion                 WHERE bitacora_id = @bid;
    DELETE FROM dbo.regionalizacion_sectores        WHERE bitacora_id = @bid;
    DELETE FROM dbo.vigencias_futuras               WHERE bitacora_id = @bid;
    DELETE FROM dbo.deflactores_pib                 WHERE bitacora_id = @bid;
    DELETE FROM dbo.credito_portafolio              WHERE bitacora_id = @bid;
    DELETE FROM dbo.credito_ejecucion_entidad       WHERE bitacora_id = @bid;
    DELETE FROM dbo.credito_ejecucion_historica     WHERE bitacora_id = @bid;
    DELETE FROM dbo.sgp_historico_participacion      WHERE bitacora_id = @bid;
    DELETE FROM dbo.sgp_historico_componentes        WHERE bitacora_id = @bid;
    DELETE FROM dbo.metadatos_bitacora              WHERE id = @bid;
    PRINT 'Bitacora 2026-II (id=' + CAST(@bid AS varchar(10)) + ') eliminada.';
END

COMMIT;
