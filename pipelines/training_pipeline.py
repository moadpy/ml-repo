"""
Azure ML Training Pipeline — RCA Incident Signature Classifier

Uses the Azure ML SDK v2 (azure-ai-ml).
Called by ml_train.yml to:
  1. Ensure the compute cluster exists (creates it if needed)
  2. Register/update the Azure ML Datastore pointing to the 'datasets' blob container
  3. Register telemetry_labeled.csv as a versioned Azure ML Data Asset
  4. Build the curated training environment (Python 3.11 + XGBoost + MLflow)
  5. Submit the training Command job
  6. Wait for completion and download metrics.json
  7. Gate: register model only if F1-macro >= threshold
  8. Deploy (Blue/Green) to Azure ML Online Endpoint if --deploy is passed

Usage (called from ml_train.yml):
    python pipelines/training_pipeline.py \\
        --config config/dev.yml \\
        --deploy

Environment variables (set by GitHub Actions):
    AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID
    STORAGE_ACCOUNT_DEV   (name of storage account holding the 'datasets' container)
    STORAGE_ACCOUNT_PROD  (for prod deployments)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import yaml
from azure.ai.ml import MLClient, Input, command
from azure.ai.ml.constants import AssetTypes
from azure.ai.ml.entities import (
    AzureBlobDatastore,
    Data,
    Environment,
    ManagedOnlineDeployment,
    ManagedOnlineEndpoint,
    Model,
    CodeConfiguration,
)
from azure.identity import DefaultAzureCredential

MODEL_NAME = "incident-signature-classifier"
ENVIRONMENT_NAME = "rca-training-env"

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Submit Azure ML RCA training pipeline")
    p.add_argument("--config", required=True, help="Path to environment YAML (e.g. config/dev.yml)")
    p.add_argument("--deploy", action="store_true", help="Deploy model to Online Endpoint after registration")
    p.add_argument("--deploy-only", action="store_true", help="Skip training and deploy the latest registered model")
    p.add_argument("--n_estimators", type=int, default=200)
    p.add_argument("--max_depth", type=int, default=6)
    p.add_argument("--learning_rate", type=float, default=0.1)
    p.add_argument("--subsample", type=float, default=0.8)
    return p.parse_args()


# ---------------------------------------------------------------------------
# Azure ML client
# ---------------------------------------------------------------------------

def get_ml_client(cfg: dict) -> MLClient:
    credential = DefaultAzureCredential()
    return MLClient(
        credential=credential,
        subscription_id=os.environ["AZURE_SUBSCRIPTION_ID"],
        resource_group_name=cfg["azure"]["resource_group"],
        workspace_name=cfg["azure_ml"]["workspace_name"],
    )





# ---------------------------------------------------------------------------
# Step 2 — Ensure datastore
# ---------------------------------------------------------------------------

def ensure_datastore(ml_client: MLClient, cfg: dict, storage_account: str) -> str:
    """Register (or update) the Azure ML Datastore. Returns datastore name."""
    ds_name = cfg["storage"]["datastore_name"]
    container = cfg["storage"]["datasets_container"]

    try:
        ml_client.datastores.get(ds_name)
        print(f"[datastore] '{ds_name}' already registered.")
    except Exception:
        print(f"[datastore] Registering datastore '{ds_name}' → {storage_account}/{container}")
        datastore = AzureBlobDatastore(
            name=ds_name,
            account_name=storage_account,
            container_name=container,
            credentials=None, # Uses identity-based access (OIDC/Managed Identity)
        )
        ml_client.datastores.create_or_update(datastore)
        print(f"[datastore] Datastore '{ds_name}' registered.")

    return ds_name


# ---------------------------------------------------------------------------
# Step 3 — Register dataset
# ---------------------------------------------------------------------------

def register_dataset(ml_client: MLClient, cfg: dict) -> str:
    """Upload telemetry_labeled.csv and register as an Azure ML Data Asset."""
    dataset_uri = cfg["storage"]["dataset_blob_uri"]
    asset_name = "incident-signature-dataset"

    data_asset = Data(
        name=asset_name,
        description="Labeled incident snapshots for RCA signature classification (6 classes)",
        type=AssetTypes.URI_FILE,
        path=dataset_uri,
    )

    registered = ml_client.data.create_or_update(data_asset)
    print(f"[dataset] Registered '{asset_name}' version {registered.version} → {dataset_uri}")
    return f"azureml:{asset_name}:{registered.version}"


# ---------------------------------------------------------------------------
# Step 5 — Submit training job
# ---------------------------------------------------------------------------

def submit_training_job(
    ml_client: MLClient,
    cfg: dict,
    dataset_uri: str,
    env_versioned: str,
    args_ns: argparse.Namespace,
) -> str:
    """Submit a Command job and return the run ID."""
    train_cfg = cfg["azure_ml"]["training"]
    comp_name = cfg["azure_ml"]["compute"]["name"]
    f1_threshold = train_cfg.get("f1_threshold", 0.72)

    job = command(
        code="./src",
        command=(
            "python train.py "
            "--data_path ${{inputs.dataset}} "
            f"--n_estimators {args_ns.n_estimators} "
            f"--max_depth {args_ns.max_depth} "
            f"--learning_rate {args_ns.learning_rate} "
            f"--subsample {args_ns.subsample} "
            f"--f1_threshold {f1_threshold}"
        ),
        inputs={
            "dataset": Input(type=AssetTypes.URI_FILE, path=dataset_uri),
        },
        environment=env_versioned,
        compute=comp_name,
        experiment_name=train_cfg["experiment_name"],
        display_name="rca-signature-classifier-training",
        tags={
            "task": "incident_signature_classification",
            "model": "XGBoostClassifier",
            "classes": "6",
        },
    )

    submitted_job = ml_client.jobs.create_or_update(job)
    run_id = submitted_job.name
    print(f"[job] Submitted training job: {run_id}")
    print(f"[job] Monitor at: {submitted_job.studio_url}")
    return run_id


# ---------------------------------------------------------------------------
# Step 6 — Wait for job and read metrics
# ---------------------------------------------------------------------------

def wait_for_job(ml_client: MLClient, run_id: str, timeout_seconds: int = 3600) -> dict:
    """Poll until job is done. Returns metrics.json dict or empty dict on failure."""
    print(f"[job] Waiting for job '{run_id}' (timeout: {timeout_seconds}s)...")
    terminal_states = {"Completed", "Failed", "Canceled"}
    elapsed = 0
    poll_interval = 30

    while elapsed < timeout_seconds:
        job = ml_client.jobs.get(run_id)
        status = job.status
        print(f"  [{elapsed}s] Status: {status}")

        if status in terminal_states:
            if status != "Completed":
                print(f"[job] Job ended with status '{status}'. Aborting.")
                sys.exit(1)
            break

        time.sleep(poll_interval)
        elapsed += poll_interval
    else:
        print(f"[job] Timeout after {timeout_seconds}s. Aborting.")
        sys.exit(1)

    # Download metrics.json from job outputs
    try:
        output_dir = "/tmp/job_outputs"
        ml_client.jobs.download(run_id, download_path=output_dir, output_name="default")
        
        # Azure ML SDK download folder structures vary depending on versions and outputs setup
        possible_paths = [
            Path(output_dir) / "named-outputs" / "default" / "outputs" / "metrics.json",
            Path(output_dir) / "artifacts" / "outputs" / "metrics.json",
            Path(output_dir) / "artifacts" / "metrics.json",
            Path(output_dir) / "outputs" / "metrics.json"
        ]
        
        for p in possible_paths:
            if p.exists():
                with open(p) as f:
                    metrics = json.load(f)
                print(f"[job] Metrics found at {p}: {metrics}")
                return metrics
                
        print(f"[job] Warning: metrics.json not found in {output_dir}")
    except Exception as e:
        print(f"[job] Could not download metrics: {e}")

    return {}


# ---------------------------------------------------------------------------
# Step 7 — Register model
# ---------------------------------------------------------------------------

def register_model(ml_client: MLClient, run_id: str, cfg: dict) -> Optional[str]:
    """Register the model from the job output. Returns model version or None."""
    env = cfg.get("environment", "dev")
    model = Model(
        name=MODEL_NAME,
        description=f"RCA incident signature classifier — 6-class XGBoost ({env})",
        path=f"azureml://jobs/{run_id}/outputs/default/outputs/model.pkl",
        type="custom_model",
        tags={
            "task": "incident_signature_classification",
            "environment": env,
            "num_classes": "6",
        },
    )
    registered = ml_client.models.create_or_update(model)
    print(f"[model] Registered '{MODEL_NAME}' version {registered.version}")
    return registered.version


# ---------------------------------------------------------------------------
# Step 8 — Deploy (Blue/Green)
# ---------------------------------------------------------------------------

def deploy_endpoint(ml_client: MLClient, model_version: str, cfg: dict) -> None:
    ep_cfg = cfg["azure_ml"]["endpoint"]
    endpoint_name = ep_cfg["name"]
    deployment_name = ep_cfg.get("deployment_name", "blue")

    # Ensure endpoint exists
    try:
        ml_client.online_endpoints.get(endpoint_name)
        print(f"[endpoint] '{endpoint_name}' already exists.")
    except Exception:
        print(f"[endpoint] Creating endpoint '{endpoint_name}'...")
        endpoint = ManagedOnlineEndpoint(
            name=endpoint_name,
            description="RCA incident signature classifier endpoint",
            auth_mode="key",
        )
        ml_client.online_endpoints.begin_create_or_update(endpoint).result()
        print(f"[endpoint] Endpoint '{endpoint_name}' created.")

    # Deploy new Blue version
    print(f"[deploy] Deploying model version {model_version} as '{deployment_name}'...")
    train_cfg = cfg["azure_ml"].get("training", {})
    env_name = train_cfg.get("environment_name", ENVIRONMENT_NAME)
    env_version = str(train_cfg.get("environment_version", "latest"))
    if env_version.lower() == "latest":
        env_versioned = f"azureml:{env_name}@latest"
    else:
        env_versioned = f"azureml:{env_name}:{env_version}"

    deployment = ManagedOnlineDeployment(
        name=deployment_name,
        endpoint_name=endpoint_name,
        model=f"{MODEL_NAME}:{model_version}",
        code_configuration=CodeConfiguration(
            code="./src",
            scoring_script="score.py",
        ),
        environment=env_versioned,
        instance_type=ep_cfg["instance_type"],
        instance_count=ep_cfg["instance_count"],
    )

    ml_client.online_deployments.begin_create_or_update(deployment).result()

    # Route 100% traffic to the new deployment
    endpoint = ml_client.online_endpoints.get(endpoint_name)
    endpoint.traffic = {deployment_name: 100}
    ml_client.online_endpoints.begin_create_or_update(endpoint).result()

    print(f"[deploy] 100% traffic now on '{deployment_name}' (model v{model_version}).")
    print(f"[deploy] Endpoint URI: {ml_client.online_endpoints.get(endpoint_name).scoring_uri}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    env_label = cfg.get("environment", "dev")
    storage_account_env = "STORAGE_ACCOUNT_PROD" if env_label == "prod" else "STORAGE_ACCOUNT_DEV"
    storage_account = os.environ[storage_account_env]

    print(f"\n=== RCA Training Pipeline | env={env_label} | storage={storage_account} ===\n")

    ml_client = get_ml_client(cfg)

    if args.deploy_only:
        print("\n[deploy] --deploy-only flag passed. Skipping training...")
        latest_model = ml_client.models.get(name=MODEL_NAME, label="latest")
        print(f"[deploy] Found latest model '{MODEL_NAME}' version {latest_model.version}")
        deploy_endpoint(ml_client, latest_model.version, cfg)
        print("\n=== Pipeline complete ===")
        return

    ensure_datastore(ml_client, cfg, storage_account)
    dataset_uri = register_dataset(ml_client, cfg)
    
    # Use the environment registered by the dedicated environment CI job
    train_cfg = cfg["azure_ml"].get("training", {})
    env_name = train_cfg.get("environment_name", ENVIRONMENT_NAME)
    env_version = str(train_cfg.get("environment_version", "latest"))
    if env_version.lower() == "latest":
        env_versioned = f"azureml:{env_name}@latest"
    else:
        env_versioned = f"azureml:{env_name}:{env_version}"
    print(f"[env] Using pre-built environment '{env_versioned}'")

    run_id = submit_training_job(ml_client, cfg, dataset_uri, env_versioned, args)
    metrics = wait_for_job(ml_client, run_id)

    f1_threshold = cfg["azure_ml"]["training"].get("f1_threshold", 0.72)
    f1_macro = metrics.get("f1_macro", 0.0)

    if f1_macro < f1_threshold:
        print(f"\n[GATE FAILED] F1-macro={f1_macro:.4f} < threshold={f1_threshold}. Model NOT registered.")
        sys.exit(1)

    print(f"\n[GATE PASSED] F1-macro={f1_macro:.4f} >= {f1_threshold}.")
    model_version = register_model(ml_client, run_id, cfg)

    if args.deploy:
        deploy_endpoint(ml_client, model_version, cfg)

    print("\n=== Pipeline complete ===")


if __name__ == "__main__":
    main()
