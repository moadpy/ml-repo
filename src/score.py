"""
Scoring script for the Azure ML Online Endpoint.

Azure ML calls:
  - init()  once when the endpoint pod starts
  - run()   for every inference request

Input JSON (single record):
    {
        "air_temperature_K": 298.1,
        "process_temperature_K": 308.6,
        "rotational_speed_rpm": 1551,
        "torque_Nm": 42.8,
        "tool_wear_min": 108,
        "type": "M"
    }

Input JSON (batch — list of records):
    [ {...}, {...} ]

Output JSON (single):
    {
        "failure_type": "Heat Dissipation Failure",
        "confidence": 0.873,
        "probabilities": {
            "No Failure": 0.000,
            "Heat Dissipation Failure": 0.873,
            "Power Failure": 0.062,
            "Overstrain Failure": 0.031,
            "Tool Wear Failure": 0.020,
            "Random Failures": 0.014
        }
    }
"""

import json
import logging
import os
import pickle

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_model_bundle = None


def init() -> None:
    """Called once when the endpoint deployment starts. Loads model.pkl into memory."""
    global _model_bundle

    model_dir = os.environ.get("AZUREML_MODEL_DIR", ".")
    model_path = _find_model_file(model_dir, "model.pkl")

    if model_path is None:
        raise FileNotFoundError(f"model.pkl not found under AZUREML_MODEL_DIR={model_dir}")

    with open(model_path, "rb") as f:
        _model_bundle = pickle.load(f)

    logger.info("Model loaded from %s", model_path)
    logger.info("Classes: %s", _model_bundle["class_names"])


def run(raw_data: str) -> str:
    """Called for each inference request."""
    try:
        data = json.loads(raw_data)
    except (json.JSONDecodeError, TypeError) as e:
        return json.dumps({"error": f"Invalid JSON input: {e}"})

    records = data if isinstance(data, list) else [data]

    try:
        results = [_predict(rec) for rec in records]
    except Exception as e:
        logger.exception("Prediction failed")
        return json.dumps({"error": str(e)})

    return json.dumps(results[0] if len(results) == 1 else results)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_model_file(base_dir: str, filename: str) -> str | None:
    """Walk base_dir to find the model file (handles nested Azure ML model dirs)."""
    for root, _dirs, files in os.walk(base_dir):
        if filename in files:
            return os.path.join(root, filename)
    return None


def _build_feature_row(rec: dict) -> dict:
    """Convert a raw sensor record into the engineered feature dict."""
    machine_type = str(rec.get("type", "M")).upper()
    return {
        "air_temperature_K": float(rec["air_temperature_K"]),
        "process_temperature_K": float(rec["process_temperature_K"]),
        "rotational_speed_rpm": float(rec["rotational_speed_rpm"]),
        "torque_Nm": float(rec["torque_Nm"]),
        "tool_wear_min": float(rec["tool_wear_min"]),
        "type_L": 1.0 if machine_type == "L" else 0.0,
        "type_M": 1.0 if machine_type == "M" else 0.0,
        "type_H": 1.0 if machine_type == "H" else 0.0,
    }


def _predict(rec: dict) -> dict:
    model = _model_bundle["model"]
    class_names = _model_bundle["class_names"]
    feature_columns = _model_bundle["feature_columns"]

    row = _build_feature_row(rec)
    X = pd.DataFrame([row])[feature_columns]

    proba = model.predict_proba(X)[0]
    predicted_idx = int(np.argmax(proba))

    return {
        "failure_type": class_names[predicted_idx],
        "confidence": round(float(proba[predicted_idx]), 6),
        "probabilities": {
            cls: round(float(p), 6) for cls, p in zip(class_names, proba)
        },
    }
