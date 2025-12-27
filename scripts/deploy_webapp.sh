#!/bin/bash
# Deploy Azure Pricing History Web App

set -e

WEBAPP_NAME="webapp-pricing-dev-gwc"
RESOURCE_GROUP="rg-pricing-dev-gwc"
LOCATION="germanywestcentral"
SQL_SERVER="sql-pricing-dev-gwc"
SQL_DATABASE="sqldb-pricing-dev"

echo "=========================================="
echo "Azure Pricing History - Web App Deployment"
echo "=========================================="
echo ""
echo "Web App: $WEBAPP_NAME"
echo "Resource Group: $RESOURCE_GROUP"
echo ""

# Check if resource group exists
if ! az group show --name "$RESOURCE_GROUP" &> /dev/null; then
    echo "❌ Resource group $RESOURCE_GROUP not found!"
    exit 1
fi

echo "Step 1: Creating App Service Plan..."
if ! az appservice plan show --name "plan-pricing-dev-gwc" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    az appservice plan create \
        --name "plan-pricing-dev-gwc" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --sku B1 \
        --is-linux \
        --output none
    echo "✓ App Service Plan created"
else
    echo "  App Service Plan already exists"
fi
echo ""

echo "Step 2: Creating Web App..."
if ! az webapp show --name "$WEBAPP_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    az webapp create \
        --name "$WEBAPP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --plan "plan-pricing-dev-gwc" \
        --runtime "PYTHON:3.11" \
        --output none
    echo "✓ Web App created"
else
    echo "  Web App already exists"
fi
echo ""

echo "Step 3: Enabling Managed Identity..."
IDENTITY_ID=$(az webapp identity assign \
    --name "$WEBAPP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query principalId \
    --output tsv)
echo "✓ Managed Identity enabled: $IDENTITY_ID"
echo ""

echo "Step 4: Configuring App Settings..."
az webapp config appsettings set \
    --name "$WEBAPP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --settings \
        SQL_SERVER_FQDN="${SQL_SERVER}.database.windows.net" \
        SQL_DATABASE_NAME="$SQL_DATABASE" \
        SCM_DO_BUILD_DURING_DEPLOYMENT=true \
    --output none
echo "✓ App settings configured"
echo ""

echo "Step 5: Granting database access to Managed Identity..."
echo "You need to run this SQL command in the database:"
echo ""
echo "CREATE USER [$WEBAPP_NAME] FROM EXTERNAL PROVIDER;"
echo "ALTER ROLE db_datareader ADD MEMBER [$WEBAPP_NAME];"
echo ""
echo "Opening Azure Portal query editor..."
az sql db show \
    --resource-group "$RESOURCE_GROUP" \
    --server "$SQL_SERVER" \
    --name "$SQL_DATABASE" \
    --query id \
    --output tsv | xargs -I {} open "https://portal.azure.com/#@/resource{}/query"
echo ""
read -p "Press Enter after you've granted the permissions..."
echo ""

echo "Step 6: Deploying application code..."
cd src/webapp

# Create deployment package
echo "Creating deployment package..."
zip -r ../../webapp-deploy.zip . -x "*.pyc" -x "__pycache__/*" -x "*.md"
cd ../..

az webapp deployment source config-zip \
    --name "$WEBAPP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --src webapp-deploy.zip \
    --timeout 300

rm webapp-deploy.zip

echo "✓ Application deployed"
echo ""

echo "Step 7: Restarting Web App..."
az webapp restart \
    --name "$WEBAPP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --output none
echo "✓ Web App restarted"
echo ""

WEBAPP_URL="https://${WEBAPP_NAME}.azurewebsites.net"

echo "=========================================="
echo "✓ WEB APP DEPLOYMENT COMPLETED!"
echo "=========================================="
echo ""
echo "Web App URL: $WEBAPP_URL"
echo ""
echo "To view logs:"
echo "  az webapp log tail --name $WEBAPP_NAME --resource-group $RESOURCE_GROUP"
echo ""
echo "Opening the web app in your browser..."
sleep 5
open "$WEBAPP_URL"
