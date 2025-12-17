#!/usr/bin/env python3
import os
import subprocess
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, send_file, abort
)

app = Flask(__name__)
app.secret_key = "dev-secret-key"

# -----------------------------
# Paths
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
LOG_DIR = os.path.join(BASE_DIR, "logs")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

VULN_DIR = os.path.join(BASE_DIR, "Vul_Automation")
MISCONF_DIR = os.path.join(BASE_DIR, "MisConfig_Automation")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

ERROR_LOG = os.path.join(LOG_DIR, "error.log")
PROC_LOG = os.path.join(LOG_DIR, "processed.log")

# -----------------------------
# Helpers
# -----------------------------
def log(msg, error=False):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    path = ERROR_LOG if error else PROC_LOG
    with open(path, "a") as f:
        f.write(f"[{ts}] {msg}\n")

def latest_upload():
    files = sorted(
        [os.path.join(UPLOAD_DIR, f) for f in os.listdir(UPLOAD_DIR)],
        key=os.path.getmtime,
        reverse=True
    )
    return files[0] if files else None

def run_script(cmd, cwd):
    """
    SAFE subprocess execution
    - Captures stdout + stderr
    - Logs everything
    - Does NOT block worker forever
    """
    try:
        log(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.stdout:
            log(result.stdout)
        if result.stderr:
            log(result.stderr, error=True)
        return result.returncode == 0
    except Exception as e:
        log(str(e), error=True)
        return False

# -----------------------------
# Pages
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
    log(f"Uploaded file: {path}")
    flash(f"Uploaded {f.filename}", "success")
    return redirect(url_for("index"))

# -----------------------------
# Vulnerability
# -----------------------------
@app.route("/run/vuln/devops", methods=["POST"])
def run_vuln_devops():
    infile = latest_upload()
    if not infile:
        flash("No uploaded file found", "danger")
        return redirect(url_for("index"))

    ok = run_script(
        ["python3", "split_vulns.py", infile, OUTPUT_DIR],
        cwd=VULN_DIR
    )

    flash(
        "Vulnerability DevOps completed" if ok else "Vulnerability DevOps failed",
        "success" if ok else "danger"
    )
    return redirect(url_for("index"))

@app.route("/run/vuln/master", methods=["POST"])
def run_vuln_master():
    ok = run_script(
        ["python3", "automate_master_report.py", OUTPUT_DIR],
        cwd=VULN_DIR
    )
    flash(
        "Vulnerability master generated" if ok else "Vulnerability master failed",
        "success" if ok else "danger"
    )
    return redirect(url_for("index"))

# -----------------------------
# Misconfiguration
# -----------------------------
@app.route("/run/misconfig/devops", methods=["POST"])
def run_misconfig_devops():
    ok = run_script(
        ["python3", "stage1_devops.py"],
        cwd=MISCONF_DIR
    )
    flash("Misconfig DevOps completed" if ok else "Misconfig DevOps failed",
          "success" if ok else "danger")
    return redirect(url_for("index"))

@app.route("/run/misconfig/aha", methods=["POST"])
def run_misconfig_aha():
    ok = run_script(
        ["python3", "stage2_split.py"],
        cwd=MISCONF_DIR
    )
    flash("Misconfig split completed" if ok else "Misconfig split failed",
          "success" if ok else "danger")
    return redirect(url_for("index"))

@app.route("/run/misconfig/final", methods=["POST"])
def run_misconfig_final():
    ok = run_script(
        ["python3", "stage3_rules.py"],
        cwd=MISCONF_DIR
    )
    flash("Misconfig rules applied" if ok else "Misconfig rules failed",
          "success" if ok else "danger")
    return redirect(url_for("index"))

@app.route("/run/misconfig/master", methods=["POST"])
def run_misconfig_master():
    ok = run_script(
        ["python3", "stage4_master.py"],
        cwd=MISCONF_DIR
    )
    flash("Misconfig master generated" if ok else "Misconfig master failed",
          "success" if ok else "danger")
    return redirect(url_for("index"))

# -----------------------------
# Logs
# -----------------------------
@app.route("/logs")
def logs_index():
    return render_template(
        "logs.html",
        error_meta={"exists": os.path.exists(ERROR_LOG),
                    "size": os.path.getsize(ERROR_LOG) if os.path.exists(ERROR_LOG) else 0},
        processed_meta={"exists": os.path.exists(PROC_LOG),
                         "size": os.path.getsize(PROC_LOG) if os.path.exists(PROC_LOG) else 0}
    )

@app.route("/logs/<which>")
def logs_view(which):
    path = ERROR_LOG if which == "error" else PROC_LOG
    if not os.path.exists(path):
        abort(404)
    with open(path) as f:
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
