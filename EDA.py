"""
CargoSense | EDA.py
Purpose: inspect the separate DataCo train and test files before feature selection and training.
Input: TRAIN_PATH and TEST_PATH (edit the two constants below to match your file names).
Output: printed summary per file, plus train versus test checks (columns, order overlap,
unseen categories, target balance) and leakage candidates.
Run: python EDA.py > eda_output.txt
"""
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
TRAIN_PATH = DATA_DIR / "train.csv"
TEST_PATH = DATA_DIR / "test.csv"
TARGET = "Late_delivery_risk"
GROUP_COLUMN = "Order Id"
NUMERIC_COLUMNS = [
    "Days for shipment (scheduled)",
    "Sales per customer",
    "Order Item Quantity",
    "Order Item Product Price",
    "Order Item Discount",
    "Benefit per order",
]
CATEGORICAL_COLUMNS = [
    "Type",
    "Shipping Mode",
    "Customer Segment",
    "Department Name",
    "Order Region",
    "Market",
]
LEAKAGE_COLUMNS = ["Days for shipping (real)", "Delivery Status"]
LEAKAGE_KEYWORDS = ("date", "status", "delivery", "shipping")


def print_section(title):
    print(f"\n=== {title} ===")


def load_data(path):
    return pd.read_csv(path, encoding="latin-1")


def report_shape(df, name):
    print_section(f"{name}: shape")
    print(f"rows: {len(df)}, columns: {df.shape[1]}")
    if GROUP_COLUMN in df.columns:
        print(f"unique {GROUP_COLUMN}: {df[GROUP_COLUMN].nunique()}")


def report_required_columns(df, name):
    print_section(f"{name}: required columns")
    required = NUMERIC_COLUMNS + CATEGORICAL_COLUMNS + [TARGET, GROUP_COLUMN]
    missing = [column for column in required if column not in df.columns]
    print("missing:", missing if missing else "none")


def report_target(df, name):
    print_section(f"{name}: target balance")
    if TARGET not in df.columns:
        print(f"{TARGET} not found in this file")
        return
    counts = df[TARGET].value_counts()
    shares = df[TARGET].value_counts(normalize=True).round(4)
    print(pd.DataFrame({"count": counts, "share": shares}))


def report_missing_and_duplicates(df, name):
    print_section(f"{name}: missing values and duplicates")
    missing = df.isna().sum()
    missing = missing[missing > 0]
    print(missing if len(missing) else "no missing values")
    print(f"fully duplicated rows: {df.duplicated().sum()}")


def report_numeric(df):
    print_section("train: numeric feature summary")
    present = [column for column in NUMERIC_COLUMNS if column in df.columns]
    print(df[present].describe().T.round(2))
    print("\nnegative values per column:")
    print((df[present] < 0).sum())


def report_categories(df):
    print_section("train: categorical values")
    for column in CATEGORICAL_COLUMNS:
        if column in df.columns:
            print(f"\n{column} ({df[column].nunique()} unique)")
            print(df[column].value_counts().head(30))


def report_late_rate_by_group(df):
    print_section("train: late rate by group")
    if TARGET not in df.columns:
        return
    for column in ("Shipping Mode", "Market", "Type", "Customer Segment"):
        if column in df.columns:
            print(f"\n{column}")
            print(df.groupby(column)[TARGET].agg(["mean", "count"]).round(3))
    scheduled = "Days for shipment (scheduled)"
    if scheduled in df.columns:
        print(f"\n{scheduled}")
        print(df.groupby(scheduled)[TARGET].agg(["mean", "count"]).round(3))


def report_leakage(df):
    print_section("train: leakage check")
    present = [column for column in LEAKAGE_COLUMNS if column in df.columns]
    print("known leakage columns present (must NOT be features):", present)
    candidates = [
        column
        for column in df.columns
        if any(keyword in column.lower() for keyword in LEAKAGE_KEYWORDS)
    ]
    print("\ncolumns to review manually before training:")
    for column in candidates:
        print(" -", column)


def report_train_test_checks(train_df, test_df):
    print_section("train vs test checks")
    only_train = sorted(set(train_df.columns) - set(test_df.columns))
    only_test = sorted(set(test_df.columns) - set(train_df.columns))
    print("columns only in train:", only_train if only_train else "none")
    print("columns only in test:", only_test if only_test else "none")

    if GROUP_COLUMN in train_df.columns and GROUP_COLUMN in test_df.columns:
        overlap = set(train_df[GROUP_COLUMN]) & set(test_df[GROUP_COLUMN])
        print(f"{GROUP_COLUMN} values in both files (should be 0): {len(overlap)}")

    for column in CATEGORICAL_COLUMNS:
        if column in train_df.columns and column in test_df.columns:
            unseen = set(test_df[column].dropna()) - set(train_df[column].dropna())
            print(f"{column} values in test but not in train:", sorted(unseen) if unseen else "none")

    if TARGET in train_df.columns and TARGET in test_df.columns:
        print(
            f"late share train: {train_df[TARGET].mean():.4f}, "
            f"test: {test_df[TARGET].mean():.4f}"
        )


def main():
    train_df = load_data(TRAIN_PATH)
    test_df = load_data(TEST_PATH)

    for df, name in ((train_df, "train"), (test_df, "test")):
        report_shape(df, name)
        report_required_columns(df, name)
        report_target(df, name)
        report_missing_and_duplicates(df, name)

    report_numeric(train_df)
    report_categories(train_df)
    report_late_rate_by_group(train_df)
    report_leakage(train_df)
    report_train_test_checks(train_df, test_df)


if __name__ == "__main__":
    main()