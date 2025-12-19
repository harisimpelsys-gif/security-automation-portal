import os
import uuid
import subprocess
import threading

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, send_from_directory, jsonify
)

# ================== PATHS ================== #

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOADS = os.path.join(BASE_DIR, "uploads")
OUTPUTS = os.path.join(BASE_DIR, "outputs")
LOGS = os.path.join(BASE_DIR, "logs")

for d in (UPLOADS, OUTPUTS, LOGS):
    os.makedirs(d, exist_ok=True)

# ================== APP CONFIG ================== #

APP_PASSWORD = os.getenv("APP_PASSWORD", "changeme")

app = Flask(__name__)
app.secret_key = "security-automation-secret"

# ================== AUTH ================== #

@app.before_request
def require_login():
    if request.endpoint not in ("login", "static") and not session.get("auth"):
        return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
def login():
    session.clear()
    if request.method == "POST":
        if request.form.get("password") == APP_PASSWORD:
            session["auth"] = True
            return redirect(url_for("index"))
        flash("Invalid password")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ================== DASHBOARD ================== #

@app.route("/index")
def index():
    return render_template("index.html")

# ================== FILE UPLOAD ================== #

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        flash("No file selected")
        return redirect(url_for("index"))

    name = f"{uuid.uuid4()}_{f.filename}"
    path = os.path.join(UPLOADS, name)
    f.save(path)

    session["uploaded_file"] = path
    flash("File uploaded successfully")
    return redirect(url_for("index"))

# ================== ASYNC EXECUTION (CRITICAL FIX) ================== #

def run_async(cmd, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    status_file = os.path.join(out_dir, "status.txt")
    log_file = os.path.join(out_dir, "run.log")

    # Always reset status at start
    with open(status_file, "w") as f:
        f.write("RUNNING")

    def task():
        try:
            p = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            with open(log_file, "w") as log:
                log.write("COMMAND:\n")
                log.write(" ".join(cmd) + "\n\n")
                log.write("STDOUT:\n")
                log.write(p.stdout + "\n\n")
                log.write("STDERR:\n")
                log.write(p.stderr + "\n")

            if p.returncode == 0:
                with open(status_file, "w") as f:
                    f.write("COMPLETED")
            else:
                with open(status_file, "w") as f:
                    f.write("FAILED")

        except Exception as e:
            with open(log_file, "a") as log:
                log.write("\nEXCEPTION:\n" + str(e))

            with open(status_file, "w") as f:
                f.write("FAILED")

    threading.Thread(target=task, daemon=True).start()

def get_status(folder):
    path = os.path.join(OUTPUTS, folder, "status.txt")
    if not os.path.exists(path):
        return "NONE"
    return open(path).read().strip()

# ================== VULNERABILITY – DEVOPS ================== #

@app.route("/run/vul/devops")
def run_vul_devops():
    inp = session.get("uploaded_file")
    if not inp:
        flash("Upload file first")
        return redirect(url_for("index"))

    out = os.path.join(OUTPUTS, "vul_devops")
    cmd = [
        "python",
        "Vul_Automation/split_vulns.py",
        inp,
        "-o",
        os.path.join(out, "Vul_By_App.xlsx")
    ]
    run_async(cmd, out)
    return redirect(url_for("index"))

@app.route("/status/vul/devops")
def status_vul_devops():
    return jsonify({"status": get_status("vul_devops")})

# ================== VULNERABILITY – MASTER ================== #

@app.route("/run/vul/master")
def run_vul_master():
    inp = session.get("uploaded_file")
    if not inp:
        flash("Upload file first")
        return redirect(url_for("index"))

    out = os.path.join(OUTPUTS, "vul_master")
    cmd = [
        "python",
        "Vul_Automation/automate_master_report.py",
        "--input", inp,
        "--output", os.path.join(out, "Master_Report_Automated.xlsx")
    ]
    run_async(cmd, out)
    return redirect(url_for("index"))

@app.route("/status/vul/master")
def status_vul_master():
    return jsonify({"status": get_status("vul_master")})

# ================== MISCONFIG – DEVOPS ================== #

@app.route("/run/mis/devops")
def run_mis_devops():
    inp = session.get("uploaded_file")
    if not inp:
        flash("Upload file first")
        return redirect(url_for("index"))

    out = os.path.join(OUTPUTS, "mis_devops")
    cmd = [
        "python",
        "MisConfig_Automation/segregate_misconfigs.py",
        inp,
        os.path.join(out, "Misconfig_By_App.xlsx"),
        "--sheet", "Misconfigurations"
    ]
    run_async(cmd, out)
    return redirect(url_for("index"))

@app.route("/status/mis/devops")
def status_mis_devops():
    return jsonify({"status": get_status("mis_devops")})

# ================== DOWNLOADS & LOGS ================== #

@app.route("/downloads/<folder>")
def downloads(folder):
    path = os.path.join(OUTPUTS, folder)
    files = os.listdir(path) if os.path.exists(path) else []
    return render_template("downloads.html", files=files, folder=folder)

@app.route("/download/<folder>/<file>")
def download(folder, file):
    return send_from_directory(os.path.join(OUTPUTS, folder), file, as_attachment=True)

@app.route("/logs/<folder>")
def logs(folder):
    log = os.path.join(OUTPUTS, folder, "run.log")
    if not os.path.exists(log):
        return "No logs available"
    return f"<pre>{open(log).read()}</pre>"

# ================== LOCAL RUN ================== #

if __name__ == "__main__":
    app.run(debug=True)
