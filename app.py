#!/usr/bin/env python3
import os
import subprocess
from datetime import datetime
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

VULN_DIR = os.path.join(BASE_DIR, "Vul_Automation")
MISCONF_DIR = os.path.join(BASE_DIR, "MisConfig_Automation")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

ERROR_LOG = os.path.join(LOG_DIR, "error.log")
PROCESSED_LOG = os.path.join(LOG_DIR, "processed.log")

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def log(msg, error=False):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    target = ERROR_LOG if error else PROCESSED_LOG
    with open(target, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

def latest_upload():
    files = sorted(
        (os.path.join(UPLOAD_DIR, f) for f in os.listdir(UPLOAD_DIR)),
        key=os.path.getmtime,
        reverse=True
    )
    return files[0] if files else None

def run_script(script_path, args=None):
    if not os.path.exists(script_path):
        raise FileNotFoundError(script_path)

    cmd = ["python", script_path]
    if args:
        cmd.extend(args)

    with open(PROCESSED_LOG, "a") as out, open(ERROR_LOG, "a") as err:
        subprocess.run(
            cmd,
            stdout=out,
            stderr=err,
            cwd=os.path.dirname(script_path),
            check=True
        )

# -------------------------------------------------
# Pages
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

    log(f"Uploaded file: {f.filename}")
    flash(f"Uploaded {f.filename}", "success")
    return redirect(url_for("index"))

# -------------------------------------------------
# Vulnerability
# -------------------------------------------------
@app.route("/run/vuln/devops", methods=["POST"])
def run_vuln_devops():
    try:
        infile = latest_upload()
        if not infile:
            raise RuntimeError("No uploaded file found")

        script = os.path.join(VULN_DIR, "split_vulns.py")
        log("Starting Vulnerability DevOps run")
        run_script(script, [infile])
        flash("Vulnerability DevOps completed", "success")
    except Exception as e:
        log(f"Vulnerability DevOps failed: {e}", error=True)
        flash("Vulnerability DevOps failed", "danger")

    return redirect(url_for("index"))

@app.route("/run/vuln/master", methods=["POST"])
def run_vuln_master():
    try:
        script = os.path.join(VULN_DIR, "automate_master_report.py")
        log("Starting Vulnerability Master run")
        run_script(script)
        flash("Vulnerability Master report generated", "success")
    except Exception as e:
        log(f"Vulnerability Master failed: {e}", error=True)
        flash("Vulnerability Master failed", "danger")

    return redirect(url_for("index"))

# -------------------------------------------------
# Misconfiguration
# -------------------------------------------------
@app.route("/run/misconfig/devops", methods=["POST"])
def run_misconfig_devops():
    try:
        script = os.path.join(MISCONF_DIR, "classify_misconfigs.py")
        log("Starting Misconfiguration DevOps run")
        run_script(script)
        flash("Misconfiguration DevOps completed", "success")
    except Exception as e:
        log(f"Misconfiguration DevOps failed: {e}", error=True)
        flash("Misconfiguration DevOps failed", "danger")

    return redirect(url_for("index"))

@app.route("/run/misconfig/master", methods=["POST"])
def run_misconfig_master():
    try:
        script = os.path.join(MISCONF_DIR, "misconfig_master.py")
        log("Starting Misconfiguration Master run")
        run_script(script)
        flash("Misconfiguration Master completed", "success")
    except Exception as e:
        log(f"Misconfiguration Master failed: {e}", error=True)
        flash("Misconfiguration Master failed", "danger")

    return redirect(url_for("index"))

# -------------------------------------------------
# Logs
# -------------------------------------------------
@app.route("/logs")
def logs_index():
    def meta(p):
        if not os.path.exists(p):
            return {"exists": False}
        s = os.stat(p)
        return {
            "exists": True,
            "size": s.st_size,
            "mtime": datetime.fromtimestamp(s.st_mtime)
        }

    return render_template(
        "logs.html",
        error_meta=meta(ERROR_LOG),
        processed_meta=meta(PROCESSED_LOG)
    )

@app.route("/logs/<which>", methods=["GET", "HEAD"])
def logs_view(which):
    path = ERROR_LOG if which == "error" else PROCESSED_LOG if which == "processed" else None
    if not path or not os.path.exists(path):
        abort(404)

    with open(path, "r", errors="ignore") as f:
        content = f.read()
    return f"<pre>{content}</pre>"

@app.route("/logs/download/<which>")
def logs_download(which):
    path = ERROR_LOG if which == "error" else PROCESSED_LOG if which == "processed" else None
    if not path or not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True)

# -------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
