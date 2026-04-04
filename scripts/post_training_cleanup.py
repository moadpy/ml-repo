"""
Post-Training Cleanup Script
============================
Deletes the Online Endpoint created by training_pipeline.py to stop
the ~$0.13/hr charge that runs continuously while the endpoint exists.

Usage:
    python scripts/post_training_cleanup.py --config config/dev.yml

    # Dry-run — show what would be deleted without deleting anything:
    python scripts/post_training_cleanup.py --config config/dev.yml --dry-run

Environment variables required (same as training_pipeline.py):
    AZURE_CLIENT_ID
    AZURE_CLIENT_SECRET
    AZURE_TENANT_ID
    AZURE_SUBSCRIPTION_ID
"""

import argparse
import os
import sys

import yaml
from azure.ai.ml import MLClient
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import ClientSecretCredential


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Delete the Azure ML Online Endpoint after training")
    p.add_argument("--config", required=True, help="Path to environment config YAML (e.g. config/dev.yml)")
    p.add_argument("--dry-run", action="store_true", help="Print what would be deleted without deleting anything")
    return p.parse_args()


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


def main() -> None:
    args = parse_args()

    required_env = ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_SUBSCRIPTION_ID"]
    missing = [v for v in required_env if not os.environ.get(v)]
    if missing:
        print(f"[ERROR] Missing environment variables: {', '.join(missing)}")
        sys.exit(1)

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    endpoint_name = cfg["azure_ml"]["endpoint"]["name"]
    mode = "DRY-RUN" if args.dry_run else "LIVE"

    print(f"=== Endpoint Cleanup ({mode}) ===")
    print(f"Workspace : {cfg['azure_ml']['workspace_name']}")
    print(f"Endpoint  : {endpoint_name}\n")

    ml_client = get_ml_client(cfg)

    try:
        ml_client.online_endpoints.get(endpoint_name)
    except ResourceNotFoundError:
        print(f"Endpoint '{endpoint_name}' not found — nothing to delete.")
        return

    if args.dry_run:
        print(f"DRY-RUN: would delete endpoint '{endpoint_name}' (and all its deployments).")
        return

    print(f"Deleting endpoint '{endpoint_name}' (this may take a few minutes) ...")
    ml_client.online_endpoints.begin_delete(name=endpoint_name).result()
    print(f"Done.")


if __name__ == "__main__":
    main()
