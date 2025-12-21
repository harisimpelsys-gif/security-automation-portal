#!/usr/bin/env python3
import sys, re, argparse
from pathlib import Path
import pandas as pd

CANONICAL_APPS = [
    "AWS AHA Master2","AWS LogArchive","AWS IdentityCenter","AWS Network","AWS Audit",
    "AWS AHA Master","AWS Atlas Dev","AWS Atlas Prod","AWS Athena Dev","AWS Athena Prod",
    "AWS WHO Dev","AWS WHO Prod","AWS Odin Dev","AWS Odin Prod",
    "AWS Data Hub Dev","AWS Data Hub Prod",
    "AWS ShopCPR Dev","AWS ShopCPR Atlas Prod",
    "AWS eLearning Dev","AWS eLearning Prod",
    "AWS CarePlans Dev","AWS CarePlans Prod",
    "AWS FLP CNTRL Dev","AWS FLP CNTRL Prod",
    "AWS FLP INST Dev","AWS FLP JHU Prod",
    "AWS GoldenAMI Prod",
    "AWS Heart Bangalore Shared",
    "AWS Heart Bangalore Security Operations",
]

def norm(s):
    return re.sub(r"\s+", " ", str(s).strip()).lower()

CANON_MAP = {norm(a): a for a in CANONICAL_APPS}

def detect_app_column(df):
    patterns = [
        r"application\s*name",
        r"\bapplication\b",
        r"\bapp\b",
        r"\bservice\s*name\b"
    ]
    for c in df.columns:
        for p in patterns:
            if re.search(p, c, re.I):
                return c
    return None

def main():
    p = argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--sheet", default=None)
    args = p.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    if not in_path.exists():
        print("ERROR: input file not found:", in_path)
        return 1

    xls = pd.ExcelFile(in_path)
    sheet = args.sheet or xls.sheet_names[0]

    df = pd.read_excel(xls, sheet_name=sheet, dtype=str).fillna("")

    if df.empty:
        print("ERROR: input sheet is empty")
        return 2

    app_col = detect_app_column(df)
    if not app_col:
        print("ERROR: Could not detect Application column")
        df.to_excel(out_path, index=False)
        return 3

    df["_MappedApp"] = df[app_col].apply(lambda x: CANON_MAP.get(norm(x), ""))

    out_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for app in CANONICAL_APPS:
            sub = df[df["_MappedApp"] == app].drop(columns="_MappedApp")
            if not sub.empty:
                sub.to_excel(writer, sheet_name=app[:31], index=False)
                written += len(sub)

        unmatched = df[df["_MappedApp"] == ""].drop(columns="_MappedApp")
        if not unmatched.empty:
            unmatched.to_excel(writer, sheet_name="Unmatched", index=False)

    if written == 0:
        print("WARNING: No rows matched canonical apps")

    print("DONE:", out_path)
    return 0

if __name__ == "__main__":
    sys.exit(main())
