"""SQLite helpers for users, tremor reports, and report history."""

from __future__ import annotations

from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)
DB_PATH = INSTANCE_DIR / "tremor_app.db"


@contextmanager
def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db():
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tremor_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                source_type TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                tremor_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                severity_confidence REAL NOT NULL,
                analysis_method TEXT NOT NULL,
                recommendation_summary TEXT NOT NULL,
                first_aid_json TEXT NOT NULL,
                food_habits_json TEXT NOT NULL,
                possible_reasons_json TEXT NOT NULL,
                doctor_recommendation TEXT NOT NULL,
                medical_priority TEXT NOT NULL,
                doctor_search_query TEXT NOT NULL,
                location TEXT,
                lifestyle_recommendations_json TEXT,
                doctor_suggestions_json TEXT,
                severity_probabilities_json TEXT NOT NULL,
                model_probabilities_json TEXT NOT NULL,
                metrics_json TEXT,
                patient_phone TEXT,
                patient_email TEXT,
                shared_via_email BOOLEAN DEFAULT 0,
                shared_via_phone BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS report_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                report_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (report_id) REFERENCES tremor_reports(id)
            );
            """
        )
        existing_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(tremor_reports)").fetchall()
        }
        if "location" not in existing_columns:
            connection.execute("ALTER TABLE tremor_reports ADD COLUMN location TEXT")
        if "lifestyle_recommendations_json" not in existing_columns:
            connection.execute("ALTER TABLE tremor_reports ADD COLUMN lifestyle_recommendations_json TEXT")
        if "doctor_suggestions_json" not in existing_columns:
            connection.execute("ALTER TABLE tremor_reports ADD COLUMN doctor_suggestions_json TEXT")
        if "patient_phone" not in existing_columns:
            connection.execute("ALTER TABLE tremor_reports ADD COLUMN patient_phone TEXT")
        if "patient_email" not in existing_columns:
            connection.execute("ALTER TABLE tremor_reports ADD COLUMN patient_email TEXT")
        if "shared_via_email" not in existing_columns:
            connection.execute("ALTER TABLE tremor_reports ADD COLUMN shared_via_email BOOLEAN DEFAULT 0")
        if "shared_via_phone" not in existing_columns:
            connection.execute("ALTER TABLE tremor_reports ADD COLUMN shared_via_phone BOOLEAN DEFAULT 0")


def create_user(full_name: str, email: str, password_hash: str):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO users (full_name, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (full_name, email.lower().strip(), password_hash),
        )
        return cursor.lastrowid


def get_user_by_email(email: str):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.lower().strip(),),
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def create_report(user_id: int, report_payload: dict):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO tremor_reports (
                user_id, source_type, original_filename, stored_filename, tremor_type,
                severity, severity_confidence, analysis_method, recommendation_summary,
                first_aid_json, food_habits_json, possible_reasons_json,
                doctor_recommendation, medical_priority, doctor_search_query, location,
                lifestyle_recommendations_json, doctor_suggestions_json,
                severity_probabilities_json, model_probabilities_json, metrics_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                report_payload["source_type"],
                report_payload["original_filename"],
                report_payload["stored_filename"],
                report_payload["tremor_type"],
                report_payload["severity"],
                report_payload["severity_confidence"],
                report_payload["analysis_method"],
                report_payload["recommendation_summary"],
                json.dumps(report_payload["first_aid"]),
                json.dumps(report_payload["food_habits"]),
                json.dumps(report_payload["possible_reasons"]),
                report_payload["doctor_recommendation"],
                report_payload["medical_priority"],
                report_payload["doctor_search_query"],
                report_payload.get("location"),
                json.dumps(report_payload.get("lifestyle_recommendations") or []),
                json.dumps(report_payload.get("doctor_suggestions") or {}),
                json.dumps(report_payload["severity_probabilities"]),
                json.dumps(report_payload["model_probabilities"]),
                json.dumps(report_payload.get("metrics") or {}),
            ),
        )
        report_id = cursor.lastrowid
        connection.execute(
            """
            INSERT INTO report_history (user_id, report_id, action)
            VALUES (?, ?, ?)
            """,
            (user_id, report_id, "created"),
        )
        return report_id


def list_reports_for_user(user_id: int):
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT *
            FROM tremor_reports
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()


def get_report_for_user(user_id: int, report_id: int):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM tremor_reports
            WHERE user_id = ? AND id = ?
            """,
            (user_id, report_id),
        ).fetchone()
        return dict(row) if row else None


def list_history_for_user(user_id: int):
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT report_history.*, tremor_reports.severity, tremor_reports.tremor_type,
                   tremor_reports.analysis_method
            FROM report_history
            JOIN tremor_reports ON tremor_reports.id = report_history.report_id
            WHERE report_history.user_id = ?
            ORDER BY report_history.created_at DESC, report_history.id DESC
            """,
            (user_id,),
        ).fetchall()
        # Convert sqlite3.Row objects to dicts for consistent API
        return [dict(row) for row in rows]


# ============= ADMIN FUNCTIONS =============
def create_admin(full_name: str, email: str, password_hash: str):
    """Create a new admin user."""
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO admin_users (full_name, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (full_name, email.lower().strip(), password_hash),
        )
        return cursor.lastrowid


def get_admin_by_email(email: str):
    """Get admin user by email."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM admin_users WHERE email = ?",
            (email.lower().strip(),),
        ).fetchone()
        return dict(row) if row else None


def get_admin_by_id(admin_id: int):
    """Get admin user by ID."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM admin_users WHERE id = ?",
            (admin_id,),
        ).fetchone()
        return dict(row) if row else None


def list_all_reports(limit: int = 1000, offset: int = 0):
    """Get all reports (admin access) with pagination."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT tr.*, u.full_name as patient_name, u.email as user_email
            FROM tremor_reports tr
            JOIN users u ON tr.user_id = u.id
            ORDER BY tr.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        # Convert sqlite3.Row objects to dicts for consistent API
        return [dict(row) for row in rows]


def get_all_reports_count():
    """Get total count of all reports."""
    with get_connection() as connection:
        result = connection.execute("SELECT COUNT(*) as count FROM tremor_reports").fetchone()
        return dict(result)["count"] if result else 0


def get_report_by_id(report_id: int):
    """Get any report by ID (admin access)."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT tr.*, u.full_name as patient_name, u.email as user_email
            FROM tremor_reports tr
            JOIN users u ON tr.user_id = u.id
            WHERE tr.id = ?
            """,
            (report_id,),
        ).fetchone()
        return dict(row) if row else None


def update_report_phone_email(report_id: int, phone: str = None, email: str = None):
    """Update patient contact info for a report."""
    with get_connection() as connection:
        if phone and email:
            connection.execute(
                "UPDATE tremor_reports SET patient_phone = ?, patient_email = ? WHERE id = ?",
                (phone, email, report_id),
            )
        elif phone:
            connection.execute("UPDATE tremor_reports SET patient_phone = ? WHERE id = ?", (phone, report_id))
        elif email:
            connection.execute("UPDATE tremor_reports SET patient_email = ? WHERE id = ?", (email, report_id))


def mark_report_shared(report_id: int, via_email: bool = False, via_phone: bool = False):
    """Mark report as shared via email or phone."""
    with get_connection() as connection:
        if via_email:
            connection.execute("UPDATE tremor_reports SET shared_via_email = 1 WHERE id = ?", (report_id,))
        if via_phone:
            connection.execute("UPDATE tremor_reports SET shared_via_phone = 1 WHERE id = ?", (report_id,))
