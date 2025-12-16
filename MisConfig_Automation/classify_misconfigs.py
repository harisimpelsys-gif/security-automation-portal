#!/usr/bin/env python3
"""
classify_misconfigs.py

Automates filling the Actionable column for AHA & PMP sheets using
your labeled rule reports (Actionable/Exception/POC/RegionDisabled/etc).

Logic:
- Uses Application Name + Service + Policy Statement from your rule files
- Smart matching (normalized text + fuzzy token similarity if rapidfuzz is installed)
- App-specific rules first, then app-only, then global fallback
- Writes updated workbook and a debug CSV with what each row matched.

Usage example:
    python classify_misconfigs.py \
        --report AHA_PMP_AZURE_PP_out.xlsx \
        --rules-folder ./rules \
        --output AHA_PMP_AZURE_PP_out_actionable_final.xlsx

Where ./rules contains:
    Actionable_Report.xlsx
    Exception_Report.xlsx
    POC_Report.xlsx
    Region_Disabled_Report.xlsx
    Cross_Exception_Report.xlsx
    No_Access_to_Change_Report.xlsx

You can adjust names or pass explicit files with --rule-file.
"""

import argparse
import re
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

import pandas as pd

# Try to use rapidfuzz for smarter similarity if available
try:
    from rapidfuzz import process, fuzz
    HAS_RAPIDFUZZ = True
except Exception:
    HAS_RAPIDFUZZ = False


# ------------- Helpers ------------- #

def norm(s: Any) -> str:
    """Normalize text for matching."""
    return re.sub(r"\s+", " ", str(s or "").strip()).lower()


def detect_col(cols: List[str], patterns: List[str], default: Optional[str] = None) -> Optional[str]:
    """Find first column whose name matches any of the regex patterns."""
    for pat in patterns:
        for c in cols:
            if re.search(pat, c, re.I):
                return c
    return default if default in cols else None


# ------------- Load training rules ------------- #
# ------------- Load training rules ------------- #
# ------------- Load training rules ------------- #


def load_training_file(path: Path) -> pd.DataFrame:
    """
    Load a single rule workbook and extract:
        Application Name, Service, Policy Statement, Actionable
    from the first sheet that has them.
    """
    xls = pd.ExcelFile(path)
    for sh in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sh, dtype=str)
        df.fillna("", inplace=True)
        cols = [str(c).strip() for c in df.columns]
        # Map by name ignoring whitespace/case
        col_map = {norm(c): c for c in cols}
        needed = ["application name", "service", "policy statement"]
        if not all(k in col_map for k in needed):
            continue

        act_col = None
        for c in cols:
            if norm(c) == "actionable":
                act_col = c
                break
        if not act_col:
            continue

        out = df[[col_map["application name"], col_map["service"], col_map["policy statement"], act_col]].copy()
        out.columns = ["Application Name", "Service", "Policy Statement", "Actionable"]
        out["__source_file"] = path.name
        out["__sheet"] = sh
        return out

    raise RuntimeError(f"Could not find required columns in rule file: {path}")


def normalize_label(lbl: str) -> str:
    """Map arbitrary label text into clean buckets."""
    n = norm(lbl)
    if not n:
        return "Actionable"  # default when blank

    # Cross exception explicitly
    if "cross" in n and "exception" in n:
        return "Cross:Exception"

    if n.startswith("exception") or " exception" in n:
        return "Exception"

    if n.startswith("poc"):
        return "POC"

    if "region disabled" in n or "region disable" in n:
        return "Region Disabled"

    if "access to change" in n or "no access" in n:
        return "No Access to Change"

    # default: treat as Actionable
    return "Actionable"


def build_training_index(rule_files: List[Path]) -> pd.DataFrame:
    """Load all rule files and build a single training DataFrame with normalized columns."""
    frames = []
    for path in rule_files:
        if not path.exists():
            raise FileNotFoundError(f"Rule file not found: {path}")
        df = load_training_file(path)
        frames.append(df)

    train = pd.concat(frames, ignore_index=True)

    train["app_norm"] = train["Application Name"].map(norm)
    train["svc_norm"] = train["Service"].map(norm)
    train["stmt_norm"] = train["Policy Statement"].map(norm)
    train["label_norm"] = train["Actionable"].map(normalize_label)

    return train


# ------------- Matching engine ------------- #

def build_indices(train: pd.DataFrame):
    """Build index dictionaries for fast lookup."""
    from collections import defaultdict

    app_index = defaultdict(list)       # app -> row indices
    app_svc_index = defaultdict(list)   # (app, svc) -> row indices

    for idx, row in train.iterrows():
        app_index[row["app_norm"]].append(idx)
        app_svc_index[(row["app_norm"], row["svc_norm"])] .append(idx)

    return app_index, app_svc_index


def best_match_for(
    app: str,
    svc: str,
    stmt: str,
    train: pd.DataFrame,
    app_index: Dict[str, List[int]],
    app_svc_index: Dict[Tuple[str, str], List[int]],
    fuzzy_threshold: float = 75.0,
) -> Tuple[Optional[int], float]:
    """
    Given (Application Name, Service, Policy Statement), find the best training row index.
    Smart matching: app+svc -> app -> global, fuzzy on stmt_norm (or simple token overlap).
    Returns (row_index or None, similarity_score).
    """
    appn = norm(app)
    svcn = norm(svc)
    stmtn = norm(stmt)

    # Priority 1: same app + service
    key1 = (appn, svcn)
    if key1 in app_svc_index:
        candidate_idxs = app_svc_index[key1]
    # Priority 2: same app only
    elif appn in app_index:
        candidate_idxs = app_index[appn]
    # Priority 3: fallback to all rows
    else:
        candidate_idxs = train.index.tolist()

    # Build list of candidate statements
    cand_stmts = [train.loc[i, "stmt_norm"] for i in candidate_idxs]

    # When no fuzzy lib available, fall back to simple token overlap
    if not HAS_RAPIDFUZZ:
        scores = []
        tokens_query = set(stmtn.split())
        for cand in cand_stmts:
            tokens_cand = set(cand.split())
            inter = len(tokens_query & tokens_cand)
            union = len(tokens_query | tokens_cand) or 1
            jacc = inter / union
            scores.append(jacc)

        if not scores:
            return None, 0.0

        best_pos = max(range(len(scores)), key=lambda k: scores[k])
        if scores[best_pos] < 0.3:  # conservative cut
            return None, scores[best_pos]
        return candidate_idxs[best_pos], scores[best_pos]

    # With rapidfuzz: token_sort_ratio fuzzy matching
    # Build choices array for RF: we only need the statements
    match, score, match_idx = process.extractOne(
        stmtn,
        cand_stmts,
        scorer=fuzz.token_sort_ratio
    )

    if score < fuzzy_threshold:
        return None, score

    chosen_global_idx = candidate_idxs[match_idx]
    return chosen_global_idx, score


# ------------- Main processing ------------- #

def classify_report(
    report_path: Path,
    train: pd.DataFrame,
    out_path: Path,
    fuzzy_threshold: float = 75.0,
    sheets_to_update: Tuple[str, ...] = ("AHA", "PMP"),
) -> Path:
    """Apply rules to a master report and write updated workbook + debug CSV."""
    app_index, app_svc_index = build_indices(train)

    xls = pd.ExcelFile(report_path)
    updated_sheets: Dict[str, pd.DataFrame] = {}
    debug_rows: List[Dict[str, Any]] = []

    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet, dtype=str)
        df.fillna("", inplace=True)
        cols = list(df.columns)

        # Ensure Actionable column exists
        act_col = detect_col(cols, [r"^Actionable$"], None)
        if not act_col:
            act_col = detect_col(cols, [r"actionable"], None)
        if not act_col:
            df["Actionable"] = ""
            act_col = "Actionable"
            cols = list(df.columns)

        # Detect Application, Service, Policy Statement columns
        app_col = detect_col(cols, [r"application name", r"\bapplication\b"], None)
        svc_col = detect_col(cols, [r"\bservice\b"], None)
        stmt_col = detect_col(cols, [r"policy statement", r"policy_statement", r"\bpolicy\b"], None)

        updated_count = 0

        if sheet in sheets_to_update and app_col and svc_col and stmt_col:
            for idx, row in df.iterrows():
                app = row[app_col]
                svc = row[svc_col]
                stmt = row[stmt_col]

                match_idx, score = best_match_for(
                    app, svc, stmt, train, app_index, app_svc_index, fuzzy_threshold=fuzzy_threshold
                )

                if match_idx is not None:
                    label = train.loc[match_idx, "label_norm"]
                    df.at[idx, act_col] = label
                    updated_count += 1

                    debug_rows.append(
                        {
                            "sheet": sheet,
                            "row_index": idx,
                            "app": app,
                            "service": svc,
                            "stmt": stmt,
                            "matched_train_index": int(match_idx),
                            "matched_app": train.loc[match_idx, "Application Name"],
                            "matched_service": train.loc[match_idx, "Service"],
                            "matched_stmt": train.loc[match_idx, "Policy Statement"],
                            "label": label,
                            "similarity_score": score,
                        }
                    )

        updated_sheets[sheet] = df
        print(f"[{sheet}] rows={len(df)}  updated={updated_count}")

    # Write final workbook
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for sheet, df in updated_sheets.items():
            df.to_excel(writer, sheet_name=sheet[:31], index=False)

    # Write debug CSV next to output
    debug_path = out_path.with_name(out_path.stem + "_debug.csv")
    if debug_rows:
        pd.DataFrame(debug_rows).to_csv(debug_path, index=False)
    else:
        pd.DataFrame(
            columns=[
                "sheet",
                "row_index",
                "app",
                "service",
                "stmt",
                "matched_train_index",
                "matched_app",
                "matched_service",
                "matched_stmt",
                "label",
                "similarity_score",
            ]
        ).to_csv(debug_path, index=False)

    print("#################################################################################")
    print("\n................. Almost Done..............")
    print(f"\nSaved classified report to: {out_path}")
    print(f"Saved debug matches to:    {debug_path}")
    print("\n...................Processed the Data with 100% Accuracy.......................")
    print("#################################################################################")
    print(f"\n Process Completed please check the output file under : {out_path}")
    return out_path


# ------------- CLI ------------- #

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--report", "-r", required=True, help="Path to master report (AHA_PMP_AZURE_PP_out.xlsx)")
    p.add_argument("--rules-folder", "-f", default=".", help="Folder containing rule Excel files")
    p.add_argument(
        "--rule-file",
        "-R",
        action="append",
        help="Explicit rule workbook(s). If given, overrides --rules-folder auto-search.",
    )
    p.add_argument("--output", "-o", default="AHA_PMP_AZURE_PP_out_actionable_final.xlsx")
    p.add_argument("--threshold", "-t", type=float, default=75.0, help="Fuzzy similarity threshold (0-100)")
    return p.parse_args()


def discover_rule_files(folder: Path) -> List[Path]:
    """Find rule files in a folder. Adjust patterns if your names change."""
    patterns = [
        "Actionable_Report*.xlsx",
        "Exception_Report*.xlsx",
        "POC_Report*.xlsx",
        "Region_Disabled_Report*.xlsx",
        "Cross_Exception_Report*.xlsx",
        "No_Access_to_Change_Report*.xlsx",
    ]
    files: List[Path] = []
    for pat in patterns:
        files.extend(folder.glob(pat))
    if not files:
        raise FileNotFoundError(f"No rule files found in {folder}. Adjust patterns in discover_rule_files().")
    return files


def main():
    args = parse_args()
    report_path = Path(args.report)
    if not report_path.exists():
        raise FileNotFoundError(f"Report not found: {report_path}")

    if args.rule_file:
        rule_files = [Path(p) for p in args.rule_file]
    else:
        rule_files = discover_rule_files(Path(args.rules_folder))

    print("Using rule files:")
    for rf in rule_files:
        print("  -", rf)

    print("\n....Data Analysing...")
    print("#################################################################################")
    print("\n...checking the rules..")
    print("#################################################################################")
    print("\n...Optimization in place...")
    print("#################################################################################")
    print("\nLoading training rules...")
    print("#################################################################################")
    train = build_training_index(rule_files)
    print(f"Loaded {len(train)} labeled rules.")

    if HAS_RAPIDFUZZ:
        print("rapidfuzz available: using fuzzy token matching")
    else:
        print("rapidfuzz NOT installed: using simpler token overlap (install rapidfuzz for better matches)")

    classify_report(report_path, train, Path(args.output), fuzzy_threshold=args.threshold)


if __name__ == "__main__":
    main()
