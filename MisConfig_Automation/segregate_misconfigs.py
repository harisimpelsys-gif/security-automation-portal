#!/usr/bin/env python3
"""
segregate_misconfigs.py

Usage:
    python segregate_misconfigs.py input.xlsx output.xlsx

Options:
    --sheet "SheetName"           (default: Misconfigurations)
    --app-col "Application Name"  (auto-detected if not provided)
    --alias-file aliases.csv
"""

import sys
import re
import csv
import argparse
from pathlib import Path
import pandas as pd

# ---------------- CANONICAL APPLICATION LIST ---------------- #

CANONICAL_APPS = [
    "AWS AHA Master2","AWS LogArchive","AWS IdentityCenter","AWS Network","AWS Audit","AWS AHA Master",
    "PMPConsumerDev","PMPConsumerProd","PMPConsumerTest","LogArchive","IdentityCenter","SharedServicesQa",
    "SharedServices","SharedServicesDev","Network","PMPDataLakeProd","PMPDataLakeTest","PMPDevOps","Audit",
    "PMPDataLakeDev","AWS Atlas Dev","AWS ShopCPR Atlas Prod","AWS Odin Dev","AWS Odin Prod","AWS Atlas Prod",
    "AWS Athena Prod","AWS WHO Prod","AWS HBChatBot Dev","AWS Athena Dev","AWS WHO Dev",
    "AWS Data Hub Dev","AWS Data Hub Prod","AWS Heart Bangalore Shared","AWS ShopCPR Dev",
    "AWS eLearning Dev","AWS eLearning Prod","AWS AUI Dev","AWS AUI Prod","AWS CarePlans Dev",
    "AWS CarePlans Prod","AWS CECME Dev","AWS CECME Prod","AWS FLP INST Dev","AWS FLP CNTRL Dev",
    "AWS FLP CNTRL Prod","AWS FLP JHU Prod","AWS GoldenAMI Prod","AWS Patient Portal Dev",
    "AWS Heart Bangalore Security Operations"
]

def norm(s):
    return re.sub(r"\s+", " ", str(s).strip()).lower()

CANON_MAP = {}
for a in CANONICAL_APPS:
    n = norm(a)
    if n not in CANON_MAP:
        CANON_MAP[n] = a

# ---------------- HELPERS ---------------- #

def load_aliases(path: Path):
    aliases = {}
    if not path or not path.exists():
        return aliases
    with path.open(newline="") as fh:
        rdr = csv.reader(fh)
        next(rdr, None)
        for row in rdr:
            if len(row) >= 2:
                aliases[norm(row[0])] = row[1].strip()
    return aliases

def detect_app_column(df):
    candidates = [c for c in df.columns if re.search(r"app|application|service", c, re.I)]
    if candidates:
        return candidates[0]
    return None

# ---------------- MAIN ---------------- #

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--sheet", default="Misconfigurations")
    parser.add_argument("--app-col", default=None)
    parser.add_argument("--alias-file", default=None)
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    if not in_path.exists():
        print(f"ERROR: input file not found: {in_path}")
        return 2

    xls = pd.ExcelFile(in_path)

    if args.sheet not in xls.sheet_names:
        raise RuntimeError(
            f"Sheet '{args.sheet}' not found. Available sheets: {xls.sheet_names}"
        )

    df = pd.read_excel(in_path, sheet_name=args.sheet, dtype=str).fillna("")

    app_col = args.app_col or detect_app_column(df)
    if not app_col:
        raise RuntimeError("Could not detect application column")

    aliases = load_aliases(Path(args.alias_file)) if args.alias_file else {}

    mapped = []
    discovered = {}

    for _, row in df.iterrows():
        raw = str(row.get(app_col, "")).strip()
        mapped_name = ""

        if raw:
            nraw = norm(raw)
            if nraw in aliases:
                mapped_name = aliases[nraw]
            elif nraw in CANON_MAP:
                mapped_name = CANON_MAP[nraw]
            else:
                for k, canon in CANON_MAP.items():
                    if k in nraw or nraw in k:
                        mapped_name = canon
                        break

        if mapped_name:
            discovered[mapped_name] = discovered.get(mapped_name, 0) + 1
        elif raw:
            discovered[raw] = discovered.get(raw, 0) + 1

        mapped.append(mapped_name)

    df["_MappedApp"] = mapped

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        written = False

        for canon in CANONICAL_APPS:
            canon_actual = CANON_MAP.get(norm(canon))
            subset = df[df["_MappedApp"] == canon_actual].drop(columns="_MappedApp")
            if not subset.empty:
                subset.to_excel(writer, sheet_name=canon_actual[:31], index=False)
                written = True

        unmatched = df[df["_MappedApp"] == ""].drop(columns="_MappedApp")
        if not unmatched.empty:
            unmatched.to_excel(writer, sheet_name="Unmatched", index=False)
            written = True

        summary = (
            df["_MappedApp"]
            .replace("", "Unmatched")
            .value_counts()
            .reset_index()
            .rename(columns={"index": "Application", "_MappedApp": "Rows"})
        )
        summary.to_excel(writer, sheet_name="Summary", index=False)

    if not written:
        raise RuntimeError("No data written — mapping rules may be incorrect")

    disc_path = out_path.with_name(out_path.stem + "_discovered_apps.csv")
    with disc_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["raw_or_canonical", "count"])
        for k, v in sorted(discovered.items(), key=lambda x: -x[1]):
            w.writerow([k, v])

    print("SUCCESS")
    print("Output:", out_path)
    print("Discovered apps:", disc_path)
    return 0

if __name__ == "__main__":
    sys.exit(main())
