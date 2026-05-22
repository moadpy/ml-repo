"""
Feature engineering for the RCA Incident Signature Classifier.

Two entry points:
  - load_and_preprocess_csv(path)  → used by train.py on the labeled dataset
  - preprocess_alert(alert_payload) → used by score.py at inference time

Both produce the same FEATURE_COLUMNS output so that training and inference
are always aligned.

Incident signatures (6 classes):
  db_pool_exhaustion, memory_leak_progressive, cpu_saturation_burst,
  cascade_failure, network_partition, normal_noisy
"""

import pandas as pd
from sklearn.preprocessing import LabelEncoder

# ---------------------------------------------------------------------------
# Constants — must stay consistent between train.py and score.py
# ---------------------------------------------------------------------------

# Canonical feature order (8 features)
FEATURE_COLUMNS = [
    "cpu_avg5",
    "mem_avg5",
    "http5xx_avg5",
    "db_wait_avg5",
    "latency_avg5",
    "db_wait_to_cpu_ratio",
    "mem_dominance",
    "all_metrics_spike",
]

TARGET_COLUMN = "incident_signature"

# Class order is fixed — index must match XGBoost class indices used at inference
CLASS_NAMES = [
    "cascade_failure",
    "cpu_saturation_burst",
    "db_pool_exhaustion",
    "memory_leak_progressive",
    "network_partition",
    "normal_noisy",
]

# Breaching metric name → integer encoding
# Unknown / new metrics fall back to 5
METRIC_ENCODING = {
    "db_conn_pool_wait_ms": 0,
    "cpu_percent": 1,
    "memory_percent": 2,
    "http_5xx_rate": 3,
    "request_latency_p99": 4,
}
_METRIC_UNKNOWN = 5

# All-metrics-spike threshold (fraction: 0.0–1.0)
_SPIKE_THRESHOLD = 0.70

# CSV column name → internal name (raw dataset format)
_CSV_RENAME_MAP = {
    "cpu_percent_avg5": "cpu_avg5",
    "memory_percent_avg5": "mem_avg5",
    "http_5xx_rate_avg5": "http5xx_avg5",
    "db_conn_pool_wait_avg5": "db_wait_avg5",
    "request_latency_p99_avg5": "latency_avg5",
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def encode_metric_name(metric_name: str) -> int:
    """Map a breaching metric name to its integer code."""
    return METRIC_ENCODING.get(metric_name, _METRIC_UNKNOWN)


def safe_divide(numerator: float, denominator: float, fallback: float = 0.0) -> float:
    """Divide with zero-denominator protection."""
    if denominator == 0.0:
        return fallback
    return numerator / denominator


def all_above_threshold(
    cpu: float,
    mem: float,
    http5xx: float,
    db_wait: float,
    latency: float,
    threshold_pct: float = _SPIKE_THRESHOLD,
) -> int:
    """
    Binary flag: 1 if all five metrics are simultaneously above their
    respective 'high' reference values (cascade failure fingerprint).

    Reference maxima used to normalise before threshold comparison:
      cpu_percent  → 100
      mem_percent  → 100
      http5xx_rate → 50
      db_wait_ms   → 450
      latency_ms   → 2500
    """
    normalised = [
        cpu / 100.0,
        mem / 100.0,
        http5xx / 50.0,
        db_wait / 450.0,
        latency / 2500.0,
    ]
    return int(all(v >= threshold_pct for v in normalised))


# ---------------------------------------------------------------------------
# Path 1 — Training: load CSV dataset and engineer features
# ---------------------------------------------------------------------------

def load_raw(csv_path: str) -> pd.DataFrame:
    """Load telemetry_labeled.csv and normalise column names."""
    df = pd.read_csv(csv_path)
    df = df.rename(columns={k: v for k, v in _CSV_RENAME_MAP.items() if k in df.columns})
    return df


def _derive_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived ratio/spike columns to a DataFrame that already has raw avg columns."""
    df = df.copy()

    df["db_wait_to_cpu_ratio"] = df.apply(
        lambda r: safe_divide(r["db_wait_avg5"], r["cpu_avg5"]), axis=1
    )

    df["mem_dominance"] = df["mem_avg5"] / (df["cpu_avg5"] + 1.0)

    df["all_metrics_spike"] = df.apply(
        lambda r: all_above_threshold(
            r["cpu_avg5"],
            r["mem_avg5"],
            r["http5xx_avg5"],
            r["db_wait_avg5"],
            r["latency_avg5"],
        ),
        axis=1,
    )

    return df


def build_feature_matrix(df: pd.DataFrame):
    """
    Parameters
    ----------
    df : DataFrame from load_raw() — must have raw avg columns + incident_signature

    Returns
    -------
    X  : pd.DataFrame  — feature matrix (FEATURE_COLUMNS order)
    y  : np.ndarray    — integer-encoded labels
    le : LabelEncoder  — fitted on CLASS_NAMES (fixed class order)
    """
    df = _derive_features(df)

    X = df[FEATURE_COLUMNS].astype(float)

    le = LabelEncoder()
    le.fit(CLASS_NAMES)
    y = le.transform(df[TARGET_COLUMN].str.strip())

    return X, y, le


# ---------------------------------------------------------------------------
# Path 2 — Inference: engineer features from a live alert payload dict
# ---------------------------------------------------------------------------

def preprocess_alert(alert_payload: dict) -> pd.DataFrame:
    """
    Convert an enriched alert payload (from FastAPI /api/incident/new) into
    the model feature matrix.

    Expected keys in alert_payload:
        cpu_percent_avg5, memory_percent_avg5, http_5xx_rate_avg5,
        db_conn_pool_wait_avg5, request_latency_p99_avg5, breaching_metric

    Returns a single-row DataFrame with FEATURE_COLUMNS.
    """
    cpu = float(alert_payload["cpu_percent_avg5"])
    mem = float(alert_payload["memory_percent_avg5"])
    http5xx = float(alert_payload["http_5xx_rate_avg5"])
    db_wait = float(alert_payload["db_conn_pool_wait_avg5"])
    latency = float(alert_payload["request_latency_p99_avg5"])
    metric_name = str(alert_payload.get("breaching_metric", ""))

    features = {
        "cpu_avg5": cpu,
        "mem_avg5": mem,
        "http5xx_avg5": http5xx,
        "db_wait_avg5": db_wait,
        "latency_avg5": latency,
        "db_wait_to_cpu_ratio": safe_divide(db_wait, cpu),
        "mem_dominance": mem / (cpu + 1.0),
        "all_metrics_spike": all_above_threshold(cpu, mem, http5xx, db_wait, latency),
    }

    return pd.DataFrame([features])[FEATURE_COLUMNS].astype(float)
