import os
import uuid
import zipfile
import subprocess
import traceback
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, send_from_directory, session
)
from werkzeug.utils import secure_filename

# ---------------- CONFIG ---------------- #

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")
LOG_FOLDER = os.path.join(BASE_DIR, "logs")

ALLOWED_EXTENSIONS = {"xlsx", "csv"}
MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # easy to increase

APP_PASSWORD = os.getenv("APP_PASSWORD", "changeme")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)

# ---------------- APP INIT ---------------- #

app = Flask(__name__)
app.secret_key = "security-automation-secret"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# ---------------- HELPERS ---------------- #

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def log_error(err):
    logfile = os.path.join(LOG_FOLDER, "app_errors.log")
    with open(logfile, "a") as f:
        f.write(f"\n[{datetime.now()}]\n")
        f.write(err + "\n")

def run_script(script_path, args):
    cmd = ["python", script_path] + args
    subprocess.run(cmd, check=True)

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

# ---------------- AUTH ---------------- #

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == APP_PASSWORD:
            session["auth"] = True
            return redirect(url_for("index"))
        flash("Invalid password")
    return render_template("login.html")

@app.before_request
def protect():
    if request.endpoint not in ("login", "static") and not session.get("auth"):
        return redirect(url_for("login"))

# ---------------- MAIN ---------------- #

@app.route("/index")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("No file selected")
        return redirect(url_for("index"))

    if not allowed_file(file.filename):
        flash("Only xlsx or csv allowed")
        return redirect(url_for("index"))

    filename = secure_filename(file.filename)
    uid = str(uuid.uuid4())
    save_name = f"{uid}_{filename}"
    path = os.path.join(UPLOAD_FOLDER, save_name)
    file.save(path)

    session["uploaded_file"] = path
    flash("File uploaded successfully")
    return redirect(url_for("index"))

# ---------------- VULNERABILITY ---------------- #

@app.route("/run/vul/devops")
def run_vul_devops():
    try:
        input_file = session.get("uploaded_file")
        out_dir = os.path.join(OUTPUT_FOLDER, "vul_devops")
        ensure_dir(out_dir)

        run_script(
            os.path.join(BASE_DIR, "Vul_Automation", "split_vulns.py"),
            [input_file, out_dir]
        )

        return redirect(url_for("downloads", folder="vul_devops"))

    except Exception:
        err = traceback.format_exc()
        log_error(err)
        flash("Vulnerability DevOps failed. Check logs.")
        return redirect(url_for("index"))

@app.route("/run/vul/master")
def run_vul_master():
    try:
        input_file = session.get("uploaded_file")
        out_dir = os.path.join(OUTPUT_FOLDER, "vul_master")
        ensure_dir(out_dir)

        run_script(
            os.path.join(BASE_DIR, "Vul_Automation", "automated_master_report.py"),
            [input_file, out_dir]
        )

        return redirect(url_for("downloads", folder="vul_master"))

    except Exception:
        err = traceback.format_exc()
        log_error(err)
        flash("Vulnerability Master failed. Check logs.")
        return redirect(url_for("index"))

# ---------------- MISCONFIG ---------------- #

@app.route("/run/mis/devops")
def run_mis_devops():
    try:
        input_file = session.get("uploaded_file")
        out_dir = os.path.join(OUTPUT_FOLDER, "mis_devops")
        ensure_dir(out_dir)

        run_script(
            os.path.join(BASE_DIR, "MisConfig_Automation", "segregate_misconfigs.py"),
            [input_file, out_dir]
        )

        return redirect(url_for("downloads", folder="mis_devops"))

    except Exception:
        err = traceback.format_exc()
        log_error(err)
        flash("Misconfig DevOps failed.")
        return redirect(url_for("index"))

@app.route("/run/mis/aha")
def run_mis_aha():
    try:
        input_file = session.get("uploaded_file")
        out_dir = os.path.join(OUTPUT_FOLDER, "mis_aha")
        ensure_dir(out_dir)

        run_script(
            os.path.join(BASE_DIR, "MisConfig_Automation", "Misconfigp2.py"),
            [input_file, out_dir]
        )

        return redirect(url_for("downloads", folder="mis_aha"))

    except Exception:
        err = traceback.format_exc()
        log_error(err)
        flash("Misconfig AHA split failed.")
        return redirect(url_for("index"))

@app.route("/run/mis/master")
def run_mis_master():
    try:
        input_file = session.get("uploaded_file")
        out_dir = os.path.join(OUTPUT_FOLDER, "mis_master")
        ensure_dir(out_dir)

        run_script(
            os.path.join(BASE_DIR, "MisConfig_Automation", "automate_master_report.py"),
            [input_file, out_dir]
        )

        return redirect(url_for("downloads", folder="mis_master"))

    except Exception:
        err = traceback.format_exc()
        log_error(err)
        flash("Misconfig Master failed.")
        return redirect(url_for("index"))

# ---------------- DOWNLOADS ---------------- #

@app.route("/downloads/<folder>")
def downloads(folder):
    folder_path = os.path.join(OUTPUT_FOLDER, folder)
    files = os.listdir(folder_path) if os.path.exists(folder_path) else []
    return render_template("downloads.html", files=files, folder=folder)

@app.route("/download/<folder>/<filename>")
def download_file(folder, filename):
    return send_from_directory(
        os.path.join(OUTPUT_FOLDER, folder),
        filename,
        as_attachment=True
    )

# ---------------- RUN ---------------- #

if __name__ == "__main__":
    app.run(debug=True)
