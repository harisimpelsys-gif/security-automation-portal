import os, uuid, subprocess, threading
import subprocess, time, signal
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
        flash("No file selected")
        return redirect("/index")

    name = f"{uuid.uuid4()}_{f.filename}"
    path = os.path.join(UPLOADS, name)
    f.save(path)

    print("UPLOADED FILE:", path)  # ✅ DEBUG
    session["uploaded_file"] = path

    flash("File uploaded successfully")
    return redirect("/index")


# ---------------- ASYNC RUNNER ---------------- #

def run_async(cmd, out_dir, timeout=900):
    os.makedirs(out_dir, exist_ok=True)
    status_file = os.path.join(out_dir, "status.txt")
    log_file = os.path.join(out_dir, "run.log")

    with open(status_file, "w") as f:
        f.write("RUNNING")

    def task():
        start = time.time()
        try:
            with open(log_file, "w") as log:
                proc = subprocess.Popen(
                    cmd,
                    stdout=log,
                    stderr=log,
                    preexec_fn=os.setsid  # important: detach from gunicorn
                )

                while True:
                    if proc.poll() is not None:
                        break

                    if time.time() - start > timeout:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                        raise TimeoutError("Process exceeded time limit")

                    time.sleep(2)

            rc = proc.returncode
            with open(status_file, "w") as f:
                f.write("COMPLETED" if rc == 0 else "FAILED")

        except Exception as e:
            with open(log_file, "a") as log:
                log.write(f"\nFATAL ERROR: {e}\n")
            with open(status_file, "w") as f:
                f.write("FAILED")

    threading.Thread(target=task, daemon=True).start()

# ---------------- MISCONFIG DEVOPS ---------------- #
@app.route("/run/mis/devops")
def run_mis_devops():
    inp = session.get("uploaded_file")

    if not inp or not os.path.exists(inp):
        flash("Upload file first (session lost). Please re-upload.")
        return redirect("/index")

    out = os.path.join(OUTPUTS, "mis_devops")
    os.makedirs(out, exist_ok=True)

    cmd = [
        "python",
        "MisConfig_Automation/segregate_misconfigs.py",
        inp,
        os.path.join(out, "Misconfig_By_App.xlsx")
    ]

    run_async(cmd, out)
    return redirect("/index")

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
