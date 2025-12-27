# Deployment Guide

This guide will help you deploy the complete Azure Pricing History solution including infrastructure, database schema, and applications.

## Directory Structure

```
azure-pricing-history/
├── infra/terraform/        # Infrastructure-as-code (Terraform)
├── scripts/                # Deployment and utility scripts
├── src/                    # Application source code
└── tests/                  # Unit tests
```

All deployment scripts are located in the [`scripts/`](scripts/) directory. See [scripts/README.md](scripts/README.md) for detailed information about each script.

## Prerequisites

- Azure CLI installed and authenticated (`az login`)
- Azure subscription with appropriate permissions
- Terraform 1.5+ (for infrastructure deployment)
- Python 3.11+
- Azure Functions Core Tools v4 (for Function App deployment)

## Deployment Steps Overview

1. Deploy Infrastructure (Terraform)
2. Deploy Database Schema
3. Grant Database Permissions
4. Deploy Function App
5. Deploy Web App
6. Verify Deployment

## Step 1: Deploy Infrastructure

Use Terraform to deploy all Azure resources:

```bash
cd infra/terraform

# Initialize Terraform
terraform init

# Review planned changes
terraform plan -var-file=envs/dev.tfvars

# Deploy infrastructure
terraform apply -var-file=envs/dev.tfvars
```

This creates:
- Resource Group
- Azure SQL Server and Database
- Storage Account
- App Service Plans (for Functions and Web App)
- Functi3: Grant Database Permissions

Grant the Managed Identities permission to access the database:

### For Function App

Execute [`scripts/grant_function_permissions.sql`](scripts/grant_function_permissions.sql) in the SQL database:

```sql
-- Create user from managed identity
CREATE USER [func-pricing-dev-gwc] FROM EXTERNAL PROVIDER;

-- Grant permissions
ALTER ROLE db_datareader ADD MEMBER [func-pricing-dev-gwc];
ALTER ROLE db_datawriter ADD MEMBER [func-pricing-dev-gwc];
GRANT EXECUTE TO [func-pricing-dev-gwc];
```

### For Web App

Execute [`scripts/grant_webapp_permissions.sql`](scripts/grant_webapp_permissions.sql) in the SQL database:

```sql
-- Create user from managed identity
CREATE USER [webapp-pricing-dev-gwc] FROM EXTERNAL PROVIDER;

-- Grant read-only permissions
ALTER ROLE db_datareader ADD MEMBER [webapp-pricing-dev-gwc];
```

## Step 4: Deploy Function App Code

### Install Azure Functions Core Tools (if not already installed)

```bash
brew tap azure/functions
brew install azure-functions-core-tools@4
```

### Deploy the Function App

```bash
cd scripts
chmod +x deploy_function.sh
./deploy_function.sh
```

The script will:
1. Install Python dependencies
2. Update Function App settings
3. Publish the code to Azure

## Step 5: Deploy Web App

```bash
cd scripts
chmod +x deploy_webapp.sh
./deploy_webapp.sh
```

The script will:
1. Build the Docker container
2. Push to Azure Container Registry (if configured) or use local deployment
3. Deploy to Azure App Servic
5. Verify the output shows all tables, indexes, and views created successfully

### Option B: Using Shell Script

```bash
cd scripts
./deploy_schema.sh
```6: Verify Deployment

### Test Authentication

Verify Managed Identity authentication works:

```bash
cd scripts
python test_auth.py
```

### Check Function App

```bash
# View Function App details
az functionapp show \
  --name func-pricing-dev-gwc \
  --resource-group rg-pricing-dev-gwc

# View logs
func azure functionapp logstream func-pricing-dev-gwc
```

### Test the Function (Optional)

You can manually trigger the function for testing without waiting for the quarterly schedule:

**Option 1: Azure Portal**
1. Go to Azure Portal → Function App → Functions → PriceSnapshot
2. Click "Code + Test" → "Test/Run"
3. Click "Run" to manually trigger

**Option 2: Using Script**
```bash
cd scripts
./trigger_function.sh
```

**Option 3: Azure CLI**
```bashmanaged identity users exist
SELECT name, type_desc FROM sys.database_principals 
WHERE name IN ('func-pricing-dev-gwc', 'webapp-pricing-dev-gwc');

-- Check permissions
SELECT 
    dp.name AS UserName,
    r.name AS RoleName
FROM sys.database_principals dp
LEFT JOIN sys.database_role_members drm ON dp.principal_id = drm.member_principal_id
LEFT JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
WHERE dp.name IN ('func-pricing-dev-gwc', 'webapp-pricing-dev-gwc');
```

Or use the utility scripts:

```bash
cd scripts

# Check data collection progress
python check_data.py

# View progress SQL
cat check_progress.sql

# Check specific record
python check_specific_record.pysites.ne
brew install azure-functions-core-tools@4
```

### Deploy the Function App

```bash
chmod +x deploy_function.sh
./deploy_function.sh
```

The script will:
1. Install Python dependencies
2. Update Function App settings
3. Publish the code to Azure

## Step 3: Verify Deployment

### Check Function App

```bash
# View Function App details
az functionapp show \
  --name func-pricing-dev-gwc \
  --resource-group rg-pricing-dev-gwc

# View logs
func azure functionapp logstream func-pricing-dev-gwc
```

### Test the Function (Optional)

You can manually trigger the function for testing without waiting for the monthly schedule:

1. Go to Azure Portal → Function App → Functions → PriceSnapshot
2. Click "Code + Test" → "Test/Run"
3. Click "Run" to manually trigger

Or use Azure CLI:

```bash
az functionapp function show \
  --name func-pricing-dev-gwc \
  --resource-group rg-pricing-dev-gwc \
  --function-name PriceSnapshot
```

### Verify Database

Connect to SQL Database and run:

```sql
-- Check if tables exist
SELECT name FROM sys.tables WHERE schema_id = SCHEMA_ID('dbo');

-- Check if Function App user exists
SELECT name, type_desc FROM sys.database_principals 
WHERE name = 'func-pricing-dev-gwc';

-- Check permissions
SELECT 
    dp.name AS UserName,
    r.name AS RoleName
FROM sys.database_principals dp
LEFT JOIN sys.database_role_members drm ON dp.principal_id = drm.member_principal_id
LEFT JOIN sys.database_principals r ON drm.role_principal_id = r.principal_id
WHERE dp.name = 'func-pricing-dev-gwc';
```

## Troubleshooting

### SQL Connection Issues

If you cannot connect to SQL Database:

1. Check firewall rules:
   ```bash
   az sql server firewall-rule list \
     --server sql-pricing-dev-gwc \
     --resource-group rg-pricing-dev-gwc
   ```

2. Add your IP if needed:
   ```bapplications cannot access the database:

1. Verify managed identities exist:
   ```bash
   # Function App
   az functionapp identity show \
     --name func-pricing-dev-gwc \
     --resource-group rg-pricing-dev-gwc
   
   # Web App
   az webapp identity show \
     --name webapp-pricing-dev-gwc \
     --resource-group rg-pricing-dev-gwc
   ```

2. Re-run the permission grants in SQL (see [`scripts/grant_function_permissions.sql`](scripts/grant_function_permissions.sql) and [`scripts/grant_webapp_permissions.sql`](scripts/grant_webapp_permissions.sql)):
   ```sql
   -- Function App
   CREATE USER [func-pricing-dev-gwc] FROM EXTERNAL PROVIDER;
   ALTER ROLE db_datareader ADD MEMBER [func-pricing-dev-gwc];
   ALTER ROLE db_datawriter ADD MEMBER [func-pricing-dev-gwc];
   GRANT EXECUTE TO [func-pricing-dev-gwc];
   
   -- Web App
   CREATE USER [webapp-pricing-dev-gwc] FROM EXTERNAL PROVIDER;
   ALTER ROLE db_datareader ADD MEMBER [webapp
   ```bash
   az functionapp show \
     --name func-pricing-dev-gwc \
     --resource-group rg-pricing-dev-gwc \
     --query state
   ```

2. View deployment logs:
   ```bash
   az functionapp deployment log show \
     --name func-pricing-dev-gwc \
     --resource-group rg-pricing-dev-gwc
   ```

3. Restart the Function App:
   ```bash
   **Monitor the first run** - Scheduled quarterly on Jan 1, Apr 1, Jul 1, Oct 1 at 01:30 UTC (see [SCHEDULE.md](SCHEDULE.md))
2. **Check Application Insights** - Monitor logs, metrics, and performance
3. **Verify data ingestion** - Query the database to confirm pricing data collection
4. **Access Web App** - View visualizations at `https://webapp-pricing-dev-gwc.azurewebsites.net`

### Monitoring Queries

```sql
-- Check snapshot runs
SELECT * FROM dbo.v_SnapshotRunSummary ORDER BY startedUtc DESC;

-- Check ingested prices
SELECT TOP 100 * FROM dbo.v_CurrentRetailPrices;

-- Check by service family
SELECT * FROM dbo.v_ServicePricingSummary 
ORDER BY meterCount DESC;
```

## Additional Resources

- **[scripts/README.md](scripts/README.md)** - Detailed script documentation
- **[SCHEDULE.md](SCHEDULE.md)** - Quarterly execution schedule details
- **[README.md](README.md)** - Project overview and architecture
- **[tests/README.md](tests/README.md)** - Unit test documentation
- **[infra/terraform/README.md](infra/terraform/README.md)** - Terraform infrastructure documentation

## Project Structure

```
azure-pricing-history/
├── DEPLOYMENT.md              # This file - deployment guide
├── README.md                  # Project overview
├── SCHEDULE.md                # Quarterly execution schedule
├── pytest.ini                 # Test configuration
├── requirements-dev.txt       # Development dependencies
├── infra/
│   └── terraform/            # Infrastructure as code
│       ├── main.tf           # Main Terraform configuration
│       ├── variables.tf      # Input variables
│       ├── outputs.tf        # Output values
│       └── envs/             # Environment configs
├── scripts/                  # Deployment and utility scripts
│   ├── README.md             # Script documentation
│   ├── deploy_complete.sql   # Complete SQL schema
│   ├── deploy_function.sh    # Function deployment
│   ├── deploy_webapp.sh      # Web app deployment
│   ├── grant_*_permissions.sql # Permission grants
│   └── test_*.py             # Test and verification scripts
├── src/
│   ├── functions-python/     # Azure Function code
│   │   └── PriceSnapshot/   # Timer-triggered function
│   ├── shared/              # Shared authentication module
│   └── webapp/              # Flask web application
└── tests/                    # Unit tests
    └── unit/                # Unit test suitespricing-dev-gwc
   ```

2. Re-run the permission grant in SQL:
   ```sql
   CREATE USER [func-pricing-dev-gwc] FROM EXTERNAL PROVIDER;
   ALTER ROLE db_datareader ADD MEMBER [func-pricing-dev-gwc];
   ALTER ROLE db_datawriter ADD MEMBER [func-pricing-dev-gwc];
   ```

## Next Steps

After successful deployment:

1. Monitor the first run (scheduled for the 1st of next month at 01:30 UTC)
2. Check Application Insights for logs and metrics
3. Query the database to verify data ingestion

```sql
-- Check snapshot runs
SELECT * FROM dbo.v_SnapshotRunSummary ORDER BY startedUtc DESC;

-- Check ingested prices
SELECT TOP 100 * FROM dbo.v_CurrentRetailPrices;

-- Check by service family
SELECT * FROM dbo.v_ServicePricingSummary 
ORDER BY meterCount DESC;
```
