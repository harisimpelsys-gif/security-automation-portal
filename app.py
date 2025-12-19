import os
import uuid
import subprocess
import threading
from flask import (
    Flask, render_template, request,
    redirect, flash, session, jsonify,
    send_from_directory
)
from werkzeug.utils import secure_filename

# ================= CONFIG =================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")

ALLOWED_EXTENSIONS = {"xlsx", "csv"}
APP_PASSWORD = os.getenv("APP_PASSWORD", "changeme")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ================= APP =================

app = Flask(__name__)
app.secret_key = "security-automation-secret"

# ================= HELPERS =================

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
        flash("Only xlsx or csv allowed")
        return redirect("/index")

    filename = f"{uuid.uuid4()}_{secure_filename(f.filename)}"
    path = os.path.join(UPLOAD_FOLDER, filename)
    f.save(path)

    session["uploaded_file"] = path
    flash("File uploaded successfully")
    return redirect("/index")

# ================= VULNERABILITY DEVOPS =================

@app.route("/run/vul/devops")
def run_vul_devops():
    input_file = session.get("uploaded_file")
    if not input_file:
        flash("Upload a file first")
        return redirect("/index")

    out_dir = os.path.join(OUTPUT_FOLDER, "vul_devops")
    os.makedirs(out_dir, exist_ok=True)

    output_file = os.path.join(
        out_dir, "Vulnerabilities_By_Application.xlsx"
    )
    status_file = os.path.join(out_dir, "status.txt")
    log_file = os.path.join(out_dir, "run.log")

    # mark running
    with open(status_file, "w") as f:
        f.write("RUNNING")

    def task():
        result = subprocess.run(
            [
                "python",
                "Vul_Automation/split_vulns.py",
                input_file,
                "-o",
                output_file,
            ],
            capture_output=True,
            text=True
        )

        # write logs always
        with open(log_file, "w") as lf:
            lf.write("STDOUT:\n")
            lf.write(result.stdout or "")
            lf.write("\n\nSTDERR:\n")
            lf.write(result.stderr or "")

        # SUCCESS CRITERIA = output exists
        if os.path.exists(output_file):
            with open(status_file, "w") as f:
                f.write("COMPLETED")
        else:
            with open(status_file, "w") as f:
                f.write("FAILED")

    threading.Thread(target=task, daemon=True).start()

    flash("Vulnerability DevOps started")
    return redirect("/index")

# ================= STATUS =================

@app.route("/status/vul/devops")
def status_vul_devops():
    status_file = os.path.join(
        OUTPUT_FOLDER, "vul_devops", "status.txt"
    )
    if not os.path.exists(status_file):
        return jsonify({"status": "NOT_STARTED"})
    return jsonify({"status": open(status_file).read().strip()})

# ================= DOWNLOADS =================

@app.route("/downloads/vul_devops")
def downloads_vul_devops():
    folder = os.path.join(OUTPUT_FOLDER, "vul_devops")
    files = os.listdir(folder) if os.path.exists(folder) else []
    return render_template("downloads.html", files=files)

@app.route("/download/vul_devops/<filename>")
def download_vul_file(filename):
    return send_from_directory(
        os.path.join(OUTPUT_FOLDER, "vul_devops"),
        filename,
        as_attachment=True
    )

# ================= LOG VIEW =================

@app.route("/logs/vul/devops")
def view_vul_logs():
    log_path = os.path.join(
        OUTPUT_FOLDER, "vul_devops", "run.log"
    )
    if not os.path.exists(log_path):
        return "No logs available"
    return f"<pre>{open(log_path).read()}</pre>"

# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)
