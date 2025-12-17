#!/usr/bin/env python3
import os
import subprocess
from datetime import datetime
from flask import (
    Flask, render_template, request,
    redirect, url_for, flash,
    send_file, abort
)

app = Flask(__name__)
app.secret_key = "dev-secret-key"

# -----------------------------
# Paths
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
LOG_DIR = os.path.join(BASE_DIR, "logs")

VULN_DIR = os.path.join(BASE_DIR, "Vul_Automation")
MISCONF_DIR = os.path.join(BASE_DIR, "MisConfig_Automation")

ERROR_LOG = os.path.join(LOG_DIR, "error.log")
PROCESSED_LOG = os.path.join(LOG_DIR, "processed.log")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# -----------------------------
# Helpers
# -----------------------------
def latest_upload():
    files = sorted(
        [os.path.join(UPLOAD_DIR, f) for f in os.listdir(UPLOAD_DIR)],
        key=os.path.getmtime,
        reverse=True
    )
    return files[0] if files else None


def log(msg, level="INFO"):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}\n"
    with open(PROCESSED_LOG if level == "INFO" else ERROR_LOG, "a") as f:
        f.write(line)


def run_cmd(cmd, cwd):
    try:
        log(f"Running: {' '.join(cmd)}")
        subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        log(e.stderr or str(e), "ERROR")
        return False

# -----------------------------
# Main Page
# -----------------------------
@app.route("/")
def index():
    return render_template(
        "index.html",
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

    ok = run_cmd(
        ["python3", "split_vulns.py", infile, "--out-dir", OUTPUT_DIR],
        VULN_DIR
    )

    flash(
        "Vulnerability DevOps completed" if ok else "Vulnerability DevOps failed",
        "success" if ok else "danger"
    )
    return redirect(url_for("index"))


@app.route("/run/vuln/master", methods=["POST"])
def run_vuln_master():
    infile = latest_upload()
    ok = run_cmd(
        ["python3", "automated_master_report.py", infile, "--out-dir", OUTPUT_DIR],
        VULN_DIR
    )
    flash(
        "Vulnerability Master generated" if ok else "Vulnerability Master failed",
        "success" if ok else "danger"
    )
    return redirect(url_for("index"))

# -----------------------------
# Misconfiguration
# -----------------------------
@app.route("/run/misconfig/devops", methods=["POST"])
def run_misconfig_devops():
    infile = latest_upload()
    ok = run_cmd(
        ["python3", "segregate_misconfigs.py", infile, "--out-dir", OUTPUT_DIR],
        MISCONF_DIR
    )
    flash(
        "Misconfig DevOps completed" if ok else "Misconfig DevOps failed",
        "success" if ok else "danger"
    )
    return redirect(url_for("index"))


@app.route("/run/misconfig/aha", methods=["POST"])
def run_misconfig_aha():
    ok = run_cmd(
        ["python3", "classify_misconfigs.py", "--out-dir", OUTPUT_DIR],
        MISCONF_DIR
    )
    flash(
        "Misconfig AHA split completed" if ok else "Misconfig AHA failed",
        "success" if ok else "danger"
    )
    return redirect(url_for("index"))


@app.route("/run/misconfig/final", methods=["POST"])
def run_misconfig_final():
    ok = run_cmd(
        ["python3", "Misconfigp2.py", "--out-dir", OUTPUT_DIR],
        MISCONF_DIR
    )
    flash(
        "Misconfig rules applied" if ok else "Misconfig rules failed",
        "success" if ok else "danger"
    )
    return redirect(url_for("index"))


@app.route("/run/misconfig/master", methods=["POST"])
def run_misconfig_master():
    ok = run_cmd(
        ["python3", "automate_master_report.py", "--out-dir", OUTPUT_DIR],
        MISCONF_DIR
    )
    flash(
        "Misconfig master generated" if ok else "Misconfig master failed",
        "success" if ok else "danger"
    )
    return redirect(url_for("index"))

# -----------------------------
# Logs
# -----------------------------
@app.route("/logs")
def logs_index():
    return render_template("logs.html")

@app.route("/logs/<which>")
def logs_view(which):
    path = ERROR_LOG if which == "error" else PROCESSED_LOG
    if not os.path.exists(path):
        abort(404)
    return f"<pre>{open(path).read()}</pre>"

@app.route("/logs/download/<which>")
def logs_download(which):
    path = ERROR_LOG if which == "error" else PROCESSED_LOG
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True)

# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
