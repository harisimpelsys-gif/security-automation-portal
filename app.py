from flask import Flask, render_template, request, redirect, url_for, flash, session
import subprocess
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "change-this-key"

# ========== FILE UPLOAD CONFIG ==========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"xlsx", "xls", "csv"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ========== COMMAND RUNNER ==========
def run_command(cmd, cwd=None):
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=False,
        )
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, (
                f"RETURN CODE: {result.returncode}\n\n"
                f"STDERR:\n{result.stderr}\n\n"
                f"STDOUT:\n{result.stdout}"
            )
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
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(save_path)

        session["uploaded_report"] = save_path
        session["last_output"] = None
        session["last_status"] = None

        flash(f"Report uploaded: {filename}", "success")
        return redirect(url_for("index"))
    else:
        flash("File type not allowed. Upload .xlsx, .xls or .csv", "danger")
        return redirect(url_for("index"))


# ========== VULNERABILITY DEVOPS REPORT ==========
@app.route("/run/vuln/devops", methods=["POST"])
def run_vuln_devops():
    report_path = session.get("uploaded_report")
    if not report_path:
        flash("Upload a report first.", "danger")
        return redirect(url_for("index"))

    script_path = r"C:\Users\mohammedharis.f\Downloads\Vul_Automation\split_vulns.py"

    output_dir = r"C:\Users\mohammedharis.f\Desktop\website\Vulnarability_devops_report"
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "vulnerabilities_by_application.xlsx")

    cmd = [
        "python",
        script_path,
        report_path,
        "--output",
        output_path,
    ]

    ok, output = run_command(cmd)

    session["last_output"] = output
    session["last_status"] = "success" if ok else "error"

    if ok:
        flash(
            "Vulnerability DevOps report executed successfully.\nSaved to:\n"
            + output_path,
            "success",
        )
    else:
        flash("Vulnerability DevOps report failed. Check details below.", "danger")

    return redirect(url_for("index"))


# ========== VULNERABILITY MASTER REPORT ==========
@app.route("/run/vuln/master", methods=["POST"])
def run_vuln_master():
    report_path = session.get("uploaded_report")
    if not report_path:
        flash("Upload a report first.", "danger")
        return redirect(url_for("index"))

    script_path = r"C:\Users\mohammedharis.f\Downloads\Vul_Automation\automated_master_report.py"

    output_dir = r"C:\Users\mohammedharis.f\Desktop\website\Vulnarability_master_report"
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "Master_Report_Automated.xlsx")

    cmd = [
        "python",
        script_path,
        "--input",
        report_path,
        "--output",
        output_path,
    ]

    ok, output = run_command(cmd)

    session["last_output"] = output
    session["last_status"] = "success" if ok else "error"

    if ok:
        flash(
            "Master Vulnerability report executed successfully.\nSaved to:\n"
            + output_path,
            "success",
        )
    else:
        flash("Master Vulnerability report failed. Check details below.", "danger")

    return redirect(url_for("index"))


# ========== MISCONFIGURATION DEVOPS REPORT ==========
@app.route("/run/misconfig/devops", methods=["POST"])
def run_misconfig_devops():
    report_path = session.get("uploaded_report")
    if not report_path:
        flash("Upload a report first.", "danger")
        return redirect(url_for("index"))

    script_path = r"C:\Users\mohammedharis.f\Downloads\MisConfig_Automation\segregate_misconfigs.py"

    output_dir = r"C:\Users\mohammedharis.f\Desktop\website\Misconfig_devops_report"
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "misconfig_segregated.xlsx")

    cmd = [
        "python",
        script_path,
        report_path,
        output_path,
    ]

    ok, output = run_command(cmd)

    session["last_output"] = output
    session["last_status"] = "success" if ok else "error"

    if ok:
        flash(
            "Misconfiguration DevOps report executed successfully.\nSaved to:\n"
            + output_path,
            "success",
        )
    else:
        flash("Misconfiguration DevOps report failed. Check details below.", "danger")

    return redirect(url_for("index"))


# ========== MISCONFIGURATION AHA / PMP / AZURE / PP REPORT ==========
@app.route("/run/misconfig/aha", methods=["POST"])
def run_misconfig_aha():
    report_path = session.get("uploaded_report")
    if not report_path:
        flash("Upload a report first.", "danger")
        return redirect(url_for("index"))

    script_path = r"C:\Users\mohammedharis.f\Downloads\MisConfig_Automation\Misconfigp2.py"

    output_dir = r"C:\Users\mohammedharis.f\Desktop\website\Misconfig_AHA_PMP_AZURE_PP_report"
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "Misconfig_AHA_PMP_AZURE_PP.xlsx")

    cmd = [
        "python",
        script_path,
        "--input",
        report_path,
        "--output",
        output_path,
    ]

    ok, output = run_command(cmd)

    session["last_output"] = output
    session["last_status"] = "success" if ok else "error"

    if ok:
        flash(
            "Misconfiguration AHA/PMP/AZURE/PP report executed successfully.\nSaved to:\n"
            + output_path,
            "success",
        )
    else:
        flash("Misconfiguration AHA/PMP/AZURE/PP report failed. Check details below.", "danger")

    return redirect(url_for("index"))


# ========== MISCONFIGURATION FINAL REPORT ==========
@app.route("/run/misconfig/final", methods=["POST"])
def run_misconfig_final():
    aha_output_path = (
        r"C:\Users\mohammedharis.f\Desktop\website"
        r"\Misconfig_AHA_PMP_AZURE_PP_report\Misconfig_AHA_PMP_AZURE_PP.xlsx"
    )

    if not os.path.exists(aha_output_path):
        session["last_output"] = (
            f"Required input not found:\n{aha_output_path}\n\n"
            "Run 'Misconfiguration AHA / PMP / AZURE / PP Report' first."
        )
        session["last_status"] = "error"
        flash(
            "AHA/PMP/AZURE/PP report not found. Run that step before Final Misconfig.",
            "danger",
        )
        return redirect(url_for("index"))

    script_path = r"C:\Users\mohammedharis.f\Downloads\MisConfig_Automation\classify_misconfigs.py"
    rules_folder = r"C:\Users\mohammedharis.f\Downloads\MisConfig_Automation\rules"

    output_dir = r"C:\Users\mohammedharis.f\Desktop\website\Misconfig_final_report"
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(
        output_dir, "Misconfig_AHA_PMP_AZURE_PP_actionable_final.xlsx"
    )

    cmd = [
        "python",
        script_path,
        "--report",
        aha_output_path,
        "--rules-folder",
        rules_folder,
        "--output",
        output_path,
    ]

    ok, output = run_command(cmd)

    session["last_output"] = output
    session["last_status"] = "success" if ok else "error"

    if ok:
        flash(
            "Misconfiguration Final report executed successfully.\nSaved to:\n"
            + output_path,
            "success",
        )
    else:
        flash("Misconfiguration Final report failed. Check details below.", "danger")

    return redirect(url_for("index"))


# ========== MISCONFIGURATION MASTER REPORT ==========
@app.route("/run/misconfig/master", methods=["POST"])
def run_misconfig_master():
    # this step works on the final actionable file from the previous step
    final_report_path = (
        r"C:\Users\mohammedharis.f\Desktop\website"
        r"\Misconfig_final_report\Misconfig_AHA_PMP_AZURE_PP_actionable_final.xlsx"
    )

    if not os.path.exists(final_report_path):
        session["last_output"] = (
            f"Required input not found:\n{final_report_path}\n\n"
            "Run 'Misconfiguration Final Report' first."
        )
        session["last_status"] = "error"
        flash(
            "Final misconfiguration report not found. Run 'Misconfiguration Final Report' first.",
            "danger",
        )
        return redirect(url_for("index"))

    script_path = r"C:\Users\mohammedharis.f\Downloads\MisConfig_Automation\automate_master_report.py"

    output_dir = r"C:\Users\mohammedharis.f\Desktop\website\Misconfig_master_report"
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "Misconfig_Master_Report_Automated.xlsx")

    # usage:
    # python automate_master_report.py --input Final_report.xlsx --output Master_Report_Automated.xlsx
    cmd = [
        "python",
        script_path,
        "--input",
        final_report_path,
        "--output",
        output_path,
    ]

    ok, output = run_command(cmd)

    session["last_output"] = output
    session["last_status"] = "success" if ok else "error"

    if ok:
        flash(
            "Misconfiguration Master report executed successfully.\nSaved to:\n"
            + output_path,
            "success",
        )
    else:
        flash("Misconfiguration Master report failed. Check details below.", "danger")

    return redirect(url_for("index"))


# ========== RUN APP ==========
if __name__ == "__main__":
    app.run(debug=True)
