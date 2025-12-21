#!/usr/bin/env python3
import sys, re, argparse
from pathlib import Path
import pandas as pd

CANONICAL_APPS = [
    "AWS Athena Dev","AWS Athena Prod",
    "AWS Atlas Dev","AWS Atlas Prod",
    "AWS Odin Dev","AWS Odin Prod",
    "AWS Data Hub Dev","AWS Data Hub Prod",
    "AWS WHO Dev","AWS WHO Prod",
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
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()

def map_app(cell):
    n = norm(cell)
    for canon in CANONICAL_APPS:
        if norm(canon) in n or n in norm(canon):
            return canon
    return "UNMATCHED"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--sheet", default=None)
    args = p.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    if not in_path.exists():
        raise RuntimeError(f"Input file not found: {in_path}")

    xls = pd.ExcelFile(in_path)
    sheet = args.sheet or xls.sheet_names[0]

    df = pd.read_excel(xls, sheet_name=sheet, dtype=str)
    df.fillna("", inplace=True)

    if df.empty:
        raise RuntimeError("Input sheet is empty")

    app_col = next((c for c in df.columns if re.search("application", c, re.I)), None)
    if not app_col:
        raise RuntimeError("Application column not found")

    df["_MappedApp"] = df[app_col].apply(map_app)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    wrote_any = False
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for app in CANONICAL_APPS:
            sub = df[df["_MappedApp"] == app].drop(columns=["_MappedApp"])
            if not sub.empty:
                sub.to_excel(writer, sheet_name=app[:31], index=False)
                wrote_any = True

        unmatched = df[df["_MappedApp"] == "UNMATCHED"].drop(columns=["_MappedApp"])
        if not unmatched.empty:
            unmatched.to_excel(writer, sheet_name="Unmatched", index=False)
            wrote_any = True

    if not wrote_any:
        raise RuntimeError("No rows matched any application")

    print("SUCCESS:", out_path)

if __name__ == "__main__":
    main()
