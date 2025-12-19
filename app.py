import os
import uuid
import subprocess
import traceback
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect,
    flash, send_from_directory, session, jsonify
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

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def run_background(cmd):
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

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
    if request.endpoint in ("login", "logout", "static"):
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

# ================= VULNERABILITY DEVOPS =================

@app.route("/run/vul/devops")
def run_vul_devops():
    try:
        inp = session.get("uploaded_file")
        if not inp:
            flash("Upload a file first")
            return redirect("/index")

        out_dir = os.path.join(OUTPUT_FOLDER, "vul_devops")
        os.makedirs(out_dir, exist_ok=True)

        output_file = os.path.join(
            out_dir,
            "Vulnerabilities_By_Application.xlsx"
        )

        status_file = os.path.join(out_dir, "status.txt")
        with open(status_file, "w") as f:
            f.write("RUNNING")

        run_background([
            "python",
            "Vul_Automation/split_vulns.py",
            inp,
            "-o", output_file
        ])

        flash("Vulnerability DevOps started")
        return redirect("/index")

    except Exception:
        log_error(traceback.format_exc())
        flash("Vulnerability DevOps failed")
        return redirect("/index")

# ================= STATUS API =================

@app.route("/status/vul/devops")
def vul_devops_status():
    status_file = os.path.join(
        OUTPUT_FOLDER, "vul_devops", "status.txt"
    )
    if not os.path.exists(status_file):
        return jsonify({"status": "NOT_STARTED"})

    with open(status_file) as f:
        return jsonify({"status": f.read().strip()})

# ================= DOWNLOADS =================

@app.route("/downloads/vul_devops")
def downloads_vul_devops():
    folder = os.path.join(OUTPUT_FOLDER, "vul_devops")
    files = os.listdir(folder) if os.path.exists(folder) else []
    return render_template(
        "downloads.html",
        files=files,
        folder="vul_devops"
    )

@app.route("/download/vul_devops/<file>")
def download_vul_devops(file):
    return send_from_directory(
        os.path.join(OUTPUT_FOLDER, "vul_devops"),
        file,
        as_attachment=True
    )

# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)
