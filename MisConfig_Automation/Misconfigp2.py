#!/usr/bin/env python3
"""
segregate_misconfigs_debug.py

- Reads the Misconfigurations sheet (auto-detect)
- Filters Severity for Critical/High (substring match)
- Matches rows to groups AHA/PMP/AZURE/PP using exact, substring, then fuzzy (rapidfuzz)
- Writes output workbook with sheets: AHA,PMP,AZURE,PP,Unmatched,Summary
- Writes discovered debug CSV with raw app cell, normalized, severity, full row text, and match reason
- Prints counts per canonical app before/after severity filter to stdout for quick verification
"""
from pathlib import Path
import re, csv, argparse, sys
import pandas as pd

# optional fuzzy
try:
    from rapidfuzz import process, fuzz
    HAS_RF = True
except Exception:
    HAS_RF = False

# canonical lists
AHA_LIST = [
"AWS Heart Bangalore Security Operations","AWS Atlas Dev","AWS ShopCPR Atlas Prod","AWS Odin Dev","AWS Odin Prod",
"AWS Atlas Prod","AWS Athena Prod","AWS WHO Prod","AWS FLP CNTRL Prod","AWS HBChatBot Dev","AWS Athena Dev","AWS WHO Dev",
"AWS Data Hub Dev","AWS Data Hub Prod","AWS Heart Bangalore Shared","AWS ShopCPR Dev","AWS eLearning Dev","AWS eLearning Prod",
"AWS AUI Dev","AWS AUI Prod","AWS CarePlans Dev","AWS CarePlans Prod","AWS CECME Dev","AWS CECME Prod","AWS FLP INST Dev",
"AWS FLP CNTRL Dev","AWS FLP JHU Prod","AWS GoldenAMI Prod"
]

PMP_LIST = [
"PMPConsumerDev","PMPConsumerProd","PMPConsumerTest","PMPDataLakeProd","PMPDataLakeTest","PMPDevOps","PMPDataLakeDev",
"SharedServicesQa","SharedServices","SharedServicesDev","AWS IdentityCenter","AWS LogArchive","AWS Network","AWS Audit",
"AWS AHA Master","LogArchive","IdentityCenter","Network","Audit","AWS AHA Master2"
]

AZURE_LIST = ["DevTest - MSDN Pricing","FLP - NonProd","Prod"]
PP_LIST = ["AWS Patient Portal Dev"]

GROUPS = {"AHA": AHA_LIST, "PMP": PMP_LIST, "AZURE": AZURE_LIST, "PP": PP_LIST}

FUZZY_THRESHOLD = 85  # 0-100

# helpers
def norm(s):
    return re.sub(r"\s+"," ", str(s or "").strip()).lower()

def detect_sheet(xls):
    for s in xls.sheet_names:
        if re.search(r"misconfig", s, re.I):
            return s
    # fallback
    return xls.sheet_names[0]

def find_col(df, patterns):
    lowered = {c.lower(): c for c in df.columns}
    for p in patterns:
        for k, orig in lowered.items():
            if re.search(p, k, re.I):
                return orig
    return None

def row_text(row):
    # join all string cells for fuzzy/substring checks
    vals = [str(v) for v in row.astype(str).values if str(v).strip()!=""]
    return " || ".join(vals)

def build_norm_maps():
    norm_maps = {}
    for g, lst in GROUPS.items():
        m = {}
        for v in lst:
            m[norm(v)] = v
        norm_maps[g] = m
    return norm_maps

def match_against_group(text_norm, app_cell_norm, norm_map):
    # exact app cell match
    if app_cell_norm and app_cell_norm in norm_map:
        return ("exact", norm_map[app_cell_norm])
    # exact presence in text
    for k, canon in norm_map.items():
        if k == text_norm:
            return ("exact_text", canon)
    # substring (canon inside text or text inside canon)
    for k, canon in norm_map.items():
        if k in text_norm or text_norm in k:
            return ("substr", canon)
    # fuzzy (if available)
    if HAS_RF and norm_map:
        choices = list(norm_map.keys())
        match = process.extractOne(text_norm, choices, scorer=fuzz.token_sort_ratio)
        if match and match[1] >= FUZZY_THRESHOLD:
            return ("fuzzy", norm_map[match[0]])
    return (None, None)

def process_file(infile:Path, outfile:Path, sheetname=None):
    xls = pd.ExcelFile(infile)
    sheet = sheetname or detect_sheet(xls)
    df = pd.read_excel(xls, sheet_name=sheet, dtype=str)
    df.fillna("", inplace=True)
    print(f"Processing sheet: {sheet}  rows: {len(df)}")

    app_col = find_col(df, [r"\bapplication\b", r"\bapp\b", r"application name", r"service"])
    sev_col = find_col(df, [r"severity", r"risk", r"level"])
    # require
    if not app_col or not sev_col:
        raise RuntimeError(f"Cannot detect columns. Found cols: {list(df.columns)[:50]}")

    # normalized canonical maps
    group_norm_maps = build_norm_maps()

    # counts per canonical before filter (inspect PMP existence)
    pre_counts = {}
    df["__app_norm"] = df[app_col].map(lambda x: norm(x))
    for g, m in group_norm_maps.items():
        cnt = df["__app_norm"].isin(set(m.keys())).sum()
        pre_counts[g] = int(cnt)
    print("Pre-severity counts per group (exact app column matches):")
    for g,c in pre_counts.items():
        print(f"  {g}: {c}")

    # severity filtering (substring contains critical/high)
    df["__sev_norm"] = df[sev_col].astype(str).map(lambda x: x.strip().lower())
    df["__keep"] = df["__sev_norm"].map(lambda s: ("critical" in s) or ("high" in s))
    df_filtered = df[df["__keep"]].copy()
    print("Rows after severity filter:", len(df_filtered))

    # counts after filter for exact app_col matches
    post_counts = {}
    for g, m in group_norm_maps.items():
        post_counts[g] = int(df_filtered["__app_norm"].isin(set(m.keys())).sum())
    print("Post-severity counts per group (exact app column matches):")
    for g,c in post_counts.items():
        print(f"  {g}: {c}")

    # assignment
    assignments = {}
    debug_rows = []  # rows to write into discovered CSV: raw app, norm app, severity, matched_group(if any), reason, full row text
    for idx, row in df_filtered.iterrows():
        app_cell = str(row[app_col]).strip()
        app_norm = norm(app_cell)
        text_norm = norm(row_text(row))
        matched = False
        matched_group = None
        matched_reason = None
        matched_canonical = None

        # try each group; collect all possible matches then choose most-specific (longest canonical)
        hits = []
        for g, normmap in group_norm_maps.items():
            reason, canon = match_against_group(text_norm, app_norm, normmap)
            if reason:
                hits.append((g, canon, len(canon), reason))
        if hits:
            # choose most specific (longest canonical string)
            hits.sort(key=lambda x: (x[2], x[1]), reverse=True)
            matched_group, matched_canonical, _, matched_reason = hits[0][0], hits[0][1], hits[0][2], hits[0][3]
            assignments[idx] = matched_group
            matched = True

        debug_rows.append({
            "index": idx,
            "raw_app": app_cell,
            "app_norm": app_norm,
            "severity": row[sev_col],
            "matched": matched_group or "",
            "match_reason": matched_reason or "",
            "matched_canonical": matched_canonical or "",
            "row_text": row_text(row)
        })

    # build DataFrames per group
    outputs = {}
    for g in GROUPS.keys():
        idxs = [i for i,grp in assignments.items() if grp==g]
        if idxs:
            outputs[g] = df_filtered.loc[idxs].drop(columns=[c for c in df_filtered.columns if c.startswith("__")], errors="ignore")
        else:
            outputs[g] = pd.DataFrame(columns=[c for c in df.columns if not c.startswith("__")])

    # unmatched
    assigned_idx = set(assignments.keys())
    unmatched_df = df_filtered.loc[[i for i in df_filtered.index if i not in assigned_idx]].drop(columns=[c for c in df_filtered.columns if c.startswith("__")], errors="ignore")

    # write outputs
    outfile.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(outfile, engine="openpyxl") as writer:
        for g, d in outputs.items():
            d.to_excel(writer, sheet_name=g[:31], index=False)
        unmatched_df.to_excel(writer, sheet_name="Unmatched", index=False)
        # summary
        summary = [{"Sheet":k, "Rows": len(v)} for k, v in {**outputs, "Unmatched": unmatched_df}.items()]
        pd.DataFrame(summary).to_excel(writer, sheet_name="Summary", index=False)

    # write debug CSV
    debug_csv = outfile.with_name(outfile.stem + "_debug.csv")
    with debug_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["index","raw_app","app_norm","severity","matched","matched_canonical","match_reason","row_text"])
        w.writeheader()
        for r in debug_rows:
            w.writerow(r)

    print("WROTE:", outfile)
    print("DEBUG CSV:", debug_csv)
    return {"outfile": str(outfile), "debug_csv": str(debug_csv), "pre_counts": pre_counts, "post_counts": post_counts, "outputs": {k:len(v) for k,v in outputs.items()}, "unmatched": len(unmatched_df)}

# CLI
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input","-i", required=True)
    p.add_argument("--output","-o", required=True)
    p.add_argument("--sheet", default=None)
    args = p.parse_args()
    res = process_file(Path(args.input), Path(args.output), sheetname=args.sheet)
    print(res)

if __name__ == "__main__":
    main()
