#!/usr/bin/env python3
import os
import subprocess
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, send_file, abort
)

app = Flask(__name__)
app.secret_key = "dev-secret-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
LOG_DIR = os.path.join(BASE_DIR, "logs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def get_log_path(which):
    if which == "error":
        return os.path.join(LOG_DIR, "error.log")
    if which == "processed":
        return os.path.join(LOG_DIR, "processed.log")
    return None


def run_script(script_path, label):
    """
    Safe subprocess execution with logging
    """
    try:
        result = subprocess.run(
            ["python3", script_path, UPLOAD_DIR],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=600
        )

        if result.stdout:
            with open(get_log_path("processed"), "a") as p:
                p.write(f"\n=== {label} OUTPUT ===\n{result.stdout}\n")

        if result.stderr:
            with open(get_log_path("error"), "a") as e:
                e.write(f"\n=== {label} ERROR ===\n{result.stderr}\n")

        return result.returncode == 0

    except Exception as ex:
        with open(get_log_path("error"), "a") as e:
            e.write(f"\n=== {label} EXCEPTION ===\n{str(ex)}\n")
        return False


# --------------------------------------------------
# Index
# --------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# --------------------------------------------------
# Upload
# --------------------------------------------------
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


# --------------------------------------------------
# Vulnerability
# --------------------------------------------------
@app.route("/run/vuln/devops", methods=["POST"])
def run_vuln_devops():
    script = os.path.join(BASE_DIR, "Vul_Automation", "split_vulns.py")

    if not os.path.exists(script):
        flash("Vulnerability DevOps script missing", "danger")
    else:
        ok = run_script(script, "VULN DEVOPS")
        flash(
            "Vulnerability DevOps completed" if ok else "Vulnerability DevOps failed",
            "success" if ok else "danger"
        )

    return redirect(url_for("index"))


@app.route("/run/vuln/master", methods=["POST"])
def run_vuln_master():
    script = os.path.join(BASE_DIR, "Vul_Automation", "automate_master_report.py")

    if not os.path.exists(script):
        flash("Vulnerability Master script missing", "danger")
    else:
        ok = run_script(script, "VULN MASTER")
        flash(
            "Vulnerability Master completed" if ok else "Vulnerability Master failed",
            "success" if ok else "danger"
        )

    return redirect(url_for("index"))


# --------------------------------------------------
# Misconfiguration
# --------------------------------------------------
@app.route("/run/misconfig/devops", methods=["POST"])
def run_misconfig_devops():
    script = os.path.join(BASE_DIR, "MisConfig_Automation", "classify_misconfigs.py")

    if not os.path.exists(script):
        flash("Misconfig DevOps script missing", "danger")
    else:
        ok = run_script(script, "MISCONFIG DEVOPS")
        flash(
            "Misconfig DevOps completed" if ok else "Misconfig DevOps failed",
            "success" if ok else "danger"
        )

    return redirect(url_for("index"))


@app.route("/run/misconfig/aha", methods=["POST"])
def run_misconfig_aha():
    script = os.path.join(BASE_DIR, "MisConfig_Automation", "Misconfigp2.py")

    if not os.path.exists(script):
        flash("Misconfig AHA script missing", "danger")
    else:
        ok = run_script(script, "MISCONFIG AHA")
        flash(
            "Misconfig AHA completed" if ok else "Misconfig AHA failed",
            "success" if ok else "danger"
        )

    return redirect(url_for("index"))


@app.route("/run/misconfig/master", methods=["POST"])
def run_misconfig_master():
    script = os.path.join(BASE_DIR, "MisConfig_Automation", "automate_master_report.py")

    if not os.path.exists(script):
        flash("Misconfig Master script missing", "danger")
    else:
        ok = run_script(script, "MISCONFIG MASTER")
        flash(
            "Misconfig Master completed" if ok else "Misconfig Master failed",
            "success" if ok else "danger"
        )

    return redirect(url_for("index"))


# --------------------------------------------------
# Logs
# --------------------------------------------------
@app.route("/logs")
def logs_index():
    return render_template("logs.html")


@app.route("/logs/<which>")
def logs_view(which):
    path = get_log_path(which)
    if not path or not os.path.exists(path):
        abort(404)
    with open(path, "r", errors="ignore") as f:
        return f"<pre>{f.read()}</pre>"


@app.route("/logs/download/<which>")
def logs_download(which):
    path = get_log_path(which)
    if not path or not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True)


# --------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
