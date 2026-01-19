from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_file,
)
import subprocess
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from pathlib import Path
import threading

app = Flask(__name__)
app.secret_key = "change-this-key"

# ========== FILE / PATH CONFIG ==========
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
LOGS_FOLDER = BASE_DIR / "logs"

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
LOGS_FOLDER.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"xlsx", "xls", "csv"}
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)

# log file paths
ERROR_LOG = LOGS_FOLDER / "error.log"
PROCESSED_LOG = LOGS_FOLDER / "processed.log"

# small lock to avoid race conditions when appending logs
_log_lock = threading.Lock()

# ========== HELPERS ==========
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def now_ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

def append_log(path: Path, header: str, body: str):
    """
    Append an entry to a log file with a header & body.
    """
    entry = []
    entry.append("=" * 100)
    entry.append(f"TIMESTAMP: {now_ts()}")
    entry.append(header)
    entry.append("-" * 80)
    entry.append(body or "")
    entry.append("\n\n")
    text = "\n".join(entry)
    with _log_lock:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(text)

def tail_file(path: Path, max_chars: int = 20000):
    """
    Read tail of file (last max_chars characters).
    """
    if not path.exists():
        return ""
    # read last chunk from file
    with path.open("rb") as fh:
        try:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            start = max(0, size - max_chars)
            fh.seek(start)
            data = fh.read().decode("utf-8", errors="replace")
            # if cut mid-line, drop first partial line
            if start > 0:
                parts = data.splitlines(True)
                if len(parts) > 1:
                    data = "".join(parts[1:])
        except Exception:
            fh.seek(0)
            data = fh.read().decode("utf-8", errors="replace")
    return data

# ========== COMMAND RUNNER ==========
def run_command(cmd, cwd=None):
    """
    Run a subprocess command (list). Returns (ok:bool, output_str).
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=False,
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        if result.returncode == 0:
            return True, stdout
        else:
            out = f"RETURN CODE: {result.returncode}\n\nSTDERR:\n{stderr}\n\nSTDOUT:\n{stdout}"
            return False, out
    except Exception as e:
        return False, f"Exception while running command:\n{e}"

# ========== ROUTES ==========
@app.route("/", methods=["GET"])
def index():
    report_path = session.get("uploaded_report")
    last_output = session.get("last_output")
    last_status = session.get("last_status")
    return render_template(
        "index.html",
        report_path=report_path,
        last_output=last_output,
        last_status=last_status,
    )

@app.route("/upload", methods=["POST"])
def upload():
    if "report_file" not in request.files:
        flash("No file part in request.", "danger")
        return redirect(url_for("index"))

    file = request.files["report_file"]

    if file.filename == "":
        flash("No file selected.", "danger")
        return redirect(url_for("index"))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        save_path = UPLOAD_FOLDER / filename
        file.save(str(save_path))

        session["uploaded_report"] = str(save_path)
        session["last_output"] = None
        session["last_status"] = None

        # log processed upload
        header = f"UPLOAD: {filename}"
        body = f"Saved to: {save_path}\nUploaded by session"
        append_log(PROCESSED_LOG, header, body)

        flash(f"Report uploaded: {filename}", "success")
        return redirect(url_for("index"))
    else:
        flash("File type not allowed. Upload .xlsx, .xls or .csv", "danger")
        return redirect(url_for("index"))

# ---------- helper for wrapping script runs and logging -----------
def execute_and_log(script_cmd: list, script_name: str, saved_output_path: str = None):
    """
    Run command, append to processed or error logs, and update session last_output/status.
    Returns (ok, output_str).
    """
    ok, output = run_command(script_cmd)
    header = f"SCRIPT: {script_name}"
    if saved_output_path:
        header += f" — OUTPUT: {saved_output_path}"
    # include the command list for traceability
    body = f"COMMAND: {' '.join(map(str, script_cmd))}\n\n{output}"
    if ok:
        append_log(PROCESSED_LOG, header, body)
        session["last_output"] = output
        session["last_status"] = "success"
        return True, output
    else:
        append_log(ERROR_LOG, header, body)
        session["last_output"] = output
        session["last_status"] = "error"
        return False, output

# ========== Existing routes (Vulnerability + Misconfig) ==========
# NOTE: keep your original script paths — they can be adjusted later to be relative.
# I kept your previous behavior but call execute_and_log to persist logs.

@app.route("/run/vuln/devops", methods=["POST"])
def run_vuln_devops():
    report_path = session.get("uploaded_report")
    if not report_path:
        flash("Upload a report first.", "danger")
        return redirect(url_for("index"))

    script_path = r"C:\Users\mohammedharis.f\Downloads\Vul_Automation\split_vulns.py"
    output_dir = Path(r"C:\Users\mohammedharis.f\Desktop\website\Vulnarability_devops_report")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "vulnerabilities_by_application.xlsx"

    cmd = ["python", script_path, report_path, "--output", str(output_path)]

    ok, output = execute_and_log(cmd, "split_vulns.py", str(output_path))

    if ok:
        flash(f"Vulnerability DevOps report executed successfully. Saved to: {output_path}", "success")
    else:
        flash("Vulnerability DevOps report failed. Check Logs -> Error Logs for details.", "danger")

    return redirect(url_for("index"))

@app.route("/run/vuln/master", methods=["POST"])
def run_vuln_master():
    report_path = session.get("uploaded_report")
    if not report_path:
        flash("Upload a report first.", "danger")
        return redirect(url_for("index"))

    script_path = r"C:\Users\mohammedharis.f\Downloads\Vul_Automation\automated_master_report.py"
    output_dir = Path(r"C:\Users\mohammedharis.f\Desktop\website\Vulnarability_master_report")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "Master_Report_Automated.xlsx"

    cmd = ["python", script_path, "--input", report_path, "--output", str(output_path)]

    ok, output = execute_and_log(cmd, "automated_master_report.py", str(output_path))

    if ok:
        flash(f"Master Vulnerability report executed successfully. Saved to: {output_path}", "success")
    else:
        flash("Master Vulnerability report failed. Check Logs -> Error Logs for details.", "danger")

    return redirect(url_for("index"))

@app.route("/run/misconfig/devops", methods=["POST"])
def run_misconfig_devops():
    report_path = session.get("uploaded_report")
    if not report_path:
        flash("Upload a report first.", "danger")
        return redirect(url_for("index"))

    script_path = r"C:\Users\mohammedharis.f\Downloads\MisConfig_Automation\segregate_misconfigs.py"
    output_dir = Path(r"C:\Users\mohammedharis.f\Desktop\website\Misconfig_devops_report")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "misconfig_segregated.xlsx"

    cmd = ["python", script_path, str(report_path), str(output_path)]

    ok, output = execute_and_log(cmd, "segregate_misconfigs.py", str(output_path))

    if ok:
        flash(f"Misconfiguration DevOps report executed successfully. Saved to: {output_path}", "success")
    else:
        flash("Misconfiguration DevOps report failed. Check Logs -> Error Logs for details.", "danger")

    return redirect(url_for("index"))

@app.route("/run/misconfig/aha", methods=["POST"])
def run_misconfig_aha():
    report_path = session.get("uploaded_report")
    if not report_path:
        flash("Upload a report first.", "danger")
        return redirect(url_for("index"))

    script_path = r"C:\Users\mohammedharis.f\Downloads\MisConfig_Automation\Misconfigp2.py"
    output_dir = Path(r"C:\Users\mohammedharis.f\Desktop\website\Misconfig_AHA_PMP_AZURE_PP_report")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "Misconfig_AHA_PMP_AZURE_PP.xlsx"

    cmd = ["python", script_path, "--input", report_path, "--output", str(output_path)]

    ok, output = execute_and_log(cmd, "Misconfigp2.py", str(output_path))

    if ok:
        flash(f"Misconfiguration AHA/PMP/AZURE/PP report executed successfully. Saved to: {output_path}", "success")
    else:
        flash("Misconfiguration AHA/PMP/AZURE/PP report failed. Check Logs -> Error Logs for details.", "danger")

    return redirect(url_for("index"))

@app.route("/run/misconfig/final", methods=["POST"])
def run_misconfig_final():
    aha_output_path = Path(r"C:\Users\mohammedharis.f\Desktop\website\Misconfig_AHA_PMP_AZURE_PP_report\Misconfig_AHA_PMP_AZURE_PP.xlsx")

    if not aha_output_path.exists():
        session["last_output"] = f"Required input not found:\n{aha_output_path}\n\nRun 'Misconfiguration AHA / PMP / AZURE / PP Report' first."
        session["last_status"] = "error"
        flash("AHA/PMP/AZURE/PP report not found. Run that step before Final Misconfig.", "danger")
        return redirect(url_for("index"))

    script_path = r"C:\Users\mohammedharis.f\Downloads\MisConfig_Automation\classify_misconfigs.py"
    rules_folder = r"C:\Users\mohammedharis.f\Downloads\MisConfig_Automation\rules"

    output_dir = Path(r"C:\Users\mohammedharis.f\Desktop\website\Misconfig_final_report")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "Misconfig_AHA_PMP_AZURE_PP_actionable_final.xlsx"

    cmd = [
        "python",
        script_path,
        "--report",
        str(aha_output_path),
        "--rules-folder",
        rules_folder,
        "--output",
        str(output_path),
    ]

    ok, output = execute_and_log(cmd, "classify_misconfigs.py", str(output_path))

    if ok:
        flash(f"Misconfiguration Final report executed successfully. Saved to: {output_path}", "success")
    else:
        flash("Misconfiguration Final report failed. Check Logs -> Error Logs for details.", "danger")

    return redirect(url_for("index"))

@app.route("/run/misconfig/master", methods=["POST"])
def run_misconfig_master():
    final_report_path = Path(r"C:\Users\mohammedharis.f\Desktop\website\Misconfig_final_report\Misconfig_AHA_PMP_AZURE_PP_actionable_final.xlsx")

    if not final_report_path.exists():
        session["last_output"] = f"Required input not found:\n{final_report_path}\n\nRun 'Misconfiguration Final Report' first."
        session["last_status"] = "error"
        flash("Final misconfiguration report not found. Run 'Misconfiguration Final Report' first.", "danger")
        return redirect(url_for("index"))

    script_path = r"C:\Users\mohammedharis.f\Downloads\MisConfig_Automation\automate_master_report.py"
    output_dir = Path(r"C:\Users\mohammedharis.f\Desktop\website\Misconfig_master_report")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "Misconfig_Master_Report_Automated.xlsx"

    cmd = ["python", script_path, "--input", str(final_report_path), "--output", str(output_path)]

    ok, output = execute_and_log(cmd, "automate_master_report.py", str(output_path))

    if ok:
        flash(f"Misconfiguration Master report executed successfully. Saved to: {output_path}", "success")
    else:
        flash("Misconfiguration Master report failed. Check Logs -> Error Logs for details.", "danger")

    return redirect(url_for("index"))

# ==========JUSTIFICATION ============
@app.route("/run/misconfig/justification", methods=["POST"])
def run_misconfig_justification():
    # INPUT: Stage-3 Final Actionable report
    final_actionable_path = Path(
        r"C:\Users\mohammedharis.f\Desktop\website\Misconfig_final_report"
        r"\Misconfig_AHA_PMP_AZURE_PP_actionable_final.xlsx"
    )

    if not final_actionable_path.exists():
        session["last_output"] = (
            f"Required input not found:\n{final_actionable_path}\n\n"
            "Run 'Misconfiguration Final Report' first."
        )
        session["last_status"] = "error"
        flash("Final actionable misconfig report not found. Run Stage 3 first.", "danger")
        return redirect(url_for("index"))

    # SCRIPT
    script_path = r"C:\Users\mohammedharis.f\Downloads\MisConfig_Automation\justification.py"

    # JUSTIFICATION RULE FILE
    justification_file = (
        r"C:\Users\mohammedharis.f\Downloads\MisConfig_Automation"
        r"\justification\justification.xlsx"
    )

    # OUTPUT
    output_dir = Path(r"C:\Users\mohammedharis.f\Desktop\website\Misconfig_justified_report")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "Misconfig_AHA_PMP_AZURE_PP_justified.xlsx"

    cmd = [
        "python",
        script_path,
        "--report",
        str(final_actionable_path),
        "--justification-file",
        justification_file,
        "--output",
        str(output_path),
    ]

    ok, output = execute_and_log(cmd, "justification.py", str(output_path))

    if ok:
        flash(
            f"Justification applied successfully. Saved to: {output_path}",
            "success"
        )
    else:
        flash(
            "Justification failed. Check Logs → Error Logs for details.",
            "danger"
        )

    return redirect(url_for("index"))

#===========Image Assessment ==========

@app.route("/run/image-assessment", methods=["POST"])
def run_image_assessment():
    report_path = session.get("uploaded_report")
    if not report_path:
        flash("Upload a report first.", "danger")
        return redirect(url_for("index"))

    script_path = r"C:\Users\mohammedharis.f\Downloads\ImageAssessment\image_assessment.py"
    output_dir = Path(r"C:\Users\mohammedharis.f\Desktop\website\Image_Assessment_Report")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "Image_Assessment_Segregated.xlsx"

    # ✅ positional args (NOT flags)
    cmd = ["python", script_path, report_path, str(output_path)]

    ok, output = execute_and_log(cmd, "image_assessment.py", str(output_path))

    if ok:
        flash(
            f"Image Assessment report executed successfully. Saved to: {output_path}",
            "success",
        )
    else:
        flash(
            "Image Assessment report failed. Check Logs -> Error Logs for details.",
            "danger",
        )

    return redirect(url_for("index"))



@app.route("/run/image-assessment/master", methods=["POST"])
def run_image_assessment_master():
    #  use RAW uploaded report (same as CLI success)
    report_path = session.get("uploaded_report")

    if not report_path:
        session["last_output"] = (
            "No base report found in session.\n\n"
            "Upload the Image Assessment report first."
        )
        session["last_status"] = "error"
        flash("Upload Image Assessment report first.", "danger")
        return redirect(url_for("index"))

    script_path = r"C:\Users\mohammedharis.f\Downloads\ImageAssessment\master_IA_report.py"

    output_dir = Path(
        r"C:\Users\mohammedharis.f\Desktop\website\Image_Assessment_Master_Report"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "Image_Assessment_Master_Report.xlsx"

    #  positional args ONLY (exactly like your working CLI)
    cmd = ["python", script_path, report_path, str(output_path)]

    ok, output = execute_and_log(
        cmd,
        "master_IA_report.py",
        str(output_path)
    )

    if ok:
        flash(
            f"Image Assessment Master report executed successfully.\n"
            f"Saved to: {output_path}",
            "success",
        )
    else:
        flash(
            "Image Assessment Master report failed.\n"
            "Check Logs -> Error Logs for details.",
            "danger",
        )

    return redirect(url_for("index"))



# ========== LOGS UI ROUTES ==========
@app.route("/logs", methods=["GET"])
def logs_index():
    """
    Logs landing page - show both logs with quick stats.
    """
    err_exists = ERROR_LOG.exists()
    proc_exists = PROCESSED_LOG.exists()

    # quick size and last-modified
    def meta(p: Path):
        if not p.exists():
            return {"exists": False, "size": 0, "mtime": None}
        return {"exists": True, "size": p.stat().st_size, "mtime": datetime.utcfromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S UTC")}
    return render_template(
        "logs.html",
        error_meta=meta(ERROR_LOG),
        processed_meta=meta(PROCESSED_LOG),
    )

@app.route("/logs/error", methods=["GET", "POST"])
def logs_error():
    """
    View error log contents and allow clearing.
    """
    if request.method == "POST":
        action = request.form.get("action")
        if action == "clear":
            with _log_lock:
                if ERROR_LOG.exists():
                    ERROR_LOG.unlink()
            flash("Error log cleared.", "success")
            return redirect(url_for("logs_error"))

    data = tail_file(ERROR_LOG, max_chars=20000)
    return render_template("logs.html", view="error", content=data, error_meta={"exists": ERROR_LOG.exists()})

@app.route("/logs/processed", methods=["GET", "POST"])
def logs_processed():
    """
    View processed log contents and allow clearing.
    """
    if request.method == "POST":
        action = request.form.get("action")
        if action == "clear":
            with _log_lock:
                if PROCESSED_LOG.exists():
                    PROCESSED_LOG.unlink()
            flash("Processed log cleared.", "success")
            return redirect(url_for("logs_processed"))

    data = tail_file(PROCESSED_LOG, max_chars=20000)
    return render_template("logs.html", view="processed", content=data, processed_meta={"exists": PROCESSED_LOG.exists()})

@app.route("/logs/download/<which>", methods=["GET"])
def logs_download(which):
    """
    Download the full log file.
    """
    if which == "error":
        path = ERROR_LOG
    else:
        path = PROCESSED_LOG
    if not path.exists():
        flash("Log file not found.", "danger")
        return redirect(url_for("logs_index"))
    return send_file(str(path), as_attachment=True, download_name=path.name)

# ========== RUN APP ==========
if __name__ == "__main__":
    # debug True for local testing only
    app.run(host="0.0.0.0", port=5000, debug=True)
