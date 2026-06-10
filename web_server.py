="""Flask application for authentication, tremor analysis, and report history."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
from functools import wraps
from uuid import uuid4

from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
import requests
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from database import create_report
from database import create_user
from database import get_report_for_user
from database import get_user_by_email
from database import get_user_by_id
from database import init_db
from database import list_history_for_user
from database import list_reports_for_user
from database import create_admin
from database import get_admin_by_email
from database import get_admin_by_id
from database import list_all_reports
from database import get_all_reports_count
from database import get_report_by_id
from database import mark_report_shared
from database import update_report_phone_email
from report_sharing import send_report_email, send_report_sms

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)
SECRET_KEY_FILE = INSTANCE_DIR / ".flask_secret_key"

API_URL = "http://localhost:8000"
API_URL = os.environ.get("TREMOR_API_URL", API_URL)
ALLOWED_VIDEO = {"mp4", "avi", "mov", "mkv", "flv", "wmv", "webm"}
PASSWORD_RULE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{6,8}$")


def get_secret_key() -> str:
    env_key = os.environ.get("TREMOR_APP_SECRET_KEY")
    if env_key:
        return env_key

    if SECRET_KEY_FILE.exists():
        return SECRET_KEY_FILE.read_text(encoding="utf-8").strip()

    secret_key = secrets.token_hex(32)
    SECRET_KEY_FILE.write_text(secret_key, encoding="utf-8")
    return secret_key

app = Flask(__name__)
app.secret_key = get_secret_key()
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
init_db()


def allowed_video(filename: str):
    if "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in ALLOWED_VIDEO


def is_valid_password(password: str) -> bool:
    return bool(PASSWORD_RULE.match(password))


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            flash("Please login first to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def admin_login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.admin is None:
            flash("Please login as admin first to continue.", "warning")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped_view


def parse_report_row(row):
    # Ensure row is always a dict - properly handle sqlite3.Row objects
    if hasattr(row, 'keys'):
        # It's a sqlite3.Row object
        row = {key: row[key] for key in row.keys()}
    elif not isinstance(row, dict):
        try:
            row = dict(row)
        except (TypeError, ValueError):
            row = {}
    
    report = row

    def safe_json_load(raw_value, fallback):
        try:
            return json.loads(raw_value) if raw_value else fallback
        except (TypeError, ValueError, json.JSONDecodeError):
            return fallback

    report["first_aid"] = safe_json_load(report.get("first_aid_json"), [])
    report["food_habits"] = safe_json_load(report.get("food_habits_json"), [])
    report["lifestyle_recommendations"] = safe_json_load(report.get("lifestyle_recommendations_json"), [])
    report["possible_reasons"] = safe_json_load(report.get("possible_reasons_json"), [])
    report["doctor_suggestions"] = safe_json_load(report.get("doctor_suggestions_json"), {})
    report["severity_probabilities"] = safe_json_load(report.get("severity_probabilities_json"), {})
    report["model_probabilities"] = safe_json_load(report.get("model_probabilities_json"), {})
    report["metrics"] = safe_json_load(report.get("metrics_json"), {})
    return report


def save_uploaded_file(file_storage):
    original_name = secure_filename(file_storage.filename or "capture.webm")
    suffix = Path(original_name).suffix or ".webm"
    stored_name = f"{uuid4().hex}{suffix}"
    target = UPLOAD_FOLDER / stored_name
    file_storage.save(target)
    return original_name, stored_name, target


@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = get_user_by_id(user_id) if user_id else None
    
    admin_id = session.get("admin_id")
    g.admin = get_admin_by_id(admin_id) if admin_id else None


@app.route("/")
def home():
    if g.user:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not full_name:
            flash("Full name is required.", "error")
        elif not email:
            flash("Email is required.", "error")
        elif not password or not confirm_password:
            flash("Password fields are required.", "error")
        elif password != confirm_password:
            flash("Password and confirm password must match.", "error")
        elif not is_valid_password(password):
            flash(
                "Password must be 6 to 8 characters and include at least one uppercase letter, one lowercase letter, one number, and one special character.",
                "error",
            )
        elif get_user_by_email(email):
            flash("That email is already registered.", "error")
        else:
            create_user(full_name, email, generate_password_hash(password))
            flash("Registration successful! Please login.", "success")
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("analyze"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required.", "error")
        else:
            user = get_user_by_email(email)

            if user is None or not check_password_hash(user["password_hash"], password):
                flash("Invalid email or password.", "error")
            else:
                session.clear()
                session["user_id"] = user["id"]
                flash("Login successful.", "success")
                return redirect(url_for("analyze"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    try:
        reports = [parse_report_row(report) for report in list_reports_for_user(g.user["id"])]
    except Exception:
        reports = []
        flash("Some saved report data could not be loaded, so only the dashboard summary is shown.", "warning")
    recent_reports = reports[:3]
    severity_counts = {"low": 0, "medium": 0, "high": 0}
    for report in reports:
        severity_counts[report["severity"]] = severity_counts.get(report["severity"], 0) + 1
    latest_report = recent_reports[0] if recent_reports else None
    return render_template(
        "dashboard.html",
        reports=recent_reports,
        report_count=len(reports),
        latest_report=latest_report,
        severity_counts=severity_counts,
    )


@app.route("/analyze", methods=["GET", "POST"])
@login_required
def analyze():
    if request.method == "GET":
        return render_template("analyze.html")

    if "video_file" not in request.files:
        flash("Please upload or record a video before analyzing.", "error")
        return redirect(url_for("analyze"))

    file = request.files["video_file"]
    if file.filename == "":
        flash("Please choose a video file.", "error")
        return redirect(url_for("analyze"))

    if not allowed_video(file.filename):
        flash("Unsupported video format. Use MP4, MOV, AVI, MKV, FLV, WMV, or WebM.", "error")
        return redirect(url_for("analyze"))

    location = request.form.get("location", "").strip()
    source_type = request.form.get("source_type", "upload")
    quick_analysis = request.form.get("quick_analysis", "false").lower() == "true"

    original_name, stored_name, stored_path = save_uploaded_file(file)
    try:
        with open(stored_path, "rb") as handle:
            files = {"file": (original_name, handle, file.content_type or "video/mp4")}
            data = {}
            if location:
                data["location"] = location
            data["quick_analysis"] = "true" if quick_analysis else "false"
            data["source_type"] = source_type
            # Adjust timeout based on analysis type
            timeout = 60 if quick_analysis else 180
            response = requests.post(f"{API_URL}/classify/video", files=files, data=data, timeout=timeout)

        if response.status_code != 200:
            try:
                detail = response.json().get("detail", "The backend could not process this file.")
            except ValueError:
                detail = "The backend could not process this file."
            flash(f"Backend processing failed. {detail}", "error")
            return redirect(url_for("analyze"))

        payload = response.json()
        report_id = create_report(
            g.user["id"],
            {
                "source_type": source_type,
                "original_filename": original_name,
                "stored_filename": stored_name,
                "tremor_type": payload["predicted_pattern"],
                "severity": payload["severity"],
                "severity_confidence": payload["severity_confidence"],
                "analysis_method": payload.get("analysis_method", "model_fallback"),
                "recommendation_summary": payload["assistance"]["summary"],
                "first_aid": payload["assistance"]["first_aid"],
                "food_habits": payload["assistance"]["food_habits"],
                "possible_reasons": payload["assistance"]["possible_reasons"],
                "doctor_recommendation": payload["assistance"]["doctor_recommendation"],
                "medical_priority": payload["assistance"]["medical_priority"],
                "doctor_search_query": payload["assistance"]["doctor_suggestions"]["search_query"],
                "location": payload["assistance"]["doctor_suggestions"].get("location_used"),
                "lifestyle_recommendations": payload["assistance"].get("lifestyle_recommendations", []),
                "doctor_suggestions": payload["assistance"].get("doctor_suggestions", {}),
                "severity_probabilities": payload["severity_probabilities"],
                "model_probabilities": payload["model_probabilities"],
                "metrics": payload.get("mediapipe_metrics"),
            },
        )
        flash("Tremor report generated and saved to your history.", "success")
        return redirect(url_for("report_detail", report_id=report_id))
    except requests.Timeout:
        flash("Analysis timed out while waiting for the backend. Please try a shorter or clearer video.", "error")
        return redirect(url_for("analyze"))
    except requests.RequestException:
        flash("The backend API is currently unavailable. Start the backend and try again.", "error")
        return redirect(url_for("analyze"))
    except Exception:
        flash("Could not complete analysis because the uploaded recording could not be processed.", "error")
        return redirect(url_for("analyze"))


@app.route("/history")
@login_required
def history():
    reports = [parse_report_row(report) for report in list_reports_for_user(g.user["id"])]
    history_rows = list_history_for_user(g.user["id"])
    return render_template("history.html", reports=reports, history_rows=history_rows)


@app.route("/reports/<int:report_id>")
@login_required
def report_detail(report_id: int):
    report = get_report_for_user(g.user["id"], report_id)
    if report is None:
        flash("Report not found.", "error")
        return redirect(url_for("history"))
    return render_template("report_detail.html", report=parse_report_row(report))


@app.route("/api/health")
def health():
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        return jsonify({"status": "ok", "backend": response.json()})
    except Exception:
        return jsonify({"status": "backend unavailable"}), 503


# ============= ADMIN ROUTES =============

@app.route("/admin")
def admin_home():
    if g.admin:
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("admin_login"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if g.admin:
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required.", "error")
        else:
            admin = get_admin_by_email(email)

            if admin is None or not check_password_hash(admin["password_hash"], password):
                flash("Invalid admin email or password.", "error")
            else:
                session.clear()
                session["admin_id"] = admin["id"]
                flash("Admin login successful.", "success")
                return redirect(url_for("admin_dashboard"))

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("admin_login"))


@app.route("/admin/dashboard")
@admin_login_required
def admin_dashboard():
    """Admin dashboard showing all reports and statistics."""
    page = request.args.get("page", 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    try:
        reports_list = list_all_reports(limit=per_page, offset=offset)
        total_count = get_all_reports_count()
        total_pages = (total_count + per_page - 1) // per_page
        
        # Parse reports
        reports = []
        for report in reports_list:
            # Convert sqlite3.Row to dict
            if hasattr(report, 'keys'):
                report_dict = {key: report[key] for key in report.keys()}
            else:
                report_dict = dict(report) if not isinstance(report, dict) else report
            
            parsed = parse_report_row(report_dict)
            parsed["patient_name"] = report_dict.get("patient_name", "Unknown")
            parsed["user_email"] = report_dict.get("user_email", "Unknown")
            reports.append(parsed)
    except Exception as e:
        reports = []
        total_count = 0
        total_pages = 1
        flash(f"Error loading reports: {str(e)}", "error")

    return render_template(
        "admin_dashboard.html",
        reports=reports,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        admin_name=g.admin.get("full_name") if g.admin else "Admin",
    )


@app.route("/admin/report/<int:report_id>")
@admin_login_required
def admin_view_report(report_id: int):
    """Admin view individual report details."""
    try:
        report = get_report_by_id(report_id)
        if report is None:
            flash("Report not found.", "error")
            return redirect(url_for("admin_dashboard"))
        
        # Convert sqlite3.Row to dict
        if hasattr(report, 'keys'):
            report_dict = {key: report[key] for key in report.keys()}
        else:
            report_dict = dict(report) if not isinstance(report, dict) else report
        
        parsed_report = parse_report_row(report_dict)
        parsed_report["patient_name"] = report_dict.get("patient_name", "Unknown")
        parsed_report["user_email"] = report_dict.get("user_email", "Unknown")
        parsed_report["patient_phone"] = report_dict.get("patient_phone", "")
        parsed_report["patient_email"] = report_dict.get("patient_email", "")
        parsed_report["shared_via_email"] = report_dict.get("shared_via_email", 0)
        parsed_report["shared_via_phone"] = report_dict.get("shared_via_phone", 0)
        
        return render_template("admin_report_detail.html", report=parsed_report)
    except Exception as e:
        flash(f"Error loading report: {str(e)}", "error")
        return redirect(url_for("admin_dashboard"))


@app.route("/admin/report/<int:report_id>/share", methods=["POST"])
@admin_login_required
def admin_share_report(report_id: int):
    """Admin share report via email or phone."""
    try:
        phone = request.form.get("phone", "").strip()
        email_addr = request.form.get("email", "").strip()
        share_method = request.form.get("share_method", "").strip()
        
        report = get_report_by_id(report_id)
        if report is None:
            return jsonify({"success": False, "error": "Report not found"}), 404
        
        report_dict = dict(report) if not isinstance(report, dict) else report
        patient_name = report_dict.get("patient_name", "Patient")
        success = False
        via_email = False
        via_phone = False
        
        # Prepare report data for sharing
        report_data = parse_report_row(report_dict)
        report_data["tremor_type"] = report_dict.get("tremor_type", "Unknown")
        report_data["severity"] = report_dict.get("severity", "Unknown")
        report_data["severity_confidence"] = report_dict.get("severity_confidence", 0)
        report_data["recommendation_summary"] = report_dict.get("recommendation_summary", "")
        report_data["doctor_recommendation"] = report_dict.get("doctor_recommendation", "")
        report_data["medical_priority"] = report_dict.get("medical_priority", "")
        report_data["created_at"] = report_dict.get("created_at", "")
        
        # Send via email
        if share_method == "email" and email_addr:
            if send_report_email(email_addr, patient_name, report_data):
                via_email = True
                success = True
                flash(f"✓ Report sent to {email_addr} successfully!", "success")
            else:
                flash("Failed to send email. Check your email configuration.", "error")
        
        # Send via SMS
        elif share_method == "phone" and phone:
            if send_report_sms(phone, report_data):
                via_phone = True
                success = True
                flash(f"✓ Report sent to {phone} successfully!", "success")
            else:
                flash("Failed to send SMS. Check your SMS configuration.", "error")
        
        # Update database
        if success:
            update_report_phone_email(report_id, phone=phone if via_phone else None, email=email_addr if via_email else None)
            mark_report_shared(report_id, via_email=via_email, via_phone=via_phone)
        
        return redirect(url_for("admin_view_report", report_id=report_id))
    except Exception as e:
        flash(f"Error sharing report: {str(e)}", "error")
        return redirect(url_for("admin_view_report", report_id=report_id))


@app.route("/favicon.ico")
def favicon():
    return ("", 204)


if __name__ == "__main__":
    host = os.environ.get("WEB_HOST", "0.0.0.0")
    port = int(os.environ.get("WEB_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"

    print("\n" + "=" * 60)
    print("TREMOR SEVERITY APPLICATION")
    print("=" * 60)
    print(f"Backend API: {API_URL}")
    print(f"Web Server: http://{host}:{port}")
    print("=" * 60)
    if os.environ.get("OPEN_BROWSER", "true").lower() == "true":
        print(f"\nOpening browser to http://localhost:{port}...")
        print("=" * 60 + "\n")
        import webbrowser

        webbrowser.open(f"http://localhost:{port}")
    else:
        print("\nBrowser auto-open disabled.")
        print("=" * 60 + "\n")

    app.run(debug=debug, host=host, port=port, use_reloader=False)
