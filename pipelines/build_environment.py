import argparse
import os
import yaml
from azure.ai.ml import MLClient
from azure.ai.ml.entities import Environment, BuildContext
from azure.identity import DefaultAzureCredential

ENVIRONMENT_NAME = "rca-training-env"

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Register Azure ML Custom Environment")
    p.add_argument("--config", required=True, help="Path to environment YAML (e.g. config/dev.yml)")
    return p.parse_args()

def get_ml_client(cfg: dict) -> MLClient:
    credential = DefaultAzureCredential()
    return MLClient(
        credential=credential,
        subscription_id=os.environ["AZURE_SUBSCRIPTION_ID"],
        resource_group_name=cfg["azure"]["resource_group"],
        workspace_name=cfg["azure_ml"]["workspace_name"],
    )

def main():
    args = parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    print(f"\n=== Registering Custom Environment for {cfg.get('environment', 'dev')} ===")
    
    ml_client = get_ml_client(cfg)
    env_name = cfg["azure_ml"].get("environment_name", ENVIRONMENT_NAME)

    env = Environment(
        name=env_name,
        description="RCA incident signature classifier — Custom Docker build",
        build=BuildContext(
            path="environments",
            dockerfile_path="Dockerfile"
        )
    )

    print(f"Submitting environment context to Azure ML...")
    registered_env = ml_client.environments.create_or_update(env)
    
    print(f"✅ Successfully registered environment '{env_name}' version {registered_env.version}")
    print(f"View in Studio: https://ml.azure.com/environments/{env_name}/version/{registered_env.version}?wsid=/subscriptions/{os.environ['AZURE_SUBSCRIPTION_ID']}/resourcegroups/{cfg['azure']['resource_group']}/workspaces/{cfg['azure_ml']['workspace_name']}")

if __name__ == "__main__":
    main()
