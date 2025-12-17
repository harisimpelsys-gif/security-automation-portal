from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, send_file
)
import subprocess
import os
from pathlib import Path
from datetime import datetime
from werkzeug.utils import secure_filename
import threading

# -----------------------------------------------------------------------------
# FLASK APP INIT
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = "change-this-key"

BASE_DIR = Path(__file__).resolve().parent

# -----------------------------------------------------------------------------
# DIRECTORIES (Render + Local Safe)
# -----------------------------------------------------------------------------
UPLOAD_FOLDER = BASE_DIR / "uploads"
OUTPUT_FOLDER = BASE_DIR / "outputs"
LOGS_FOLDER = BASE_DIR / "logs"
SCRIPTS_VULN = BASE_DIR / "Vul_Automation"
SCRIPTS_MISCONFIG = BASE_DIR / "MisConfig_Automation"

for p in [UPLOAD_FOLDER, OUTPUT_FOLDER, LOGS_FOLDER]:
    p.mkdir(exist_ok=True)

ERROR_LOG = LOGS_FOLDER / "error.log"
PROCESSED_LOG = LOGS_FOLDER / "processed.log"

ALLOWED_EXTENSIONS = {"xlsx", "xls", "csv"}
_log_lock = threading.Lock()

# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def now_ts():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

def append_log(path: Path, header: str, body: str):
    entry = (
        "\n" + "=" * 100 +
        f"\nTIMESTAMP: {now_ts()}\n{header}\n" +
        "-" * 80 + f"\n{body}\n"
    )
    with _log_lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)

def tail_file(path: Path, max_chars=20000):
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[-max_chars:]

# -----------------------------------------------------------------------------
# COMMAND EXECUTOR
# -----------------------------------------------------------------------------
def run_command(cmd):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, shell=False
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        if result.returncode == 0:
            return True, stdout
        else:
            return False, (
                f"RETURN CODE: {result.returncode}\n\n"
                f"STDERR:\n{stderr}\n\nSTDOUT:\n{stdout}"
            )
    except Exception as e:
        return False, f"Exception occurred:\n{e}"

def execute_and_log(cmd, script_name, output_path=None):
    ok, output = run_command(cmd)

    header = f"SCRIPT RUN: {script_name}"
    if output_path:
        header += f" — OUTPUT: {output_path}"

    body = f"COMMAND: {' '.join(map(str, cmd))}\n\n{output}"

    if ok:
        append_log(PROCESSED_LOG, header, body)
        session["last_status"] = "success"
    else:
        append_log(ERROR_LOG, header, body)
        session["last_status"] = "error"

    session["last_output"] = output
    return ok

# -----------------------------------------------------------------------------
# ROUTES
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template(
        "index.html",
        report_path=session.get("uploaded_report"),
        last_output=session.get("last_output"),
        last_status=session.get("last_status"),
    )

# ---------------------------- FILE UPLOAD ------------------------------------
@app.route("/upload", methods=["POST"])
def upload():
    if "report_file" not in request.files:
        flash("No file part.", "danger")
        return redirect(url_for("index"))

    file = request.files["report_file"]

    if file.filename == "":
        flash("No file selected.", "danger")
        return redirect(url_for("index"))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        save_path = UPLOAD_FOLDER / filename
        file.save(save_path)

        session["uploaded_report"] = str(save_path)
        session["last_output"] = None
        session["last_status"] = None

        append_log(PROCESSED_LOG, "FILE UPLOAD", f"Uploaded: {save_path}")

        flash(f"File uploaded: {filename}", "success")
        return redirect(url_for("index"))

    flash("Invalid file type.", "danger")
    return redirect(url_for("index"))

# -----------------------------------------------------------------------------
# VULNERABILITY – DEVOPS
# -----------------------------------------------------------------------------
@app.route("/run/vuln/devops", methods=["POST"])
def run_vuln_devops():
    report = session.get("uploaded_report")
    if not report:
        flash("Upload a report first.", "danger")
        return redirect(url_for("index"))

    output_dir = OUTPUT_FOLDER / "vulnerability_devops"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "vulnerabilities_by_application.xlsx"

    script = SCRIPTS_VULN / "split_vulns.py"

    cmd = ["python", str(script), report, "--output", str(output_path)]
    ok = execute_and_log(cmd, "split_vulns.py", str(output_path))

    flash(
        ("Vulnerability DevOps done!" if ok else "Error — check logs."),
        "success" if ok else "danger",
    )
    return redirect(url_for("index"))

# -----------------------------------------------------------------------------
# VULNERABILITY – MASTER REPORT
# -----------------------------------------------------------------------------
@app.route("/run/vuln/master", methods=["POST"])
def run_vuln_master():
    report = session.get("uploaded_report")
    if not report:
        flash("Upload report first.", "danger")
        return redirect(url_for("index"))

    output_dir = OUTPUT_FOLDER / "vulnerability_master"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "Master_Report_Automated.xlsx"

    script = SCRIPTS_VULN / "automated_master_report.py"

    cmd = ["python", str(script), "--input", report, "--output", str(output_path)]
    ok = execute_and_log(cmd, "automated_master_report.py", str(output_path))

    flash(
        ("Master report done!" if ok else "Error — check logs."),
        "success" if ok else "danger",
    )
    return redirect(url_for("index"))

# -----------------------------------------------------------------------------
# MISCONFIG – DEVOPS
# -----------------------------------------------------------------------------
@app.route("/run/misconfig/devops", methods=["POST"])
def run_misconfig_devops():
    report = session.get("uploaded_report")
    if not report:
        flash("Upload report first.", "danger")
        return redirect(url_for("index"))

    output_dir = OUTPUT_FOLDER / "misconfig_devops"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "misconfig_segregated.xlsx"

    script = SCRIPTS_MISCONFIG / "segregate_misconfigs.py"

    cmd = ["python", str(script), report, str(output_path)]
    ok = execute_and_log(cmd, "segregate_misconfigs.py", str(output_path))

    flash(
        ("Misconfig DevOps done!" if ok else "Error — check logs."),
        "success" if ok else "danger",
    )
    return redirect(url_for("index"))

# -----------------------------------------------------------------------------
# MISCONFIG – AHA/PMP/AZURE/PP
# -----------------------------------------------------------------------------
@app.route("/run/misconfig/aha", methods=["POST"])
def run_misconfig_aha():
    report = session.get("uploaded_report")
    if not report:
        flash("Upload report first.", "danger")
        return redirect(url_for("index"))

    output_dir = OUTPUT_FOLDER / "misconfig_p2"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "Misconfig_AHA_PMP_AZURE_PP.xlsx"

    script = SCRIPTS_MISCONFIG / "Misconfigp2.py"

    cmd = ["python", str(script), "--input", report, "--output", str(output_path)]
    ok = execute_and_log(cmd, "Misconfigp2.py", str(output_path))

    flash(
        ("AHA/PMP/AZURE/PP Done!" if ok else "Error — check logs."),
        "success" if ok else "danger",
    )
    return redirect(url_for("index"))

# -----------------------------------------------------------------------------
# MISCONFIG – FINAL
# -----------------------------------------------------------------------------
@app.route("/run/misconfig/final", methods=["POST"])
def run_misconfig_final():
    p2_file = OUTPUT_FOLDER / "misconfig_p2" / "Misconfig_AHA_PMP_AZURE_PP.xlsx"
    if not p2_file.exists():
        flash("Run AHA/PMP/AZURE/PP step first!", "danger")
        return redirect(url_for("index"))

    output_dir = OUTPUT_FOLDER / "misconfig_final"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "Misconfig_Actionable_Final.xlsx"

    script = SCRIPTS_MISCONFIG / "classify_misconfigs.py"
    rules_dir = SCRIPTS_MISCONFIG / "rules"

    cmd = [
        "python",
        str(script),
        "--report", str(p2_file),
        "--rules-folder", str(rules_dir),
        "--output", str(output_path),
    ]

    ok = execute_and_log(cmd, "classify_misconfigs.py", str(output_path))

    flash(
        ("Final Misconfig done!" if ok else "Error — check logs."),
        "success" if ok else "danger",
    )
    return redirect(url_for("index"))

# -----------------------------------------------------------------------------
# MISCONFIG – MASTER
# -----------------------------------------------------------------------------
@app.route("/run/misconfig/master", methods=["POST"])
def run_misconfig_master():
    final_file = OUTPUT_FOLDER / "misconfig_final" / "Misconfig_Actionable_Final.xlsx"
    if not final_file.exists():
        flash("Run Final Misconfig first!", "danger")
        return redirect(url_for("index"))

    output_dir = OUTPUT_FOLDER / "misconfig_master"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "Misconfig_Master_Report.xlsx"

    script = SCRIPTS_MISCONFIG / "automate_master_report.py"

    cmd = ["python", str(script), "--input", str(final_file), "--output", str(output_path)]
    ok = execute_and_log(cmd, "automate_master_report.py", str(output_path))

    flash(
        ("Master Misconfig done!" if ok else "Error — check logs."),
        "success" if ok else "danger",
    )
    return redirect(url_for("index"))

# -----------------------------------------------------------------------------
# LOGS UI
# -----------------------------------------------------------------------------
@app.route("/logs")
def logs_index():
    return render_template(
        "logs.html",
        error_data=tail_file(ERROR_LOG),
        processed_data=tail_file(PROCESSED_LOG),
    )

# -----------------------------------------------------------------------------
# RUN FLASK
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
