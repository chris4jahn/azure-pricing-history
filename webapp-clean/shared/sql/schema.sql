-- Azure Pricing History - Database Schema
-- Creates tables for storing Azure Retail Prices data with historicization

-- 1. Main pricing table with idempotency key
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
GO

-- Indexes for common query patterns
CREATE NONCLUSTERED INDEX IX_AzureRetailPrices_ByRegionService
    ON dbo.AzureRetailPrices (armRegionName, serviceFamily, serviceName)
    INCLUDE (meterId, retailPrice, unitPrice);
GO

CREATE NONCLUSTERED INDEX IX_AzureRetailPrices_ByProductSku
    ON dbo.AzureRetailPrices (productName, skuName)
    INCLUDE (meterId, retailPrice, currencyCode);
GO

CREATE NONCLUSTERED INDEX IX_AzureRetailPrices_EffectiveDate
    ON dbo.AzureRetailPrices (effectiveStartDate DESC)
    INCLUDE (meterId, currencyCode, retailPrice);
GO

-- 2. Snapshot run tracking table
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
GO

CREATE NONCLUSTERED INDEX IX_PriceSnapshotRuns_Status
    ON dbo.PriceSnapshotRuns (status, startedUtc DESC);
GO

-- 3. Mapping table to track which prices belong to which snapshot
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
GO

CREATE NONCLUSTERED INDEX IX_AzureRetailPricesSnapshotMap_BySnapshot
    ON dbo.AzureRetailPricesSnapshotMap (snapshotId, currencyCode);
GO
