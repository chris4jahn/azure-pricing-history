# Input variables for Azure Pricing History infrastructure

#
# Core Configuration
#
variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

variable "tenant_id" {
  description = "Azure AD tenant ID"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, test, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "Environment must be one of: dev, test, prod."
  }
}

variable "location" {
  description = "Azure region for resources"
  type        = string
  default     = "germanywestcentral"
}

variable "location_short" {
  description = "Short name for the Azure region (e.g., gwc, weu, eus)"
  type        = string
  default     = "gwc"
}

#
# SQL Server Configuration
#
variable "sql_admin_login" {
  description = "Azure AD admin login name for SQL Server"
  type        = string
}

variable "sql_admin_object_id" {
  description = "Azure AD admin object ID for SQL Server"
  type        = string
}

variable "sql_max_size_gb" {
  description = "Maximum size of the SQL database in GB"
  type        = number
  default     = 32
}

variable "sql_sku_name" {
  description = "SKU name for the SQL database (e.g., GP_S_Gen5_1 for serverless)"
  type        = string
  default     = "GP_S_Gen5_1"
}

variable "sql_min_capacity" {
  description = "Minimum capacity for serverless SQL database"
  type        = number
  default     = 0.5
}

variable "sql_auto_pause_delay" {
  description = "Auto-pause delay in minutes for serverless SQL (-1 to disable)"
  type        = number
  default     = 60
}

variable "sql_zone_redundant" {
  description = "Enable zone redundancy for SQL database"
  type        = bool
  default     = false
}

variable "sql_allow_client_ip" {
  description = "Client IP address to allow SQL Server access (optional)"
  type        = string
  default     = ""
}

#
# Monitoring Configuration
#
variable "appinsights_retention_days" {
  description = "Retention period in days for Application Insights"
  type        = number
  default     = 30

  validation {
    condition     = contains([30, 60, 90, 120, 180, 270, 365, 550, 730], var.appinsights_retention_days)
    error_message = "Retention days must be one of: 30, 60, 90, 120, 180, 270, 365, 550, 730."
  }
}

variable "log_analytics_retention_days" {
  description = "Retention period in days for Log Analytics Workspace"
  type        = number
  default     = 30

  validation {
    condition     = var.log_analytics_retention_days >= 30 && var.log_analytics_retention_days <= 730
    error_message = "Log Analytics retention must be between 30 and 730 days."
  }
}

#
# Web App Configuration
#
variable "webapp_sku_name" {
  description = "SKU name for the web app (B1, B2, B3, S1, etc.)"
  type        = string
  default     = "B1"
}

#
# Pricing API Configuration
#
variable "azure_pricing_api_version" {
  description = "Azure Retail Prices API version"
  type        = string
  default     = "2023-01-01-preview"
}

variable "pricing_currencies" {
  description = "Comma-separated list of currencies to fetch (e.g., USD,EUR)"
  type        = string
  default     = "USD,EUR"
}

variable "pricing_batch_size" {
  description = "Batch size for SQL inserts (must be <= 95 to avoid parameter limit)"
  type        = number
  default     = 90

  validation {
    condition     = var.pricing_batch_size > 0 && var.pricing_batch_size <= 95
    error_message = "Batch size must be between 1 and 95 to avoid SQL parameter limits."
  }
}

#
# Tagging
#
variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
