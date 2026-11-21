"""
CargoSense | model_training.py
Purpose: split, train, evaluate and save the leakage-free late-delivery XGBoost model.
Input: data/train.csv and data/test.csv (DataCo). Both files are pooled and re-split grouped by
Order Id, because the provided files share Order Ids (items of one order sit in both files).
Output: models/final_xgb_model.pkl, processed_data_pipeline.pkl, defaults.json, metrics.json.
Run: python model_training.py
"""
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

import feature_data as fd

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
TRAIN_PATH = DATA_DIR / "train.csv"
TEST_PATH = DATA_DIR / "test.csv"
RANDOM_STATE = 42
TEST_FOLDS = 5
VALIDATION_FOLDS = 6
THRESHOLD = 0.5
THRESHOLDS = [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7]
CALIBRATION_EDGES = [i / 10 for i in range(11)]
SUSPICIOUS_AUC = 0.95
DOMINANT_SHARE = 0.5


def load_pooled():
    train_raw = pd.read_csv(TRAIN_PATH, encoding="latin-1")
    test_raw = pd.read_csv(TEST_PATH, encoding="latin-1")
    shared = set(train_raw[fd.GROUP_COLUMN]) & set(test_raw[fd.GROUP_COLUMN])
    print(f"{fd.GROUP_COLUMN} shared between the provided files: {len(shared)}")
    return pd.concat([train_raw, test_raw], ignore_index=True)


def first_fold(index_source, y, groups, n_splits):
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
    rest, held = next(splitter.split(index_source, y, groups))
    return rest, held


def split_pooled(df):
    y = fd.get_target(df)
    groups = df[fd.GROUP_COLUMN]
    rest_idx, test_idx = first_fold(df, y, groups, TEST_FOLDS)
    rest = df.iloc[rest_idx]
    train_pos, val_pos = first_fold(rest, y.iloc[rest_idx], groups.iloc[rest_idx], VALIDATION_FOLDS)
    train_df, val_df, test_df = rest.iloc[train_pos], rest.iloc[val_pos], df.iloc[test_idx]
    sets = [set(d[fd.GROUP_COLUMN]) for d in (train_df, val_df, test_df)]
    assert not (sets[0] & sets[1] or sets[0] & sets[2] or sets[1] & sets[2]), "Order Id leak across splits"
    return train_df, val_df, test_df


def evaluate(y_true, proba, threshold=THRESHOLD):
    pred = (proba >= threshold).astype(int)
    return {
        "roc_auc": float(roc_auc_score(y_true, proba)),
        "accuracy": float(accuracy_score(y_true, pred)),
        "f1": float(f1_score(y_true, pred)),
        "precision": float(precision_score(y_true, pred)),
        "recall": float(recall_score(y_true, pred)),
        "confusion_matrix": confusion_matrix(y_true, pred).tolist(),
    }


def threshold_table(y_true, proba):
    rows = []
    for threshold in THRESHOLDS:
        pred = (proba >= threshold).astype(int)
        rows.append(
            {
                "threshold": threshold,
                "precision": float(precision_score(y_true, pred, zero_division=0)),
                "recall": float(recall_score(y_true, pred, zero_division=0)),
                "f1": float(f1_score(y_true, pred, zero_division=0)),
                "share_flagged": float(pred.mean()),
            }
        )
    return rows


def calibration_table(y_true, proba):
    frame = pd.DataFrame({"predicted": proba, "actual": y_true.to_numpy()})
    frame["bin"] = pd.cut(frame["predicted"], bins=CALIBRATION_EDGES, include_lowest=True).astype(str)
    grouped = frame.groupby("bin", observed=True).agg(
        mean_predicted=("predicted", "mean"),
        observed_late_rate=("actual", "mean"),
        count=("actual", "size"),
    )
    return grouped.reset_index().to_dict("records")


def fit_xgb(X_train, y_train, X_val, y_val):
    model = XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.1,
        eval_metric=["auc", "logloss"],
        early_stopping_rounds=30,
        tree_method="hist",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    return model


def fit_baselines(X_train, y_train):
    logistic = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    forest = RandomForestClassifier(
        n_estimators=200, max_depth=12, min_samples_leaf=20, n_jobs=-1, random_state=RANDOM_STATE
    )
    return {"logistic_regression": logistic.fit(X_train, y_train), "random_forest": forest.fit(X_train, y_train)}


def sanity_checks(model, columns, defaults, test_auc):
    if test_auc > SUSPICIOUS_AUC:
        print(f"WARNING: test ROC-AUC {test_auc:.4f} is above {SUSPICIOUS_AUC}; re-check for leakage")
    importances = pd.Series(model.feature_importances_, index=columns).sort_values(ascending=False)
    if importances.iloc[0] > DOMINANT_SHARE:
        print(f"WARNING: {importances.index[0]} holds {importances.iloc[0]:.2f} of total importance")
    cases = {
        "Same Day, 0 scheduled days": {"Shipping Mode": "Same Day", "Days for shipment (scheduled)": 0},
        "First Class, 1 scheduled day": {"Shipping Mode": "First Class", "Days for shipment (scheduled)": 1},
        "Standard Class, 4 scheduled days": {"Shipping Mode": "Standard Class", "Days for shipment (scheduled)": 4},
    }
    print("\nhand-made rows (late probability):")
    results = {}
    for name, values in cases.items():
        row = fd.encode_inference(fd.row_to_features(values, defaults), columns)
        results[name] = float(model.predict_proba(row)[0, 1])
        print(f"  {name}: {results[name]:.3f}")
    return importances, results


def main():
    MODELS_DIR.mkdir(exist_ok=True)
    pooled = load_pooled()
    train_df, val_df, test_df = split_pooled(pooled)
    sizes = {"train": len(train_df), "validation": len(val_df), "test": len(test_df)}
    print("rows:", sizes)

    X_train, columns = fd.encode_train(fd.select_features(train_df))
    X_val = fd.encode_inference(fd.select_features(val_df), columns)
    X_test = fd.encode_inference(fd.select_features(test_df), columns)
    y_train, y_val, y_test = fd.get_target(train_df), fd.get_target(val_df), fd.get_target(test_df)

    model = fit_xgb(X_train, y_train, X_val, y_val)

    baselines = fit_baselines(X_train, y_train)
    results = {name: evaluate(y_test, m.predict_proba(X_test)[:, 1]) for name, m in baselines.items()}
    results["xgboost"] = evaluate(y_test, model.predict_proba(X_test)[:, 1])
    for name, scores in results.items():
        print(f"\n{name}")
        print({k: round(v, 4) for k, v in scores.items() if k != "confusion_matrix"})
        print("confusion matrix:", scores["confusion_matrix"])

    defaults = fd.compute_defaults(fd.select_features(train_df))
    importances, hand_made = sanity_checks(model, columns, defaults, results["xgboost"]["roc_auc"])
    print("\ntop 10 feature importances:")
    print(importances.head(10).round(4))

    sweep = threshold_table(y_val, model.predict_proba(X_val)[:, 1])
    calibration = calibration_table(y_test, model.predict_proba(X_test)[:, 1])
    print("\nthreshold sweep on validation (choose the dashboard threshold here):")
    print(pd.DataFrame(sweep).round(4).to_string(index=False))
    print("\ncalibration on test (predicted vs observed late rate):")
    print(pd.DataFrame(calibration).round(4).to_string(index=False))

    joblib.dump(model, MODELS_DIR / "final_xgb_model.pkl")
    joblib.dump(columns, MODELS_DIR / "processed_data_pipeline.pkl")
    (MODELS_DIR / "defaults.json").write_text(json.dumps(defaults, indent=2))
    metrics = {
        **results["xgboost"],
        "threshold": THRESHOLD,
        "split": "pooled train+test, StratifiedGroupKFold by Order Id (test 1/5, validation 1/6 of rest)",
        "random_state": RANDOM_STATE,
        "rows": sizes,
        "best_iteration": int(model.best_iteration),
        "baselines": {name: results[name] for name in baselines},
        "hand_made_rows": hand_made,
        "threshold_sweep_validation": sweep,
        "calibration_test": calibration,
        "top_importances": importances.head(10).round(4).to_dict(),
    }
    (MODELS_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print("\nsaved:", sorted(p.name for p in MODELS_DIR.iterdir()))


if __name__ == "__main__":
    main()