"""
Azure ML Training Script — RCA Incident Signature Classifier

Runs as an Azure ML Job on a cpu-cluster compute target.
Logs all params, metrics, and artifacts to MLflow (native Azure ML tracking).
Exits with code 1 if the quality gate (F1-macro >= 0.72) is not met —
this causes the GitHub Actions workflow to abort model registration.

Model: XGBoost multi-class classifier (objective="multi:softprob", num_class=6)
Target: incident_signature — 6 named classes

Usage (Azure ML Job entrypoint):
    python train.py --data_path ${{inputs.dataset}} --n_estimators 200 ...
"""

import argparse
import json
import os
import pickle
import sys

import matplotlib.pyplot as plt
import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from preprocess import CLASS_NAMES, FEATURE_COLUMNS, build_feature_matrix, load_raw


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train RCA incident signature classifier")
    p.add_argument("--data_path", type=str, required=True, help="Path to telemetry_labeled.csv")
    p.add_argument("--n_estimators", type=int, default=200)
    p.add_argument("--max_depth", type=int, default=6)
    p.add_argument("--learning_rate", type=float, default=0.1)
    p.add_argument("--subsample", type=float, default=0.8)
    p.add_argument("--colsample_bytree", type=float, default=0.8)
    p.add_argument(
        "--f1_threshold",
        type=float,
        default=0.72,
        help="Minimum F1-macro across 6 classes required to register the model",
    )
    return p.parse_args()


def _plot_confusion_matrix(y_true, y_pred, output_dir: str) -> str:
    cm = confusion_matrix(y_true, y_pred)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=CLASS_NAMES)
    fig, ax = plt.subplots(figsize=(10, 8))
    disp.plot(ax=ax, xticks_rotation=45, colorbar=True)
    ax.set_title("Confusion Matrix — RCA Incident Signature Classifier")
    plt.tight_layout()
    path = os.path.join(output_dir, "confusion_matrix.png")
    plt.savefig(path, dpi=120)
    plt.close(fig)
    return path


def _plot_feature_importances(model: XGBClassifier, output_dir: str) -> str:
    importances = model.feature_importances_
    idx = np.argsort(importances)[::-1]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(range(len(importances)), importances[idx], color="steelblue")
    ax.set_xticks(range(len(importances)))
    ax.set_xticklabels([FEATURE_COLUMNS[i] for i in idx], rotation=45, ha="right")
    ax.set_ylabel("Importance score")
    ax.set_title("XGBoost Feature Importances — Incident Signature Classifier")
    plt.tight_layout()
    path = os.path.join(output_dir, "feature_importances.png")
    plt.savefig(path, dpi=120)
    plt.close(fig)
    return path


def main() -> None:
    args = parse_args()

    with mlflow.start_run():
        mlflow.xgboost.autolog()
        mlflow.set_tag("model_type", "XGBoostClassifier")
        mlflow.set_tag("task", "incident_signature_classification")
        mlflow.set_tag("num_classes", str(len(CLASS_NAMES)))
        mlflow.log_param("f1_threshold", args.f1_threshold)

        # --- Data loading & feature engineering ---
        print(f"Loading dataset from: {args.data_path}")
        df = load_raw(args.data_path)
        print(f"Dataset shape: {df.shape}")
        print(f"Class distribution:\n{df['incident_signature'].value_counts()}\n")

        X, y, le = build_feature_matrix(df)
        mlflow.log_param("n_samples", len(X))
        mlflow.log_param("n_features", X.shape[1])

        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.20, random_state=42, stratify=y
        )
        mlflow.log_param("train_size", len(X_train))
        mlflow.log_param("val_size", len(X_val))

        # Per-sample weights to handle class imbalance
        sample_weights = compute_sample_weight(class_weight="balanced", y=y_train)

        # --- Model training ---
        model = XGBClassifier(
            objective="multi:softprob",
            num_class=len(CLASS_NAMES),
            n_estimators=args.n_estimators,
            max_depth=args.max_depth,
            learning_rate=args.learning_rate,
            subsample=args.subsample,
            colsample_bytree=args.colsample_bytree,
            use_label_encoder=False,
            eval_metric="mlogloss",
            random_state=42,
            n_jobs=-1,
        )

        print("Training XGBoost multi-class classifier...")
        model.fit(
            X_train,
            y_train,
            sample_weight=sample_weights,
            eval_set=[(X_val, y_val)],
            verbose=50,
        )

        # --- Evaluation ---
        y_pred = model.predict(X_val)
        f1_macro = f1_score(y_val, y_pred, average="macro")

        print(f"\nF1-macro (validation): {f1_macro:.4f}")
        print(f"Quality gate threshold: {args.f1_threshold}")
        print(f"\n{classification_report(y_val, y_pred, target_names=CLASS_NAMES)}")

        mlflow.log_metric("f1_macro", f1_macro)

        # Per-class F1 scores
        per_class_f1 = f1_score(y_val, y_pred, average=None)
        for cls_name, cls_f1 in zip(CLASS_NAMES, per_class_f1):
            mlflow.log_metric(f"f1_{cls_name}", cls_f1)
            print(f"  F1({cls_name}): {cls_f1:.4f}")

        # --- Artifacts ---
        output_dir = "outputs"
        os.makedirs(output_dir, exist_ok=True)

        cm_path = _plot_confusion_matrix(y_val, y_pred, output_dir)
        fi_path = _plot_feature_importances(model, output_dir)
        mlflow.log_artifact(cm_path)
        mlflow.log_artifact(fi_path)

        metrics = {
            "f1_macro": f1_macro,
            "per_class_f1": dict(zip(CLASS_NAMES, per_class_f1.tolist())),
            "n_train": len(X_train),
            "n_val": len(X_val),
        }
        metrics_path = os.path.join(output_dir, "metrics.json")
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)
        mlflow.log_artifact(metrics_path)

        # --- Quality gate ---
        if f1_macro < args.f1_threshold:
            print(
                f"\n[GATE FAILED] F1-macro {f1_macro:.4f} < threshold {args.f1_threshold}. "
                "Model will NOT be registered."
            )
            sys.exit(1)

        print(f"\n[GATE PASSED] F1-macro {f1_macro:.4f} >= {args.f1_threshold}. Saving model.")

        # --- Save model bundle ---
        # Bundle includes the LabelEncoder and FEATURE_COLUMNS so that score.py
        # can reconstruct predictions without importing preprocess.py at inference.
        model_bundle = {
            "model": model,
            "label_encoder": le,
            "feature_columns": FEATURE_COLUMNS,
            "class_names": CLASS_NAMES,
        }
        model_path = os.path.join(output_dir, "model.pkl")
        with open(model_path, "wb") as f:
            pickle.dump(model_bundle, f)

        mlflow.log_artifact(model_path)
        print(f"Model saved to: {model_path}")


if __name__ == "__main__":
    main()
