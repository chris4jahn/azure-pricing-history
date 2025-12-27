# Deployment and Utility Scripts

This directory contains all deployment scripts, SQL files, and utility scripts for the Azure Pricing History project.

## Deployment Scripts

### Infrastructure Deployment
- **Terraform**: See `/infra/terraform/` for infrastructure-as-code deployment

### Database Scripts
- **[deploy_complete.sql](deploy_complete.sql)** - Complete SQL schema deployment (tables, indexes, views)
- **[grant_function_permissions.sql](grant_function_permissions.sql)** - Grant database permissions to Function App managed identity
- **[grant_webapp_permissions.sql](grant_webapp_permissions.sql)** - Grant database permissions to Web App managed identity
- **[deploy_schema.py](deploy_schema.py)** - Python script to deploy schema programmatically
- **[deploy_schema.sh](deploy_schema.sh)** - Shell script to deploy schema

### Application Deployment
- **[deploy_function.sh](deploy_function.sh)** - Deploy Azure Function App code
- **[deploy_webapp.sh](deploy_webapp.sh)** - Deploy Flask web application

## Utility Scripts

### Testing & Verification
- **[test_auth.py](test_auth.py)** - Test managed identity authentication to SQL Database
- **[trigger_function.sh](trigger_function.sh)** - Manually trigger the PriceSnapshot function
- **[check_data.py](check_data.py)** - Verify pricing data in database
- **[check_specific_record.py](check_specific_record.py)** - Check specific pricing records

### SQL Queries
- **[check_progress.sql](check_progress.sql)** - Query snapshot run progress and statistics

## Quick Start

See [DEPLOYMENT.md](../DEPLOYMENT.md) for complete deployment instructions.

### Deploy Infrastructure
```bash
cd infra/terraform
terraform init
terraform plan -var-file=envs/dev.tfvars
terraform apply -var-file=envs/dev.tfvars
```

### Deploy Database Schema
```bash
cd scripts
./deploy_schema.sh
```

### Deploy Function App
```bash
cd scripts
./deploy_function.sh
```

### Deploy Web App
```bash
cd scripts
./deploy_webapp.sh
```

## Usage Examples

### Test Authentication
```bash
cd scripts
python test_auth.py
```

### Trigger Function Manually
```bash
cd scripts
./trigger_function.sh
```

### Check Data Collection Progress
```bash
cd scripts
python check_data.py
```

## File Organization

```
scripts/
├── README.md                          # This file
├── deploy_complete.sql                # Complete SQL schema
├── deploy_function.sh                 # Function app deployment
├── deploy_schema.py                   # Schema deployment (Python)
├── deploy_schema.sh                   # Schema deployment (Shell)
├── deploy_webapp.sh                   # Web app deployment
├── grant_function_permissions.sql     # Function app DB permissions
├── grant_webapp_permissions.sql       # Web app DB permissions
├── trigger_function.sh                # Manual function trigger
├── test_auth.py                       # Authentication test
├── check_data.py                      # Data verification
├── check_progress.sql                 # Progress query
└── check_specific_record.py           # Record lookup
```

## Prerequisites

- Azure CLI installed and authenticated
- Python 3.11+ with required packages
- Azure Functions Core Tools v4
- Appropriate Azure permissions
- Terraform 1.5+ (for infrastructure)

## Notes

- All scripts assume you're running from the project root unless otherwise noted
- Database connection uses Managed Identity authentication
- Scripts are idempotent where possible
- See individual script files for detailed usage information
