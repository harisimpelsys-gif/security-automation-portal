#!/usr/bin/env python3
"""
split_vulns.py

Reads an Excel workbook, takes the "Vulnerabilities" sheet and splits rows
by "Application Name" into separate sheets in one workbook (or separate files).

Features:
- CLI args for input/output paths
- Option to create one workbook with sheets or separate files per app
- Sanitizes sheet names (<=31 chars, no invalid chars)
- Applies header bolding and autofit-like column widths
- Adds color-coding for Age In Days buckets (best-effort matching)
"""

import argparse
import pathlib
import re
import sys

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

# -------- config: colors for aging buckets (hex) --------
AGE_COLOR_MAP = {
    "0-30": "C6EFCE",   # greenish
    "31-60": "FFEB9C",  # yellow
    "61-90": "F4B084",  # orange
    "90+": "FFC7CE",    # red/pink
}
# fallback mapping when values vary, using substring detection
AGE_KEYWORDS = {
    "0": "C6EFCE",
    "30": "C6EFCE",
    "31": "FFEB9C",
    "60": "FFEB9C",
    "61": "F4B084",
    "90": "FFC7CE",
}

INVALID_SHEET_CHARS = r'[:\\/?*\[\]]'

# -------- helpers --------
def sanitize_sheet_name(name: str) -> str:
    if not isinstance(name, str):
        name = str(name)
    name = re.sub(INVALID_SHEET_CHARS, "_", name).strip()
    if len(name) == 0:
        name = "Sheet"
    return name[:31]

def pick_age_color(cell_val: str):
    if pd.isna(cell_val):
        return None
    s = str(cell_val).strip()
    # exact match
    if s in AGE_COLOR_MAP:
        return AGE_COLOR_MAP[s]
    # common patterns: "0-30", "0 - 30", "0to30"
    for k, v in AGE_COLOR_MAP.items():
        if k.replace("-", "") in s.replace(" ", "").replace("-", ""):
            return v
    # substring keywords
    for kw, color in AGE_KEYWORDS.items():
        if kw in s:
            return color
    return None

def style_workbook(path: pathlib.Path, age_col_name="Age In Days"):
    wb = load_workbook(path)
    for ws in wb.worksheets:
        # header bold
        header_row = 1
        max_col = ws.max_column
        for c in range(1, max_col+1):
            cell = ws.cell(row=header_row, column=c)
            cell.font = Font(bold=True)
        # apply color-coding to age column (if exists)
        age_col_idx = None
        for c in range(1, max_col+1):
            if str(ws.cell(row=1, column=c).value).strip().lower() == age_col_name.strip().lower():
                age_col_idx = c
                break
        if age_col_idx:
            max_row = ws.max_row
            for r in range(2, max_row+1):
                val = ws.cell(row=r, column=age_col_idx).value
                color = pick_age_color(val)
                if color:
                    ws.cell(row=r, column=age_col_idx).fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
        # autofit-ish: set column width to max length in column (capped)
        for c in range(1, max_col+1):
            max_len = 0
            for r in range(1, ws.max_row+1):
                v = ws.cell(row=r, column=c).value
                if v is None:
                    continue
                max_len = max(max_len, len(str(v)))
            adjusted = min(max(8, max_len + 2), 50)
            ws.column_dimensions[get_column_letter(c)].width = adjusted
    wb.save(path)

# -------- main functionality --------
def split_to_workbook(input_path, output_path, sheet_name="Vulnerabilities", app_col="Application Name"):
    df = pd.read_excel(input_path, sheet_name=sheet_name, dtype=str)
    if app_col not in df.columns:
        raise KeyError(f"Column '{app_col}' not found in sheet '{sheet_name}'. Columns: {list(df.columns)}")

    apps = df[app_col].fillna("Undefined").unique()
    # use pandas ExcelWriter with openpyxl engine
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for app in sorted(apps):
            sub = df[df[app_col].fillna("Undefined") == app].copy()
            sheet_name_s = sanitize_sheet_name(app)
            sub.to_excel(writer, sheet_name=sheet_name_s, index=False)
    # style workbook
    style_workbook(pathlib.Path(output_path))
    return output_path

def split_to_files(input_path, out_dir, sheet_name="Vulnerabilities", app_col="Application Name"):
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_excel(input_path, sheet_name=sheet_name, dtype=str)
    if app_col not in df.columns:
        raise KeyError(f"Column '{app_col}' not found in sheet '{sheet_name}'. Columns: {list(df.columns)}")
    apps = df[app_col].fillna("Undefined").unique()
    out_files = []
    for app in sorted(apps):
        sub = df[df[app_col].fillna("Undefined") == app].copy()
        filename = sanitize_sheet_name(app) or "app"
        out_path = out_dir / f"{filename}.xlsx"
        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            sub.to_excel(writer, sheet_name="Vulnerabilities", index=False)
        style_workbook(out_path)
        out_files.append(str(out_path))
    return out_files

# -------- CLI --------
def main(argv=None):
    p = argparse.ArgumentParser(description="Split Vulnerabilities sheet by Application Name")
    p.add_argument("input", help="Input Excel file path")
    p.add_argument("--output", "-o", help="Output file (single workbook). Default: vulnerabilities_by_application.xlsx", default="vulnerabilities_by_application.xlsx")
    p.add_argument("--separate", action="store_true", help="Write separate xlsx files per application into --out-dir")
    p.add_argument("--out-dir", default="vuln_apps", help="Directory for separate files (used with --separate)")
    p.add_argument("--sheet", default="Vulnerabilities", help="Name of the vulnerabilities sheet (default: Vulnerabilities)")
    p.add_argument("--app-col", default="Application Name", help="Column name that contains application name (default: 'Application Name')")
    args = p.parse_args(argv)

    input_path = pathlib.Path(args.input)
    if not input_path.exists():
        print("Input file not found:", input_path, file=sys.stderr)
        sys.exit(2)

    if args.separate:
        files = split_to_files(input_path, args.out_dir, sheet_name=args.sheet, app_col=args.app_col)
        print(f"Wrote {len(files)} files to '{args.out_dir}'")
    else:
        out_path = pathlib.Path(args.output)
        split_to_workbook(input_path, out_path, sheet_name=args.sheet, app_col=args.app_col)
        print(f"Wrote workbook: {out_path}")

if __name__ == "__main__":
    main()
