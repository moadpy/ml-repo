"""
Post-training cleanup — retire old Online Endpoint deployments.

After a Blue/Green swap, the old deployment still consumes instance resources.
This script deletes all non-traffic deployments from the RCA endpoint.

Called by ml_train.yml after a successful deploy step.

Usage:
    python scripts/post_training_cleanup.py --config config/dev.yml --keep blue

Environment variables:
    AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID
"""

import argparse
import os

import yaml
from azure.ai.ml import MLClient
from azure.identity import ClientSecretCredential


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Clean up old Online Endpoint deployments")
    p.add_argument("--config", required=True, help="Path to environment config YAML")
    p.add_argument(
        "--keep",
        required=True,
        help="Deployment name to keep (receives 100%% traffic). All others are deleted.",
    )
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


def cleanup(ml_client: MLClient, endpoint_name: str, keep: str) -> None:
    try:
        endpoint = ml_client.online_endpoints.get(endpoint_name)
    except Exception:
        print(f"[cleanup] Endpoint '{endpoint_name}' not found — nothing to clean.")
        return

    deployments = list(ml_client.online_deployments.list(endpoint_name=endpoint_name))
    print(f"[cleanup] Found {len(deployments)} deployment(s) on '{endpoint_name}'.")

    for dep in deployments:
        if dep.name == keep:
            print(f"[cleanup] Keeping deployment '{dep.name}' (active).")
            continue

        traffic_pct = endpoint.traffic.get(dep.name, 0)
        if traffic_pct > 0:
            print(
                f"[cleanup] Skipping deployment '{dep.name}' — still receives {traffic_pct}%% traffic. "
                "Manually verify before deleting."
            )
            continue

        print(f"[cleanup] Deleting deployment '{dep.name}' (0%% traffic)...")
        ml_client.online_deployments.begin_delete(
            name=dep.name, endpoint_name=endpoint_name
        ).result()
        print(f"[cleanup] Deleted '{dep.name}'.")

    print("[cleanup] Done.")


def main() -> None:
    args = parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    endpoint_name = cfg["azure_ml"]["endpoint"]["name"]
    print(f"\n=== Post-training cleanup | endpoint={endpoint_name} | keep={args.keep} ===\n")

    ml_client = get_ml_client(cfg)
    cleanup(ml_client, endpoint_name, keep=args.keep)


if __name__ == "__main__":
    main()
