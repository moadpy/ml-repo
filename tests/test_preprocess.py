"""
Unit tests for src/preprocess.py — RCA Incident Signature Classifier
Run with: pytest tests/
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from preprocess import (
    CLASS_NAMES,
    FEATURE_COLUMNS,
    METRIC_ENCODING,
    all_above_threshold,
    build_feature_matrix,
    encode_metric_name,
    load_raw,
    preprocess_alert,
    safe_divide,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_df(**overrides) -> pd.DataFrame:
    """Minimal valid DataFrame with one row per signature class.

    Uses the *internal* column names (post load_raw() rename) so that
    build_feature_matrix() / _derive_features() can find db_wait_avg5 etc.
    """
    base = {
        "timestamp": ["2026-04-01T10:00:00Z"] * 6,
        "service_name": [
            "payment-api",
            "auth-service",
            "order-service",
            "inventory-api",
            "notification-svc",
            "payment-api",
        ],
        "breaching_metric": [
            "db_conn_pool_wait_ms",
            "memory_percent",
            "cpu_percent",
            "http_5xx_rate",
            "http_5xx_rate",
            "cpu_percent",
        ],
        # Internal names (after load_raw() rename)
        "cpu_avg5": [15.0, 28.0, 94.0, 80.0, 12.0, 30.0],
        "mem_avg5": [52.0, 88.0, 60.0, 82.0, 45.0, 40.0],
        "http5xx_avg5": [8.0, 2.0, 18.0, 35.0, 38.0, 1.5],
        "db_wait_avg5": [340.0, 20.0, 45.0, 200.0, 15.0, 10.0],
        "latency_avg5": [620.0, 140.0, 1200.0, 1500.0, 900.0, 90.0],
        "incident_signature": [
            "db_pool_exhaustion",
            "memory_leak_progressive",
            "cpu_saturation_burst",
            "cascade_failure",
            "network_partition",
            "normal_noisy",
        ],
        "incident_id": ["INC-001", "INC-002", "INC-003", "INC-004", "INC-005", "INC-006"],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def make_alert_payload(**overrides) -> dict:
    payload = {
        "cpu_percent_avg5": 15.0,
        "memory_percent_avg5": 52.0,
        "http_5xx_rate_avg5": 8.0,
        "db_conn_pool_wait_avg5": 342.0,
        "request_latency_p99_avg5": 620.0,
        "breaching_metric": "db_conn_pool_wait_ms",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# encode_metric_name
# ---------------------------------------------------------------------------

class TestEncodeMetricName:
    def test_known_metrics_return_expected_codes(self):
        assert encode_metric_name("db_conn_pool_wait_ms") == 0
        assert encode_metric_name("cpu_percent") == 1
        assert encode_metric_name("memory_percent") == 2
        assert encode_metric_name("http_5xx_rate") == 3
        assert encode_metric_name("request_latency_p99") == 4

    def test_unknown_metric_returns_fallback(self):
        assert encode_metric_name("some_new_metric") == 5
        assert encode_metric_name("") == 5

    def test_all_keys_in_encoding_map_are_unique(self):
        values = list(METRIC_ENCODING.values())
        assert len(values) == len(set(values))


# ---------------------------------------------------------------------------
# safe_divide
# ---------------------------------------------------------------------------

class TestSafeDivide:
    def test_normal_division(self):
        assert safe_divide(100.0, 4.0) == pytest.approx(25.0)

    def test_zero_denominator_returns_fallback(self):
        assert safe_divide(100.0, 0.0) == pytest.approx(0.0)

    def test_zero_denominator_custom_fallback(self):
        assert safe_divide(100.0, 0.0, fallback=99.0) == pytest.approx(99.0)

    def test_both_zero(self):
        assert safe_divide(0.0, 0.0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# all_above_threshold
# ---------------------------------------------------------------------------

class TestAllAboveThreshold:
    def test_cascade_failure_all_high(self):
        # All metrics well above threshold
        result = all_above_threshold(
            cpu=85.0, mem=85.0, http5xx=40.0, db_wait=350.0, latency=2000.0
        )
        assert result == 1

    def test_normal_all_low(self):
        result = all_above_threshold(
            cpu=20.0, mem=40.0, http5xx=1.0, db_wait=15.0, latency=80.0
        )
        assert result == 0

    def test_mixed_not_all_above(self):
        # CPU high but others normal
        result = all_above_threshold(
            cpu=95.0, mem=40.0, http5xx=1.0, db_wait=15.0, latency=80.0
        )
        assert result == 0

    def test_returns_int(self):
        result = all_above_threshold(
            cpu=90.0, mem=90.0, http5xx=40.0, db_wait=400.0, latency=2000.0
        )
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# build_feature_matrix
# ---------------------------------------------------------------------------

class TestBuildFeatureMatrix:
    def test_output_shapes(self):
        df = make_df()
        X, y, le = build_feature_matrix(df)
        assert X.shape == (6, len(FEATURE_COLUMNS))
        assert y.shape == (6,)

    def test_feature_column_order(self):
        df = make_df()
        X, _, _ = build_feature_matrix(df)
        assert list(X.columns) == FEATURE_COLUMNS

    def test_all_classes_encoded(self):
        df = make_df()
        _, y, le = build_feature_matrix(df)
        # Should have all 6 unique class indices
        assert len(set(y)) == 6

    def test_label_encoder_fixed_class_order(self):
        df = make_df()
        _, _, le = build_feature_matrix(df)
        assert list(le.classes_) == sorted(CLASS_NAMES)

    def test_x_dtype_is_float(self):
        df = make_df()
        X, _, _ = build_feature_matrix(df)
        assert X.dtypes.apply(lambda d: np.issubdtype(d, np.floating)).all()

    def test_derived_db_wait_to_cpu_ratio(self):
        # For db_pool_exhaustion row: db_wait=340, cpu=15 → ratio ~22.67
        df = make_df()
        X, _, _ = build_feature_matrix(df)
        dpe_idx = df[df["incident_signature"] == "db_pool_exhaustion"].index[0]
        expected_ratio = 340.0 / 15.0
        assert X.loc[dpe_idx, "db_wait_to_cpu_ratio"] == pytest.approx(expected_ratio, rel=1e-3)

    def test_cascade_failure_all_metrics_spike_flag(self):
        # cascade_failure row has all metrics high → all_metrics_spike should be 1
        df = make_df()
        X, _, _ = build_feature_matrix(df)
        cf_row = df[df["incident_signature"] == "cascade_failure"].index[0]
        assert X.loc[cf_row, "all_metrics_spike"] == 1


# ---------------------------------------------------------------------------
# preprocess_alert
# ---------------------------------------------------------------------------

class TestPreprocessAlert:
    def test_output_columns_match_feature_columns(self):
        payload = make_alert_payload()
        X = preprocess_alert(payload)
        assert list(X.columns) == FEATURE_COLUMNS

    def test_output_shape_single_row(self):
        payload = make_alert_payload()
        X = preprocess_alert(payload)
        assert X.shape == (1, len(FEATURE_COLUMNS))

    def test_output_dtype_float(self):
        payload = make_alert_payload()
        X = preprocess_alert(payload)
        assert X.dtypes.apply(lambda d: np.issubdtype(d, np.floating)).all()

    def test_breaching_metric_encoded(self):
        payload = make_alert_payload(breaching_metric="db_conn_pool_wait_ms")
        X = preprocess_alert(payload)
        assert X["breaching_metric_enc"].iloc[0] == encode_metric_name("db_conn_pool_wait_ms")

    def test_db_wait_to_cpu_ratio_computed(self):
        payload = make_alert_payload(db_conn_pool_wait_avg5=300.0, cpu_percent_avg5=15.0)
        X = preprocess_alert(payload)
        assert X["db_wait_to_cpu_ratio"].iloc[0] == pytest.approx(300.0 / 15.0)

    def test_mem_dominance_computed(self):
        payload = make_alert_payload(memory_percent_avg5=80.0, cpu_percent_avg5=20.0)
        X = preprocess_alert(payload)
        assert X["mem_dominance"].iloc[0] == pytest.approx(80.0 / 21.0)

    def test_unknown_metric_uses_fallback_encoding(self):
        payload = make_alert_payload(breaching_metric="unknown_new_metric")
        X = preprocess_alert(payload)
        assert X["breaching_metric_enc"].iloc[0] == 5

    def test_zero_cpu_does_not_raise(self):
        payload = make_alert_payload(cpu_percent_avg5=0.0)
        X = preprocess_alert(payload)  # should not raise ZeroDivisionError
        assert X["db_wait_to_cpu_ratio"].iloc[0] == pytest.approx(0.0)  # safe_divide fallback


# ---------------------------------------------------------------------------
# load_raw — column renaming
# ---------------------------------------------------------------------------

class TestLoadRaw:
    def _make_csv_df(self) -> pd.DataFrame:
        """Build a DataFrame with raw CSV column names (pre-rename) for load_raw tests."""
        return pd.DataFrame(
            {
                "timestamp": ["2026-04-01T10:00:00Z"] * 2,
                "service_name": ["payment-api", "auth-service"],
                "breaching_metric": ["db_conn_pool_wait_ms", "memory_percent"],
                "cpu_percent_avg5": [15.0, 28.0],
                "memory_percent_avg5": [52.0, 88.0],
                "http_5xx_rate_avg5": [8.0, 2.0],
                "db_conn_pool_wait_avg5": [340.0, 20.0],
                "request_latency_p99_avg5": [620.0, 140.0],
                "incident_signature": ["db_pool_exhaustion", "memory_leak_progressive"],
                "incident_id": ["INC-001", "INC-002"],
            }
        )

    def test_csv_columns_renamed_correctly(self, tmp_path):
        df_csv = self._make_csv_df()
        csv_path = tmp_path / "test.csv"
        df_csv.to_csv(csv_path, index=False)

        loaded = load_raw(str(csv_path))
        assert "cpu_avg5" in loaded.columns
        assert "mem_avg5" in loaded.columns
        assert "http5xx_avg5" in loaded.columns
        assert "db_wait_avg5" in loaded.columns
        assert "latency_avg5" in loaded.columns

    def test_original_csv_columns_absent_after_rename(self, tmp_path):
        df_csv = self._make_csv_df()
        csv_path = tmp_path / "test.csv"
        df_csv.to_csv(csv_path, index=False)

        loaded = load_raw(str(csv_path))
        assert "cpu_percent_avg5" not in loaded.columns
        assert "memory_percent_avg5" not in loaded.columns


# ---------------------------------------------------------------------------
# CLASS_NAMES and FEATURE_COLUMNS consistency
# ---------------------------------------------------------------------------

class TestConstants:
    def test_class_names_count(self):
        assert len(CLASS_NAMES) == 6

    def test_feature_columns_count(self):
        assert len(FEATURE_COLUMNS) == 9

    def test_no_duplicate_class_names(self):
        assert len(CLASS_NAMES) == len(set(CLASS_NAMES))

    def test_no_duplicate_feature_columns(self):
        assert len(FEATURE_COLUMNS) == len(set(FEATURE_COLUMNS))

    def test_all_six_signatures_in_class_names(self):
        expected = {
            "db_pool_exhaustion",
            "memory_leak_progressive",
            "cpu_saturation_burst",
            "cascade_failure",
            "network_partition",
            "normal_noisy",
        }
        assert set(CLASS_NAMES) == expected
