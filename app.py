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

# ================= CONFIG =================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")
LOG_FOLDER = os.path.join(BASE_DIR, "logs")

ALLOWED_EXTENSIONS = {"xlsx", "csv"}
APP_PASSWORD = os.getenv("APP_PASSWORD", "changeme")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)

# ================= APP =================

app = Flask(__name__)
app.secret_key = "security-automation-secret"

# ================= HELPERS =================

def log_error(err):
    with open(os.path.join(LOG_FOLDER, "errors.log"), "a") as f:
        f.write(f"\n[{datetime.now()}]\n{err}\n")

def run_background(cmd):
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ================= AUTH =================

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

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.before_request
def protect():
    if request.endpoint in ("login", "static", "logout"):
        return
    if not session.get("auth"):
        return redirect("/")

# ================= DASHBOARD =================

@app.route("/index")
def index():
    return render_template("index.html")

# ================= UPLOAD =================

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f or f.filename == "":
        flash("No file selected")
        return redirect("/index")

    if not allowed_file(f.filename):
        flash("Only .xlsx or .csv files allowed")
        return redirect("/index")

    name = f"{uuid.uuid4()}_{secure_filename(f.filename)}"
    path = os.path.join(UPLOAD_FOLDER, name)
    f.save(path)

    session["uploaded_file"] = path
    flash("File uploaded successfully")

    return redirect("/index")

# ================= VULNERABILITY =================

@app.route("/run/vul/devops")
def run_vul_devops():
    try:
        inp = session.get("uploaded_file")
        if not inp:
            flash("Upload a file first")
            return redirect("/index")

        out = os.path.join(OUTPUT_FOLDER, "vul_devops")
        os.makedirs(out, exist_ok=True)

        run_background([
            "python",
            "Vul_Automation/split_vulns.py",
            inp,
            "--out-dir", out
        ])

        flash("Vulnerability DevOps started")
        return redirect("/index")

    except Exception:
        log_error(traceback.format_exc())
        flash("Vulnerability DevOps failed")
        return redirect("/index")

# ================= MISCONFIG =================

@app.route("/run/mis/devops")
def run_mis_devops():
    try:
        inp = session.get("uploaded_file")
        if not inp:
            flash("Upload a file first")
            return redirect("/index")

        out = os.path.join(OUTPUT_FOLDER, "mis_devops")
        os.makedirs(out, exist_ok=True)

        run_background([
            "python",
            "MisConfig_Automation/segregate_misconfigs.py",
            inp, out
        ])

        flash("Misconfig DevOps started")
        return redirect("/index")

    except Exception:
        log_error(traceback.format_exc())
        flash("Misconfig DevOps failed")
        return redirect("/index")

# ================= DOWNLOADS =================

@app.route("/downloads/<folder>")
def downloads(folder):
    path = os.path.join(OUTPUT_FOLDER, folder)
    files = os.listdir(path) if os.path.exists(path) else []
    return render_template("downloads.html", files=files, folder=folder)

@app.route("/download/<folder>/<file>")
def download(folder, file):
    return send_from_directory(
        os.path.join(OUTPUT_FOLDER, folder),
        file,
        as_attachment=True
    )

# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)
