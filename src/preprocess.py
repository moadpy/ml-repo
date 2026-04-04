"""
Feature engineering for the Machine Predictive Maintenance Classification dataset.

Input:  raw DataFrame from the Kaggle CSV
Output: feature matrix X, encoded label vector y, fitted LabelEncoder

Kaggle dataset: https://www.kaggle.com/datasets/shivamb/machine-predictive-maintenance-classification
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

# Canonical feature order — must stay consistent between train.py and score.py
FEATURE_COLUMNS = [
    "air_temperature_K",
    "process_temperature_K",
    "rotational_speed_rpm",
    "torque_Nm",
    "tool_wear_min",
    "type_L",
    "type_M",
    "type_H",
]

TARGET_COLUMN = "failure_type"

# Class order is fixed — index must match XGBoost class indices used at inference
CLASS_NAMES = [
    "No Failure",
    "Heat Dissipation Failure",
    "Power Failure",
    "Overstrain Failure",
    "Tool Wear Failure",
    "Random Failures",
]

# Kaggle CSV column name → internal name
_RENAME_MAP = {
    "Air temperature [K]": "air_temperature_K",
    "Process temperature [K]": "process_temperature_K",
    "Rotational speed [rpm]": "rotational_speed_rpm",
    "Torque [Nm]": "torque_Nm",
    "Tool wear [min]": "tool_wear_min",
    "Type": "type",
    "Failure Type": "failure_type",
}


def load_raw(csv_path: str) -> pd.DataFrame:
    """Load the Kaggle CSV and normalise column names."""
    df = pd.read_csv(csv_path)
    df = df.rename(columns={k: v for k, v in _RENAME_MAP.items() if k in df.columns})
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """One-hot encode the machine type column (L/M/H)."""
    type_dummies = pd.get_dummies(df["type"], prefix="type")
    # Guarantee all three columns exist even if a data split drops a category
    for col in ["type_L", "type_M", "type_H"]:
        if col not in type_dummies.columns:
            type_dummies[col] = 0
    return pd.concat([df, type_dummies], axis=1)


def build_feature_matrix(df: pd.DataFrame):
    """
    Returns
    -------
    X : pd.DataFrame  — feature matrix (FEATURE_COLUMNS order)
    y : np.ndarray    — integer-encoded labels
    le : LabelEncoder — fitted with CLASS_NAMES as fixed class order
    """
    df = engineer_features(df)

    X = df[FEATURE_COLUMNS].astype(float)

    le = LabelEncoder()
    le.classes_ = np.array(CLASS_NAMES)
    y = le.transform(df[TARGET_COLUMN])

    return X, y, le
