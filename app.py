#!/usr/bin/env python3

import os
import subprocess
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file,
    abort
)

# -----------------------------------------------------------------------------
# App setup
# -----------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = "dev-secret-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
LOG_DIR = os.path.join(BASE_DIR, "logs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

ERROR_LOG = os.path.join(LOG_DIR, "error.log")
PROCESSED_LOG = os.path.join(LOG_DIR, "processed.log")

CURRENT_REPORT = None


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def get_log_path(which):
    if which == "error":
        return ERROR_LOG
    if which == "processed":
        return PROCESSED_LOG
    return None


def log_meta(path):
    if not path or not os.path.exists(path):
        return {"exists": False}
    stat = os.stat(path)
    return {
        "exists": True,
        "size": stat.st_size,
        "mtime": stat.st_mtime,
    }


# -----------------------------------------------------------------------------
# Main page
# -----------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template(
        "index.html",
        report_path=CURRENT_REPORT,
        vuln_master_exists=False,
        mis_master_exists=False,
        vuln_chart_data=None,
        mis_chart_data=None,
        last_output=None,
    )


# -----------------------------------------------------------------------------
# Upload
# -----------------------------------------------------------------------------

@app.route("/upload", methods=["POST"])
def upload():
    global CURRENT_REPORT

    file = request.files.get("report_file")
    if not file:
        flash("No file uploaded", "danger")
        return redirect(url_for("index"))

    save_path = os.path.join(UPLOAD_DIR, file.filename)
    file.save(save_path)
    CURRENT_REPORT = save_path

    flash(f"Uploaded: {file.filename}", "success")
    return redirect(url_for("index"))


# -----------------------------------------------------------------------------
# Vulnerability routes (DUMMY but REQUIRED)
# -----------------------------------------------------------------------------

@app.route("/run/vuln/devops", methods=["POST"])
def run_vuln_devops():
    flash("Vulnerability DevOps segregation executed (dev stub).", "success")
    return redirect(url_for("index"))


@app.route("/run/vuln/master", methods=["POST"])
def run_vuln_master():
    flash("Master Vulnerability report generated (dev stub).", "success")
    return redirect(url_for("index"))


# -----------------------------------------------------------------------------
# Misconfiguration routes (DUMMY but REQUIRED)
# -----------------------------------------------------------------------------

@app.route("/run/misconfig/devops", methods=["POST"])
def run_misconfig_devops():
    flash("Misconfig DevOps segregation executed (dev stub).", "success")
    return redirect(url_for("index"))


@app.route("/run/misconfig/aha", methods=["POST"])
def run_misconfig_aha():
    flash("AHA/PMP/AZURE/PP split executed (dev stub).", "success")
    return redirect(url_for("index"))


@app.route("/run/misconfig/final", methods=["POST"])
def run_misconfig_final():
    flash("Rules engine applied (dev stub).", "success")
    return redirect(url_for("index"))


@app.route("/run/misconfig/master", methods=["POST"])
def run_misconfig_master():
    flash("Master misconfiguration report generated (dev stub).", "success")
    return redirect(url_for("index"))


# -----------------------------------------------------------------------------
# Logs
# -----------------------------------------------------------------------------

@app.route("/logs")
def logs_index():
    return render_template(
        "logs.html",
        error_meta=log_meta(ERROR_LOG),
        processed_meta=log_meta(PROCESSED_LOG),
    )


@app.route("/logs/<which>")
def logs_view(which):
    path = get_log_path(which)
    if not path or not os.path.exists(path):
        abort(404)

    with open(path, "r", errors="ignore") as f:
        content = f.read()

    return render_template(
        "logs.html",
        content=content,
        error_meta=log_meta(ERROR_LOG),
        processed_meta=log_meta(PROCESSED_LOG),
    )


@app.route("/logs/download/<which>")
def logs_download(which):
    path = get_log_path(which)
    if not path or not os.path.exists(path):
        abort(404)

    return send_file(path, as_attachment=True)


# -----------------------------------------------------------------------------
# Run locally
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
