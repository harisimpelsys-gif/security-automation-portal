#!/usr/bin/env python3
import os
import subprocess
import datetime
from pathlib import Path
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file,
    abort,
    session
)

# -------------------------------------------------
# App setup
# -------------------------------------------------
app = Flask(__name__)
app.secret_key = "dev-secret-key"

BASE_DIR = Path(__file__).resolve().parent

UPLOAD_DIR = BASE_DIR / "uploads"
LOG_DIR = BASE_DIR / "logs"
OUT_DIR = BASE_DIR / "outputs"

VULN_DIR = OUT_DIR / "vuln"
MIS_DIR = OUT_DIR / "misconfig"

UPLOAD_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
VULN_DIR.mkdir(parents=True, exist_ok=True)
MIS_DIR.mkdir(parents=True, exist_ok=True)

PROCESSED_LOG = LOG_DIR / "processed.log"
ERROR_LOG = LOG_DIR / "error.log"

# -------------------------------------------------
# Logging helpers
# -------------------------------------------------
def log_processed(msg):
    with open(PROCESSED_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now()}] {msg}\n")

def log_error(msg):
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now()}] {msg}\n")

# -------------------------------------------------
# Main Page
# -------------------------------------------------
@app.route("/")
def index():
    return render_template(
        "index.html",
        last_output=None
    )

# -------------------------------------------------
# Upload
# -------------------------------------------------
@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("report_file")
    if not f:
        flash("No file uploaded", "danger")
        return redirect(url_for("index"))

    path = UPLOAD_DIR / f.filename
    f.save(path)

    session["uploaded_report"] = str(path)

    log_processed(f"Uploaded file: {path}")
    flash(f"Uploaded {f.filename}", "success")
    return redirect(url_for("index"))

# =================================================
# VULNERABILITY PIPELINE
# =================================================
@app.route("/run/vuln/devops", methods=["POST"])
def run_vuln_devops():
    report = session.get("uploaded_report")
    if not report or not Path(report).exists():
        flash("Upload a file first", "danger")
        return redirect(url_for("index"))

    output = VULN_DIR / "Vuln_DevOps_Output.xlsx"

    cmd = [
        "python",
        str(BASE_DIR / "Vul_Automation" / "split_vulns.py"),
        "--input", report,
        "--output", str(output)
    ]

    log_processed(f"Running Vuln DevOps: {' '.join(cmd)}")

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        log_processed(res.stdout)
        flash("Vulnerability DevOps completed", "success")
    except subprocess.CalledProcessError as e:
        log_error(e.stderr)
        flash("Vulnerability DevOps failed", "danger")

    return redirect(url_for("index"))

@app.route("/run/vuln/master", methods=["POST"])
def run_vuln_master():
    devops_out = VULN_DIR / "Vuln_DevOps_Output.xlsx"
    if not devops_out.exists():
        flash("Run DevOps first", "warning")
        return redirect(url_for("index"))

    master_out = VULN_DIR / "Vuln_Master_Report.xlsx"

    cmd = [
        "python",
        str(BASE_DIR / "Vul_Automation" / "automated_master_report.py"),
        "--input", str(devops_out),
        "--output", str(master_out)
    ]

    log_processed(f"Running Vuln Master: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        flash("Vulnerability Master generated", "success")
    except subprocess.CalledProcessError as e:
        log_error(e.stderr)
        flash("Vulnerability Master failed", "danger")

    return redirect(url_for("index"))

# =================================================
# MISCONFIGURATION PIPELINE
# =================================================
@app.route("/run/misconfig/devops", methods=["POST"])
def run_misconfig_devops():
    report = session.get("uploaded_report")
    if not report or not Path(report).exists():
        flash("Upload a file first", "danger")
        return redirect(url_for("index"))

    stage1 = MIS_DIR / "misconfig_stage1.xlsx"

    cmd = [
        "python",
        str(BASE_DIR / "MisConfig_Automation" / "segregate_misconfigs.py"),
        report,
        str(stage1)
    ]

    log_processed(f"Running Misconfig DevOps: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        flash("Misconfig DevOps completed", "success")
    except subprocess.CalledProcessError as e:
        log_error(e.stderr)
        flash("Misconfig DevOps failed", "danger")

    return redirect(url_for("index"))

@app.route("/run/misconfig/aha", methods=["POST"])
def run_misconfig_aha():
    stage1 = MIS_DIR / "misconfig_stage1.xlsx"
    stage2 = MIS_DIR / "misconfig_stage2.xlsx"

    cmd = [
        "python",
        str(BASE_DIR / "MisConfig_Automation" / "Misconfigp2.py"),
        str(stage1),
        str(stage2)
    ]

    log_processed(f"Running Misconfig Split: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        flash("Misconfig split completed", "success")
    except subprocess.CalledProcessError as e:
        log_error(e.stderr)
        flash("Misconfig split failed", "danger")

    return redirect(url_for("index"))

@app.route("/run/misconfig/final", methods=["POST"])
def run_misconfig_final():
    stage2 = MIS_DIR / "misconfig_stage2.xlsx"
    stage3 = MIS_DIR / "misconfig_rules.xlsx"

    cmd = [
        "python",
        str(BASE_DIR / "MisConfig_Automation" / "classify_misconfigs.py"),
        str(stage2),
        str(stage3)
    ]

    log_processed(f"Running Misconfig Rules: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        flash("Misconfig rules applied", "success")
    except subprocess.CalledProcessError as e:
        log_error(e.stderr)
        flash("Misconfig rules failed", "danger")

    return redirect(url_for("index"))

@app.route("/run/misconfig/master", methods=["POST"])
def run_misconfig_master():
    stage3 = MIS_DIR / "misconfig_rules.xlsx"
    master = MIS_DIR / "Misconfig_Master_Report.xlsx"

    cmd = [
        "python",
        str(BASE_DIR / "MisConfig_Automation" / "automate_master_report.py"),
        str(stage3),
        str(master)
    ]

    log_processed(f"Running Misconfig Master: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        flash("Misconfig Master generated", "success")
    except subprocess.CalledProcessError as e:
        log_error(e.stderr)
        flash("Misconfig Master failed", "danger")

    return redirect(url_for("index"))

# =================================================
# LOGS
# =================================================
def get_log_path(which):
    if which == "error":
        return ERROR_LOG
    if which == "processed":
        return PROCESSED_LOG
    return None

@app.route("/logs")
def logs_index():
    return render_template("logs.html")

@app.route("/logs/<which>")
def logs_view(which):
    path = get_log_path(which)
    if not path or not path.exists():
        abort(404)
    return f"<pre>{path.read_text(errors='ignore')}</pre>"

@app.route("/logs/download/<which>")
def logs_download(which):
    path = get_log_path(which)
    if not path or not path.exists():
        abort(404)
    return send_file(path, as_attachment=True)

# -------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
