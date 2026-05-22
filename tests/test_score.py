"""
Unit tests for src/score.py — RCA Incident Signature Classifier scoring script.
Run with: pytest tests/

These tests mock model artifacts so no real model.pkl is required.
"""

import json
import os
import pickle
import sys
import types
from unittest.mock import MagicMock

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Path setup — make src/ importable and stub out the preprocess import
# so score.py can be imported without the full sklearn stack being called.
# ---------------------------------------------------------------------------
SRC_DIR = os.path.join(os.path.dirname(__file__), "../src")
sys.path.insert(0, SRC_DIR)

# Provide a minimal preprocess stub so score.py imports cleanly
import pandas as pd  # noqa: E402

_preprocess_stub = types.ModuleType("preprocess")

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

CLASS_NAMES = [
    "cascade_failure",
    "cpu_saturation_burst",
    "db_pool_exhaustion",
    "memory_leak_progressive",
    "network_partition",
    "normal_noisy",
]

N_CLASSES = len(CLASS_NAMES)
N_FEATURES = len(FEATURE_COLUMNS)

_SAMPLE_PAYLOAD = {
    "cpu_percent_avg5": 15.0,
    "memory_percent_avg5": 52.0,
    "http_5xx_rate_avg5": 8.0,
    "db_conn_pool_wait_avg5": 342.0,
    "request_latency_p99_avg5": 620.0,
    "breaching_metric": "db_conn_pool_wait_ms",
}

_SAMPLE_FEATURES = pd.DataFrame(
    [[15.0, 52.0, 8.0, 342.0, 620.0, 342.0 / 15.0, 52.0 / 16.0, 0]],
    columns=FEATURE_COLUMNS,
).astype(float)


def _stub_preprocess_alert(payload: dict) -> pd.DataFrame:
    return _SAMPLE_FEATURES.copy()


_preprocess_stub.preprocess_alert = _stub_preprocess_alert
sys.modules["preprocess"] = _preprocess_stub

import score  # noqa: E402  (must come after stub registration)


# ---------------------------------------------------------------------------
# Helpers to build a fake model bundle
# ---------------------------------------------------------------------------

class _FakeModel:
    """
    Minimal picklable model that mimics the XGBoost classifier interface.
    Used in tests that call pickle.dump() (i.e. TestInit).
    """

    def __init__(self, predicted_class_idx: int = 2):
        self._predicted_class_idx = predicted_class_idx
        self.feature_importances_ = np.linspace(0.01, 0.5, N_FEATURES)

    def predict_proba(self, X):
        proba = np.zeros((1, N_CLASSES))
        proba[0, self._predicted_class_idx] = 0.91
        rest = (1 - 0.91) / (N_CLASSES - 1)
        for i in range(N_CLASSES):
            if i != self._predicted_class_idx:
                proba[0, i] = rest
        return proba


def _make_model_bundle(predicted_class_idx: int = 2) -> dict:
    """Bundle with MagicMock model — fast, NOT picklable. Use for run/classify tests."""
    mock_model = MagicMock()

    proba = np.zeros((1, N_CLASSES))
    proba[0, predicted_class_idx] = 0.91
    rest = (1 - 0.91) / (N_CLASSES - 1)
    for i in range(N_CLASSES):
        if i != predicted_class_idx:
            proba[0, i] = rest

    mock_model.predict_proba = MagicMock(return_value=proba)
    mock_model.feature_importances_ = np.linspace(0.01, 0.5, N_FEATURES)

    from sklearn.preprocessing import LabelEncoder

    le = LabelEncoder()
    le.fit(CLASS_NAMES)

    return {
        "model": mock_model,
        "label_encoder": le,
        "class_names": CLASS_NAMES,
        "feature_columns": FEATURE_COLUMNS,
    }


def _make_model_bundle_picklable(predicted_class_idx: int = 2) -> dict:
    """Bundle with a real picklable _FakeModel — required for init() / pickle tests."""
    from sklearn.preprocessing import LabelEncoder

    le = LabelEncoder()
    le.fit(CLASS_NAMES)

    return {
        "model": _FakeModel(predicted_class_idx),
        "label_encoder": le,
        "class_names": CLASS_NAMES,
        "feature_columns": FEATURE_COLUMNS,
    }


# ---------------------------------------------------------------------------
# _find_model_file
# ---------------------------------------------------------------------------

class TestFindModelFile:
    def test_finds_file_in_root(self, tmp_path):
        (tmp_path / "model.pkl").touch()
        result = score._find_model_file(str(tmp_path), "model.pkl")
        assert result is not None
        assert result.endswith("model.pkl")

    def test_finds_file_in_subdirectory(self, tmp_path):
        sub = tmp_path / "models" / "v1"
        sub.mkdir(parents=True)
        (sub / "model.pkl").touch()
        result = score._find_model_file(str(tmp_path), "model.pkl")
        assert result is not None
        assert "model.pkl" in result

    def test_returns_none_when_missing(self, tmp_path):
        result = score._find_model_file(str(tmp_path), "model.pkl")
        assert result is None


# ---------------------------------------------------------------------------
# init()
# ---------------------------------------------------------------------------

class TestInit:
    def test_init_loads_bundle_from_env(self, tmp_path, monkeypatch):
        bundle = _make_model_bundle_picklable()  # must be picklable for pickle.dump
        pkl_path = tmp_path / "model.pkl"
        with open(pkl_path, "wb") as f:
            pickle.dump(bundle, f)

        monkeypatch.setenv("AZUREML_MODEL_DIR", str(tmp_path))
        score._model_bundle = None  # reset global

        score.init()

        assert score._model_bundle is not None
        assert score._model_bundle["class_names"] == CLASS_NAMES

    def test_init_raises_when_model_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AZUREML_MODEL_DIR", str(tmp_path))
        score._model_bundle = None

        with pytest.raises(FileNotFoundError, match="model.pkl not found"):
            score.init()

    def test_init_defaults_to_current_dir_when_env_absent(self, tmp_path, monkeypatch):
        """When AZUREML_MODEL_DIR is not set, init() should fall back to '.'."""
        monkeypatch.delenv("AZUREML_MODEL_DIR", raising=False)
        score._model_bundle = None

        # Should raise FileNotFoundError (no model in '.') — not crash differently
        with pytest.raises(FileNotFoundError):
            score.init()


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------

class TestRun:
    @pytest.fixture(autouse=True)
    def load_bundle(self):
        score._model_bundle = _make_model_bundle(predicted_class_idx=2)  # db_pool_exhaustion

    def test_run_single_record_returns_json_string(self):
        raw = json.dumps(_SAMPLE_PAYLOAD)
        result = score.run(raw)
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_run_batch_returns_list(self):
        raw = json.dumps([_SAMPLE_PAYLOAD, _SAMPLE_PAYLOAD])
        result = score.run(raw)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 2

    def test_run_output_has_required_keys(self):
        raw = json.dumps(_SAMPLE_PAYLOAD)
        parsed = json.loads(score.run(raw))
        for key in ("incident_signature", "confidence", "class_probabilities", "top_contributing_features"):
            assert key in parsed

    def test_run_confidence_is_float_in_range(self):
        raw = json.dumps(_SAMPLE_PAYLOAD)
        parsed = json.loads(score.run(raw))
        assert 0.0 <= parsed["confidence"] <= 1.0

    def test_run_class_probabilities_sum_to_one(self):
        raw = json.dumps(_SAMPLE_PAYLOAD)
        parsed = json.loads(score.run(raw))
        total = sum(parsed["class_probabilities"].values())
        assert total == pytest.approx(1.0, abs=0.01)

    def test_run_top_contributing_features_length(self):
        raw = json.dumps(_SAMPLE_PAYLOAD)
        parsed = json.loads(score.run(raw))
        assert len(parsed["top_contributing_features"]) == score._TOP_N_FEATURES

    def test_run_predicted_signature_in_class_names(self):
        raw = json.dumps(_SAMPLE_PAYLOAD)
        parsed = json.loads(score.run(raw))
        assert parsed["incident_signature"] in CLASS_NAMES

    def test_run_batch_each_item_has_required_keys(self):
        raw = json.dumps([_SAMPLE_PAYLOAD, _SAMPLE_PAYLOAD])
        results = json.loads(score.run(raw))
        for item in results:
            assert "incident_signature" in item
            assert "confidence" in item


# ---------------------------------------------------------------------------
# _classify()
# ---------------------------------------------------------------------------

class TestClassify:
    @pytest.fixture(autouse=True)
    def load_bundle(self):
        score._model_bundle = _make_model_bundle(predicted_class_idx=2)

    def test_classify_returns_dict(self):
        result = score._classify(_SAMPLE_PAYLOAD)
        assert isinstance(result, dict)

    def test_classify_incident_signature_type(self):
        result = score._classify(_SAMPLE_PAYLOAD)
        assert isinstance(result["incident_signature"], str)

    def test_classify_confidence_rounded(self):
        result = score._classify(_SAMPLE_PAYLOAD)
        # Should be rounded to 4 decimal places
        val = result["confidence"]
        assert val == round(val, 4)

    def test_classify_all_classes_in_probabilities(self):
        result = score._classify(_SAMPLE_PAYLOAD)
        assert set(result["class_probabilities"].keys()) == set(CLASS_NAMES)


# ---------------------------------------------------------------------------
# _get_top_features()
# ---------------------------------------------------------------------------

class TestGetTopFeatures:
    def test_returns_correct_count(self):
        mock_model = MagicMock()
        # importances ascending — highest is last feature
        mock_model.feature_importances_ = np.linspace(0.01, 0.5, N_FEATURES)
        result = score._get_top_features(mock_model, FEATURE_COLUMNS, top_n=3)
        assert len(result) == 3

    def test_top_feature_has_highest_importance(self):
        mock_model = MagicMock()
        importances = np.zeros(N_FEATURES)
        importances[4] = 0.99  # latency_avg5 is most important
        mock_model.feature_importances_ = importances
        result = score._get_top_features(mock_model, FEATURE_COLUMNS, top_n=1)
        assert result[0] == FEATURE_COLUMNS[4]

    def test_returns_feature_names_not_indices(self):
        mock_model = MagicMock()
        mock_model.feature_importances_ = np.linspace(0.01, 0.5, N_FEATURES)
        result = score._get_top_features(mock_model, FEATURE_COLUMNS, top_n=3)
        for feature in result:
            assert isinstance(feature, str)
            assert feature in FEATURE_COLUMNS

    def test_top_n_zero_returns_empty(self):
        mock_model = MagicMock()
        mock_model.feature_importances_ = np.ones(N_FEATURES)
        result = score._get_top_features(mock_model, FEATURE_COLUMNS, top_n=0)
        assert result == []
