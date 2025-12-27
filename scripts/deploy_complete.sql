-- ========================================
-- Azure Pricing History - Complete Schema Deployment
-- Execute this script in Azure Portal Query Editor or any SQL client
-- ========================================

-- Step 1: Create Tables
-- ========================================

-- Main pricing table
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[AzureRetailPrices]') AND type in (N'U'))
BEGIN
    CREATE TABLE dbo.AzureRetailPrices (
        meterId NVARCHAR(100) NOT NULL,
        effectiveStartDate DATETIME2 NOT NULL,
        currencyCode NVARCHAR(10) NOT NULL,
        retailPrice DECIMAL(38,10) NULL,
        unitPrice DECIMAL(38,10) NULL,
        unitOfMeasure NVARCHAR(100) NULL,
        armRegionName NVARCHAR(200) NULL,
        location NVARCHAR(200) NULL,
        productId NVARCHAR(100) NULL,
        productName NVARCHAR(500) NULL,
        skuId NVARCHAR(200) NULL,
        skuName NVARCHAR(200) NULL,
        serviceId NVARCHAR(100) NULL,
        serviceName NVARCHAR(200) NULL,
        serviceFamily NVARCHAR(200) NULL,
        meterName NVARCHAR(300) NULL,
        armSkuName NVARCHAR(200) NULL,
        reservationTerm NVARCHAR(50) NULL,
        type NVARCHAR(50) NULL,
        isPrimaryMeterRegion BIT NULL,
        tierMinimumUnits DECIMAL(38,10) NULL,
        availabilityId NVARCHAR(100) NULL,
        lastSeenUtc DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        
        CONSTRAINT PK_AzureRetailPrices PRIMARY KEY CLUSTERED (meterId, effectiveStartDate, currencyCode)
    );
    PRINT '✓ Created dbo.AzureRetailPrices table';
END
ELSE
BEGIN
    PRINT '  dbo.AzureRetailPrices table already exists';
END

-- Snapshot runs table
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[PriceSnapshotRuns]') AND type in (N'U'))
BEGIN
    CREATE TABLE dbo.PriceSnapshotRuns (
        snapshotId NVARCHAR(8) NOT NULL,
        currencyCode NVARCHAR(10) NOT NULL,
        startedUtc DATETIME2 NOT NULL,
        finishedUtc DATETIME2 NULL,
        status NVARCHAR(20) NOT NULL,
        itemCount INT NULL,
        
        CONSTRAINT PK_PriceSnapshotRuns PRIMARY KEY CLUSTERED (snapshotId, currencyCode),
        CONSTRAINT CK_PriceSnapshotRuns_Status CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED'))
    );
    PRINT '✓ Created dbo.PriceSnapshotRuns table';
END
ELSE
BEGIN
    PRINT '  dbo.PriceSnapshotRuns table already exists';
END

-- Snapshot map table
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[AzureRetailPricesSnapshotMap]') AND type in (N'U'))
BEGIN
    CREATE TABLE dbo.AzureRetailPricesSnapshotMap (
        meterId NVARCHAR(100) NOT NULL,
        effectiveStartDate DATETIME2 NOT NULL,
        currencyCode NVARCHAR(10) NOT NULL,
        snapshotId NVARCHAR(8) NOT NULL,
        
        CONSTRAINT PK_AzureRetailPricesSnapshotMap PRIMARY KEY CLUSTERED (meterId, effectiveStartDate, currencyCode, snapshotId),
        CONSTRAINT FK_AzureRetailPricesSnapshotMap_Price FOREIGN KEY (meterId, effectiveStartDate, currencyCode)
            REFERENCES dbo.AzureRetailPrices (meterId, effectiveStartDate, currencyCode),
        CONSTRAINT FK_AzureRetailPricesSnapshotMap_Snapshot FOREIGN KEY (snapshotId, currencyCode)
            REFERENCES dbo.PriceSnapshotRuns (snapshotId, currencyCode)
    );
    PRINT '✓ Created dbo.AzureRetailPricesSnapshotMap table';
END
ELSE
BEGIN
    PRINT '  dbo.AzureRetailPricesSnapshotMap table already exists';
END

PRINT '';
PRINT 'Step 2: Creating Indexes...';
PRINT '';

-- Indexes
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_AzureRetailPrices_ByRegionService' AND object_id = OBJECT_ID('dbo.AzureRetailPrices'))
BEGIN
    CREATE NONCLUSTERED INDEX IX_AzureRetailPrices_ByRegionService
        ON dbo.AzureRetailPrices (armRegionName, serviceFamily, serviceName)
        INCLUDE (meterId, retailPrice, unitPrice);
    PRINT '✓ Created IX_AzureRetailPrices_ByRegionService index';
END
ELSE
BEGIN
    PRINT '  IX_AzureRetailPrices_ByRegionService index already exists';
END

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_AzureRetailPrices_ByProductSku' AND object_id = OBJECT_ID('dbo.AzureRetailPrices'))
BEGIN
    CREATE NONCLUSTERED INDEX IX_AzureRetailPrices_ByProductSku
        ON dbo.AzureRetailPrices (productName, skuName)
        INCLUDE (meterId, retailPrice, currencyCode);
    PRINT '✓ Created IX_AzureRetailPrices_ByProductSku index';
END
ELSE
BEGIN
    PRINT '  IX_AzureRetailPrices_ByProductSku index already exists';
END

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_AzureRetailPrices_EffectiveDate' AND object_id = OBJECT_ID('dbo.AzureRetailPrices'))
BEGIN
    CREATE NONCLUSTERED INDEX IX_AzureRetailPrices_EffectiveDate
        ON dbo.AzureRetailPrices (effectiveStartDate DESC)
        INCLUDE (meterId, currencyCode, retailPrice);
    PRINT '✓ Created IX_AzureRetailPrices_EffectiveDate index';
END
ELSE
BEGIN
    PRINT '  IX_AzureRetailPrices_EffectiveDate index already exists';
END

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_PriceSnapshotRuns_Status' AND object_id = OBJECT_ID('dbo.PriceSnapshotRuns'))
BEGIN
    CREATE NONCLUSTERED INDEX IX_PriceSnapshotRuns_Status
        ON dbo.PriceSnapshotRuns (status, startedUtc DESC);
    PRINT '✓ Created IX_PriceSnapshotRuns_Status index';
END
ELSE
BEGIN
    PRINT '  IX_PriceSnapshotRuns_Status index already exists';
END

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_AzureRetailPricesSnapshotMap_BySnapshot' AND object_id = OBJECT_ID('dbo.AzureRetailPricesSnapshotMap'))
BEGIN
    CREATE NONCLUSTERED INDEX IX_AzureRetailPricesSnapshotMap_BySnapshot
        ON dbo.AzureRetailPricesSnapshotMap (snapshotId, currencyCode);
    PRINT '✓ Created IX_AzureRetailPricesSnapshotMap_BySnapshot index';
END
ELSE
BEGIN
    PRINT '  IX_AzureRetailPricesSnapshotMap_BySnapshot index already exists';
END

PRINT '';
PRINT 'Step 3: Creating Views...';
PRINT '';

-- View: Current Retail Prices
IF OBJECT_ID('dbo.v_CurrentRetailPrices', 'V') IS NOT NULL
    DROP VIEW dbo.v_CurrentRetailPrices;

EXEC('
CREATE VIEW dbo.v_CurrentRetailPrices
AS
SELECT 
    p.meterId,
    p.currencyCode,
    p.effectiveStartDate,
    p.retailPrice,
    p.unitPrice,
    p.unitOfMeasure,
    p.armRegionName,
    p.location,
    p.productName,
    p.skuName,
    p.serviceName,
    p.serviceFamily,
    p.meterName,
    p.armSkuName,
    p.type,
    p.lastSeenUtc
FROM dbo.AzureRetailPrices p
INNER JOIN (
    SELECT 
        meterId,
        currencyCode,
        MAX(effectiveStartDate) AS latestEffectiveDate
    FROM dbo.AzureRetailPrices
    GROUP BY meterId, currencyCode
) latest ON p.meterId = latest.meterId 
        AND p.currencyCode = latest.currencyCode
        AND p.effectiveStartDate = latest.latestEffectiveDate
');
PRINT '✓ Created dbo.v_CurrentRetailPrices view';

-- Function: Snapshot Retail Prices
IF OBJECT_ID('dbo.fn_SnapshotRetailPrices', 'IF') IS NOT NULL
    DROP FUNCTION dbo.fn_SnapshotRetailPrices;

EXEC('
CREATE FUNCTION dbo.fn_SnapshotRetailPrices
(
    @snapshotId NVARCHAR(8),
    @currencyCode NVARCHAR(10) = NULL
)
RETURNS TABLE
AS
RETURN
(
    SELECT 
        p.meterId,
        p.effectiveStartDate,
        p.currencyCode,
        p.retailPrice,
        p.unitPrice,
        p.unitOfMeasure,
        p.armRegionName,
        p.location,
        p.productId,
        p.productName,
        p.skuId,
        p.skuName,
        p.serviceId,
        p.serviceName,
        p.serviceFamily,
        p.meterName,
        p.armSkuName,
        p.reservationTerm,
        p.type,
        p.isPrimaryMeterRegion,
        p.tierMinimumUnits,
        p.availabilityId,
        p.lastSeenUtc,
        m.snapshotId
    FROM dbo.AzureRetailPrices p
    INNER JOIN dbo.AzureRetailPricesSnapshotMap m
        ON p.meterId = m.meterId
        AND p.effectiveStartDate = m.effectiveStartDate
        AND p.currencyCode = m.currencyCode
    WHERE m.snapshotId = @snapshotId
        AND (@currencyCode IS NULL OR m.currencyCode = @currencyCode)
)
');
PRINT '✓ Created dbo.fn_SnapshotRetailPrices function';

-- View: Price History
IF OBJECT_ID('dbo.v_PriceHistory', 'V') IS NOT NULL
    DROP VIEW dbo.v_PriceHistory;

EXEC('
CREATE VIEW dbo.v_PriceHistory
AS
SELECT 
    meterId,
    currencyCode,
    effectiveStartDate,
    retailPrice,
    unitPrice,
    productName,
    skuName,
    serviceName,
    serviceFamily,
    armRegionName,
    location,
    meterName,
    lastSeenUtc,
    ROW_NUMBER() OVER (
        PARTITION BY meterId, currencyCode 
        ORDER BY effectiveStartDate DESC
    ) AS priceVersion
FROM dbo.AzureRetailPrices
');
PRINT '✓ Created dbo.v_PriceHistory view';

-- View: Service Pricing Summary
IF OBJECT_ID('dbo.v_ServicePricingSummary', 'V') IS NOT NULL
    DROP VIEW dbo.v_ServicePricingSummary;

EXEC('
CREATE VIEW dbo.v_ServicePricingSummary
AS
SELECT 
    serviceFamily,
    serviceName,
    currencyCode,
    armRegionName,
    COUNT(DISTINCT meterId) AS meterCount,
    MIN(retailPrice) AS minPrice,
    MAX(retailPrice) AS maxPrice,
    AVG(retailPrice) AS avgPrice,
    MAX(lastSeenUtc) AS lastUpdated
FROM dbo.AzureRetailPrices
WHERE retailPrice > 0
GROUP BY serviceFamily, serviceName, currencyCode, armRegionName
');
PRINT '✓ Created dbo.v_ServicePricingSummary view';

-- View: Snapshot Run Summary
IF OBJECT_ID('dbo.v_SnapshotRunSummary', 'V') IS NOT NULL
    DROP VIEW dbo.v_SnapshotRunSummary;

EXEC('
CREATE VIEW dbo.v_SnapshotRunSummary
AS
SELECT 
    snapshotId,
    currencyCode,
    startedUtc,
    finishedUtc,
    status,
    itemCount,
    DATEDIFF(SECOND, startedUtc, finishedUtc) AS durationSeconds,
    CASE 
        WHEN status = ''SUCCEEDED'' AND itemCount > 0 
        THEN CAST(itemCount AS FLOAT) / NULLIF(DATEDIFF(SECOND, startedUtc, finishedUtc), 0)
        ELSE NULL
    END AS itemsPerSecond
FROM dbo.PriceSnapshotRuns
');
PRINT '✓ Created dbo.v_SnapshotRunSummary view';

PRINT '';
PRINT 'Step 4: Granting Permissions...';
PRINT '';

-- Create user and grant permissions for Function App
DECLARE @FunctionAppName NVARCHAR(100) = 'func-pricing-dev-gwc';
DECLARE @SQL NVARCHAR(MAX);

IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = @FunctionAppName)
BEGIN
    SET @SQL = 'CREATE USER [' + @FunctionAppName + '] FROM EXTERNAL PROVIDER';
    EXEC sp_executesql @SQL;
    PRINT '✓ Created user [' + @FunctionAppName + ']';
END
ELSE
BEGIN
    PRINT '  User [' + @FunctionAppName + '] already exists';
END

-- Grant db_datareader
IF IS_ROLEMEMBER('db_datareader', @FunctionAppName) = 0
BEGIN
    SET @SQL = 'ALTER ROLE db_datareader ADD MEMBER [' + @FunctionAppName + ']';
    EXEC sp_executesql @SQL;
    PRINT '✓ Granted db_datareader role to [' + @FunctionAppName + ']';
END
ELSE
BEGIN
    PRINT '  [' + @FunctionAppName + '] already has db_datareader role';
END

-- Grant db_datawriter
IF IS_ROLEMEMBER('db_datawriter', @FunctionAppName) = 0
BEGIN
    SET @SQL = 'ALTER ROLE db_datawriter ADD MEMBER [' + @FunctionAppName + ']';
    EXEC sp_executesql @SQL;
    PRINT '✓ Granted db_datawriter role to [' + @FunctionAppName + ']';
END
ELSE
BEGIN
    PRINT '  [' + @FunctionAppName + '] already has db_datawriter role';
END

PRINT '';
PRINT '==========================================';
PRINT '✓ SCHEMA DEPLOYMENT COMPLETED!';
PRINT '==========================================';
PRINT '';
PRINT 'Tables created: 3';
PRINT 'Indexes created: 6';
PRINT 'Views created: 4';
PRINT 'Functions created: 1';
PRINT 'Permissions granted: db_datareader, db_datawriter';
PRINT '';
