# Azure Pricing History - Web Visualization

A Flask-based web application to visualize Azure pricing data stored in Azure SQL Database.

## Features

- 📊 Interactive dashboards with real-time charts
- 🔍 Search functionality for pricing data
- 📈 Service and region comparisons
- 📅 Snapshot run history
- 🌍 Multi-currency support (USD, EUR)
- 🎨 Modern, responsive UI

## Prerequisites

- Python 3.11+
- Azure SQL Database access
- ODBC Driver 18 for SQL Server

## Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables:**
   ```bash
   export SQL_SERVER_FQDN="sql-pricing-dev-gwc.database.windows.net"
   export SQL_DATABASE_NAME="sqldb-pricing-dev"
   ```

3. **Run the application:**
   ```bash
   python app.py
   ```

4. **Open browser:**
   Navigate to http://localhost:5000

## Deployment to Azure

### Option 1: Azure App Service (Recommended)

1. **Create App Service:**
   ```bash
   az webapp up \
     --name webapp-pricing-dev-gwc \
     --resource-group rg-pricing-dev-gwc \
     --runtime "PYTHON:3.11" \
     --sku B1
   ```

2. **Enable Managed Identity:**
   ```bash
   az webapp identity assign \
     --name webapp-pricing-dev-gwc \
     --resource-group rg-pricing-dev-gwc
   ```

3. **Configure app settings:**
   ```bash
   az webapp config appsettings set \
     --name webapp-pricing-dev-gwc \
     --resource-group rg-pricing-dev-gwc \
     --settings \
       SQL_SERVER_FQDN="sql-pricing-dev-gwc.database.windows.net" \
       SQL_DATABASE_NAME="sqldb-pricing-dev"
   ```

4. **Grant database access:**
   - Get the Managed Identity Object ID
   - Add it as a database user (see deploy_complete.sql for reference)

5. **Deploy code:**
   ```bash
   cd src/webapp
   zip -r app.zip .
   az webapp deployment source config-zip \
     --name webapp-pricing-dev-gwc \
     --resource-group rg-pricing-dev-gwc \
     --src app.zip
   ```

### Option 2: Docker Container

1. **Build image:**
   ```bash
   docker build -t azure-pricing-webapp .
   ```

2. **Run locally:**
   ```bash
   docker run -p 5000:5000 \
     -e SQL_SERVER_FQDN="..." \
     -e SQL_DATABASE_NAME="..." \
     azure-pricing-webapp
   ```

## API Endpoints

- `GET /` - Main dashboard
- `GET /api/summary` - Overall statistics
- `GET /api/services?currency=USD` - Top services by meter count
- `GET /api/regions?currency=USD` - Pricing by region
- `GET /api/snapshots` - Snapshot run history
- `GET /api/search?q=query&currency=USD` - Search pricing data

## Database Views Used

The application queries these database objects:
- `dbo.v_CurrentRetailPrices` - Latest prices per meter
- `dbo.v_PriceHistory` - Historical price data
- `dbo.v_SnapshotRunSummary` - Snapshot metadata
- `dbo.AzureRetailPrices` - Main pricing table

## Security

- Uses Azure Managed Identity for passwordless database authentication
- No credentials stored in code or configuration
- HTTPS enforced in production
- CORS configured for API endpoints

## Troubleshooting

**Connection errors:**
- Verify firewall rules allow your IP
- Check Managed Identity has database permissions
- Ensure ODBC Driver 18 is installed

**Charts not loading:**
- Check browser console for JavaScript errors
- Verify API endpoints return data
- Check database has been populated

## Future Enhancements

- [ ] Export data to CSV/Excel
- [ ] Price change alerts
- [ ] Cost estimation calculator
- [ ] Comparison tool for regions
- [ ] Historical trend analysis
- [ ] User authentication
