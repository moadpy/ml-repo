"""
Azure ML Training Script — Predictive Maintenance Failure Classifier

Runs as an Azure ML Job on a cpu-cluster compute target.
Logs all params, metrics, and artifacts to MLflow (native Azure ML tracking).
Exits with code 1 if the quality gate (F1-macro threshold) is not met —
this causes the GitHub Actions workflow to abort model registration.

Usage (Azure ML Job entrypoint):
    python train.py --data_path ${{inputs.dataset}} --n_estimators 200 ...
"""

import argparse
import json
import os
import pickle

import matplotlib.pyplot as plt
import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

# preprocess.py lives in the same src/ directory
from preprocess import CLASS_NAMES, FEATURE_COLUMNS, build_feature_matrix, load_raw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train predictive maintenance classifier")
    parser.add_argument("--data_path", type=str, required=True, help="Path to dataset CSV")
    parser.add_argument("--n_estimators", type=int, default=200)
    parser.add_argument("--max_depth", type=int, default=6)
    parser.add_argument("--learning_rate", type=float, default=0.1)
    parser.add_argument("--subsample", type=float, default=0.8)
    parser.add_argument("--colsample_bytree", type=float, default=0.8)
    parser.add_argument(
        "--f1_threshold",
        type=float,
        default=0.85,
        help="Minimum F1-macro score required to register the model",
    )
    return parser.parse_args()


def _plot_confusion_matrix(y_true, y_pred, output_dir: str) -> str:
    cm = confusion_matrix(y_true, y_pred)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=CLASS_NAMES)
    fig, ax = plt.subplots(figsize=(10, 8))
    disp.plot(ax=ax, xticks_rotation=45, colorbar=True)
    ax.set_title("Confusion Matrix — Predictive Maintenance Classifier")
    plt.tight_layout()
    path = os.path.join(output_dir, "confusion_matrix.png")
    plt.savefig(path, dpi=120)
    plt.close(fig)
    return path


def _plot_feature_importances(model: XGBClassifier, feature_names: list, output_dir: str) -> str:
    importances = model.feature_importances_
    idx = np.argsort(importances)[::-1]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(range(len(importances)), importances[idx], color="steelblue")
    ax.set_xticks(range(len(importances)))
    ax.set_xticklabels([feature_names[i] for i in idx], rotation=45, ha="right")
    ax.set_ylabel("Importance score")
    ax.set_title("XGBoost Feature Importances")
    plt.tight_layout()
    path = os.path.join(output_dir, "feature_importances.png")
    plt.savefig(path, dpi=120)
    plt.close(fig)
    return path


def main() -> None:
    args = parse_args()

    mlflow.xgboost.autolog()
    mlflow.set_tag("model_type", "XGBoostClassifier")
    mlflow.set_tag("task", "predictive_maintenance_classification")
    mlflow.set_tag("dataset", "kaggle/machine-predictive-maintenance")
    mlflow.log_param("f1_threshold", args.f1_threshold)

    # --- Data loading & feature engineering ---
    print(f"Loading dataset from: {args.data_path}")
    df = load_raw(args.data_path)
    print(f"Dataset shape: {df.shape}")
    print(f"Class distribution:\n{df['failure_type'].value_counts()}\n")

    X, y, label_encoder = build_feature_matrix(df)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"Train: {X_train.shape[0]} rows  |  Test: {X_test.shape[0]} rows")

    # --- Model training ---
    model = XGBClassifier(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
        subsample=args.subsample,
        colsample_bytree=args.colsample_bytree,
        objective="multi:softprob",
        num_class=len(CLASS_NAMES),
        eval_metric="mlogloss",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    # --- Evaluation ---
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    f1_macro = f1_score(y_test, y_pred, average="macro")
    f1_weighted = f1_score(y_test, y_pred, average="weighted")

    mlflow.log_metric("accuracy", accuracy)
    mlflow.log_metric("f1_macro", f1_macro)
    mlflow.log_metric("f1_weighted", f1_weighted)

    # Per-class F1 scores
    per_class_f1 = f1_score(y_test, y_pred, average=None)
    for cls_name, cls_f1 in zip(CLASS_NAMES, per_class_f1):
        safe_key = cls_name.lower().replace(" ", "_")
        mlflow.log_metric(f"f1_{safe_key}", cls_f1)

    print("\n=== Evaluation Results ===")
    print(f"Accuracy      : {accuracy:.4f}")
    print(f"F1 (macro)    : {f1_macro:.4f}")
    print(f"F1 (weighted) : {f1_weighted:.4f}")
    print(f"\nClassification Report:\n{classification_report(y_test, y_pred, target_names=CLASS_NAMES)}")

    # --- Artifacts ---
    output_dir = "./outputs"
    os.makedirs(output_dir, exist_ok=True)

    cm_path = _plot_confusion_matrix(y_test, y_pred, output_dir)
    fi_path = _plot_feature_importances(model, X.columns.tolist(), output_dir)
    mlflow.log_artifact(cm_path)
    mlflow.log_artifact(fi_path)

    # Bundle model + metadata into a single pickle so score.py has everything it needs
    model_bundle = {
        "model": model,
        "label_encoder": label_encoder,
        "class_names": CLASS_NAMES,
        "feature_columns": FEATURE_COLUMNS,
    }
    model_path = os.path.join(output_dir, "model.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(model_bundle, f)
    mlflow.log_artifact(model_path)

    # Metrics JSON — used by ml_train.yml quality gate step
    metrics = {
        "accuracy": round(accuracy, 6),
        "f1_macro": round(f1_macro, 6),
        "f1_weighted": round(f1_weighted, 6),
        "f1_threshold": args.f1_threshold,
        "gate_passed": f1_macro >= args.f1_threshold,
    }
    metrics_path = os.path.join(output_dir, "metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    mlflow.log_artifact(metrics_path)

    print(f"\nArtifacts saved to: {output_dir}")

    # --- Quality gate ---
    if f1_macro >= args.f1_threshold:
        print(f"\n[GATE PASSED] F1-macro {f1_macro:.4f} >= threshold {args.f1_threshold}")
        print("Model will be registered in Azure ML Model Registry.")
    else:
        print(f"\n[GATE FAILED] F1-macro {f1_macro:.4f} < threshold {args.f1_threshold}")
        print("Model will NOT be registered. Check class imbalance, hyperparameters, or data quality.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
