"""
Scoring script for the Azure ML Online Endpoint — RCA Incident Signature Classifier.

Azure ML calls:
  - init()  once when the endpoint pod starts
  - run()   for every inference request

Input JSON (alert payload — single record):
    {
        "cpu_percent_avg5": 15.0,
        "memory_percent_avg5": 52.0,
        "http_5xx_rate_avg5": 8.0,
        "db_conn_pool_wait_avg5": 342.0,
        "request_latency_p99_avg5": 620.0,
        "breaching_metric": "db_conn_pool_wait_ms"
    }

Input JSON (batch — list of records):
    [ {...}, {...} ]

Output JSON (single):
    {
        "incident_signature": "db_pool_exhaustion",
        "confidence": 0.91,
        "class_probabilities": {
            "db_pool_exhaustion": 0.91,
            "memory_leak_progressive": 0.04,
            "cascade_failure": 0.03,
            "cpu_saturation_burst": 0.01,
            "network_partition": 0.01,
            "normal_noisy": 0.00
        },
        "top_contributing_features": ["db_wait_avg5", "db_wait_to_cpu_ratio", "latency_avg5"]
    }
"""

import json
import logging
import os
import pickle

import numpy as np

from preprocess import preprocess_alert

logger = logging.getLogger(__name__)

_model_bundle = None

# Number of top features to report in output
_TOP_N_FEATURES = 3


def init() -> None:
    """Called once when the endpoint deployment starts. Loads model.pkl into memory."""
    global _model_bundle

    model_dir = os.environ.get("AZUREML_MODEL_DIR", ".")
    model_path = _find_model_file(model_dir, "model.pkl")

    if model_path is None:
        raise FileNotFoundError(f"model.pkl not found under AZUREML_MODEL_DIR={model_dir}")

    with open(model_path, "rb") as f:
        _model_bundle = pickle.load(f)

    logger.info("Model loaded from: %s", model_path)
    logger.info("Classes: %s", _model_bundle["class_names"])


def run(raw_data: str) -> str:
    """
    Called for every inference request.

    Parameters
    ----------
    raw_data : str — JSON string (single dict or list of dicts)

    Returns
    -------
    str — JSON string (single result or list of results)
    """
    payload = json.loads(raw_data)

    if isinstance(payload, list):
        results = [_classify(record) for record in payload]
        return json.dumps(results)

    return json.dumps(_classify(payload))


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _classify(alert_payload: dict) -> dict:
    """Run the classifier on a single alert payload and return structured output."""
    model = _model_bundle["model"]
    label_encoder = _model_bundle["label_encoder"]
    class_names = _model_bundle["class_names"]
    feature_columns = _model_bundle["feature_columns"]

    X = preprocess_alert(alert_payload)

    # class_proba shape: (1, n_classes)
    class_proba = model.predict_proba(X)[0]
    predicted_idx = int(np.argmax(class_proba))
    predicted_signature = label_encoder.inverse_transform([predicted_idx])[0]
    confidence = float(class_proba[predicted_idx])

    class_probabilities = {
        cls: round(float(prob), 4)
        for cls, prob in zip(class_names, class_proba)
    }

    top_features = _get_top_features(model, feature_columns, _TOP_N_FEATURES)

    return {
        "incident_signature": predicted_signature,
        "confidence": round(confidence, 4),
        "class_probabilities": class_probabilities,
        "top_contributing_features": top_features,
    }


def _get_top_features(model, feature_columns: list, top_n: int) -> list:
    """Return feature names sorted by XGBoost global importance (descending)."""
    importances = model.feature_importances_
    idx = np.argsort(importances)[::-1][:top_n]
    return [feature_columns[i] for i in idx]


def _find_model_file(base_dir: str, filename: str):
    """Search recursively for model file under base_dir."""
    for root, _dirs, files in os.walk(base_dir):
        if filename in files:
            return os.path.join(root, filename)
    return None
