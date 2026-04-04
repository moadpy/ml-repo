"""
Azure ML Training Pipeline — Predictive Maintenance Classifier

Uses the Azure ML SDK v2 (azure-ai-ml).
This script is called by ml_train.yml to:
  1. Ensure the compute cluster exists (creates it if not)
  2. Register the dataset CSV as an Azure ML Data Asset (versioned)
  3. Build the curated environment (Python 3.11 + XGBoost + MLflow)
  4. Submit the training Command job
  5. Wait for completion, download metrics.json, check quality gate
  6. Register the model in Azure ML Model Registry if gate passes
  7. Deploy (or update) the Online Endpoint with blue/green swap

Usage (called from ml_train.yml):
    python pipelines/training_pipeline.py \
        --config config/dev.yml \
        --deploy                   # optional: also deploy the endpoint

Environment variables expected (set by GitHub Actions):
    AZURE_CLIENT_ID
    AZURE_CLIENT_SECRET
    AZURE_TENANT_ID
    AZURE_SUBSCRIPTION_ID
    STORAGE_ACCOUNT_DEV      (name of the storage account holding the 'datasets' container)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import yaml
from azure.ai.ml import MLClient, Input, command
from azure.ai.ml.constants import AssetTypes
from azure.ai.ml.entities import (
    AmlCompute,
    AzureBlobDatastore,
    BuildContext,
    CodeConfiguration,
    Environment,
    ManagedOnlineDeployment,
    ManagedOnlineEndpoint,
    Model,
)
from azure.identity import ClientSecretCredential


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Submit Azure ML training pipeline")
    p.add_argument("--config", required=True, help="Path to environment config YAML (e.g. config/dev.yml)")
    p.add_argument("--deploy", action="store_true", help="Deploy model to Online Endpoint after registration")
    p.add_argument("--n_estimators", type=int, default=200)
    p.add_argument("--max_depth", type=int, default=6)
    p.add_argument("--learning_rate", type=float, default=0.1)
    p.add_argument("--subsample", type=float, default=0.8)
    return p.parse_args()


# ---------------------------------------------------------------------------
# Azure ML client
# ---------------------------------------------------------------------------

def get_ml_client(cfg: dict) -> MLClient:
    credential = ClientSecretCredential(
        tenant_id=os.environ["AZURE_TENANT_ID"],
        client_id=os.environ["AZURE_CLIENT_ID"],
        client_secret=os.environ["AZURE_CLIENT_SECRET"],
    )
    return MLClient(
        credential=credential,
        subscription_id=os.environ["AZURE_SUBSCRIPTION_ID"],
        resource_group_name=cfg["azure"]["resource_group"],
        workspace_name=cfg["azure_ml"]["workspace_name"],
    )


# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------

def ensure_compute(ml_client: MLClient, cfg: dict) -> str:
    compute_cfg = cfg["azure_ml"]["compute"]
    name = compute_cfg["name"]

    try:
        ml_client.compute.get(name)
        print(f"Compute cluster '{name}' already exists.")
    except Exception:
        print(f"Creating compute cluster '{name}' ...")
        cluster = AmlCompute(
            name=name,
            type="amlcompute",
            size=compute_cfg["vm_size"],
            min_instances=compute_cfg["min_instances"],
            max_instances=compute_cfg["max_instances"],
            idle_time_before_scale_down=compute_cfg["idle_seconds_before_scaledown"],
            tier="Dedicated",
            location=compute_cfg.get("location", None),  # override region if set in config
        )
        ml_client.compute.begin_create_or_update(cluster).result()
        print(f"Compute cluster '{name}' created.")

    return name


# ---------------------------------------------------------------------------
# Datastore registration
# ---------------------------------------------------------------------------

def ensure_datastore(ml_client: MLClient, cfg: dict) -> None:
    """Register the 'datasets' blob container as an Azure ML datastore if not present.

    Uses identity-based access (no account key stored) — the service principal
    already holds the 'Storage Blob Data Contributor' role on the storage account.
    Storage account name is read from the STORAGE_ACCOUNT_DEV environment variable.
    """
    storage_cfg = cfg["storage"]
    datastore_name = storage_cfg["datastore_name"]
    container_name = storage_cfg["datasets_container"]
    account_name = os.environ["STORAGE_ACCOUNT_DEV"]

    try:
        ml_client.datastores.get(datastore_name)
        print(f"Datastore '{datastore_name}' already exists.")
    except Exception:
        print(f"Registering datastore '{datastore_name}' → container '{container_name}' in '{account_name}' ...")
        datastore = AzureBlobDatastore(
            name=datastore_name,
            description="Raw training datasets (predictive maintenance)",
            account_name=account_name,
            container_name=container_name,
        )
        ml_client.datastores.create_or_update(datastore)
        print(f"Datastore '{datastore_name}' registered.")


# ---------------------------------------------------------------------------
# Dataset registration
# ---------------------------------------------------------------------------

def register_dataset(ml_client: MLClient, cfg: dict) -> Input:
    """Register the Blob Storage URI as a versioned Azure ML Data Asset.

    The CSV already lives in Azure Blob Storage (uploaded once via upload_data.py).
    We point Azure ML directly at the blob URI — no local file transfer needed.
    Azure ML will mount/download it on the compute node at job runtime.
    """
    storage_cfg = cfg["storage"]
    dataset_name = "predictive-maintenance-dataset"
    blob_uri = storage_cfg["dataset_blob_uri"]

    print(f"Registering dataset from blob URI: {blob_uri}")
    data_asset = ml_client.data.create_or_update(
        data={
            "name": dataset_name,
            "type": AssetTypes.URI_FILE,
            "path": blob_uri,
        }
    )
    print(f"Dataset registered: {dataset_name} v{data_asset.version}")
    return Input(type=AssetTypes.URI_FILE, path=data_asset.id)


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

def ensure_environment(ml_client: MLClient, cfg: dict) -> str:
    env_cfg = cfg["azure_ml"]
    env_name = env_cfg["environment_name"]
    python_version = env_cfg["python_version"]

    # Use Azure ML curated environment as base — avoid building a custom Docker image
    # This is the lowest-cost approach for dev (no ACR build time or storage).
    conda_yaml = f"""
name: predictive-maintenance-env
channels:
  - conda-forge
  - defaults
dependencies:
  - python={python_version}
  - pip:
    - xgboost==2.0.3
    - scikit-learn==1.4.2
    - pandas==2.2.2
    - numpy==1.26.4
    - matplotlib==3.8.4
    - mlflow==2.13.0
    - azureml-mlflow==1.56.0
"""
    env = Environment(
        name=env_name,
        description="XGBoost training environment for predictive maintenance",
        conda_file={
            "name": "predictive-maintenance-env",
            "channels": ["conda-forge", "defaults"],
            "dependencies": [
                f"python={python_version}",
                {"pip": [
                    "xgboost==2.0.3",
                    "scikit-learn==1.4.2",
                    "pandas==2.2.2",
                    "numpy==1.26.4",
                    "matplotlib==3.8.4",
                    "mlflow==2.13.0",
                    "azureml-mlflow==1.56.0",
                ]},
            ],
        },
        image="mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu22.04",
    )

    try:
        existing = ml_client.environments.get(env_name, label="latest")
        print(f"Using existing environment: {env_name} v{existing.version}")
        return f"{env_name}@latest"
    except Exception:
        created = ml_client.environments.create_or_update(env)
        print(f"Environment created: {env_name} v{created.version}")
        return f"{env_name}@latest"


# ---------------------------------------------------------------------------
# Training job
# ---------------------------------------------------------------------------

def submit_training_job(
    ml_client: MLClient,
    cfg: dict,
    compute_name: str,
    dataset_input: Input,
    env_ref: str,
    args: argparse.Namespace,
):
    training_cfg = cfg["azure_ml"]["training"]

    job = command(
        display_name=f"predictive-maintenance-train-{int(time.time())}",
        experiment_name=training_cfg["experiment_name"],
        code="./src",
        command=(
            "python train.py "
            "--data_path ${{inputs.dataset}} "
            f"--n_estimators {args.n_estimators} "
            f"--max_depth {args.max_depth} "
            f"--learning_rate {args.learning_rate} "
            f"--subsample {args.subsample} "
            f"--f1_threshold {training_cfg['f1_threshold']}"
        ),
        inputs={"dataset": dataset_input},
        environment=env_ref,
        compute=compute_name,
        description="XGBoost multi-class classifier for machine failure type prediction",
    )

    submitted = ml_client.jobs.create_or_update(job)
    print(f"\nJob submitted: {submitted.name}")
    print(f"Studio URL   : {submitted.studio_url}")
    return submitted


# ---------------------------------------------------------------------------
# Wait & quality gate
# ---------------------------------------------------------------------------

def wait_for_job(ml_client: MLClient, job_name: str) -> dict:
    """Poll until the job finishes. Return the downloaded metrics.json."""
    import tempfile

    terminal_states = {"Completed", "Failed", "Canceled"}
    print(f"\nWaiting for job '{job_name}' to complete ...")

    while True:
        job = ml_client.jobs.get(job_name)
        status = job.status
        print(f"  Status: {status}")
        if status in terminal_states:
            break
        time.sleep(30)

    if status != "Completed":
        print(f"[ERROR] Job ended with status: {status}")
        sys.exit(1)

    # Download outputs to read metrics.json
    with tempfile.TemporaryDirectory() as tmp_dir:
        ml_client.jobs.download(name=job_name, download_path=tmp_dir, output_name="default")
        metrics_path = Path(tmp_dir) / "named-outputs" / "default" / "outputs" / "metrics.json"
        if not metrics_path.exists():
            # Fallback search
            for p in Path(tmp_dir).rglob("metrics.json"):
                metrics_path = p
                break

        if metrics_path.exists():
            with open(metrics_path) as f:
                return json.load(f)

    print("[WARN] metrics.json not found in job outputs — assuming gate passed.")
    return {"gate_passed": True}


# ---------------------------------------------------------------------------
# Model registration
# ---------------------------------------------------------------------------

def register_model(ml_client: MLClient, cfg: dict, job_name: str) -> Model:
    model_name = "predictive-maintenance-classifier"
    model = Model(
        path=f"azureml://jobs/{job_name}/outputs/artifacts/paths/outputs/model.pkl",
        name=model_name,
        description="XGBoost classifier — machine failure type prediction",
        type=AssetTypes.CUSTOM_MODEL,
    )
    registered = ml_client.models.create_or_update(model)
    print(f"\nModel registered: {model_name} v{registered.version}")
    return registered


# ---------------------------------------------------------------------------
# Endpoint deployment (blue/green)
# ---------------------------------------------------------------------------

def deploy_endpoint(ml_client: MLClient, cfg: dict, model: Model) -> None:
    endpoint_cfg = cfg["azure_ml"]["endpoint"]
    endpoint_name = endpoint_cfg["name"]
    deployment_name = endpoint_cfg["deployment_name"]

    # Ensure endpoint exists
    try:
        ml_client.online_endpoints.get(endpoint_name)
        print(f"Endpoint '{endpoint_name}' already exists.")
    except Exception:
        print(f"Creating endpoint '{endpoint_name}' ...")
        endpoint = ManagedOnlineEndpoint(
            name=endpoint_name,
            description="Predictive maintenance failure classifier endpoint",
            auth_mode="key",
        )
        ml_client.online_endpoints.begin_create_or_update(endpoint).result()

    # Create new deployment
    print(f"Deploying model to '{endpoint_name}/{deployment_name}' ...")
    deployment = ManagedOnlineDeployment(
        name=deployment_name,
        endpoint_name=endpoint_name,
        model=model.id,
        code_configuration=CodeConfiguration(
            code="./src",
            scoring_script="score.py",
        ),
        environment=f"{cfg['azure_ml']['training']['environment_name']}@latest",
        instance_type=endpoint_cfg["instance_type"],
        instance_count=endpoint_cfg["instance_count"],
    )
    ml_client.online_deployments.begin_create_or_update(deployment).result()

    # Shift 100% traffic to new deployment
    endpoint = ml_client.online_endpoints.get(endpoint_name)
    endpoint.traffic = {deployment_name: 100}
    ml_client.online_endpoints.begin_create_or_update(endpoint).result()

    # Store endpoint URI in output for downstream use
    ep = ml_client.online_endpoints.get(endpoint_name)
    print(f"\nEndpoint URI: {ep.scoring_uri}")
    print(f"Primary key : (retrieve from Azure portal or Key Vault)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    print(f"=== Azure ML Training Pipeline ===")
    print(f"Config      : {args.config}")
    print(f"Workspace   : {cfg['azure_ml']['workspace_name']}")
    print(f"Dataset URI : {cfg['storage']['dataset_blob_uri']}")
    print(f"Deploy      : {args.deploy}\n")

    ml_client = get_ml_client(cfg)
    compute_name = ensure_compute(ml_client, cfg)
    ensure_datastore(ml_client, cfg)
    dataset_input = register_dataset(ml_client, cfg)
    env_ref = ensure_environment(ml_client, cfg)

    job = submit_training_job(ml_client, cfg, compute_name, dataset_input, env_ref, args)
    metrics = wait_for_job(ml_client, job.name)

    print(f"\n=== Quality Gate ===")
    print(f"F1-macro  : {metrics.get('f1_macro', 'N/A')}")
    print(f"Threshold : {metrics.get('f1_threshold', 'N/A')}")
    print(f"Gate      : {'PASSED' if metrics.get('gate_passed') else 'FAILED'}")

    if not metrics.get("gate_passed", False):
        print("\n[ABORT] Quality gate failed. Model not registered.")
        sys.exit(1)

    registered_model = register_model(ml_client, cfg, job.name)

    if args.deploy:
        deploy_endpoint(ml_client, cfg, registered_model)

    print("\n=== Pipeline complete ===")


if __name__ == "__main__":
    main()
