#!/usr/bin/env python3
"""
segregate_misconfigs.py
Stage 1 – Application-wise segregation of Misconfiguration report
(Enterprise Excel safe + Canonical mapping preserved)
"""

import sys, re, csv, argparse
from pathlib import Path
import pandas as pd

pd.set_option("mode.copy_on_write", True)


# ================= CANONICAL APPS ================= #

CANONICAL_APPS = [
"AWS AHA Master2","AWS LogArchive","AWS IdentityCenter","AWS Network","AWS Audit","AWS AHA Master",
"PMPConsumerDev","PMPConsumerProd","PMPConsumerTest","LogArchive","IdentityCenter","SharedServicesQa",
"SharedServices","SharedServicesDev","Network","PMPDataLakeProd","PMPDataLakeTest","PMPDevOps","Audit",
"PMPDataLakeDev","AWS Atlas Dev","AWS ShopCPR Atlas Prod","AWS Odin Dev","AWS Odin Prod","AWS Atlas Prod",
"AWS Athena Prod","AWS WHO Prod","AWS HBChatBot Dev","AWS Athena Dev","AWS WHO Dev",
"AWS Data Hub Dev","AWS Data Hub Prod","AWS Heart Bangalore Shared","AWS ShopCPR Dev",
"AWS eLearning Dev","AWS eLearning Prod","AWS AUI Dev","AWS AUI Prod",
"AWS CarePlans Dev","AWS CarePlans Prod","AWS CECME Dev","AWS CECME Prod",
"AWS FLP INST Dev","AWS FLP CNTRL Dev","AWS FLP CNTRL Prod","AWS FLP JHU Prod",
"AWS GoldenAMI Prod","AWS Patient Portal Dev",
"AWS Heart Bangalore Security Operations"
]

def norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip()).lower()

CANON_MAP = {}
for a in CANONICAL_APPS:
    n = norm(a)
    if n not in CANON_MAP:
        CANON_MAP[n] = a

# ================= DETECTION HELPERS ================= #

MISCONFIG_KEYS = ["misconfiguration", "misconfig"]
HEADER_KEYS = ["application", "service", "policy", "severity"]

def find_misconfig_sheet(xls: pd.ExcelFile) -> str:
    for s in xls.sheet_names:
        if any(k in norm(s) for k in MISCONFIG_KEYS):
            return s
    raise RuntimeError(
        f"Misconfiguration sheet not found. Sheets: {xls.sheet_names}"
    )

def find_header_row(df_preview: pd.DataFrame) -> int:
    for i in range(len(df_preview)):
        row = df_preview.iloc[i].astype(str).str.lower().tolist()
        hits = sum(any(k in cell for k in HEADER_KEYS) for cell in row)
        if hits >= 2:
            return i
    raise RuntimeError("Header row not detected in Misconfiguration sheet")

def detect_app_column(columns):
    for c in columns:
        if re.search(r"application|app", c, re.I):
            return c
    return None

# ================= MAIN ================= #

def main():
    p = argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("output")
    args = p.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    if not in_path.exists():
        raise FileNotFoundError(f"Input file not found: {in_path}")

    xls = pd.ExcelFile(in_path)

    # 1️⃣ Select Misconfiguration sheet
    sheet = find_misconfig_sheet(xls)
    print(f"[INFO] Using sheet: {sheet}")

    # 2️⃣ Detect header row safely
    preview = pd.read_excel(
        xls,
        sheet_name=sheet,
        header=None,
        nrows=40,
        dtype=str
    )

    header_row = find_header_row(preview)
    print(f"[INFO] Header row detected at index: {header_row}")

    # 3️⃣ Load real data
    df = pd.read_excel(
        xls,
        sheet_name=sheet,
        header=header_row,
        dtype=str
    )
    df.fillna("", inplace=True)

    if df.empty:
        raise RuntimeError("Misconfiguration sheet has no data rows")

    # 4️⃣ Detect Application column
    app_col = detect_app_column(df.columns)
    if not app_col:
        raise RuntimeError(
            f"Application column not found. Columns: {list(df.columns)}"
        )

    print(f"[INFO] Application column: {app_col}")
    print(f"[INFO] Total rows: {len(df)}")

    # ================= CANONICAL MAPPING ================= #

    mapped = []
    discovered = {}

    for _, row in df.iterrows():
        raw = str(row.get(app_col, "")).strip()
        mapped_app = ""

        if raw:
            nraw = norm(raw)
            if nraw in CANON_MAP:
                mapped_app = CANON_MAP[nraw]
            else:
                for k, canon in CANON_MAP.items():
                    if k in nraw or nraw in k:
                        mapped_app = canon
                        break

        if mapped_app:
            discovered[mapped_app] = discovered.get(mapped_app, 0) + 1
        else:
            discovered[raw or "Unmatched"] = discovered.get(raw or "Unmatched", 0) + 1

        mapped.append(mapped_app)

    df["_MappedApp"] = mapped

    # ================= WRITE OUTPUT ================= #

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        summary = []

        for canon in CANONICAL_APPS:
            subset = df[df["_MappedApp"] == canon].drop(columns=["_MappedApp"])
            if not subset.empty:
                subset.to_excel(writer, sheet_name=canon[:31], index=False)
                summary.append({"Application": canon, "Rows": len(subset)})

        unmatched = df[df["_MappedApp"] == ""].drop(columns=["_MappedApp"])
        if not unmatched.empty:
            unmatched.to_excel(writer, sheet_name="Unmatched", index=False)
            summary.append({"Application": "Unmatched", "Rows": len(unmatched)})

        pd.DataFrame(summary).to_excel(writer, sheet_name="Summary", index=False)

    # ================= DISCOVERY CSV ================= #

    disc_path = out_path.with_name(out_path.stem + "_discovered_apps.csv")
    with disc_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["raw_or_canonical", "count"])
        for k, v in sorted(discovered.items(), key=lambda x: -x[1]):
            w.writerow([k, v])

    print("✅ Misconfiguration segregation completed")
    print("Output:", out_path)
    print("Discovery CSV:", disc_path)
    return 0

if __name__ == "__main__":
    sys.exit(main())
