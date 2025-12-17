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

app = Flask(__name__)
app.secret_key = "dev-secret-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
LOG_DIR = os.path.join(BASE_DIR, "logs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# -----------------------------
# Helpers
# -----------------------------
def get_log_path(which):
    if which == "error":
        return os.path.join(LOG_DIR, "error.log")
    if which == "processed":
        return os.path.join(LOG_DIR, "processed.log")
    return None

# -----------------------------
# Main Pages
# -----------------------------
@app.route("/")
def index():
    return render_template(
        "index.html",
        report_path=None,
        vuln_master_exists=False,
        mis_master_exists=False,
        vuln_chart_data=None,
        mis_chart_data=None,
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
# Vulnerability (placeholders)
# -----------------------------
@app.route("/run/vuln/devops", methods=["POST"])
def run_vuln_devops():
    flash("Vulnerability DevOps run started", "success")
    return redirect(url_for("index"))

@app.route("/run/vuln/master", methods=["POST"])
def run_vuln_master():
    flash("Vulnerability master report generated", "success")
    return redirect(url_for("index"))

# -----------------------------
# Misconfiguration (placeholders)
# -----------------------------
@app.route("/run/misconfig/devops", methods=["POST"])
def run_misconfig_devops():
    flash("Misconfig DevOps run started", "success")
    return redirect(url_for("index"))

@app.route("/run/misconfig/aha", methods=["POST"])
def run_misconfig_aha():
    flash("Misconfig AHA/PMP/AZURE/PP split done", "success")
    return redirect(url_for("index"))

@app.route("/run/misconfig/final", methods=["POST"])
def run_misconfig_final():
    flash("Misconfig rules applied", "success")
    return redirect(url_for("index"))

@app.route("/run/misconfig/master", methods=["POST"])
def run_misconfig_master():
    flash("Misconfig master report generated", "success")
    return redirect(url_for("index"))

# -----------------------------
# Logs Pages
# -----------------------------
@app.route("/logs")
def logs_index():
    error_meta = None
    processed_meta = None

    err = get_log_path("error")
    proc = get_log_path("processed")

    if err and os.path.exists(err):
        stat = os.stat(err)
        error_meta = {
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        }

    if proc and os.path.exists(proc):
        stat = os.stat(proc)
        processed_meta = {
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        }

    return render_template(
        "logs.html",
        error_meta=error_meta,
        processed_meta=processed_meta
    )

@app.route("/logs/<which>")
def logs_view(which):
    path = get_log_path(which)
    if not path or not os.path.exists(path):
        abort(404)
    with open(path, "r", errors="ignore") as f:
        content = f.read()
    return f"<pre>{content}</pre>"

@app.route("/logs/download/<which>")
def logs_download(which):
    path = get_log_path(which)
    if not path or not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True)

# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
