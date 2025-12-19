import os, uuid, subprocess, threading
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOADS = os.path.join(BASE_DIR, "uploads")
OUTPUTS = os.path.join(BASE_DIR, "outputs")
LOGS = os.path.join(BASE_DIR, "logs")

for d in [UPLOADS, OUTPUTS, LOGS]:
    os.makedirs(d, exist_ok=True)

APP_PASSWORD = os.getenv("APP_PASSWORD", "changeme")

app = Flask(__name__)
app.secret_key = "security-automation-secret"

# ---------------- AUTH ---------------- #

@app.before_request
def require_login():
    if request.endpoint not in ("login", "static") and not session.get("auth"):
        return redirect("/")

@app.route("/", methods=["GET", "POST"])
def login():
    session.clear()
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

# ---------------- DASHBOARD ---------------- #

@app.route("/index")
def index():
    return render_template("index.html")

# ---------------- UPLOAD ---------------- #

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f:
        flash("No file selected")
        return redirect("/index")

    name = f"{uuid.uuid4()}_{f.filename}"
    path = os.path.join(UPLOADS, name)
    f.save(path)

    session["uploaded_file"] = path
    flash("File uploaded successfully")
    return redirect("/index")

# ---------------- HELPERS ---------------- #

def run_async(cmd, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    status = os.path.join(out_dir, "status.txt")
    log = os.path.join(out_dir, "run.log")

    with open(status, "w") as f:
        f.write("RUNNING")

    def task():
        p = subprocess.run(cmd, capture_output=True, text=True)
        with open(log, "w") as l:
            l.write(p.stdout + "\n" + p.stderr)
        with open(status, "w") as f:
            f.write("COMPLETED" if p.returncode == 0 else "FAILED")

    threading.Thread(target=task, daemon=True).start()

def get_status(folder):
    f = os.path.join(OUTPUTS, folder, "status.txt")
    return open(f).read() if os.path.exists(f) else "NONE"

# ---------------- DEVOPS ---------------- #

@app.route("/run/vul/devops")
def run_devops():
    inp = session.get("uploaded_file")
    if not inp:
        flash("Upload file first")
        return redirect("/index")

    out = os.path.join(OUTPUTS, "vul_devops")
    cmd = ["python", "Vul_Automation/split_vulns.py", inp, "-o", os.path.join(out, "Vul_By_App.xlsx")]
    run_async(cmd, out)
    session["devops_started"] = True
    return redirect("/index")

@app.route("/status/vul/devops")
def status_devops():
    return jsonify({"status": get_status("vul_devops")})

# ---------------- MASTER ---------------- #

@app.route("/run/vul/master")
def run_master():
    inp = session.get("uploaded_file")
    if not inp:
        flash("Upload file first")
        return redirect("/index")

    out = os.path.join(OUTPUTS, "vul_master")
    cmd = [
        "python",
        "Vul_Automation/automate_master_report.py",
        "--input", inp,
        "--output", os.path.join(out, "Master_Report_Automated.xlsx")
    ]
    run_async(cmd, out)
    session["master_started"] = True
    return redirect("/index")

@app.route("/status/vul/master")
def status_master():
    return jsonify({"status": get_status("vul_master")})

# ---------------- DOWNLOADS ---------------- #

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
    return f"<pre>{open(log).read()}</pre>" if os.path.exists(log) else "No logs"

if __name__ == "__main__":
    app.run()
