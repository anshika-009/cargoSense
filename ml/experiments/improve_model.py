"""
CargoSense | experiments/improve_model.py
Purpose: measure which changes improve late-delivery accuracy, one change at a time.
Input: data/train.csv and data/test.csv, split exactly as in model_training.py (grouped by Order Id).
Output: a table of validation and test metrics per experiment, saved to models/experiments.json.
Notes: raw hour (experiment 1) is kept only as evidence: it adds a spurious hour effect to modes that have
no cut-off rule, so the adopted feature (3) uses the hour for Same Day orders only. Every experiment is compared with the baseline on the same rows. Choices are made on the
validation part; the test part is reported for all rows so nothing is hidden. Cancelled and
suspected-fraud orders never ship, so a second test column excludes them.
Run from the repo root: python -m experiments.improve_model
"""
import json

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from xgboost import XGBClassifier

from ml import feature_data as fd
from ml import model_training as mt

NEVER_SHIPPED = ("CANCELED", "SUSPECTED_FRAUD")
BASE_NUMERIC = [c for c in fd.NUMERIC_FEATURES if c != "same_day_order_hour"]
BASE_CATEGORICAL = list(fd.CATEGORICAL_FEATURES)


def add_time_features(df):
    ordered = pd.to_datetime(df[fd.ORDER_DATE_COLUMN])
    df["order_month"] = ordered.dt.month
    df["order_dow"] = ordered.dt.dayofweek
    return fd.add_time_features(df)


def build(df, numeric, categorical, columns=None):
    X = pd.get_dummies(df[numeric + categorical].astype({c: str for c in categorical}), columns=categorical)
    X = X.astype(float)
    if columns is None:
        return X, list(X.columns)
    return X.reindex(columns=columns, fill_value=0.0), columns


def metrics(y, proba, threshold=0.5):
    pred = (proba >= threshold).astype(int)
    return {
        "auc": roc_auc_score(y, proba), "acc": accuracy_score(y, pred), "f1": f1_score(y, pred),
        "prec": precision_score(y, pred, zero_division=0), "rec": recall_score(y, pred, zero_division=0),
    }


def run(name, parts, numeric, categorical, drop_unshipped=False, params=None):
    train, val, test = parts
    if drop_unshipped:
        train = train[~train["Order Status"].isin(NEVER_SHIPPED)]
        val = val[~val["Order Status"].isin(NEVER_SHIPPED)]
    X_train, columns = build(train, numeric, categorical)
    X_val, _ = build(val, numeric, categorical, columns)
    settings = dict(
        n_estimators=300, max_depth=5, learning_rate=0.1, eval_metric="logloss", early_stopping_rounds=30,
        tree_method="hist", random_state=mt.RANDOM_STATE, n_jobs=-1,
    )
    settings.update(params or {})
    model = XGBClassifier(**settings)
    model.fit(X_train, train[fd.TARGET], eval_set=[(X_val, val[fd.TARGET])], verbose=False)
    shipped = test[~test["Order Status"].isin(NEVER_SHIPPED)]
    result = {"name": name, "val": metrics(val[fd.TARGET], model.predict_proba(X_val)[:, 1])}
    for label, part in (("test_all", test), ("test_shipped", shipped)):
        X_part, _ = build(part, numeric, categorical, columns)
        result[label] = metrics(part[fd.TARGET], model.predict_proba(X_part)[:, 1])
    return result, model, columns


def main():
    df = add_time_features(mt.load_pooled())
    parts = mt.split_pooled(df)
    time_features = ["order_hour", "order_month", "order_dow"]
    same_day = "same_day_order_hour"
    experiments = [
        ("0 baseline (10 features)", BASE_NUMERIC, BASE_CATEGORICAL, False, None),
        ("1 + raw order hour", BASE_NUMERIC + ["order_hour"], BASE_CATEGORICAL, False, None),
        ("2 + raw hour, month, weekday", BASE_NUMERIC + time_features, BASE_CATEGORICAL, False, None),
        ("3 + same-day order hour (adopted)", BASE_NUMERIC + [same_day], BASE_CATEGORICAL, False, None),
        ("4 = 3, drop cancelled/fraud in training", BASE_NUMERIC + [same_day], BASE_CATEGORICAL, True, None),
        ("5 = 3 + product category", BASE_NUMERIC + [same_day], BASE_CATEGORICAL + ["Category Name"], False, None),
        ("6 = 3 + order region", BASE_NUMERIC + [same_day], BASE_CATEGORICAL + ["Order Region"], False, None),
        ("7 = 3 + deeper trees (depth 7)", BASE_NUMERIC + [same_day], BASE_CATEGORICAL, False, {"max_depth": 7}),
    ]
    rows = []
    for name, numeric, categorical, drop, params in experiments:
        result, _, _ = run(name, parts, numeric, categorical, drop, params)
        rows.append(result)
        print(f"{name:<44} val auc {result['val']['auc']:.4f} acc {result['val']['acc']:.4f} | "
              f"test(all) auc {result['test_all']['auc']:.4f} acc {result['test_all']['acc']:.4f} | "
              f"test(shipped) auc {result['test_shipped']['auc']:.4f} acc {result['test_shipped']['acc']:.4f}")
    mt.MODELS_DIR.mkdir(exist_ok=True)
    (mt.MODELS_DIR / "experiments.json").write_text(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
