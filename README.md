# Azure Pricing History

A low-maintenance service that tracks Azure Retail Prices API data over time, storing historical pricing information in Azure SQL Database for analysis and reporting.

## Overview

This service runs quarterly via Azure Functions (Timer Trigger) to:
- Fetch all pricing data from the [Azure Retail Prices API](https://learn.microsoft.com/azure/cost-management-billing/automate/retail-prices-api-overview)
- Support multiple currencies (USD, EUR)
- Store data in Azure SQL Database (Serverless) with full historicization
- Track price changes over time with snapshot-based versioning
- Use Managed Identities for secure, passwordless authentication

## Architecture

- **Runtime**: Azure Functions (Python 3.11, Consumption Plan)
- **Trigger**: Timer (Cron: `0 30 1 1 1,4,7,10 *` - Quarterly on Jan 1, Apr 1, Jul 1, Oct 1 at 01:30 UTC)
- **Database**: Azure SQL Database (Serverless, GP_S_Gen5_1)
- **Security**: System-assigned Managed Identity (no secrets in code)
- **Monitoring**: Application Insights with structured logging

## Repository Structure

```
.
├── src/
│   ├── functions-python/          # Azure Functions Python code
│   │   ├── host.json              # Function host configuration
│   │   ├── requirements.txt       # Python dependencies
│   │   ├── local.settings.json.example
│   │   └── PriceSnapshot/         # Timer trigger function
│   │       ├── __init__.py        # Function implementation
│   │       └── function.json      # Function binding configuration
│   └── shared/
│       └── sql/                   # Database scripts
│           ├── schema.sql         # Table definitions
│           └── views.sql          # Convenience views
├── infra/
│   └── terraform/                 # Infrastructure as Code
│       ├── main.tf               # Core resources
│       ├── variables.tf          # Input variables
│       ├── outputs.tf            # Output values
│       └── envs/                 # Environment configs
│           ├── dev.tfvars
│           ├── test.tfvars.example
│           └── prod.tfvars.example
└── copilot-instructions.md        # Detailed implementation guide
```

## Database Schema

### Tables

1. **dbo.AzureRetailPrices** - Main pricing data table
   - Unique key: `(meterId, effectiveStartDate, currencyCode)`
   - Stores all pricing attributes from Azure Retail Prices API
   - Tracks `lastSeenUtc` for each price record

2. **dbo.PriceSnapshotRuns** - Snapshot execution tracking
   - Composite key: `(snapshotId, currencyCode)`
   - Format: `YYYYMM` (e.g., "202512")
   - Tracks status: RUNNING | SUCCEEDED | FAILED

3. **dbo.AzureRetailPricesSnapshotMap** - Price-to-snapshot mapping
   - Links prices to specific snapshot runs
   - Enables time-based queries and historical analysis

### Views

- `v_CurrentRetailPrices` - Latest price for each meter
- `fn_SnapshotRetailPrices(@snapshotId, @currencyCode)` - Prices for specific snapshot
- `v_PriceHistory` - Price changes over time
- `v_ServicePricingSummary` - Aggregated pricing by service
- `v_SnapshotRunSummary` - Execution statistics

## Deployment

### Prerequisites

- Azure subscription
- Terraform >= 1.5.0
- Azure CLI (authenticated)
- Python 3.11 (for local development)

### Infrastructure Deployment

```bash
cd infra/terraform

# Initialize Terraform
terraform init

# Plan deployment
terraform plan -var-file=envs/dev.tfvars

# Deploy infrastructure
terraform apply -var-file=envs/dev.tfvars
```

### Database Setup

After infrastructure deployment, connect to the SQL Database and run:

```bash
# 1. Create schema
sqlcmd -S <sql-server-fqdn> -d <database-name> -G -i src/shared/sql/schema.sql

# 2. Create views
sqlcmd -S <sql-server-fqdn> -d <database-name> -G -i src/shared/sql/views.sql

# 3. Grant permissions to Function App Managed Identity
# In SQL Server:
CREATE USER [func-pricing-dev-neu] FROM EXTERNAL PROVIDER;
ALTER ROLE db_datareader ADD MEMBER [func-pricing-dev-neu];
ALTER ROLE db_datawriter ADD MEMBER [func-pricing-dev-neu];
GO
```

### Function App Deployment

```bash
cd src/functions-python

# Create deployment package
func azure functionapp publish <function-app-name>
```

## Configuration

### Environment Variables

Set in Azure Function App settings (managed by Terraform):

- `FUNCTIONS_WORKER_RUNTIME`: python
- `SQL_SERVER_FQDN`: SQL Server fully qualified domain name
- `SQL_DATABASE_NAME`: Database name
- `API_VERSION`: 2023-01-01-preview
- `CURRENCIES`: USD,EUR
- `BATCH_SIZE`: 500 (items per SQL transaction)

### Local Development

```bash
cp src/functions-python/local.settings.json.example src/functions-python/local.settings.json

# Edit local.settings.json with your values
# Install dependencies
cd src/functions-python
pip install -r requirements.txt

# Start Functions host
func start
```

## Features

### Idempotency
- MERGE statements ensure safe re-runs
- Unique key prevents duplicates: `(meterId, effectiveStartDate, currencyCode)`
- Multiple runs update `lastSeenUtc` without creating duplicates

### Error Handling
- Exponential backoff on HTTP 429 (rate limiting)
- 5 retry attempts with 2^n second delays
- Transient error handling for network issues
- Failed runs marked in `PriceSnapshotRuns` table

### Performance
- Batch processing (500 items per transaction)
- Pagination with `NextPageLink` following
- Configurable batch size via `BATCH_SIZE`
- Indexed queries for common patterns

### Security
- **No secrets in code or configuration**
- System-assigned Managed Identity for SQL authentication
- Azure AD tokens for database connections
- TLS 1.2 minimum for all connections

## Monitoring

### Application Insights

- Structured logs with snapshot metadata
- Custom metrics: items processed, duration, errors
- Failed runs automatically logged with stack traces

### Query Examples

```sql
-- Latest prices for Compute services
SELECT * FROM dbo.v_CurrentRetailPrices 
WHERE serviceFamily = 'Compute' 
ORDER BY retailPrice DESC;

-- Prices from December 2025 snapshot
SELECT * FROM dbo.fn_SnapshotRetailPrices('202512', 'USD');

-- Price history for a specific meter
SELECT * FROM dbo.v_PriceHistory 
WHERE meterId = 'xxx' 
ORDER BY effectiveStartDate DESC;

-- Snapshot execution summary
SELECT * FROM dbo.v_SnapshotRunSummary 
ORDER BY startedUtc DESC;
```

## Cost Optimization

- **Azure Functions**: Consumption Plan (pay-per-execution)
- **SQL Database**: Serverless tier with auto-pause after 60 minutes
- **Storage**: Standard LRS for Function App storage
- **Estimated monthly cost**: ~$10-30 depending on database usage

## License

MIT License - see [LICENSE](LICENSE) file for details.

## References

- [Azure Retail Prices API Documentation](https://learn.microsoft.com/azure/cost-management-billing/automate/retail-prices-api-overview)
- [Azure Functions Python Developer Guide](https://learn.microsoft.com/azure/azure-functions/functions-reference-python)
- [Azure SQL Database with Managed Identity](https://learn.microsoft.com/azure/azure-sql/database/authentication-aad-overview)
