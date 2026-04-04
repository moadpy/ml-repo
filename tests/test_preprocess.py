"""
Unit tests for src/preprocess.py
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
    build_feature_matrix,
    engineer_features,
    load_raw,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_df(**overrides) -> pd.DataFrame:
    base = {
        "air_temperature_K": [298.1, 305.0, 310.2, 295.5, 302.0, 308.8],
        "process_temperature_K": [308.6, 315.0, 320.0, 306.0, 312.0, 318.0],
        "rotational_speed_rpm": [1551, 1400, 1600, 1500, 1450, 1520],
        "torque_Nm": [42.8, 55.0, 38.5, 48.0, 52.0, 41.0],
        "tool_wear_min": [108, 200, 50, 150, 30, 180],
        "type": ["M", "L", "H", "M", "L", "H"],
        "failure_type": [
            "No Failure",
            "Heat Dissipation Failure",
            "Power Failure",
            "Overstrain Failure",
            "Tool Wear Failure",
            "Random Failures",
        ],
    }
    base.update(overrides)
    return pd.DataFrame(base)


# ---------------------------------------------------------------------------
# engineer_features
# ---------------------------------------------------------------------------

class TestEngineerFeatures:
    def test_one_hot_columns_created(self):
        df = engineer_features(make_df())
        assert "type_L" in df.columns
        assert "type_M" in df.columns
        assert "type_H" in df.columns

    def test_type_M_encoding(self):
        df = engineer_features(make_df())
        m_rows = df[df["type"] == "M"]
        assert (m_rows["type_M"] == 1).all()
        assert (m_rows["type_L"] == 0).all()
        assert (m_rows["type_H"] == 0).all()

    def test_type_L_encoding(self):
        df = engineer_features(make_df())
        l_rows = df[df["type"] == "L"]
        assert (l_rows["type_L"] == 1).all()
        assert (l_rows["type_M"] == 0).all()

    def test_type_H_encoding(self):
        df = engineer_features(make_df())
        h_rows = df[df["type"] == "H"]
        assert (h_rows["type_H"] == 1).all()

    def test_missing_category_filled_with_zero(self):
        # DataFrame with only M and L types — type_H should still exist
        df = make_df(type=["M", "L", "M", "L", "M", "L"])
        result = engineer_features(df)
        assert "type_H" in result.columns
        assert (result["type_H"] == 0).all()

    def test_original_columns_preserved(self):
        df = make_df()
        result = engineer_features(df)
        for col in ["air_temperature_K", "torque_Nm", "failure_type"]:
            assert col in result.columns


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

    def test_label_encoding_no_failure(self):
        df = make_df()
        _, y, le = build_feature_matrix(df)
        no_failure_idx = CLASS_NAMES.index("No Failure")
        assert y[0] == no_failure_idx

    def test_label_encoding_all_classes_covered(self):
        df = make_df()
        _, y, _ = build_feature_matrix(df)
        # All 6 classes should appear exactly once
        assert len(set(y)) == 6

    def test_x_dtype_is_float(self):
        df = make_df()
        X, _, _ = build_feature_matrix(df)
        assert X.dtypes.apply(lambda d: d == float).all()

    def test_label_encoder_classes_fixed(self):
        df = make_df()
        _, _, le = build_feature_matrix(df)
        assert list(le.classes_) == CLASS_NAMES


# ---------------------------------------------------------------------------
# load_raw — column renaming
# ---------------------------------------------------------------------------

class TestLoadRaw:
    def test_kaggle_column_rename(self, tmp_path):
        csv_content = (
            "UDI,Product ID,Type,Air temperature [K],Process temperature [K],"
            "Rotational speed [rpm],Torque [Nm],Tool wear [min],Target,Failure Type\n"
            "1,M14860,M,298.1,308.6,1551,42.8,108,0,No Failure\n"
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        df = load_raw(str(csv_file))
        assert "air_temperature_K" in df.columns
        assert "process_temperature_K" in df.columns
        assert "rotational_speed_rpm" in df.columns
        assert "torque_Nm" in df.columns
        assert "tool_wear_min" in df.columns
        assert "failure_type" in df.columns
        assert "type" in df.columns
