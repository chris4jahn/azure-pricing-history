-- Quick check for pricing data collection progress
-- Run this every few minutes to see if data is being inserted

-- Check snapshot runs
SELECT 
    'Snapshot Runs' as Check,
    COUNT(*) as Count,
    MAX(startedUtc) as LatestRun,
    MAX(status) as Status
FROM dbo.PriceSnapshotRuns;

-- Check pricing records
SELECT 
    'Pricing Records' as Check,
    COUNT(*) as Count,
    COUNT(DISTINCT currencyCode) as Currencies,
    MAX(lastSeenUtc) as LastUpdated
FROM dbo.AzureRetailPrices;

-- If data exists, show sample
SELECT TOP 5
    productName,
    skuName,
    meterName,
    retailPrice,
    currencyCode,
    armRegionName
FROM dbo.AzureRetailPrices
ORDER BY lastSeenUtc DESC;
