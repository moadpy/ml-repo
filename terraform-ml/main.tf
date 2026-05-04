# ===========================================================================
# Predictive Maintenance ML — Azure Infrastructure (Dev)
# ===========================================================================
# What this creates:
#   1. Resource Group
#   2. Storage Account + Blob Containers:
#        ml-data-dev  → procedures, prompts, telemetry, ML artifacts
#        datasets     → raw input datasets (read by Azure ML training jobs)
#   3. Key Vault                         (required by Azure ML)
#   4. Application Insights              (metrics / logging for the workspace)
#   5. Log Analytics Workspace           (backend for App Insights)
#   6. Container Registry                (stores Docker images for ML envs)
#   7. Azure Machine Learning Workspace  (the ML control plane)
#   8. Service Principal                 (GitHub Actions identity — least-privilege)
#   9. Role assignments                  (SP gets Contributor on RG + Storage access)
#
# The compute cluster, training jobs, model registry, and online endpoint
# are NOT managed here — they are created dynamically by training_pipeline.py
# because Azure ML SDK handles their lifecycle more naturally.
# ===========================================================================

data "azurerm_client_config" "current" {}

# ---------------------------------------------------------------------------
# Random suffix — keeps globally-unique names collision-free
# ---------------------------------------------------------------------------
resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

locals {
  # Short suffix appended to names that need to be globally unique
  suffix = random_string.suffix.result
  tags = {
    environment = var.environment
    project     = "predictive-maintenance"
    managed_by  = "terraform"
  }
}

# ---------------------------------------------------------------------------
# 1. Resource Group
# ---------------------------------------------------------------------------
resource "azurerm_resource_group" "ml" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.tags
}

# ---------------------------------------------------------------------------
# 2. Storage Account + Blob Container
# ---------------------------------------------------------------------------
resource "azurerm_storage_account" "ml" {
  name                     = "samlops${local.suffix}"   # max 24 chars, lowercase+digits only
  resource_group_name      = azurerm_resource_group.ml.name
  location                 = azurerm_resource_group.ml.location
  account_tier             = "Standard"
  account_replication_type = "LRS"                       # cheapest replication for dev
  min_tls_version          = "TLS1_2"
  tags                     = local.tags
}

resource "azurerm_storage_container" "ml_data" {
  name                  = var.storage_container_name
  storage_account_name  = azurerm_storage_account.ml.name
  container_access_type = "private"
}

# Dedicated container for raw training datasets — isolated from ML outputs
# Azure ML training jobs read directly from this container via azureml:// URIs
resource "azurerm_storage_container" "datasets" {
  name                  = "datasets"
  storage_account_name  = azurerm_storage_account.ml.name
  container_access_type = "private"
}

# ---------------------------------------------------------------------------
# 3. Key Vault (Azure ML workspace requires one)
# ---------------------------------------------------------------------------
resource "azurerm_key_vault" "ml" {
  name                       = "kv-mlops-${local.suffix}"
  resource_group_name        = azurerm_resource_group.ml.name
  location                   = azurerm_resource_group.ml.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 7
  purge_protection_enabled   = false   # keep false for dev so we can clean up easily
  tags                       = local.tags
}

# Give the Terraform caller (you) full access so the workspace can write secrets
resource "azurerm_key_vault_access_policy" "terraform_caller" {
  key_vault_id = azurerm_key_vault.ml.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions      = ["Get", "List", "Set", "Delete", "Purge", "Recover"]
  key_permissions         = ["Get", "List", "Create", "Delete", "Purge", "Recover"]
  certificate_permissions = ["Get", "List", "Create", "Delete", "Purge", "Recover"]
}

# ---------------------------------------------------------------------------
# 4 & 5. Log Analytics Workspace + Application Insights
# ---------------------------------------------------------------------------
resource "azurerm_log_analytics_workspace" "ml" {
  name                = "law-mlops-${local.suffix}"
  resource_group_name = azurerm_resource_group.ml.name
  location            = azurerm_resource_group.ml.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.tags
}

resource "azurerm_application_insights" "ml" {
  name                = "appi-mlops-${local.suffix}"
  resource_group_name = azurerm_resource_group.ml.name
  location            = azurerm_resource_group.ml.location
  workspace_id        = azurerm_log_analytics_workspace.ml.id
  application_type    = "web"
  tags                = local.tags
}

# ---------------------------------------------------------------------------
# 6. Container Registry (Azure ML builds conda envs into Docker images)
# ---------------------------------------------------------------------------
resource "azurerm_container_registry" "ml" {
  name                = "crmlops${local.suffix}"
  resource_group_name = azurerm_resource_group.ml.name
  location            = azurerm_resource_group.ml.location
  sku                 = "Standard" # free for 12 months on new Azure accounts
  admin_enabled       = true
  tags                = local.tags
}

# ---------------------------------------------------------------------------
# 7. Azure Machine Learning Workspace
# ---------------------------------------------------------------------------
resource "azurerm_machine_learning_workspace" "ml" {
  name                    = var.workspace_name
  resource_group_name     = azurerm_resource_group.ml.name
  location                = azurerm_resource_group.ml.location
  application_insights_id = azurerm_application_insights.ml.id
  key_vault_id            = azurerm_key_vault.ml.id
  storage_account_id      = azurerm_storage_account.ml.id
  container_registry_id   = azurerm_container_registry.ml.id
  tags                    = local.tags

  identity {
    type = "SystemAssigned"
  }

  depends_on = [azurerm_key_vault_access_policy.terraform_caller]
}

# ---------------------------------------------------------------------------
# 8. Service Principal — used by GitHub Actions (and training_pipeline.py)
# ---------------------------------------------------------------------------
resource "azuread_application" "github_actions" {
  display_name = "sp-mlops-github-actions-${var.environment}"
}

resource "azuread_service_principal" "github_actions" {
  client_id = azuread_application.github_actions.client_id
}

resource "azuread_service_principal_password" "github_actions" {
  service_principal_id = azuread_service_principal.github_actions.id
  end_date_relative    = "8760h"   # 1 year
}

# ---------------------------------------------------------------------------
# 9. Role Assignments
# ---------------------------------------------------------------------------

# Contributor on the Resource Group — lets the SP create/manage all resources
# including the compute cluster and online endpoint inside the AML workspace
resource "azurerm_role_assignment" "sp_contributor" {
  scope                = azurerm_resource_group.ml.id
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.github_actions.object_id
}

# Storage Blob Data Contributor — lets the SP upload the dataset and read outputs
resource "azurerm_role_assignment" "sp_storage_blob" {
  scope                = azurerm_storage_account.ml.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azuread_service_principal.github_actions.object_id
}

# AcrPull — lets Azure ML pull the training Docker image from the registry
resource "azurerm_role_assignment" "aml_acr_pull" {
  scope                = azurerm_container_registry.ml.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_machine_learning_workspace.ml.identity[0].principal_id
}
