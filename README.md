# ml-repo — Predictive Maintenance MLOps

ML training source repo for the Azure industrial predictive maintenance platform.
Trains an XGBoost classifier on machine sensor telemetry to predict failure types.
Also hosts the RAG knowledge base (maintenance procedures) and GPT-4o system prompt.

---

## Repository Structure

```
ml-repo/
├── .github/workflows/
│   ├── ml_ci.yml           # Lint + unit tests — triggers on PR
│   ├── ml_train.yml        # Submit Azure ML training job — triggers on merge
│   └── blob_sync.yml       # Sync procedures/ + prompts/ to Blob Storage
├── src/
│   ├── train.py            # Azure ML training script (XGBoost + MLflow)
│   ├── preprocess.py       # Feature engineering (one-hot, label encoding)
│   └── score.py            # Scoring script for Azure ML Online Endpoint
├── pipelines/
│   └── training_pipeline.py   # Azure ML SDK v2 — submits job, gates on F1, registers model
├── config/
│   ├── dev.yml             # Dev environment (lowest cost — scale-to-zero compute)
│   └── prod.yml            # Production environment
├── tests/
│   └── test_preprocess.py  # Unit tests for preprocess.py
├── data/
│   └── .gitkeep            # Dataset not in git — download separately
├── scripts/
│   └── download_data.py    # Download Kaggle dataset
├── procedures/             # RAG knowledge base — one .md per failure type
│   ├── heat_dissipation_failure.md
│   ├── power_failure.md
│   ├── overstrain_failure.md
│   ├── tool_wear_failure.md
│   ├── random_failure.md
│   └── preventive_maintenance.md
├── prompts/
│   └── system_prompt.txt   # GPT-4o system prompt (versioned in Blob Storage)
├── requirements.txt
└── requirements-dev.txt
```

---

## ML Model

**Task**: 6-class failure type classification
**Algorithm**: XGBoost
**Dataset**: [Kaggle — Machine Predictive Maintenance Classification](https://www.kaggle.com/datasets/shivamb/machine-predictive-maintenance-classification) (10,000 records)

**Features**:

| Feature | Description |
|---|---|
| `air_temperature_K` | Ambient air temperature (Kelvin) |
| `process_temperature_K` | Internal process temperature (Kelvin) |
| `rotational_speed_rpm` | Spindle speed (RPM) |
| `torque_Nm` | Mechanical torque (Newton-metres) |
| `tool_wear_min` | Cumulative tool wear (minutes) |
| `type` | Machine grade: L / M / H (one-hot encoded) |

**Classes**: No Failure · Heat Dissipation Failure · Power Failure · Overstrain Failure · Tool Wear Failure · Random Failures

**Quality gate**: F1-macro >= 0.85 (dev) / >= 0.88 (prod) — model is only registered if this threshold is met.

---

## Dev Environment Setup

### Prerequisites
- Python 3.11
- Azure subscription with the following pre-created:
  - Azure ML Workspace (`aml-predictive-maintenance-dev`)
  - Resource group (`rg-mlops-dev`)
- Service Principal with Contributor role on the resource group

### 1. Install dependencies

```bash
pip install -r requirements-dev.txt
```

### 2. Download the dataset

```bash
# Set Kaggle credentials first: https://www.kaggle.com/docs/api
export KAGGLE_USERNAME=your_username
export KAGGLE_KEY=your_api_key

python scripts/download_data.py
# -> data/predictive_maintenance.csv
```

### 3. Run unit tests locally

```bash
pytest tests/ -v
```

### 4. Submit training job manually

```bash
export AZURE_CLIENT_ID=...
export AZURE_CLIENT_SECRET=...
export AZURE_TENANT_ID=...
export AZURE_SUBSCRIPTION_ID=...

python pipelines/training_pipeline.py \
  --config config/dev.yml \
  --data_path data/predictive_maintenance.csv
  # Add --deploy to also deploy the Online Endpoint
```

---

## GitHub Actions CI/CD

### Secrets Required

Configure in Settings -> Secrets and variables -> Actions:

| Secret | Description |
|---|---|
| `AZURE_CLIENT_ID` | Service Principal Application ID |
| `AZURE_CLIENT_SECRET` | Service Principal secret |
| `AZURE_TENANT_ID` | Azure AD tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Subscription ID |
| `STORAGE_ACCOUNT_DEV` | Dev storage account name (for blob_sync.yml) |
| `STORAGE_ACCOUNT_PROD` | Prod storage account name (for blob_sync.yml) |

### Workflow Triggers

| Workflow | Trigger | Target |
|---|---|---|
| `ml_ci.yml` | PR to `develop` or `main` (src/ or tests/ changed) | Lint + pytest |
| `ml_train.yml` | Push to `develop` | Dev Azure ML Workspace |
| `ml_train.yml` | Push to `main` | Prod Azure ML Workspace |
| `blob_sync.yml` | Push to `develop` or `main` (procedures/ or prompts/ changed) | Blob Storage |

### Manual training run (with endpoint deploy)

Go to Actions -> ML Train -> Run workflow and set `deploy_endpoint = true`.

---

## Dev Cost Profile

| Resource | SKU | Cost |
|---|---|---|
| Compute cluster (idle) | Standard_DS2_v2, min=0 | $0/hr (scales to zero) |
| Compute cluster (running) | Standard_DS2_v2, max=1 | ~$0.13/hr (only during training, ~10 min/run) |
| Online Endpoint | Standard_DS2_v2, 1 replica | ~$0.13/hr (only while endpoint is up) |
| Azure ML Workspace | Basic | Free |

Estimated training cost per run: < $0.03 (10 minutes on DS2_v2)
