import os, uuid, subprocess, threading
from flask import Flask, render_template, request, redirect, jsonify, session, send_from_directory, flash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOADS = os.path.join(BASE_DIR, "uploads")
OUTPUTS = os.path.join(BASE_DIR, "outputs")

for d in [UPLOADS, OUTPUTS]:
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

    fname = f"{uuid.uuid4()}_{f.filename}"
    path = os.path.join(UPLOADS, fname)
    f.save(path)

    session["uploaded_file"] = path
    flash("File uploaded successfully")
    return redirect("/index")

# ---------------- ASYNC RUNNER ---------------- #

def run_async(cmd, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    status_file = os.path.join(out_dir, "status.txt")
    log_file = os.path.join(out_dir, "run.log")

    with open(status_file, "w") as f:
        f.write("RUNNING")

    def task():
        try:
            p = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=BASE_DIR
            )
            with open(log_file, "w") as l:
                l.write(p.stdout + "\n" + p.stderr)

            # ✅ SUCCESS IF FILE EXISTS
            produced = [f for f in os.listdir(out_dir) if f.endswith(".xlsx")]
            with open(status_file, "w") as f:
                f.write("COMPLETED" if produced else "FAILED")

        except Exception as e:
            with open(log_file, "w") as l:
                l.write(str(e))
            with open(status_file, "w") as f:
                f.write("FAILED")

    threading.Thread(target=task, daemon=True).start()

def get_status(folder):
    f = os.path.join(OUTPUTS, folder, "status.txt")
    return open(f).read().strip() if os.path.exists(f) else ""

# ---------------- MISCONFIG DEVOPS ---------------- #

@app.route("/run/mis/devops")
def run_mis_devops():
    inp = session.get("uploaded_file")
    if not inp or not os.path.exists(inp):
        flash("Upload file first")
        return redirect("/index")

    out = os.path.join(OUTPUTS, "mis_devops")
    cmd = [
        "python",
        os.path.join("MisConfig_Automation", "segregate_misconfigs.py"),
        inp,
        os.path.join(out, "Misconfig_By_App.xlsx"),
    ]
    run_async(cmd, out)
    return redirect("/index")

@app.route("/status/mis/devops")
def status_mis_devops():
    return jsonify({"status": get_status("mis_devops")})

# ---------------- DOWNLOADS / LOGS ---------------- #

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
