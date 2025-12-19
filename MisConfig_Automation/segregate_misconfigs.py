#!/usr/bin/env python3
"""
segregate_misconfigs_fixed.py

Usage:
    python segregate_misconfigs_fixed.py input.xlsx output.xlsx

Options:
    --sheet "SheetName"        # default: Misconfigurations
    --app-col "Application Name"  # column header to use; script will try to auto-detect if not provided
    --alias-file aliases.csv   # optional CSV with alias,canonical
"""
import sys, re, csv, argparse
from pathlib import Path
import pandas as pd

# ---------- Canonical application list (from your message) ----------
CANONICAL_APPS = [
"AWS AHA Master2","AWS LogArchive","AWS IdentityCenter","AWS Network","AWS Audit","AWS AHA Master",
"PMPConsumerDev","PMPConsumerProd","PMPConsumerTest","LogArchive","IdentityCenter","SharedServicesQa",
"SharedServices","SharedServicesDev","Network","PMPDataLakeProd","PMPDataLakeTest","PMPDevOps","Audit",
"PMPDataLakeDev","AWS Atlas Dev","AWS ShopCPR Atlas Prod","AWS Odin Dev","AWS Odin Prod","AWS Atlas Prod",
"AWS Athena Prod","AWS WHO Prod","AWS HBChatBot Dev","AWS Athena Dev","AWS WHO Dev","AWS HBChatBot Dev",
"AWS Data Hub Dev","AWS Data Hub Prod","AWS Heart Bangalore Shared","AWS ShopCPR Dev","AWS eLearning Dev",
"AWS eLearning Prod","AWS AUI Dev","AWS AUI Prod","AWS CarePlans Dev","AWS CarePlans Prod","AWS CECME Dev",
"AWS CECME Prod","AWS FLP INST Dev","AWS FLP CNTRL Dev","AWS FLP CNTRL Prod","AWS FLP JHU Prod",
"AWS GoldenAMI Prod","AWS Patient Portal Dev","AWS Heart Bangalore Security Operations","AWS AHA Master2",
"AWS Atlas Prod","AWS FLP CNTRL Prod"
]

def norm(s):
    return re.sub(r"\s+"," ", str(s).strip()).lower()

# normalized canonical map: normalized -> canonical (first occurrence preserved)
CANON_MAP = {}
for a in CANONICAL_APPS:
    n = norm(a)
    if n not in CANON_MAP:
        CANON_MAP[n] = a

def load_aliases(path: Path):
    m = {}
    if not path or not path.exists():
        return m
    with path.open(newline='') as fh:
        rdr = csv.reader(fh)
        hdr = next(rdr, None)
        for row in rdr:
            if len(row) >= 2:
                a = norm(row[0]); c = row[1].strip()
                if a:
                    m[a] = c
    return m

def detect_app_column(df):
    # prefer exact headers likely to contain app names
    candidates = [c for c in df.columns if re.search(r"application|app name|app|application name|service", str(c), re.I)]
    if candidates:
        # pick one with most non-empty values
        best = max(candidates, key=lambda c: df[c].astype(str).str.strip().replace("", pd.NA).notna().mean())
        return best
    # fallback: column with many short unique values
    best_col = None; best_score = -1
    for c in df.columns:
        s = df[c].astype(str).fillna("").str.strip()
        non = s[s!=""]
        uniq = non.nunique()
        avglen = non.map(len).mean() if len(non)>0 else 0
        score = uniq - (avglen/100)
        if score>best_score:
            best_score=score; best_col=c
    return best_col

def main():
    p = argparse.ArgumentParser()
    p.add_argument("input"); p.add_argument("output")
    p.add_argument("--sheet", default="Misconfigurations")
    p.add_argument("--app-col", default=None)
    p.add_argument("--alias-file", default=None)
    args = p.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    if not in_path.exists():
        print("ERROR: input file not found:", in_path); return 2

    aliases = load_aliases(Path(args.alias_file)) if args.alias_file else {}

    xls = pd.ExcelFile(in_path)
    if args.sheet not in xls.sheet_names:
    raise RuntimeError(
        f"Sheet '{args.sheet}' not found. Available: {xls.sheet_names}"
    )

    df = pd.read_excel(xls, sheet_name=args.sheet, dtype=str)
    df.fillna("", inplace=True)

    app_col = args.app_col or detect_app_column(df)
    if not app_col:
        print("ERROR: could not detect an application column."); return 4
    print("Using application column:", app_col)

    # Map each row to canonical app name if exact/alias/substr match; otherwise keep blank (unmatched)
    mapped = []
    discovered = {}
    for _, row in df.iterrows():
        cell = str(row.get(app_col, "")).strip()
        mapped_name = ""
        if cell:
            ncell = norm(cell)
            # alias exact
            if ncell in aliases:
                mapped_name = aliases[ncell]
            # canonical exact
            elif ncell in CANON_MAP:
                mapped_name = CANON_MAP[ncell]
            else:
                # substring match: try canonical names appearing in cell or vice-versa
                for k, canon in CANON_MAP.items():
                    if k in ncell or ncell in k:
                        mapped_name = canon
                        break
        if not mapped_name:
            # mark discovered raw value for review
            if cell:
                discovered[cell] = discovered.get(cell, 0) + 1
        else:
            # increment discovered canonical counts (helpful)
            discovered[mapped_name] = discovered.get(mapped_name, 0) + 1
        mapped.append(mapped_name)

    df['_MappedApp'] = mapped

    # write output file: one sheet per canonical app found (from CANON_MAP) plus Unmatched and Summary
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        apps_written = []
        # ensure deterministic order by using canonical list
        for canon in CANONICAL_APPS:
            # canonical list may contain duplicates; use normalized map for uniqueness
            canon_norm = norm(canon)
            canon_actual = CANON_MAP.get(canon_norm, canon)
            subset = df[df['_MappedApp'] == canon_actual].drop(columns=['_MappedApp'])
            if not subset.empty:
                sheet_name = canon_actual if len(canon_actual) <= 31 else canon_actual[:28] + "..."
                subset.to_excel(writer, sheet_name=sheet_name, index=False)
                apps_written.append((canon_actual, len(subset)))
        # Unmatched
        unmatched = df[df['_MappedApp'].astype(str).str.strip() == ""].drop(columns=['_MappedApp'])
        if not unmatched.empty:
            unmatched.to_excel(writer, sheet_name="Unmatched", index=False)
        # Summary
        summary_rows = [{"Application": a, "Rows": n} for a, n in apps_written]
        summary_rows.append({"Application": "Unmatched", "Rows": len(unmatched)})
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)

    # write discovered apps file (raw -> count)
    disc_path = out_path.with_name(out_path.stem + "_discovered_apps.csv")
    with disc_path.open("w", newline='') as fh:
        w = csv.writer(fh)
        w.writerow(["raw_or_canonical","count"])
        for k, v in sorted(discovered.items(), key=lambda x: -x[1]):
            w.writerow([k, v])

    print("Done. Output:", out_path)
    print("Discovered apps list:", disc_path)
    return 0

if __name__ == "__main__":
    sys.exit(main())
