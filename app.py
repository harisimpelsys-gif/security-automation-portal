#!/usr/bin/env python3
import os
import subprocess
from datetime import datetime
from flask import (
    Flask, render_template, request,
    redirect, url_for, flash,
    send_file, abort
)

# -------------------------------------------------
# App setup
# -------------------------------------------------
app = Flask(__name__)
app.secret_key = "dev-secret-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
LOG_DIR = os.path.join(BASE_DIR, "logs")

for d in (UPLOAD_DIR, OUTPUT_DIR, LOG_DIR):
    os.makedirs(d, exist_ok=True)

ERROR_LOG = os.path.join(LOG_DIR, "error.log")
PROCESSED_LOG = os.path.join(LOG_DIR, "processed.log")

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def log(msg, error=False):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    path = ERROR_LOG if error else PROCESSED_LOG
    with open(path, "a") as f:
        f.write(line)

def latest_upload():
    files = [
        os.path.join(UPLOAD_DIR, f)
        for f in os.listdir(UPLOAD_DIR)
        if f.lower().endswith(".xlsx")
    ]
    return max(files, key=os.path.getmtime) if files else None

def run_cmd(cmd):
    log(f"EXEC: {' '.join(cmd)}")
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=900
        )
        log(p.stdout)
        if p.stderr:
            log(p.stderr, error=True)
        return p.returncode == 0
    except Exception as e:
        log(str(e), error=True)
        return False

def get_log_meta(path):
    if not os.path.exists(path):
        return {"exists": False}
    st = os.stat(path)
    return {
        "exists": True,
        "size": st.st_size,
        "mtime": datetime.fromtimestamp(st.st_mtime)
    }

# -------------------------------------------------
# Pages
# -------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html", last_output=None)

# -------------------------------------------------
# Upload
# -------------------------------------------------
@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("report_file")
    if not f:
        flash("No file selected", "danger")
        return redirect(url_for("index"))

    path = os.path.join(UPLOAD_DIR, f.filename)
    f.save(path)
    log(f"Uploaded file: {path}")
    flash(f"Uploaded {f.filename}", "success")
    return redirect(url_for("index"))

# -------------------------------------------------
# Vulnerability
# -------------------------------------------------
@app.route("/run/vuln/devops", methods=["POST"])
def run_vuln_devops():
    infile = latest_upload()
    if not infile:
        flash("No uploaded file found", "danger")
        return redirect(url_for("index"))

    script = os.path.join(BASE_DIR, "Vul_Automation", "split_vulns.py")
    ok = run_cmd([
        "python3", script,
        infile,
        "--out-dir", OUTPUT_DIR
    ])

    flash(
        "Vulnerability DevOps completed" if ok else "Vulnerability DevOps failed",
        "success" if ok else "danger"
    )
    return redirect(url_for("index"))

@app.route("/run/vuln/master", methods=["POST"])
def run_vuln_master():
    script = os.path.join(BASE_DIR, "Vul_Automation", "automated_master_report.py")
    ok = run_cmd(["python3", script, "--out-dir", OUTPUT_DIR])
    flash(
        "Vulnerability master generated" if ok else "Vulnerability master failed",
        "success" if ok else "danger"
    )
    return redirect(url_for("index"))

# -------------------------------------------------
# Misconfiguration
# -------------------------------------------------
@app.route("/run/misconfig/devops", methods=["POST"])
def run_misconfig_devops():
    script = os.path.join(BASE_DIR, "MisConfig_Automation", "stage1_devops.py")
    ok = run_cmd(["python3", script, "--out-dir", OUTPUT_DIR])
    flash("Misconfig DevOps done" if ok else "Misconfig DevOps failed",
          "success" if ok else "danger")
    return redirect(url_for("index"))

@app.route("/run/misconfig/aha", methods=["POST"])
def run_misconfig_aha():
    script = os.path.join(BASE_DIR, "MisConfig_Automation", "stage2_split.py")
    ok = run_cmd(["python3", script, "--out-dir", OUTPUT_DIR])
    flash("Misconfig split done" if ok else "Misconfig split failed",
          "success" if ok else "danger")
    return redirect(url_for("index"))

@app.route("/run/misconfig/final", methods=["POST"])
def run_misconfig_final():
    script = os.path.join(BASE_DIR, "MisConfig_Automation", "stage3_rules.py")
    ok = run_cmd(["python3", script, "--out-dir", OUTPUT_DIR])
    flash("Misconfig rules applied" if ok else "Misconfig rules failed",
          "success" if ok else "danger")
    return redirect(url_for("index"))

@app.route("/run/misconfig/master", methods=["POST"])
def run_misconfig_master():
    script = os.path.join(BASE_DIR, "MisConfig_Automation", "stage4_master.py")
    ok = run_cmd(["python3", script, "--out-dir", OUTPUT_DIR])
    flash("Misconfig master generated" if ok else "Misconfig master failed",
          "success" if ok else "danger")
    return redirect(url_for("index"))

# -------------------------------------------------
# Logs
# -------------------------------------------------
@app.route("/logs")
def logs_index():
    return render_template(
        "logs.html",
        error_meta=get_log_meta(ERROR_LOG),
        processed_meta=get_log_meta(PROCESSED_LOG)
    )

@app.route("/logs/<which>")
def logs_view(which):
    path = ERROR_LOG if which == "error" else PROCESSED_LOG
    if not os.path.exists(path):
        abort(404)
    with open(path) as f:
        return f"<pre>{f.read()}</pre>"

@app.route("/logs/download/<which>")
def logs_download(which):
    path = ERROR_LOG if which == "error" else PROCESSED_LOG
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True)

# -------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
