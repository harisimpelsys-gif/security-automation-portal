import os
import uuid
import subprocess
import traceback
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, send_from_directory, session
)
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")
LOG_FOLDER = os.path.join(BASE_DIR, "logs")

ALLOWED_EXTENSIONS = {"xlsx", "csv"}
APP_PASSWORD = os.getenv("APP_PASSWORD", "changeme")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = "security-automation-secret"

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def log_error(e):
    with open(os.path.join(LOG_FOLDER, "errors.log"), "a") as f:
        f.write(f"\n[{datetime.now()}]\n{e}\n")

def run(cmd):
    subprocess.run(cmd, check=True)

# --------------------------------------------------
# Auth
# --------------------------------------------------

@app.route("/", methods=["GET", "POST"])
def login():
    if session.get("auth"):
        return redirect("/index")

    if request.method == "POST":
        if request.form.get("password") == APP_PASSWORD:
            session["auth"] = True
            return redirect("/index")
        flash("Invalid password")

    return render_template("login.html")

@app.before_request
def protect():
    if request.endpoint in ("login", "static"):
        return
    if not session.get("auth"):
        return redirect("/")

# --------------------------------------------------
# Dashboard
# --------------------------------------------------

@app.route("/index")
def index():
    return render_template("index.html")

# --------------------------------------------------
# Upload
# --------------------------------------------------

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f:
        flash("No file selected")
        return redirect("/index")

    name = f"{uuid.uuid4()}_{secure_filename(f.filename)}"
    path = os.path.join(UPLOAD_FOLDER, name)
    f.save(path)
    session["uploaded_file"] = path

    flash("File uploaded")
    return redirect("/index")

# --------------------------------------------------
# Vulnerability
# --------------------------------------------------

@app.route("/run/vul/devops")
def vul_devops():
    try:
        inp = session["uploaded_file"]
        out = os.path.join(OUTPUT_FOLDER, "vul_devops")
        os.makedirs(out, exist_ok=True)

        run([
            "python",
            "Vul_Automation/split_vulns.py",
            inp,
            "--out-dir", out
        ])

        return redirect("/downloads/vul_devops")

    except Exception:
        log_error(traceback.format_exc())
        flash("Vulnerability DevOps failed")
        return redirect("/index")

@app.route("/run/vul/master")
def vul_master():
    try:
        inp = session["uploaded_file"]
        out_file = os.path.join(OUTPUT_FOLDER, "vul_master.xlsx")

        run([
            "python",
            "Vul_Automation/automated_master_report.py",
            "--input", inp,
            "--output", out_file
        ])

        return redirect("/download-file/vul_master.xlsx")

    except Exception:
        log_error(traceback.format_exc())
        flash("Vulnerability master failed")
        return redirect("/index")

# --------------------------------------------------
# Misconfig
# --------------------------------------------------

@app.route("/run/mis/devops")
def mis_devops():
    try:
        inp = session["uploaded_file"]
        out = os.path.join(OUTPUT_FOLDER, "mis_devops")
        os.makedirs(out, exist_ok=True)

        run([
            "python",
            "MisConfig_Automation/segregate_misconfigs.py",
            inp, out
        ])

        return redirect("/downloads/mis_devops")

    except Exception:
        log_error(traceback.format_exc())
        flash("Misconfig DevOps failed")
        return redirect("/index")

@app.route("/run/mis/aha")
def mis_aha():
    try:
        inp = session["uploaded_file"]
        out = os.path.join(OUTPUT_FOLDER, "mis_aha.xlsx")

        run([
            "python",
            "MisConfig_Automation/Misconfigp2.py",
            "--input", inp,
            "--output", out
        ])

        return redirect("/download-file/mis_aha.xlsx")

    except Exception:
        log_error(traceback.format_exc())
        flash("Misconfig AHA failed")
        return redirect("/index")

# --------------------------------------------------
# Downloads
# --------------------------------------------------

@app.route("/downloads/<folder>")
def downloads(folder):
    path = os.path.join(OUTPUT_FOLDER, folder)
    files = os.listdir(path) if os.path.exists(path) else []
    return render_template("downloads.html", files=files, folder=folder)

@app.route("/download-file/<filename>")
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
