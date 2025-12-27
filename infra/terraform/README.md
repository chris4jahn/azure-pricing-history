# Terraform Infrastructure README

## Overview

This Terraform configuration deploys the Azure Pricing History infrastructure:

- **Azure Functions** (Python, Consumption plan) with Timer trigger
- **Azure SQL Database** (Serverless) for price storage
- **Application Insights** for monitoring and logging
- **Managed Identities** for secure authentication (no secrets)

## Prerequisites

- Terraform >= 1.5.0
- Azure CLI installed and authenticated
- Azure subscription with appropriate permissions
- Azure AD admin credentials for SQL Server

## Getting Started

### 1. Authenticate with Azure

```bash
az login
az account set --subscription "your-subscription-id"
```

### 2. Create Environment Variables File

```bash
cd infra/terraform/envs
cp dev.tfvars.example dev.tfvars
# Edit dev.tfvars with your values
```

### 3. Initialize Terraform

```bash
cd infra/terraform
terraform init
```

### 4. Plan Deployment

```bash
terraform plan -var-file=envs/dev.tfvars
```

### 5. Apply Configuration

```bash
terraform apply -var-file=envs/dev.tfvars
```

## Environment Variables

Create a `.tfvars` file for each environment (dev, test, prod):

| Variable | Description | Required |
|----------|-------------|----------|
| `subscription_id` | Azure subscription ID | Yes |
| `tenant_id` | Azure AD tenant ID | Yes |
| `environment` | Environment name (dev/test/prod) | Yes |
| `location` | Azure region | Yes |
| `sql_admin_login` | SQL Server AD admin email | Yes |
| `sql_admin_object_id` | SQL Server AD admin object ID | Yes |
| `sql_max_size_gb` | SQL Database max size | No (default: 32) |
| `sql_allow_client_ip` | Client IP for SQL access | No |

## Resources Created

- Resource Group: `rg-pricing-{env}-{location}`
- Function App: `func-pricing-{env}-{location}`
- SQL Server: `sql-pricing-{env}-{location}`
- SQL Database: `sqldb-pricing-{env}`
- Storage Account: `stfn{env}{location}`
- Application Insights: `appi-pricing-{env}-{location}`

## Security

- **Managed Identities**: Function App uses System-Assigned Managed Identity
- **No Secrets**: No connection strings or passwords in code
- **SQL Authentication**: Azure AD authentication only
- **TLS**: Minimum TLS 1.2 enforced

## Post-Deployment

After deployment, you need to:

1. **Grant SQL Permissions** to the Function App identity:
   ```sql
   CREATE USER [func-pricing-{env}-{location}] FROM EXTERNAL PROVIDER;
   ALTER ROLE db_datareader ADD MEMBER [func-pricing-{env}-{location}];
   ALTER ROLE db_datawriter ADD MEMBER [func-pricing-{env}-{location}];
   ```

2. **Deploy SQL Schema**: Run `src/shared/sql/schema.sql`

3. **Deploy Function Code**: Use Azure Functions Core Tools or CI/CD

## Cleanup

```bash
terraform destroy -var-file=envs/dev.tfvars
```

## Troubleshooting

**Issue**: SQL connection fails from Function App

**Solution**: Ensure the Function App managed identity has been granted database permissions.

---

**Issue**: Cannot connect to SQL Server

**Solution**: Add your client IP to `sql_allow_client_ip` variable or use Azure Cloud Shell.
