"""
Synthetic dataset generator for the RCA Incident Signature Classifier.

Generates two artefacts saved to data/rca_poc/:
  1. telemetry_labeled.csv  — ~1,500 labeled incident snapshots (training data)
  2. rag_context.json       — knowledge base documents for RAG (PRs, Jira, runbooks)

Usage:
    python src/generate_labeled_incidents.py
    python src/generate_labeled_incidents.py --n_samples 1500 --output_dir data/rca_poc

Metric fingerprints per signature class (realistic value ranges):
  db_pool_exhaustion       : db_wait ↑↑ (200-450ms), CPU normal (10-30%)
  memory_leak_progressive  : mem ↑↑ (80-95%), CPU moderate (20-40%)
  cpu_saturation_burst     : cpu ↑↑ (88-99%), latency ↑ (500-2500ms)
  cascade_failure          : ALL metrics ↑↑ simultaneously
  network_partition        : http5xx ↑↑ (25-50), CPU normal (10-30%)
  normal_noisy             : all metrics mild, no sustained breach
"""

import argparse
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

RANDOM_SEED = 42
SIGNATURES = [
    "db_pool_exhaustion",
    "memory_leak_progressive",
    "cpu_saturation_burst",
    "cascade_failure",
    "network_partition",
    "normal_noisy",
]
SERVICES = ["payment-api", "auth-service", "order-service", "inventory-api", "notification-svc"]


def _rng(low: float, high: float, n: int, seed_offset: int = 0) -> np.ndarray:
    rng = np.random.default_rng(RANDOM_SEED + seed_offset)
    return rng.uniform(low, high, n)


def _generate_class_samples(signature: str, n: int, base_time: datetime, seed_offset: int) -> list:
    rng = np.random.default_rng(RANDOM_SEED + seed_offset)
    rows = []

    for i in range(n):
        ts = base_time - timedelta(hours=int(rng.integers(1, 720)))
        service = rng.choice(SERVICES)
        inc_id = f"INC-{seed_offset * 1000 + i + 1:04d}"

        if signature == "db_pool_exhaustion":
            # 80% typical high wait time, 20% early onset or lower pool capacity exhaustion
            db_wait = rng.uniform(200, 450) if rng.random() < 0.8 else rng.uniform(80, 200)
            cpu = rng.uniform(10, 60)
            mem = rng.uniform(30, 70)
            # HTTP 5xx rate can be high if web server fails to get connections, or moderate
            http5xx = rng.uniform(5, 30)
            # Latency is high because requests block on connection acquisition
            latency = rng.uniform(200, 1200)
            breaching = rng.choice(["db_conn_pool_wait_ms", "request_latency_p99", "http_5xx_rate"])

        elif signature == "memory_leak_progressive":
            # 90% typical high memory, 10% early memory pressure
            mem = rng.uniform(75, 98) if rng.random() < 0.9 else rng.uniform(60, 75)
            # Garbage Collection thrashing can cause moderate to high CPU
            cpu = rng.uniform(15, 85)
            http5xx = rng.uniform(0, 8)
            # Slowdowns due to memory pressure/GC pauses
            latency = rng.uniform(100, 800)
            db_wait = rng.uniform(5, 60)
            breaching = rng.choice(["memory_percent", "request_latency_p99", "cpu_percent"])

        elif signature == "cpu_saturation_burst":
            cpu = rng.uniform(85, 100)
            mem = rng.uniform(20, 75)
            # Scenario A: High traffic load (70% probability) -> impacts latency/5xx
            if rng.random() < 0.70:
                http5xx = rng.uniform(5, 35)
                db_wait = rng.uniform(15, 80)
                latency = rng.uniform(400, 2500)
            # Scenario B: Background jobs / compute-bound tasks / gc spikes (30% probability) -> normal downstream metrics
            else:
                http5xx = rng.uniform(0, 3)
                db_wait = rng.uniform(3, 20)
                latency = rng.uniform(40, 250)
            breaching = rng.choice(["cpu_percent", "request_latency_p99", "http_5xx_rate"])

        elif signature == "cascade_failure":
            cpu = rng.uniform(65, 100)
            mem = rng.uniform(60, 98)
            http5xx = rng.uniform(20, 60)
            db_wait = rng.uniform(80, 450)
            latency = rng.uniform(800, 3000)
            breaching = rng.choice(
                ["cpu_percent", "http_5xx_rate", "request_latency_p99", "db_conn_pool_wait_ms", "memory_percent"]
            )

        elif signature == "network_partition":
            cpu = rng.uniform(8, 45)
            mem = rng.uniform(30, 70)
            http5xx = rng.uniform(20, 60)
            db_wait = rng.uniform(5, 60)
            # 60% slow timeout, 40% fail fast immediate failure (low latency)
            latency = rng.uniform(1000, 3000) if rng.random() < 0.6 else rng.uniform(10, 150)
            breaching = rng.choice(["http_5xx_rate", "request_latency_p99"])

        else:  # normal_noisy
            # 60% completely quiet baseline
            if rng.random() < 0.6:
                cpu = rng.uniform(5, 45)
                mem = rng.uniform(15, 55)
                http5xx = rng.uniform(0, 2)
                db_wait = rng.uniform(2, 20)
                latency = rng.uniform(20, 150)
            # 40% transient spikes in single metrics (representing alerts that fire but aren't root causes)
            else:
                cpu = rng.uniform(15, 98) if rng.random() < 0.35 else rng.uniform(5, 45)
                mem = rng.uniform(20, 65)
                http5xx = rng.uniform(0, 10) if rng.random() < 0.2 else rng.uniform(0, 2)
                db_wait = rng.uniform(5, 350) if rng.random() < 0.2 else rng.uniform(2, 20)
                latency = rng.uniform(30, 600) if rng.random() < 0.25 else rng.uniform(20, 150)
            breaching = rng.choice(["cpu_percent", "memory_percent", "http_5xx_rate", "request_latency_p99"])

        rows.append(
            {
                "timestamp": ts.isoformat(),
                "service_name": service,
                "breaching_metric": breaching,
                "cpu_percent_avg5": round(float(cpu), 2),
                "memory_percent_avg5": round(float(mem), 2),
                "http_5xx_rate_avg5": round(float(http5xx), 2),
                "db_conn_pool_wait_avg5": round(float(db_wait), 2),
                "request_latency_p99_avg5": round(float(latency), 2),
                "incident_signature": signature,
                "incident_id": inc_id,
            }
        )

    return rows


def generate_telemetry_csv(n_samples: int, output_path: str) -> None:
    base_time = datetime(2026, 4, 7, 12, 0, 0, tzinfo=timezone.utc)

    per_class = n_samples // len(SIGNATURES)
    remainder = n_samples % len(SIGNATURES)

    all_rows = []
    for i, sig in enumerate(SIGNATURES):
        count = per_class + (1 if i < remainder else 0)
        all_rows.extend(_generate_class_samples(sig, count, base_time, seed_offset=i))

    df = pd.DataFrame(all_rows)
    df = df.sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"[telemetry] Generated {len(df)} rows → {output_path}")
    print(f"[telemetry] Class distribution:\n{df['incident_signature'].value_counts()}\n")


def generate_rag_context(output_path: str) -> None:
    """
    Generate a representative knowledge base with:
    - 5 github_pr docs  (no signature — retrieved by time + service)
    - 3 jira_ticket docs (no signature — retrieved by time + service)
    - 2 terraform_pr docs (no signature — retrieved by time + service)
    - 6 runbook docs    (one per signature — exact signature match)
    """
    base_time = datetime(2026, 4, 7, 6, 0, 0, tzinfo=timezone.utc)

    docs = []

    # --- GitHub PRs ---
    pr_data = [
        {
            "title": "PR #104: Optimize DB connection pool settings",
            "content": "Reduced max_connections to improve resource utilization on payment-api.",
            "code_diff": (
                "diff --git a/config/db.yml b/config/db.yml\n"
                "--- a/config/db.yml\n"
                "+++ b/config/db.yml\n"
                "@@ -3,4 +3,4 @@\n"
                " database:\n"
                "-  max_connections: 100\n"
                "+  max_connections: 10\n"
                "   connection_timeout: 30s"
            ),
            "service_affected": "payment-api",
            "author": "john.doe",
            "minutes_before_alert": 12,
        },
        {
            "title": "PR #105: Add Redis caching layer for session tokens",
            "content": "Introduced an in-memory cache for session tokens to reduce auth latency.",
            "code_diff": (
                "diff --git a/src/cache.py b/src/cache.py\n"
                "+++ b/src/cache.py\n"
                "@@ -0,0 +1,20 @@\n"
                "+import redis\n"
                "+cache = redis.Redis(host='localhost', max_connections=None)\n"
                "+session_store: dict = {}  # unbounded"
            ),
            "service_affected": "auth-service",
            "author": "jane.smith",
            "minutes_before_alert": 45,
        },
        {
            "title": "PR #106: Increase API rate limiting threshold",
            "content": "Raised rate limit from 100 to 1000 req/s to handle Black Friday traffic.",
            "code_diff": (
                "diff --git a/config/nginx.conf b/config/nginx.conf\n"
                "-  limit_req_zone $binary_remote_addr zone=api:10m rate=100r/s;\n"
                "+  limit_req_zone $binary_remote_addr zone=api:10m rate=1000r/s;"
            ),
            "service_affected": "payment-api",
            "author": "dev.ops",
            "minutes_before_alert": 90,
        },
        {
            "title": "PR #107: Migrate NSG rules for private subnet",
            "content": "Updated NSG inbound rules to restrict traffic to internal CIDR only.",
            "code_diff": (
                "diff --git a/infra/nsg_rules.json b/infra/nsg_rules.json\n"
                '-  "sourceAddressPrefix": "*"\n'
                '+  "sourceAddressPrefix": "10.0.0.0/16"'
            ),
            "service_affected": "*",
            "author": "infra.team",
            "minutes_before_alert": 65,
        },
        {
            "title": "PR #108: Refactor order processing batch size",
            "content": "Increased batch processing size to improve throughput on order-service.",
            "code_diff": (
                "diff --git a/src/processor.py b/src/processor.py\n"
                "-BATCH_SIZE = 50\n"
                "+BATCH_SIZE = 500"
            ),
            "service_affected": "order-service",
            "author": "alice.wong",
            "minutes_before_alert": 110,
        },
    ]

    for pr in pr_data:
        ts = base_time - timedelta(minutes=pr["minutes_before_alert"])
        docs.append(
            {
                "id": str(uuid.uuid4()),
                "content": f"{pr['title']}: {pr['content']}",
                "code_diff": pr["code_diff"],
                "doc_type": "github_pr",
                "incident_signature": "unknown",
                "service_affected": pr["service_affected"],
                "author": pr["author"],
                "timestamp": ts.isoformat(),
                "incident_id": None,
            }
        )

    # --- Jira Tickets ---
    jira_data = [
        {
            "title": "JIRA-501: payment-api DB timeouts spiking",
            "content": "Multiple users reporting payment failures. DB wait times have exceeded SLA. Opened by: ops-team.",
            "service_affected": "payment-api",
            "author": "ops-team",
            "minutes_before_alert": 8,
        },
        {
            "title": "JIRA-502: auth-service memory usage climbing",
            "content": "Memory utilisation on auth-service pods has been climbing steadily for 3 hours. No deployment in the last 4h.",
            "service_affected": "auth-service",
            "author": "sre-team",
            "minutes_before_alert": 180,
        },
        {
            "title": "JIRA-503: order-service 5xx errors after NSG change",
            "content": "Order placement failing with 502 Bad Gateway since the NSG rule migration (PR #107). Possible connectivity issue.",
            "service_affected": "order-service",
            "author": "dev-team",
            "minutes_before_alert": 60,
        },
    ]

    for jira in jira_data:
        ts = base_time - timedelta(minutes=jira["minutes_before_alert"])
        docs.append(
            {
                "id": str(uuid.uuid4()),
                "content": f"{jira['title']}: {jira['content']}",
                "code_diff": None,
                "doc_type": "jira_ticket",
                "incident_signature": "unknown",
                "service_affected": jira["service_affected"],
                "author": jira["author"],
                "timestamp": ts.isoformat(),
                "incident_id": None,
            }
        )

    # --- Terraform PRs ---
    tf_data = [
        {
            "title": "TF-PR #23: Resize AKS node pool (DS2_v2 → DS3_v2)",
            "content": "Scaling up AKS node pool VM size to handle projected traffic increase.",
            "code_diff": (
                "diff --git a/modules/aks/main.tf b/modules/aks/main.tf\n"
                '-  vm_size = "Standard_DS2_v2"\n'
                '+  vm_size = "Standard_DS3_v2"'
            ),
            "service_affected": "*",
            "author": "infra.team",
            "minutes_before_alert": 95,
        },
        {
            "title": "TF-PR #24: Update Cosmos DB throughput from 400 to 800 RU/s",
            "content": "Increased Cosmos DB provisioned throughput to handle write load.",
            "code_diff": (
                "diff --git a/modules/cosmos_db/main.tf b/modules/cosmos_db/main.tf\n"
                "-  throughput = 400\n"
                "+  throughput = 800"
            ),
            "service_affected": "payment-api",
            "author": "data.team",
            "minutes_before_alert": 40,
        },
    ]

    for tf in tf_data:
        ts = base_time - timedelta(minutes=tf["minutes_before_alert"])
        docs.append(
            {
                "id": str(uuid.uuid4()),
                "content": f"{tf['title']}: {tf['content']}",
                "code_diff": tf["code_diff"],
                "doc_type": "terraform_pr",
                "incident_signature": "unknown",
                "service_affected": tf["service_affected"],
                "author": tf["author"],
                "timestamp": ts.isoformat(),
                "incident_id": None,
            }
        )

    # --- Runbooks (one per signature — tagged for exact match retrieval) ---
    runbook_data = [
        {
            "signature": "db_pool_exhaustion",
            "content": (
                "RB-012: DB Pool Exhaustion Runbook. "
                "Step 1: Verify DB pool wait time via Azure Monitor. "
                "Step 2: Check recent PRs that modified DB config files. "
                "Step 3: Emergency fix — kubectl set env deployment/<svc> DB_MAX_POOL=50. "
                "Step 4: Permanent fix — revert the PR that reduced max_connections. "
                "Step 5: Monitor db_conn_pool_wait_ms until below 50ms."
            ),
        },
        {
            "signature": "memory_leak_progressive",
            "content": (
                "RB-008: Memory Leak Runbook. "
                "Step 1: Identify the pod with highest memory via kubectl top pods. "
                "Step 2: Capture heap dump — kubectl exec <pod> -- jmap -dump:format=b,file=/tmp/heap.hprof <pid>. "
                "Step 3: Immediate relief — kubectl rollout restart deployment/<svc>. "
                "Step 4: Review recent code changes introducing caches or buffers. "
                "Step 5: Add memory limits and liveness probe to prevent recurrence."
            ),
        },
        {
            "signature": "cpu_saturation_burst",
            "content": (
                "RB-003: CPU Saturation Runbook. "
                "Step 1: Identify top CPU consumers — kubectl top pods --sort-by=cpu. "
                "Step 2: Check for traffic spikes in Azure Monitor. "
                "Step 3: Scale out — kubectl scale deployment/<svc> --replicas=<n+2>. "
                "Step 4: Enable HPA if not already — kubectl autoscale deployment/<svc> --min=2 --max=10 --cpu-percent=70. "
                "Step 5: Investigate for catastrophic regex or tight loop introduced by recent PRs."
            ),
        },
        {
            "signature": "cascade_failure",
            "content": (
                "RB-015: Cascade Failure Runbook. "
                "Step 1: Identify the failed downstream dependency (all metrics spike simultaneously). "
                "Step 2: Check Azure Monitor service health for all dependencies. "
                "Step 3: Activate circuit breakers — toggle feature flag CIRCUIT_BREAKER_<DEP>=true. "
                "Step 4: Restart affected services after dependency recovers. "
                "Step 5: Add retry with exponential backoff and circuit breaker to prevent future cascades."
            ),
        },
        {
            "signature": "network_partition",
            "content": (
                "RB-007: Network Partition Runbook. "
                "Step 1: Check NSG rules for recent changes — az network nsg rule list --nsg-name <nsg>. "
                "Step 2: Test connectivity — kubectl exec <pod> -- curl -v http://<service>:<port>/health. "
                "Step 3: Revert NSG change if identified as the cause. "
                "Step 4: Verify Private DNS Zone records are resolving correctly. "
                "Step 5: Check Azure Service Health for regional network incidents."
            ),
        },
        {
            "signature": "normal_noisy",
            "content": (
                "RB-001: Normal Noisy / False Positive Runbook. "
                "Step 1: Confirm metrics returned to baseline within 5 minutes. "
                "Step 2: Mark incident as planned_maintenance or false_alarm in Cosmos DB. "
                "Step 3: If during deployment, alert is expected — tag alert with deployment_window. "
                "Step 4: Consider tightening the alarm threshold if recurrence is frequent. "
                "Step 5: No remediation action required."
            ),
        },
    ]

    for rb in runbook_data:
        docs.append(
            {
                "id": str(uuid.uuid4()),
                "content": rb["content"],
                "code_diff": None,
                "doc_type": "runbook",
                "incident_signature": rb["signature"],
                "service_affected": "general",
                "author": "sre-team",
                "timestamp": "2026-01-15T00:00:00",
                "incident_id": None,
            }
        )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(docs, f, indent=2)

    print(f"[rag_context] Generated {len(docs)} documents → {output_path}")
    doc_types = {}
    for d in docs:
        doc_types[d["doc_type"]] = doc_types.get(d["doc_type"], 0) + 1
    for dt, count in sorted(doc_types.items()):
        print(f"  {dt}: {count}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate synthetic RCA training data and RAG context")
    p.add_argument("--n_samples", type=int, default=3000, help="Number of labeled CSV rows")
    p.add_argument("--output_dir", type=str, default="data/rca_poc")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    csv_path = os.path.join(args.output_dir, "telemetry_labeled.csv")
    rag_path = os.path.join(args.output_dir, "rag_context.json")

    generate_telemetry_csv(args.n_samples, csv_path)
    generate_rag_context(rag_path)
    print("\nDone. Run `python src/index_knowledge_base.py` to embed and index rag_context.json.")
