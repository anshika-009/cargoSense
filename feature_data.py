"""
CargoSense | feature_data.py
Purpose: select leakage-free features, build the target, one-hot encode, and compute UI defaults.
Input: raw DataCo DataFrames (train or test), or a dict of UI values for a single order.
Output: feature matrix X, target y, the encoded column list, and a defaults dict.
Used by: model_training.py (training, evaluation) and the API (inference).
"""
import pandas as pd

TARGET = "Late_delivery_risk"
GROUP_COLUMN = "Order Id"
NUMERIC_FEATURES = [
    "Days for shipment (scheduled)",
    "Sales per customer",
    "Order Item Quantity",
    "Order Item Product Price",
    "Order Item Discount",
]
CATEGORICAL_FEATURES = [
    "Type",
    "Shipping Mode",
    "Customer Segment",
    "Department Name",
    "Market",
]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
FORBIDDEN_COLUMNS = ["Days for shipping (real)", "Delivery Status"]
FORBIDDEN_KEYWORDS = ("date", "status", "delivery", "(real)")


def assert_no_leakage(columns):
    banned = [c for c in columns if c in FORBIDDEN_COLUMNS]
    suspect = [c for c in columns if any(k in c.lower() for k in FORBIDDEN_KEYWORDS)]
    assert not banned, f"leakage columns in features: {banned}"
    assert not suspect, f"suspicious columns in features: {suspect}"


assert_no_leakage(FEATURES)


def clean_categories(df):
    for column in CATEGORICAL_FEATURES:
        df[column] = df[column].astype(str).str.split().str.join(" ")
    return df


def select_features(df):
    missing = [c for c in FEATURES if c not in df.columns]
    if missing:
        raise KeyError(f"missing feature columns: {missing}")
    return clean_categories(df[FEATURES].copy())


def get_target(df):
    if TARGET not in df.columns:
        raise KeyError(f"{TARGET} not found; split a test set out of the train file instead")
    return df[TARGET].astype(int)


def encode_train(X):
    encoded = pd.get_dummies(X, columns=CATEGORICAL_FEATURES, dtype=int)
    return encoded, list(encoded.columns)


def encode_inference(X, columns):
    encoded = pd.get_dummies(X, columns=CATEGORICAL_FEATURES, dtype=int)
    return encoded.reindex(columns=columns, fill_value=0)


def compute_defaults(df):
    defaults = {}
    for column in NUMERIC_FEATURES:
        defaults[column] = float(df[column].median())
    for column in CATEGORICAL_FEATURES:
        defaults[column] = str(df[column].mode().iloc[0])
    return defaults


def row_to_features(values, defaults):
    row = {column: values.get(column, defaults[column]) for column in FEATURES}
    return clean_categories(pd.DataFrame([row]))