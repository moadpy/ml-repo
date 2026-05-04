variable "environment" {
  description = "Deployment environment (dev or prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be 'dev' or 'prod'."
  }
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "westeurope"
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
  default     = "rg-mlops-rca-dev"
}

variable "workspace_name" {
  description = "Azure ML workspace name"
  type        = string
  default     = "aml-rca-dev"
}

variable "storage_container_name" {
  description = "Blob container name for ML data"
  type        = string
  default     = "ml-data-dev"
}

# Pulled from environment so you never hard-code credentials
variable "subscription_id" {
  description = "Azure Subscription ID — set via ARM_SUBSCRIPTION_ID env var or TF_VAR_subscription_id"
  type        = string
  sensitive   = true
}
