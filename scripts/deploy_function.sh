#!/bin/bash
# Deploy Azure Functions App

set -e

FUNCTION_APP="func-pricing-dev-gwc"
RESOURCE_GROUP="rg-pricing-dev-gwc"

echo "=========================================="
echo "Azure Pricing History - Function App Deployment"
echo "=========================================="
echo ""
echo "Function App: $FUNCTION_APP"
echo "Resource Group: $RESOURCE_GROUP"
echo ""

# Check if Azure Functions Core Tools is installed
if ! command -v func &> /dev/null; then
    echo "❌ Azure Functions Core Tools not found!"
    echo ""
    echo "Install it using:"
    echo "  brew tap azure/functions"
    echo "  brew install azure-functions-core-tools@4"
    echo ""
    exit 1
fi

echo "Step 1: Installing Python dependencies locally..."
cd src/functions-python
pip3 install -r requirements.txt --target .python_packages/lib/site-packages --quiet
echo "✓ Dependencies installed"
echo ""

echo "Step 2: Updating Function App settings..."
cd ../..

# Update app settings with SQL connection info
az functionapp config appsettings set \
  --name "$FUNCTION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --settings \
    "SQL_SERVER_FQDN=sql-pricing-dev-gwc.database.windows.net" \
    "SQL_DATABASE_NAME=sqldb-pricing-dev" \
    "API_VERSION=2023-01-01-preview" \
    "CURRENCIES=USD,EUR" \
    "BATCH_SIZE=500" \
  --output none

echo "✓ App settings updated"
echo ""

echo "Step 3: Publishing Function App code..."
cd src/functions-python

func azure functionapp publish "$FUNCTION_APP" --python

echo ""
echo "=========================================="
echo "✓ FUNCTION APP DEPLOYMENT COMPLETED!"
echo "=========================================="
echo ""
echo "Function App URL: https://$FUNCTION_APP.azurewebsites.net"
echo ""
echo "To view logs:"
echo "  func azure functionapp logstream $FUNCTION_APP"
echo ""
echo "To manually trigger the function for testing:"
echo "  az functionapp function show --name $FUNCTION_APP --resource-group $RESOURCE_GROUP --function-name PriceSnapshot"
echo ""
