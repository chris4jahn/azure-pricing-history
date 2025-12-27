# Output values for Azure Pricing History infrastructure

#
# Resource Group Outputs
#
output "resource_group_name" {
  description = "Name of the resource group"
  value       = azurerm_resource_group.main.name
}

output "resource_group_id" {
  description = "ID of the resource group"
  value       = azurerm_resource_group.main.id
}

output "location" {
  description = "Azure region where resources are deployed"
  value       = azurerm_resource_group.main.location
}

#
# Function App Outputs
#
output "function_app_name" {
  description = "Name of the Function App"
  value       = azurerm_linux_function_app.main.name
}

output "function_app_identity_principal_id" {
  description = "Principal ID of the Function App managed identity"
  value       = azurerm_linux_function_app.main.identity[0].principal_id
}

output "function_app_default_hostname" {
  description = "Default hostname of the Function App"
  value       = azurerm_linux_function_app.main.default_hostname
}

output "function_app_url" {
  description = "Full URL of the Function App"
  value       = "https://${azurerm_linux_function_app.main.default_hostname}"
}

#
# Web App Outputs
#
output "web_app_name" {
  description = "Name of the Web App"
  value       = azurerm_linux_web_app.main.name
}

output "web_app_identity_principal_id" {
  description = "Principal ID of the Web App managed identity"
  value       = azurerm_linux_web_app.main.identity[0].principal_id
}

output "web_app_default_hostname" {
  description = "Default hostname of the Web App"
  value       = azurerm_linux_web_app.main.default_hostname
}

output "web_app_url" {
  description = "Full URL of the Web App"
  value       = "https://${azurerm_linux_web_app.main.default_hostname}"
}

#
# SQL Server Outputs
#
output "sql_server_name" {
  description = "Name of the SQL Server"
  value       = azurerm_mssql_server.main.name
}

output "sql_server_fqdn" {
  description = "Fully qualified domain name of the SQL Server"
  value       = azurerm_mssql_server.main.fully_qualified_domain_name
}

output "sql_server_id" {
  description = "ID of the SQL Server"
  value       = azurerm_mssql_server.main.id
}

output "sql_database_name" {
  description = "Name of the SQL Database"
  value       = azurerm_mssql_database.main.name
}

output "sql_database_id" {
  description = "ID of the SQL Database"
  value       = azurerm_mssql_database.main.id
}

output "sql_connection_string" {
  description = "Connection string template for SQL Database (requires Managed Identity)"
  value       = "Server=tcp:${azurerm_mssql_server.main.fully_qualified_domain_name},1433;Database=${azurerm_mssql_database.main.name};Authentication=Active Directory Default;Encrypt=yes;"
  sensitive   = true
}

#
# Monitoring Outputs
#
output "application_insights_name" {
  description = "Name of Application Insights"
  value       = azurerm_application_insights.main.name
}

output "application_insights_app_id" {
  description = "Application ID of Application Insights"
  value       = azurerm_application_insights.main.app_id
}

output "application_insights_instrumentation_key" {
  description = "Instrumentation key for Application Insights"
  value       = azurerm_application_insights.main.instrumentation_key
  sensitive   = true
}

output "application_insights_connection_string" {
  description = "Connection string for Application Insights"
  value       = azurerm_application_insights.main.connection_string
  sensitive   = true
}

output "log_analytics_workspace_name" {
  description = "Name of Log Analytics Workspace"
  value       = azurerm_log_analytics_workspace.main.name
}

output "log_analytics_workspace_id" {
  description = "ID of Log Analytics Workspace"
  value       = azurerm_log_analytics_workspace.main.id
}

#
# Storage Outputs
#
output "storage_account_name" {
  description = "Name of the Storage Account for Functions"
  value       = azurerm_storage_account.functions.name
}

output "storage_account_id" {
  description = "ID of the Storage Account"
  value       = azurerm_storage_account.functions.id
}

#
# Deployment Information
#
output "deployment_summary" {
  description = "Summary of deployed resources"
  value = {
    environment    = var.environment
    location       = var.location
    resource_group = azurerm_resource_group.main.name
    function_app   = azurerm_linux_function_app.main.name
    web_app        = azurerm_linux_web_app.main.name
    sql_server     = azurerm_mssql_server.main.name
    sql_database   = azurerm_mssql_database.main.name
    app_insights   = azurerm_application_insights.main.name
    log_analytics  = azurerm_log_analytics_workspace.main.name
  }
}

#
# Managed Identity Principal IDs (for database permissions)
#
output "managed_identities" {
  description = "Managed Identity Principal IDs for granting database access"
  value = {
    function_app = {
      principal_id = azurerm_linux_function_app.main.identity[0].principal_id
      name         = azurerm_linux_function_app.main.name
    }
    web_app = {
      principal_id = azurerm_linux_web_app.main.identity[0].principal_id
      name         = azurerm_linux_web_app.main.name
    }
  }
}
