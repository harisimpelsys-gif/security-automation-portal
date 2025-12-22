import os, uuid, subprocess, threading
from flask import Flask, render_template, request, redirect, session, jsonify, send_from_directory

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOADS = os.path.join(BASE_DIR, "uploads")
OUTPUTS = os.path.join(BASE_DIR, "outputs")

os.makedirs(UPLOADS, exist_ok=True)
os.makedirs(OUTPUTS, exist_ok=True)

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
        return redirect("/index")

    name = f"{uuid.uuid4()}_{f.filename}"
    path = os.path.join(UPLOADS, name)
    f.save(path)

    session["uploaded_file"] = path
    return redirect("/index")

# ---------------- ASYNC RUNNER ---------------- #

def run_async(cmd, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    status = os.path.join(out_dir, "status.txt")
    log = os.path.join(out_dir, "run.log")

    with open(status, "w") as f:
        f.write("RUNNING")

    def task():
        try:
            p = subprocess.run(cmd, capture_output=True, text=True)
            with open(log, "w") as l:
                l.write(p.stdout + "\n" + p.stderr)
            with open(status, "w") as f:
                f.write("COMPLETED" if p.returncode == 0 else "FAILED")
        except Exception as e:
            with open(log, "w") as l:
                l.write(str(e))
            with open(status, "w") as f:
                f.write("FAILED")

    threading.Thread(target=task, daemon=True).start()

def get_status(folder):
    f = os.path.join(OUTPUTS, folder, "status.txt")
    return open(f).read() if os.path.exists(f) else "NONE"

# ---------------- MISCONFIG DEVOPS ---------------- #

@app.route("/run/mis/devops")
def run_mis_devops():
    inp = session.get("uploaded_file")
    if not inp:
        return redirect("/index")

    out = os.path.join(OUTPUTS, "mis_devops")
    cmd = [
        "python",
        "MisConfig_Automation/segregate_misconfigs.py",
        inp,
        os.path.join(out, "Misconfig_By_App.xlsx")
    ]

    run_async(cmd, out)
    return redirect("/index")

@app.route("/status/mis/devops")
def status_mis_devops():
    return jsonify({"status": get_status("mis_devops")})

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
