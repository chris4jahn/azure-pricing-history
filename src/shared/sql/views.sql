-- Azure Pricing History - Database Views
-- Provides convenient views for querying current and historical pricing data

-- 1. Current Retail Prices View
-- Returns the latest price for each meter and currency combination
CREATE OR ALTER VIEW dbo.v_CurrentRetailPrices
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
        AND p.effectiveStartDate = latest.latestEffectiveDate;
GO

-- 2. Snapshot Retail Prices Function
-- Returns all prices that belong to a specific snapshot
CREATE OR ALTER FUNCTION dbo.fn_SnapshotRetailPrices
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
);
GO

-- 3. Price History View
-- Shows price changes over time for each meter
CREATE OR ALTER VIEW dbo.v_PriceHistory
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
FROM dbo.AzureRetailPrices;
GO

-- 4. Service Summary View
-- Aggregates pricing information by service family
CREATE OR ALTER VIEW dbo.v_ServicePricingSummary
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
GROUP BY serviceFamily, serviceName, currencyCode, armRegionName;
GO

-- 5. Snapshot Run Summary View
-- Provides overview of all snapshot runs
CREATE OR ALTER VIEW dbo.v_SnapshotRunSummary
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
        WHEN status = 'SUCCEEDED' AND itemCount > 0 
        THEN CAST(itemCount AS FLOAT) / NULLIF(DATEDIFF(SECOND, startedUtc, finishedUtc), 0)
        ELSE NULL
    END AS itemsPerSecond
FROM dbo.PriceSnapshotRuns;
GO

-- Example usage:
-- SELECT * FROM dbo.v_CurrentRetailPrices WHERE serviceFamily = 'Compute';
-- SELECT * FROM dbo.fn_SnapshotRetailPrices('202512', 'USD');
-- SELECT * FROM dbo.v_PriceHistory WHERE meterId = 'xxx' ORDER BY effectiveStartDate DESC;
-- SELECT * FROM dbo.v_ServicePricingSummary ORDER BY meterCount DESC;
-- SELECT * FROM dbo.v_SnapshotRunSummary ORDER BY startedUtc DESC;
