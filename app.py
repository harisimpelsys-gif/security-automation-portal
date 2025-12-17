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
LOG_DIR = os.path.join(BASE_DIR, "logs")
VUL_DIR = os.path.join(BASE_DIR, "Vul_Automation")
MIS_DIR = os.path.join(BASE_DIR, "MisConfig_Automation")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

ERROR_LOG = os.path.join(LOG_DIR, "error.log")
PROC_LOG = os.path.join(LOG_DIR, "processed.log")

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


def log(msg, error=False):
    path = ERROR_LOG if error else PROC_LOG
    with open(path, "a") as f:
        f.write(f"[{datetime.now()}] {msg}\n")


def run_script(cmd, cwd):
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
        log("Completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        log(e.stderr, error=True)
        return False


# -----------------------------
# Main Page
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
    flash(f"Uploaded {f.filename}", "success")
    log(f"Uploaded file {f.filename}")
    return redirect(url_for("index"))

# -----------------------------
# Vulnerability
# -----------------------------
@app.route("/run/vuln/devops", methods=["POST"])
def run_vuln_devops():
    report = latest_upload()
    if not report:
        flash("Upload a report first", "danger")
        return redirect(url_for("index"))

    ok = run_script(
        ["python3", "split_vulns.py", report],
        cwd=VUL_DIR
    )

    flash(
        "Vulnerability DevOps completed" if ok else "Vulnerability DevOps failed",
        "success" if ok else "danger"
    )
    return redirect(url_for("index"))


@app.route("/run/vuln/master", methods=["POST"])
def run_vuln_master():
    report = latest_upload()
    ok = run_script(
        ["python3", "automated_master_report.py", report],
        cwd=VUL_DIR
    )

    flash(
        "Vulnerability Master report generated" if ok else "Vulnerability Master failed",
        "success" if ok else "danger"
    )
    return redirect(url_for("index"))

# -----------------------------
# Misconfiguration
# -----------------------------
@app.route("/run/misconfig/devops", methods=["POST"])
def run_misconfig_devops():
    report = latest_upload()
    ok = run_script(
        ["python3", "segregate_misconfigs.py", report],
        cwd=MIS_DIR
    )

    flash(
        "Misconfig DevOps completed" if ok else "Misconfig DevOps failed",
        "success" if ok else "danger"
    )
    return redirect(url_for("index"))


@app.route("/run/misconfig/aha", methods=["POST"])
def run_misconfig_aha():
    ok = run_script(
        ["python3", "Misconfigp2.py"],
        cwd=MIS_DIR
    )
    flash(
        "AHA/PMP/AZURE/PP split completed" if ok else "AHA split failed",
        "success" if ok else "danger"
    )
    return redirect(url_for("index"))


@app.route("/run/misconfig/final", methods=["POST"])
def run_misconfig_final():
    ok = run_script(
        ["python3", "classify_misconfigs.py"],
        cwd=MIS_DIR
    )
    flash(
        "Rules applied" if ok else "Rules failed",
        "success" if ok else "danger"
    )
    return redirect(url_for("index"))


@app.route("/run/misconfig/master", methods=["POST"])
def run_misconfig_master():
    ok = run_script(
        ["python3", "automate_master_report.py"],
        cwd=MIS_DIR
    )
    flash(
        "Misconfig Master report generated" if ok else "Master failed",
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


if __name__ == "__main__":
    app.run(debug=True)
