# ===========================================================================
# Outputs — copy these values into GitHub Actions secrets
# ===========================================================================

output "resource_group_name" {
  description = "Name of the resource group"
  value       = azurerm_resource_group.ml.name
}

output "azure_ml_workspace_name" {
  description = "Azure ML workspace name (used in config/dev.yml → azure_ml.workspace_name)"
  value       = azurerm_machine_learning_workspace.ml.name
}

output "storage_account_name" {
  description = "Storage account name (needed for blob_sync.yml → STORAGE_ACCOUNT_DEV secret)"
  value       = azurerm_storage_account.ml.name
}

output "storage_container_name" {
  description = "Blob container for datasets and ML outputs"
  value       = azurerm_storage_container.ml_data.name
}

output "container_registry_login_server" {
  description = "ACR login server (for reference)"
  value       = azurerm_container_registry.ml.login_server
}

# ---------------------------------------------------------------------------
# GitHub Actions secrets — add these to repo Settings > Secrets
# ---------------------------------------------------------------------------

output "AZURE_CLIENT_ID" {
  description = "GitHub Actions secret: AZURE_CLIENT_ID"
  value       = azuread_application.github_actions.client_id
}

output "AZURE_CLIENT_SECRET" {
  description = "GitHub Actions secret: AZURE_CLIENT_SECRET (sensitive)"
  value       = azuread_service_principal_password.github_actions.value
  sensitive   = true
}

output "AZURE_TENANT_ID" {
  description = "GitHub Actions secret: AZURE_TENANT_ID"
  value       = data.azurerm_client_config.current.tenant_id
}

output "AZURE_SUBSCRIPTION_ID" {
  description = "GitHub Actions secret: AZURE_SUBSCRIPTION_ID"
  value       = var.subscription_id
  sensitive   = true
}

output "STORAGE_ACCOUNT_DEV" {
  description = "GitHub Actions secret: STORAGE_ACCOUNT_DEV (used by blob_sync.yml)"
  value       = azurerm_storage_account.ml.name
}

output "instructions" {
  description = "Next steps after terraform apply"
  value       = <<-EOT
    ============================================================
    NEXT STEPS
    ============================================================
    1. Run:  terraform output -json > terraform_outputs.json
       Then add these values as GitHub Actions secrets:
         AZURE_CLIENT_ID        = ${azuread_application.github_actions.client_id}
         AZURE_CLIENT_SECRET    = (run: terraform output -raw AZURE_CLIENT_SECRET)
         AZURE_TENANT_ID        = ${data.azurerm_client_config.current.tenant_id}
         AZURE_SUBSCRIPTION_ID  = <your subscription id>
         STORAGE_ACCOUNT_DEV    = ${azurerm_storage_account.ml.name}

    2. Download the Kaggle dataset and place it at:
         data/predictive_maintenance.csv

    3. Trigger the training workflow manually via GitHub Actions
       (ml_train.yml > Run workflow) or push a change to develop branch.

    See POC_GUIDE.md for the full step-by-step walkthrough.
    ============================================================
  EOT
}
