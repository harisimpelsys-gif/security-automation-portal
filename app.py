#!/usr/bin/env python3
import os
import subprocess
from datetime import datetime
from flask import (
    Flask, render_template, request,
    redirect, url_for, flash,
    send_file, abort
)

# -----------------------------
# App setup
# -----------------------------
app = Flask(__name__)
app.secret_key = "dev-secret-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
LOG_DIR = os.path.join(BASE_DIR, "logs")

VULN_DIR = os.path.join(BASE_DIR, "Vul_Automation")
MISCONF_DIR = os.path.join(BASE_DIR, "MisConfig_Automation")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

ERROR_LOG = os.path.join(LOG_DIR, "error.log")
PROC_LOG = os.path.join(LOG_DIR, "processed.log")

# -----------------------------
# Logging helpers
# -----------------------------
def log_info(msg):
    with open(PROC_LOG, "a") as f:
        f.write(f"[{datetime.now()}] INFO: {msg}\n")

def log_error(msg):
    with open(ERROR_LOG, "a") as f:
        f.write(f"[{datetime.now()}] ERROR: {msg}\n")

def latest_upload():
    files = [
        os.path.join(UPLOAD_DIR, f)
        for f in os.listdir(UPLOAD_DIR)
        if os.path.isfile(os.path.join(UPLOAD_DIR, f))
    ]
    return max(files, key=os.path.getmtime) if files else None

# -----------------------------
# Main page
# -----------------------------
@app.route("/")
def index():
    return render_template(
        "index.html",
        report_path=latest_upload(),
        last_output=None
    )

# -----------------------------
# Upload
# -----------------------------
@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("report_file")
    if not f:
        flash("No file uploaded", "danger")
        return redirect(url_for("index"))

    path = os.path.join(UPLOAD_DIR, f.filename)
    f.save(path)

    log_info(f"Uploaded file: {path}")
    flash(f"Uploaded {f.filename}", "success")
    return redirect(url_for("index"))

# -----------------------------
# Vulnerability – DevOps
# -----------------------------
@app.route("/run/vuln/devops", methods=["POST"])
def run_vuln_devops():
    report = latest_upload()
    if not report:
        flash("Upload a report first", "danger")
        return redirect(url_for("index"))

    script = os.path.join(VULN_DIR, "split_vulns.py")

    try:
        log_info("Starting Vulnerability DevOps segregation")
        subprocess.run(
            ["python", script, report],
            check=True,
            capture_output=True,
            text=True
        )
        log_info("Vulnerability DevOps completed successfully")
        flash("Vulnerability DevOps run completed", "success")
    except subprocess.CalledProcessError as e:
        log_error(e.stderr)
        flash("Vulnerability DevOps failed", "danger")

    return redirect(url_for("index"))

# -----------------------------
# Vulnerability – Master
# -----------------------------
@app.route("/run/vuln/master", methods=["POST"])
def run_vuln_master():
    report = latest_upload()
    if not report:
        flash("Upload a report first", "danger")
        return redirect(url_for("index"))

    script = os.path.join(VULN_DIR, "automate_master_report.py")

    try:
        log_info("Starting Vulnerability Master Report")
        subprocess.run(
            ["python", script, report],
            check=True,
            capture_output=True,
            text=True
        )
        log_info("Vulnerability Master Report completed")
        flash("Vulnerability master report generated", "success")
    except subprocess.CalledProcessError as e:
        log_error(e.stderr)
        flash("Vulnerability master failed", "danger")

    return redirect(url_for("index"))

# -----------------------------
# Misconfiguration – DevOps
# -----------------------------
@app.route("/run/misconfig/devops", methods=["POST"])
def run_misconfig_devops():
    report = latest_upload()
    if not report:
        flash("Upload a report first", "danger")
        return redirect(url_for("index"))

    script = os.path.join(MISCONF_DIR, "devops_split.py")

    try:
        log_info("Starting Misconfiguration DevOps")
        subprocess.run(
            ["python", script, report],
            check=True,
            capture_output=True,
            text=True
        )
        log_info("Misconfiguration DevOps completed")
        flash("Misconfiguration DevOps completed", "success")
    except subprocess.CalledProcessError as e:
        log_error(e.stderr)
        flash("Misconfiguration DevOps failed", "danger")

    return redirect(url_for("index"))

# -----------------------------
# Logs
# -----------------------------
@app.route("/logs")
def logs_index():
    def meta(path):
        if not os.path.exists(path):
            return {"exists": False}
        st = os.stat(path)
        return {
            "exists": True,
            "size": st.st_size,
            "mtime": datetime.fromtimestamp(st.st_mtime)
        }

    return render_template(
        "logs.html",
        error_meta=meta(ERROR_LOG),
        processed_meta=meta(PROC_LOG)
    )

@app.route("/logs/<which>")
def logs_view(which):
    path = ERROR_LOG if which == "error" else PROC_LOG
    if not os.path.exists(path):
        abort(404)
    with open(path, "r", errors="ignore") as f:
        return f"<pre>{f.read()}</pre>"

@app.route("/logs/download/<which>")
def logs_download(which):
    path = ERROR_LOG if which == "error" else PROC_LOG
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True)

# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
