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
    abort,
)

# --------------------------------------------------
# App setup
# --------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
LOG_DIR = os.path.join(BASE_DIR, "logs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = "dev-secret-key"

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def get_log_path(which):
    if which == "error":
        return os.path.join(LOG_DIR, "error.log")
    if which == "processed":
        return os.path.join(LOG_DIR, "processed.log")
    return None

# --------------------------------------------------
# Main pages
# --------------------------------------------------
@app.route("/")
def index():
    return render_template(
        "index.html",
        report_path=None,
        vuln_master_exists=False,
        mis_master_exists=False,
        vuln_chart_data=None,
        mis_chart_data=None,
        last_output=None,
    )

# --------------------------------------------------
# Upload
# --------------------------------------------------
@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("report_file")
    if not file:
        flash("No file uploaded", "danger")
        return redirect(url_for("index"))

    save_path = os.path.join(UPLOAD_DIR, file.filename)
    file.save(save_path)
    flash(f"Uploaded: {file.filename}", "success")
    return redirect(url_for("index"))

# --------------------------------------------------
# Vulnerability routes (placeholders for now)
# --------------------------------------------------
@app.route("/run/vuln/devops", methods=["POST"])
def run_vuln_devops():
    flash("Vulnerability DevOps segregation completed.", "success")
    return redirect(url_for("index"))

@app.route("/run/vuln/master", methods=["POST"])
def run_vuln_master():
    flash("Master Vulnerability report generated.", "success")
    return redirect(url_for("index"))

# --------------------------------------------------
# Misconfiguration routes (placeholders)
# --------------------------------------------------
@app.route("/run/misconfig/devops", methods=["POST"])
def run_misconfig_devops():
    flash("Misconfiguration DevOps segregation completed.", "success")
    return redirect(url_for("index"))

@app.route("/run/misconfig/aha", methods=["POST"])
def run_misconfig_aha():
    flash("AHA / PMP / AZURE / PP split completed.", "success")
    return redirect(url_for("index"))

@app.route("/run/misconfig/final", methods=["POST"])
def run_misconfig_final():
    flash("Rules applied. Final misconfig report ready.", "success")
    return redirect(url_for("index"))

@app.route("/run/misconfig/master", methods=["POST"])
def run_misconfig_master():
    flash("Master misconfiguration report generated.", "success")
    return redirect(url_for("index"))

# --------------------------------------------------
# Logs views
# --------------------------------------------------
@app.route("/logs")
def logs_index():
    return render_template("logs.html")

@app.route("/logs/<which>")
def logs_view(which):
    path = get_log_path(which)
    if not path or not os.path.exists(path):
        return f"No {which} logs found.", 404

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    return f"<pre>{content}</pre>"

# --------------------------------------------------
# ✅ FIXED: Logs download route (THIS WAS MISSING)
# --------------------------------------------------
@app.route("/logs/download/<which>")
def logs_download(which):
    path = get_log_path(which)
    if not path or not os.path.exists(path):
        abort(404)

    return send_file(path, as_attachment=True)

# --------------------------------------------------
# Entry point
# --------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
