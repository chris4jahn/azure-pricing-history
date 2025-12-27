#!/bin/bash
# Trigger Azure Function to fetch pricing data

set -e

FUNCTION_APP="func-pricing-dev-gwc"
RESOURCE_GROUP="rg-pricing-dev-gwc"
FUNCTION_NAME="PriceSnapshot"

echo "=========================================="
echo "Triggering Azure Function: $FUNCTION_NAME"
echo "=========================================="
echo ""

# Get master key
echo "Getting function app master key..."
MASTER_KEY=$(az functionapp keys list \
    --name "$FUNCTION_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query "masterKey" \
    --output tsv)

if [ -z "$MASTER_KEY" ]; then
    echo "❌ Failed to get master key"
    exit 1
fi

echo "✓ Got master key"
echo ""

# Trigger function
echo "Triggering function..."
RESPONSE=$(curl -s -X POST \
    "https://$FUNCTION_APP.azurewebsites.net/admin/functions/$FUNCTION_NAME" \
    -H "Content-Type: application/json" \
    -H "x-functions-key: $MASTER_KEY" \
    -d '{"input":""}')

echo "✓ Function triggered!"
echo ""
echo "Response: $RESPONSE"
echo ""
echo "=========================================="
echo "Monitoring Progress"
echo "=========================================="
echo ""
echo "The function will:"
echo "  1. Connect to SQL Database"
echo "  2. Fetch pricing data from Azure API"
echo "  3. Process USD and EUR currencies"
echo "  4. Insert ~100,000+ pricing records"
echo ""
echo "Expected duration: 10-15 minutes"
echo ""
echo "Monitor progress:"
echo "  • Application Insights: https://portal.azure.com/#@/resource/subscriptions/33d063dc-2392-4d6f-ba58-3128b84aa2fc/resourceGroups/rg-pricing-dev-gwc/providers/microsoft.insights/components/appi-pricing-dev-gwc/logs"
echo ""
echo "  • Check database after 5 minutes:"
echo "    SELECT COUNT(*) FROM dbo.PriceSnapshotRuns;"
echo "    SELECT COUNT(*) FROM dbo.AzureRetailPrices;"
echo ""
echo "Opening Application Insights logs..."
sleep 2
open "https://portal.azure.com/#@/resource/subscriptions/33d063dc-2392-4d6f-ba58-3128b84aa2fc/resourceGroups/rg-pricing-dev-gwc/providers/microsoft.insights/components/appi-pricing-dev-gwc/logs"
