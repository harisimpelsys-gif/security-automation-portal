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

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
LOG_DIR = os.path.join(BASE_DIR, "logs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = "dev-secret-key"


# ---------------------------------------------------
# Helpers
# ---------------------------------------------------

def get_log_path(which):
    if which == "error":
        return os.path.join(LOG_DIR, "error.log")
    if which == "processed":
        return os.path.join(LOG_DIR, "processed.log")
    return None


def log_meta(path):
    if not path or not os.path.exists(path):
        return {"exists": False, "size": 0, "mtime": None}

    stat = os.stat(path)
    return {
        "exists": True,
        "size": stat.st_size,
        "mtime": stat.st_mtime,
    }


# ---------------------------------------------------
# Main pages
# ---------------------------------------------------

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


# ---------------------------------------------------
# Upload
# ---------------------------------------------------

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("report_file")
    if not file:
        flash("No file uploaded", "danger")
        return redirect(url_for("index"))

    path = os.path.join(UPLOAD_DIR, file.filename)
    file.save(path)
    flash("Report uploaded successfully", "success")
    return redirect(url_for("index"))


# ---------------------------------------------------
# Logs pages (FIXED)
# ---------------------------------------------------

@app.route("/logs")
def logs_index():
    return render_template(
        "logs.html",
        view=None,
        content=None,
        error_meta=log_meta(get_log_path("error")),
        processed_meta=log_meta(get_log_path("processed")),
    )


@app.route("/logs/error")
def logs_error():
    path = get_log_path("error")
    content = ""

    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()[-20000:]

    return render_template(
        "logs.html",
        view="error",
        content=content,
        error_meta=log_meta(path),
        processed_meta=log_meta(get_log_path("processed")),
    )


@app.route("/logs/processed")
def logs_processed():
    path = get_log_path("processed")
    content = ""

    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()[-20000:]

    return render_template(
        "logs.html",
        view="processed",
        content=content,
        error_meta=log_meta(get_log_path("error")),
        processed_meta=log_meta(path),
    )


@app.route("/logs/download/<which>")
def logs_download(which):
    path = get_log_path(which)
    if not path or not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True)


# ---------------------------------------------------
# App entry
# ---------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
