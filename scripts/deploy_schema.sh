#!/bin/bash
# Deploy SQL schema to Azure SQL Database

set -e

SERVER="sql-pricing-dev-gwc"
DATABASE="sqldb-pricing-dev"
FUNCTION_APP="func-pricing-dev-gwc"

echo "=========================================="
echo "Azure Pricing History - Schema Deployment"
echo "=========================================="
echo ""
echo "Server: $SERVER.database.windows.net"
echo "Database: $DATABASE"
echo ""

# Read schema.sql and split by GO statements
echo "Step 1: Creating tables..."
echo ""

# Create main pricing table
az sql db query \
  --server "$SERVER" \
  --database "$DATABASE" \
  --auth-type ADIntegrated \
  --query "CREATE TABLE dbo.AzureRetailPrices (
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
)"

echo "✓ Created dbo.AzureRetailPrices table"

# Create snapshot runs table
az sql db query \
  --server "$SERVER" \
  --database "$DATABASE" \
  --auth-type ADIntegrated \
  --query "CREATE TABLE dbo.PriceSnapshotRuns (
    snapshotId NVARCHAR(8) NOT NULL,
    currencyCode NVARCHAR(10) NOT NULL,
    startedUtc DATETIME2 NOT NULL,
    finishedUtc DATETIME2 NULL,
    status NVARCHAR(20) NOT NULL,
    itemCount INT NULL,
    CONSTRAINT PK_PriceSnapshotRuns PRIMARY KEY CLUSTERED (snapshotId, currencyCode),
    CONSTRAINT CK_PriceSnapshotRuns_Status CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED'))
)"

echo "✓ Created dbo.PriceSnapshotRuns table"

# Create snapshot map table
az sql db query \
  --server "$SERVER" \
  --database "$DATABASE" \
  --auth-type ADIntegrated \
  --query "CREATE TABLE dbo.AzureRetailPricesSnapshotMap (
    meterId NVARCHAR(100) NOT NULL,
    effectiveStartDate DATETIME2 NOT NULL,
    currencyCode NVARCHAR(10) NOT NULL,
    snapshotId NVARCHAR(8) NOT NULL,
    CONSTRAINT PK_AzureRetailPricesSnapshotMap PRIMARY KEY CLUSTERED (meterId, effectiveStartDate, currencyCode, snapshotId),
    CONSTRAINT FK_AzureRetailPricesSnapshotMap_Price FOREIGN KEY (meterId, effectiveStartDate, currencyCode)
        REFERENCES dbo.AzureRetailPrices (meterId, effectiveStartDate, currencyCode),
    CONSTRAINT FK_AzureRetailPricesSnapshotMap_Snapshot FOREIGN KEY (snapshotId, currencyCode)
        REFERENCES dbo.PriceSnapshotRuns (snapshotId, currencyCode)
)"

echo "✓ Created dbo.AzureRetailPricesSnapshotMap table"
echo ""

echo "Step 2: Creating indexes..."
echo ""

# Indexes
az sql db query \
  --server "$SERVER" \
  --database "$DATABASE" \
  --auth-type ADIntegrated \
  --query "CREATE NONCLUSTERED INDEX IX_AzureRetailPrices_ByRegionService
    ON dbo.AzureRetailPrices (armRegionName, serviceFamily, serviceName)
    INCLUDE (meterId, retailPrice, unitPrice)"

echo "✓ Created IX_AzureRetailPrices_ByRegionService index"

az sql db query \
  --server "$SERVER" \
  --database "$DATABASE" \
  --auth-type ADIntegrated \
  --query "CREATE NONCLUSTERED INDEX IX_AzureRetailPrices_ByProductSku
    ON dbo.AzureRetailPrices (productName, skuName)
    INCLUDE (meterId, retailPrice, currencyCode)"

echo "✓ Created IX_AzureRetailPrices_ByProductSku index"

az sql db query \
  --server "$SERVER" \
  --database "$DATABASE" \
  --auth-type ADIntegrated \
  --query "CREATE NONCLUSTERED INDEX IX_AzureRetailPrices_EffectiveDate
    ON dbo.AzureRetailPrices (effectiveStartDate DESC)
    INCLUDE (meterId, currencyCode, retailPrice)"

echo "✓ Created IX_AzureRetailPrices_EffectiveDate index"

az sql db query \
  --server "$SERVER" \
  --database "$DATABASE" \
  --auth-type ADIntegrated \
  --query "CREATE NONCLUSTERED INDEX IX_PriceSnapshotRuns_Status
    ON dbo.PriceSnapshotRuns (status, startedUtc DESC)"

echo "✓ Created IX_PriceSnapshotRuns_Status index"

az sql db query \
  --server "$SERVER" \
  --database "$DATABASE" \
  --auth-type ADIntegrated \
  --query "CREATE NONCLUSTERED INDEX IX_AzureRetailPricesSnapshotMap_BySnapshot
    ON dbo.AzureRetailPricesSnapshotMap (snapshotId, currencyCode)"

echo "✓ Created IX_AzureRetailPricesSnapshotMap_BySnapshot index"
echo ""

echo "Step 3: Granting permissions to Function App..."
echo ""

# Create database user for Function App managed identity
az sql db query \
  --server "$SERVER" \
  --database "$DATABASE" \
  --auth-type ADIntegrated \
  --query "IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = '$FUNCTION_APP')
BEGIN
    CREATE USER [$FUNCTION_APP] FROM EXTERNAL PROVIDER
END"

echo "✓ Created user [$FUNCTION_APP]"

# Grant permissions
az sql db query \
  --server "$SERVER" \
  --database "$DATABASE" \
  --auth-type ADIntegrated \
  --query "ALTER ROLE db_datareader ADD MEMBER [$FUNCTION_APP]"

echo "✓ Granted db_datareader role"

az sql db query \
  --server "$SERVER" \
  --database "$DATABASE" \
  --auth-type ADIntegrated \
  --query "ALTER ROLE db_datawriter ADD MEMBER [$FUNCTION_APP]"

echo "✓ Granted db_datawriter role"
echo ""

echo "=========================================="
echo "✓ SCHEMA DEPLOYMENT COMPLETED!"
echo "=========================================="
echo ""
echo "Next step: Deploy the Function App code"
echo "Run: ./deploy_function.sh"
