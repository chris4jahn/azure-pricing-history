# Azure Pricing History Infrastructure
# Main Terraform configuration

# Local variables for naming and tagging
locals {
  resource_suffix = "${var.environment}-${var.location_short}"

  # Resource naming conventions
  resource_names = {
    resource_group   = "rg-pricing-${local.resource_suffix}"
    storage_account  = "stfn${replace(local.resource_suffix, "-", "")}"
    app_insights     = "appi-pricing-${local.resource_suffix}"
    app_service_plan = "asp-pricing-${local.resource_suffix}"
    function_app     = "func-pricing-${local.resource_suffix}"
    web_app          = "webapp-pricing-${local.resource_suffix}"
    sql_server       = "sql-pricing-${local.resource_suffix}"
    sql_database     = "sqldb-pricing-${var.environment}"
    log_analytics    = "log-pricing-${local.resource_suffix}"
  }

  common_tags = merge(
    var.tags,
    {
      Environment = var.environment
      ManagedBy   = "Terraform"
      Project     = "Azure Pricing History"
      Repository  = "azure-pricing-history"
      LastUpdated = timestamp()
    }
  )
}

#
# Resource Group
#
resource "azurerm_resource_group" "main" {
  name     = local.resource_names.resource_group
  location = var.location
  tags     = local.common_tags

  lifecycle {
    ignore_changes = [tags["LastUpdated"]]
  }
}

#
# Log Analytics Workspace (for better monitoring)
#
resource "azurerm_log_analytics_workspace" "main" {
  name                = local.resource_names.log_analytics
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = var.log_analytics_retention_days

  tags = local.common_tags

  lifecycle {
    ignore_changes = [tags["LastUpdated"]]
  }
}

#
# Application Insights
#
resource "azurerm_application_insights" "main" {
  name                = local.resource_names.app_insights
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  application_type    = "web"
  workspace_id        = azurerm_log_analytics_workspace.main.id
  retention_in_days   = var.appinsights_retention_days

  tags = local.common_tags

  lifecycle {
    ignore_changes = [tags["LastUpdated"]]
  }
}

#
# Storage Account for Function App
#
resource "azurerm_storage_account" "functions" {
  name                       = local.resource_names.storage_account
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  account_tier               = "Standard"
  account_replication_type   = "LRS"
  min_tls_version            = "TLS1_2"
  https_traffic_only_enabled = true

  # Network rules
  network_rules {
    default_action = "Allow"
    bypass         = ["AzureServices"]
  }

  tags = local.common_tags

  lifecycle {
    ignore_changes = [tags["LastUpdated"]]
  }
}

#
# App Service Plan (Consumption for Functions, B1 for Web App)
#
resource "azurerm_service_plan" "functions" {
  name                = "${local.resource_names.app_service_plan}-func"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "Y1" # Consumption plan

  tags = local.common_tags

  lifecycle {
    ignore_changes = [tags["LastUpdated"]]
  }
}

resource "azurerm_service_plan" "webapp" {
  name                = "${local.resource_names.app_service_plan}-web"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = var.webapp_sku_name

  tags = local.common_tags

  lifecycle {
    ignore_changes = [tags["LastUpdated"]]
  }
}

#
# Function App
#
resource "azurerm_linux_function_app" "main" {
  name                       = local.resource_names.function_app
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  service_plan_id            = azurerm_service_plan.functions.id
  storage_account_name       = azurerm_storage_account.functions.name
  storage_account_access_key = azurerm_storage_account.functions.primary_access_key

  https_only = true

  site_config {
    application_stack {
      python_version = "3.11"
    }

    # Security headers
    ftps_state = "FtpsOnly"
  }

  app_settings = {
    "FUNCTIONS_WORKER_RUNTIME"              = "python"
    "AzureWebJobsDisableHomepage"           = "true"
    "WEBSITE_RUN_FROM_PACKAGE"              = "1"
    "SQL_SERVER_FQDN"                       = azurerm_mssql_server.main.fully_qualified_domain_name
    "SQL_DATABASE_NAME"                     = azurerm_mssql_database.main.name
    "API_VERSION"                           = var.azure_pricing_api_version
    "CURRENCIES"                            = var.pricing_currencies
    "BATCH_SIZE"                            = tostring(var.pricing_batch_size)
    "APPLICATIONINSIGHTS_CONNECTION_STRING" = azurerm_application_insights.main.connection_string
  }

  identity {
    type = "SystemAssigned"
  }

  tags = local.common_tags

  lifecycle {
    ignore_changes = [
      tags["LastUpdated"],
      app_settings["WEBSITE_RUN_FROM_PACKAGE"]
    ]
  }
}

#
# Web App for Visualization
#
resource "azurerm_linux_web_app" "main" {
  name                = local.resource_names.web_app
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  service_plan_id     = azurerm_service_plan.webapp.id

  https_only = true

  site_config {
    application_stack {
      python_version = "3.11"
    }

    always_on = var.webapp_sku_name != "F1" && var.webapp_sku_name != "D1"

    ftps_state = "FtpsOnly"
  }

  app_settings = {
    "SQL_SERVER_FQDN"                       = azurerm_mssql_server.main.fully_qualified_domain_name
    "SQL_DATABASE_NAME"                     = azurerm_mssql_database.main.name
    "APPLICATIONINSIGHTS_CONNECTION_STRING" = azurerm_application_insights.main.connection_string
  }

  identity {
    type = "SystemAssigned"
  }

  tags = local.common_tags

  lifecycle {
    ignore_changes = [tags["LastUpdated"]]
  }
}

#
# SQL Server
#
resource "azurerm_mssql_server" "main" {
  name                          = local.resource_names.sql_server
  resource_group_name           = azurerm_resource_group.main.name
  location                      = azurerm_resource_group.main.location
  version                       = "12.0"
  minimum_tls_version           = "1.2"
  public_network_access_enabled = true

  azuread_administrator {
    login_username              = var.sql_admin_login
    object_id                   = var.sql_admin_object_id
    azuread_authentication_only = true
  }

  identity {
    type = "SystemAssigned"
  }

  tags = local.common_tags

  lifecycle {
    ignore_changes = [tags["LastUpdated"]]
  }
}

#
# SQL Database (Serverless)
#
resource "azurerm_mssql_database" "main" {
  name                        = local.resource_names.sql_database
  server_id                   = azurerm_mssql_server.main.id
  collation                   = "SQL_Latin1_General_CP1_CI_AS"
  max_size_gb                 = var.sql_max_size_gb
  sku_name                    = var.sql_sku_name
  min_capacity                = var.sql_min_capacity
  auto_pause_delay_in_minutes = var.sql_auto_pause_delay
  zone_redundant              = var.sql_zone_redundant

  tags = local.common_tags

  lifecycle {
    ignore_changes = [tags["LastUpdated"]]
  }
}

#
# SQL Server Diagnostic Settings
#
resource "azurerm_monitor_diagnostic_setting" "sql_server" {
  name                       = "diag-${local.resource_names.sql_server}"
  target_resource_id         = azurerm_mssql_server.main.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log {
    category = "SQLSecurityAuditEvents"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "sql_database" {
  name                       = "diag-${local.resource_names.sql_database}"
  target_resource_id         = azurerm_mssql_database.main.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log {
    category = "SQLInsights"
  }

  enabled_log {
    category = "AutomaticTuning"
  }

  enabled_log {
    category = "QueryStoreRuntimeStatistics"
  }

  enabled_log {
    category = "QueryStoreWaitStatistics"
  }

  enabled_log {
    category = "Errors"
  }

  enabled_log {
    category = "DatabaseWaitStatistics"
  }

  enabled_log {
    category = "Timeouts"
  }

  enabled_log {
    category = "Blocks"
  }

  enabled_log {
    category = "Deadlocks"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

#
# SQL Firewall Rules
#
resource "azurerm_mssql_firewall_rule" "allow_azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_mssql_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azurerm_mssql_firewall_rule" "client_ip" {
  count            = var.sql_allow_client_ip != "" ? 1 : 0
  name             = "ClientIP"
  server_id        = azurerm_mssql_server.main.id
  start_ip_address = var.sql_allow_client_ip
  end_ip_address   = var.sql_allow_client_ip
}

#
# Role Assignments for Managed Identities
#
# Function App needs Contributor on SQL Server to manage its access
resource "azurerm_role_assignment" "function_to_sql" {
  scope                = azurerm_mssql_server.main.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_linux_function_app.main.identity[0].principal_id

  depends_on = [
    azurerm_linux_function_app.main,
    azurerm_mssql_server.main
  ]
}

# Web App needs Contributor on SQL Server for read access
resource "azurerm_role_assignment" "webapp_to_sql" {
  scope                = azurerm_mssql_server.main.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_linux_web_app.main.identity[0].principal_id

  depends_on = [
    azurerm_linux_web_app.main,
    azurerm_mssql_server.main
  ]
}
