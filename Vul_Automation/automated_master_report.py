# Automated master report generator
# This code will be saved as a script and also executed here to produce an example output
# It reads an Excel workbook (either a single sheet "Vulnerabilities" or multiple app-named sheets),
# computes per-application metrics, orders rows according to a provided desired order (with fuzzy matching),
# and writes the final ordered master report to an output Excel file.
# Save this script as `automate_master_report.py` and run it with Python.
# Dependencies: pandas, openpyxl
# Example usage (from command line):
# python automate_master_report.py --input Vul_By_app.xlsx --output Master_Report_Automated.xlsx

import argparse
from pathlib import Path
import pandas as pd
from difflib import get_close_matches
import sys

DESIRED_ORDER = [
 "AWS.AthenaDev",
 "AWS.AtlasDev",
 "AWS CarePlans Dev",
 "AWS.CECMEDev",
 "AWS.DataHubDev",
 "AWS eLearning Dev",
 "AWS Heart Security Operations",
 "AWS.OdinDev",
 "AWS Heart Bangalore Shared",
 "AWS.ShopCPRDev",
 "AWS FLP CNTRL Dev",
 "AWS FLP INST Dev",
 "AWS PMPConsumerDev",
 "AWS WHO Dev",
 "AWS PMPConsumerTest",
 "AWS.CarePlansProd",
 "AWS Athena Prod",
 "AWS.CECMEProd",
 "AWS.DataHubProd",
 "AWS eLearning Prod",
 "AWS.OdinProd",
 "AWS ShopCPR Atlas Prod",
 "AWS FLP CNTRL Prod",
 "AWS PMP 2.0",
 "AWS GoldenAMI Prod",
 "AWS FLP JHU Prod",
 "AWS WHO Prod",
 "AWS Atlas Prod"
]

def read_input_workbook(path: Path) -> pd.DataFrame:
    """Read an Excel workbook. If it contains a sheet named 'Vulnerabilities', use that.
       Otherwise, read all sheets and add Application Name from sheet names when missing."""
    xls = pd.ExcelFile(path)
    if "Vulnerabilities" in xls.sheet_names:
        df = pd.read_excel(path, sheet_name="Vulnerabilities", dtype=str).fillna("")
        if "Application Name" not in df.columns:
            raise ValueError("Vulnerabilities sheet found but 'Application Name' column missing.")
        return df
    # else combine all sheets
    frames = []
    for sheet in xls.sheet_names:
        df_sheet = pd.read_excel(path, sheet_name=sheet, dtype=str).fillna("")
        if "Application Name" not in df_sheet.columns:
            df_sheet["Application Name"] = sheet
        frames.append(df_sheet)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    return df

def normalize_severity(s):
    s = str(s).strip()
    if not s:
        return ""
    return s

def detect_actively_exploited_by_sev(s):
    if not s:
        return False
    s = str(s).lower()
    return "actively exploited" in s or "critical - actively exploited" in s or "act" in s and "exploit" in s

def detect_actively_exploited_by_text(row, columns):
    text = " ".join([str(row.get(c,"")).lower() for c in columns])
    return (("actively" in text and "exploit" in text) or
            ("critical - actively exploited" in text) or
            ("actively exploited" in text) or
            ("exploited" in text and "critical" in text))

def compute_summary(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    # Ensure some common columns exist
    for c in ["Resource Id", "IP", "Severity"]:
        if c not in df.columns:
            df[c] = ""
    # Keep original column list for text scanning
    all_cols = df.columns.tolist()
    apps = sorted(df["Application Name"].fillna("Undefined").unique())
    rows = []
    for app in apps:
        sub = df[df["Application Name"]==app]
        total_active_instances = sub["Resource Id"].nunique(dropna=True)
        unique_ip_count = sub["IP"].nunique(dropna=True)
        total_active_vulns = len(sub)
        terminated_entry = ""
        # counts by severity values, case-insensitive
        sev_lower = sub["Severity"].astype(str).str.strip().str.lower()
        critical_total = int((sev_lower == "critical").sum())
        high_total = int((sev_lower == "high").sum())
        medium_total = int((sev_lower == "medium").sum())
        low_total = int((sev_lower == "low").sum())
        # critical actively exploited counted from rows whose severity explicitly indicates AE
        crit_ae_by_sev = int(sub["Severity"].apply(detect_actively_exploited_by_sev).sum())
        # plus rows where Severity == Critical and other columns mention actively/exploit
        crit_ae_by_text = 0
        for _, r in sub.iterrows():
            if str(r.get("Severity","")).strip().lower() == "critical" and detect_actively_exploited_by_text(r, all_cols):
                crit_ae_by_text += 1
        crit_actively = crit_ae_by_sev + crit_ae_by_text
        total_vuln_severity = high_total + critical_total + crit_actively + low_total + medium_total
        rows.append({
            "Application Name": app,
            "Total number of Active Instances": total_active_instances,
            "Total number of Active Vulnerabilities": total_active_vulns,
            "Terminated entry": terminated_entry,
            "Total number of Critical - Actively Exploited": crit_actively,
            "Total number of Critical": critical_total,
            "Total number of High": high_total,
            "Total number of Medium": medium_total,
            "Total number of Low": low_total,
            "Total Vulnerability Severity (High+Critical+Critical-AE+Low+Medium)": total_vuln_severity,
            "Total number of Unique IPs": unique_ip_count
        })
    return pd.DataFrame(rows)

def fuzzy_order_dataframe(summary_df: pd.DataFrame, desired_order: list, cutoff=0.6) -> pd.DataFrame:
    actual_names = summary_df["Application Name"].tolist()
    used = set()
    ordered_rows = []
    for desired in desired_order:
        match = get_close_matches(desired, actual_names, n=1, cutoff=cutoff)
        if match:
            matched = match[0]
            used.add(matched)
            ordered_rows.append(summary_df[summary_df["Application Name"]==matched].iloc[0])
        else:
            # insert empty placeholder row to preserve order
            empty = {col: "" for col in summary_df.columns}
            empty["Application Name"] = desired
            ordered_rows.append(pd.Series(empty))
    # append any remaining actual names not mapped
    remaining = [a for a in actual_names if a not in used]
    for a in sorted(remaining):
        ordered_rows.append(summary_df[summary_df["Application Name"]==a].iloc[0])
    final = pd.DataFrame(ordered_rows)[summary_df.columns]
    return final

def style_and_save(df: pd.DataFrame, out_path: Path):
    # minimal styling using openpyxl through pandas ExcelWriter
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Master Report")
        workbook = writer.book
        ws = writer.sheets["Master Report"]
        # bold header and adjust column widths
        from openpyxl.styles import Font
        header_font = Font(bold=True)
        for cell in list(ws.rows)[0]:
            cell.font = header_font
        # simple autofit
        for col in ws.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col:
                try:
                    val = str(cell.value) if cell.value is not None else ""
                except:
                    val = ""
                if len(val) > max_len:
                    max_len = len(val)
            ws.column_dimensions[col_letter].width = min(max(8, max_len+2), 60)

def main(argv=None):
    p = argparse.ArgumentParser(description="Automate Master Report generation")
    p.add_argument("--input", "-i", required=True, help="Input Excel file path (single workbook)")
    p.add_argument("--output", "-o", default="Master_Report_Automated.xlsx", help="Output excel path")
    p.add_argument("--cutoff", type=float, default=0.6, help="Fuzzy match cutoff (0-1)")
    args = p.parse_args(argv)
    input_path = Path(args.input)
    if not input_path.exists():
        print("Input file not found:", input_path, file=sys.stderr)
        sys.exit(2)
    df_raw = read_input_workbook(input_path)
    summary = compute_summary(df_raw)
    ordered = fuzzy_order_dataframe(summary, DESIRED_ORDER, cutoff=args.cutoff)
    out_path = Path(args.output)
    style_and_save(ordered, out_path)
    print("Wrote:", out_path)
    # show preview
    print("\nPreview (first 20 rows):\n")
    with pd.option_context('display.max_rows', 20, 'display.max_columns', None, 'display.width', 200):
        print(ordered.head(20).to_string(index=False))

if __name__ == "__main__":
    # If running inside this notebook environment, run with the example file if present
    example_input = Path("/mnt/data/Vul_By_app.xlsx")
    example_output = Path("/mnt/data/Master_Report_Automated.xlsx")
    if example_input.exists():
        sys.argv = ["automate_master_report.py", "--input", str(example_input), "--output", str(example_output)]
    main()
