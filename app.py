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

# ======================================================
# CONFIG
# ======================================================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")
LOG_FOLDER = os.path.join(BASE_DIR, "logs")

ALLOWED_EXTENSIONS = {"xlsx", "csv"}
MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200 MB

APP_PASSWORD = os.getenv("APP_PASSWORD", "changeme")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)

# ======================================================
# APP INIT
# ======================================================

app = Flask(__name__)
app.secret_key = "security-automation-secret"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# ======================================================
# HELPERS
# ======================================================

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_dir(path):
    os.makedirs(path, exist_okoxist_ok=True)

def log_error(err):
    logfile = os.path.join(LOG_FOLDER, "app_errors.log")
    with open(logfile, "a") as f:
        f.write(f"\n[{datetime.now()}]\n")
        f.write(err + "\n")

def run_cmd(cmd):
    """
    Run subprocess safely and raise error if it fails
    """
    subprocess.run(cmd, check=True)

# ======================================================
# AUTH
# ======================================================

@app.route("/", methods=["GET", "POST"])
def login():
    if session.get("auth"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        if request.form.get("password") == APP_PASSWORD:
            session["auth"] = True
            return redirect(url_for("dashboard"))
        flash("Invalid password")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.before_request
def protect():
    if request.endpoint in ("login", "logout", "static"):
        return
    if not session.get("auth"):
        return redirect(url_for("login"))

# ======================================================
# DASHBOARD
# ======================================================

@app.route("/index", methods=["GET"])
def dashboard():
    return render_template("index.html")

# ======================================================
# UPLOAD
# ======================================================

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")

    if not file or file.filename == "":
        flash("No file selected")
        return redirect(url_for("dashboard"))

    if not allowed_file(file.filename):
        flash("Only .xlsx or .csv files are allowed")
        return redirect(url_for("dashboard"))

    filename = secure_filename(file.filename)
    uid = str(uuid.uuid4())
    saved_name = f"{uid}_{filename}"
    saved_path = os.path.join(UPLOAD_FOLDER, saved_name)

    file.save(saved_path)
    session["uploaded_file"] = saved_path

    flash("File uploaded successfully")
    return redirect(url_for("dashboard"))

# ======================================================
# VULNERABILITY
# ======================================================

@app.route("/run/vul/devops")
def run_vul_devops():
    try:
        input_file = session.get("uploaded_file")
        if not input_file:
            flash("Upload file first")
            return redirect(url_for("dashboard"))

        out_dir = os.path.join(OUTPUT_FOLDER, "vul_devops")
        os.makedirs(out_dir, exist_ok=True)

        run_cmd([
            "python",
            os.path.join(BASE_DIR, "Vul_Automation", "split_vulns.py"),
            "--input", input_file,
            "--out-dir", out_dir
        ])

        return redirect(url_for("downloads", folder="vul_devops"))

    except Exception:
        log_error(traceback.format_exc())
        flash("Vulnerability DevOps failed")
        return redirect(url_for("dashboard"))


@app.route("/run/vul/master")
def run_vul_master():
    try:
        input_file = session.get("uploaded_file")
        if not input_file:
            flash("Upload file first")
            return redirect(url_for("dashboard"))

        out_dir = os.path.join(OUTPUT_FOLDER, "vul_master")
        os.makedirs(out_dir, exist_ok=True)

        run_cmd([
            "python",
            os.path.join(BASE_DIR, "Vul_Automation", "automated_master_report.py"),
            "--input", input_file,
            "--output", out_dir
        ])

        return redirect(url_for("downloads", folder="vul_master"))

    except Exception:
        log_error(traceback.format_exc())
        flash("Vulnerability Master failed")
        return redirect(url_for("dashboard"))

# ======================================================
# MISCONFIGURATION
# ======================================================

@app.route("/run/mis/devops")
def run_mis_devops():
    try:
        input_file = session.get("uploaded_file")
        if not input_file:
            flash("Upload file first")
            return redirect(url_for("dashboard"))

        out_dir = os.path.join(OUTPUT_FOLDER, "mis_devops")
        os.makedirs(out_dir, exist_ok=True)

        run_cmd([
            "python",
            os.path.join(BASE_DIR, "MisConfig_Automation", "segregate_misconfigs.py"),
            "--input", input_file,
            "--output", out_dir
        ])

        return redirect(url_for("downloads", folder="mis_devops"))

    except Exception:
        log_error(traceback.format_exc())
        flash("Misconfig DevOps failed")
        return redirect(url_for("dashboard"))


@app.route("/run/mis/aha")
def run_mis_aha():
    try:
        input_file = session.get("uploaded_file")
        if not input_file:
            flash("Upload file first")
            return redirect(url_for("dashboard"))

        out_dir = os.path.join(OUTPUT_FOLDER, "mis_aha")
        os.makedirs(out_dir, exist_ok=True)

        run_cmd([
            "python",
            os.path.join(BASE_DIR, "MisConfig_Automation", "Misconfigp2.py"),
            "--input", input_file,
            "--output", out_dir
        ])

        return redirect(url_for("downloads", folder="mis_aha"))

    except Exception:
        log_error(traceback.format_exc())
        flash("Misconfig AHA split failed")
        return redirect(url_for("dashboard"))


@app.route("/run/mis/master")
def run_mis_master():
    try:
        input_file = session.get("uploaded_file")
        if not input_file:
            flash("Upload file first")
            return redirect(url_for("dashboard"))

        out_dir = os.path.join(OUTPUT_FOLDER, "mis_master")
        os.makedirs(out_dir, exist_ok=True)

        run_cmd([
            "python",
            os.path.join(BASE_DIR, "MisConfig_Automation", "automate_master_report.py"),
            "--input", input_file,
            "--output", out_dir
        ])

        return redirect(url_for("downloads", folder="mis_master"))

    except Exception:
        log_error(traceback.format_exc())
        flash("Misconfig Master failed")
        return redirect(url_for("dashboard"))

# ======================================================
# DOWNLOADS
# ======================================================

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

# ======================================================
# RUN
# ======================================================

if __name__ == "__main__":
    app.run(debug=True)
