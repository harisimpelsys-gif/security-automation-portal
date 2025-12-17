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

# -------------------------------------------------
# App setup
# -------------------------------------------------
app = Flask(__name__)
app.secret_key = "dev-secret-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
LOG_DIR = os.path.join(BASE_DIR, "logs")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

VULN_DIR = os.path.join(BASE_DIR, "Vul_Automation")
MISCONFIG_DIR = os.path.join(BASE_DIR, "MisConfig_Automation")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def get_log_path(which):
    if which == "error":
        return os.path.join(LOG_DIR, "error.log")
    if which == "processed":
        return os.path.join(LOG_DIR, "processed.log")
    return None


def latest_upload():
    files = [
        os.path.join(UPLOAD_DIR, f)
        for f in os.listdir(UPLOAD_DIR)
        if os.path.isfile(os.path.join(UPLOAD_DIR, f))
    ]
    if not files:
        return None
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def run_script(cmd, cwd):
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=600
        )
        with open(get_log_path("processed"), "a") as f:
            f.write(proc.stdout + "\n")
        return proc.returncode == 0
    except Exception as e:
        with open(get_log_path("error"), "a") as f:
            f.write(str(e) + "\n")
        return False


# -------------------------------------------------
# Main page
# -------------------------------------------------
@app.route("/")
def index():
    return render_template(
        "index.html",
        report_path=latest_upload(),
        last_output=None
    )


# -------------------------------------------------
# Upload
# -------------------------------------------------
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


# -------------------------------------------------
# Vulnerability
# -------------------------------------------------
@app.route("/run/vuln/devops", methods=["POST"])
def run_vuln_devops():
    infile = latest_upload()
    if not infile:
        flash("No uploaded file found", "danger")
        return redirect(url_for("index"))

    ok = run_script(
        ["python3", "split_vulns.py", infile, "--out-dir", OUTPUT_DIR],
        cwd=VULN_DIR
    )

    flash(
        "Vulnerability DevOps completed" if ok else "Vulnerability DevOps failed",
        "success" if ok else "danger"
    )
    return redirect(url_for("index"))


@app.route("/run/vuln/master", methods=["POST"])
def run_vuln_master():
    infile = latest_upload()
    if not infile:
        flash("No uploaded file found", "danger")
        return redirect(url_for("index"))

    ok = run_script(
        ["python3", "automate_master_report.py", infile, OUTPUT_DIR],
        cwd=VULN_DIR
    )

    flash(
        "Vulnerability Master completed" if ok else "Vulnerability Master failed",
        "success" if ok else "danger"
    )
    return redirect(url_for("index"))


# -------------------------------------------------
# Misconfiguration
# -------------------------------------------------
@app.route("/run/misconfig/devops", methods=["POST"])
def run_misconfig_devops():
    infile = latest_upload()
    if not infile:
        flash("No uploaded file found", "danger")
        return redirect(url_for("index"))

    ok = run_script(
        ["python3", "stage1_devops.py", infile, OUTPUT_DIR],
        cwd=MISCONFIG_DIR
    )

    flash(
        "Misconfig DevOps completed" if ok else "Misconfig DevOps failed",
        "success" if ok else "danger"
    )
    return redirect(url_for("index"))


@app.route("/run/misconfig/master", methods=["POST"])
def run_misconfig_master():
    infile = latest_upload()
    if not infile:
        flash("No uploaded file found", "danger")
        return redirect(url_for("index"))

    ok = run_script(
        ["python3", "misconfig_master.py", infile, OUTPUT_DIR],
        cwd=MISCONFIG_DIR
    )

    flash(
        "Misconfig Master completed" if ok else "Misconfig Master failed",
        "success" if ok else "danger"
    )
    return redirect(url_for("index"))


# -------------------------------------------------
# Logs
# -------------------------------------------------
@app.route("/logs")
def logs_index():
    def meta(p):
        if not p or not os.path.exists(p):
            return {"exists": False}
        s = os.stat(p)
        return {"exists": True, "size": s.st_size, "mtime": s.st_mtime}

    return render_template(
        "logs.html",
        error_meta=meta(get_log_path("error")),
        processed_meta=meta(get_log_path("processed"))
    )


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


# -------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
