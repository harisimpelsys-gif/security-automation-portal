#!/usr/bin/env python3
"""
Build Master Misconfiguration Report from Final_report.xlsx

Usage:
    python automate_master_report.py --input "Final_report.xlsx" --output "Master_Report_Automated.xlsx"
"""

import argparse
from pathlib import Path
import pandas as pd


SHEETS_TO_USE = ["AHA", "PMP", "AZURE", "PP"]

OUT_COL_ACCT = "AWS Accounts Dev"
OUT_COL_TOTAL = "Total Misconfigurations[Critical & High]"
OUT_COL_ACT   = "Total Actionable"
OUT_COL_MIT   = "Total Mitigated"
OUT_COL_OOS   = "Total Out of scope[AHA, Exceptions, Duplicates, NACL, False positive etc]"


def build_master_from_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per application for a single sheet."""
    if "Application Name" not in df.columns:
        raise ValueError("Required column 'Application Name' not found in sheet.")
    if "Actionable" not in df.columns:
        raise ValueError("Required column 'Actionable' not found in sheet.")

    # Total misconfigs per application (all rows)
    total_per_app = df.groupby("Application Name").size()

    # Normalize Actionable column text
    actionable_series = (
        df["Actionable"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df_actionable = df[actionable_series == "actionable"]
    actionable_per_app = df_actionable.groupby("Application Name").size()
    actionable_per_app = actionable_per_app.reindex(total_per_app.index, fill_value=0)

    # Out-of-scope = total - actionable
    out_of_scope_per_app = total_per_app - actionable_per_app

    # Build aggregated dataframe
    result = pd.DataFrame({
        OUT_COL_ACCT: total_per_app.index,  # Application Name
        OUT_COL_TOTAL: total_per_app.values,
        OUT_COL_ACT: actionable_per_app.values,
        OUT_COL_MIT: "",  # blank
        OUT_COL_OOS: out_of_scope_per_app.values,
    })

    # Sort by account name (you can tweak if you want custom order)
    result = result.sort_values(OUT_COL_ACCT).reset_index(drop=True)
    return result


def add_total_row(df: pd.DataFrame) -> pd.DataFrame:
    """Append a TOTAL row like in your sample sheet."""
    total_misconfigs = df[OUT_COL_TOTAL].sum()
    total_actionable = df[OUT_COL_ACT].sum()
    total_oos = df[OUT_COL_OOS].sum()

    total_row = {
        OUT_COL_ACCT: "TOTAL",
        OUT_COL_TOTAL: total_misconfigs,
        OUT_COL_ACT: total_actionable,
        OUT_COL_MIT: "",
        OUT_COL_OOS: total_oos,
    }

    df_with_total = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)
    return df_with_total


def build_master_report(input_path: Path) -> pd.DataFrame:
    """Read the input workbook and build the combined master report."""
    all_results = []

    for sheet_name in SHEETS_TO_USE:
        try:
            df = pd.read_excel(input_path, sheet_name=sheet_name)
        except ValueError:
            raise ValueError(f"Sheet '{sheet_name}' not found in {input_path}")

        if df.empty:
            continue

        sheet_result = build_master_from_sheet(df)
        all_results.append(sheet_result)

    if not all_results:
        raise ValueError("No data found in any of the expected sheets.")

    master_df = pd.concat(all_results, ignore_index=True)

    # Ensure column order
    master_df = master_df[
        [OUT_COL_ACCT, OUT_COL_TOTAL, OUT_COL_ACT, OUT_COL_MIT, OUT_COL_OOS]
    ]

    # Numeric columns as int
    for col in [OUT_COL_TOTAL, OUT_COL_ACT, OUT_COL_OOS]:
        master_df[col] = pd.to_numeric(master_df[col], errors="coerce").fillna(0).astype(int)

    # Add TOTAL row at the end
    master_df = add_total_row(master_df)

    return master_df


def main():
    parser = argparse.ArgumentParser(description="Generate Master Misconfiguration Report.")
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Path to Final_report.xlsx (with AHA, PMP, AZURE, PP sheets).",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Path to output Master_Report.xlsx.",
    )

    args = parser.parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    master_df = build_master_report(input_path)

    # Write to Excel
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        master_df.to_excel(writer, sheet_name="Sheet1", index=False)

    print(f"Master report generated at: {output_path}")


if __name__ == "__main__":
    main()
