"""
database/registration_db.py — MySQL version
Student registration, rankings, schedules, bank requests, weak topics
"""
import mysql.connector
from database.db_setup import (get_connection, dict_cursor,
                                hash_password, generate_password)


# ── STUDENT REGISTRATION ──────────────────────────────────────────────────────

def register_student(full_name: str, email: str, phone: str) -> dict:
    conn   = get_connection()
    cursor = dict_cursor(conn)

    cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
    if cursor.fetchone():
        conn.close()
        return {"success": False, "error": "This email is already registered. Please login."}

    base = full_name.lower().strip().replace(" ", "_")[:12]
    username = base; suffix = 1
    while True:
        cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
        if not cursor.fetchone(): break
        username = f"{base}{suffix}"; suffix += 1

    raw_password = generate_password(8)
    try:
        cursor.execute("""
            INSERT INTO users (username, password, role, full_name, email, phone)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (username, hash_password(raw_password), "student", full_name, email, phone))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return {"success": True, "user_id": user_id, "username": username,
                "password": raw_password, "full_name": full_name, "email": email}
    except mysql.connector.IntegrityError as e:
        conn.close()
        return {"success": False, "error": str(e)}


def get_student_by_email(email: str):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("SELECT * FROM users WHERE email=%s AND role='student'", (email,))
    row = cursor.fetchone(); conn.close()
    return row


# ── RANKINGS ──────────────────────────────────────────────────────────────────

def get_rankings_for_bank(bank_id: int) -> list:
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT u.id, u.username, u.full_name, u.email,
               COUNT(es.id)           AS total_exams,
               ROUND(AVG(es.score),2) AS avg_score,
               MAX(es.score)          AS best_score,
               SUM(es.passed)         AS total_passed
        FROM users u
        JOIN exam_sessions es ON es.student_id = u.id
        WHERE es.bank_id=%s AND es.completed_at IS NOT NULL AND u.role='student'
        GROUP BY u.id, u.username, u.full_name, u.email
        ORDER BY avg_score DESC, best_score DESC
    """, (bank_id,))
    rows = cursor.fetchall(); conn.close()
    return [{"rank": i+1, **r} for i, r in enumerate(rows)]


def get_overall_rankings() -> list:
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT u.id, u.username, u.full_name, u.email,
               COUNT(DISTINCT es.bank_id)  AS banks_attempted,
               COUNT(es.id)                AS total_exams,
               ROUND(AVG(es.score),2)      AS avg_score,
               MAX(es.score)               AS best_score,
               SUM(es.passed)              AS total_passed
        FROM users u
        JOIN exam_sessions es ON es.student_id = u.id
        WHERE es.completed_at IS NOT NULL AND u.role='student'
        GROUP BY u.id, u.username, u.full_name, u.email
        ORDER BY avg_score DESC, total_passed DESC
    """)
    rows = cursor.fetchall(); conn.close()
    return [{"rank": i+1, **r} for i, r in enumerate(rows)]


# ── RESULT SCHEDULES ──────────────────────────────────────────────────────────

def create_result_schedule(bank_id, send_date, send_time, message, admin_id) -> int:
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        INSERT INTO result_schedules (bank_id, send_date, send_time, message, created_by)
        VALUES (%s,%s,%s,%s,%s)
    """, (bank_id, send_date, send_time, message, admin_id))
    sid = cursor.lastrowid
    conn.commit(); conn.close()
    return sid


def get_all_schedules():
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT rs.*, qb.name AS bank_name, u.username AS created_by_name
        FROM result_schedules rs
        LEFT JOIN question_banks qb ON rs.bank_id    = qb.id
        LEFT JOIN users u           ON rs.created_by = u.id
        ORDER BY rs.send_date DESC
    """)
    rows = cursor.fetchall(); conn.close()
    return rows


def get_pending_schedules(today: str):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute(
        "SELECT * FROM result_schedules WHERE send_date <= %s AND sent=0",
        (today,)
    )
    rows = cursor.fetchall(); conn.close()
    return rows


def mark_schedule_sent(schedule_id: int):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("UPDATE result_schedules SET sent=1 WHERE id=%s", (schedule_id,))
    conn.commit(); conn.close()


def delete_schedule(schedule_id: int):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("DELETE FROM result_schedules WHERE id=%s", (schedule_id,))
    conn.commit(); conn.close()


# ── BANK REQUESTS ─────────────────────────────────────────────────────────────

def submit_bank_request(student_id: int, subject: str, description: str) -> int:
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute(
        "INSERT INTO bank_requests (student_id, subject, description) VALUES (%s,%s,%s)",
        (student_id, subject, description)
    )
    req_id = cursor.lastrowid
    conn.commit(); conn.close()
    return req_id


def get_all_bank_requests():
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT br.*, u.username, u.full_name, u.email
        FROM bank_requests br
        JOIN users u ON br.student_id = u.id
        ORDER BY br.requested_at DESC
    """)
    rows = cursor.fetchall(); conn.close()
    return rows


def get_student_bank_requests(student_id: int):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute(
        "SELECT * FROM bank_requests WHERE student_id=%s ORDER BY requested_at DESC",
        (student_id,)
    )
    rows = cursor.fetchall(); conn.close()
    return rows


def update_bank_request_status(request_id: int, status: str, note: str = ""):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        UPDATE bank_requests SET status=%s, trainer_note=%s, updated_at=NOW()
        WHERE id=%s
    """, (status, note, request_id))
    conn.commit(); conn.close()


# ── WEAK TOPICS ───────────────────────────────────────────────────────────────

def get_weak_topics(student_id: int, bank_id: int = None) -> list:
    conn   = get_connection()
    cursor = dict_cursor(conn)
    if bank_id:
        cursor.execute("""
            SELECT q.question_text, COUNT(*) AS wrong_count
            FROM exam_answers ea
            JOIN questions q      ON ea.question_id = q.id
            JOIN exam_sessions es ON ea.session_id  = es.id
            WHERE es.student_id=%s AND es.bank_id=%s AND ea.is_correct=0
            GROUP BY q.id, q.question_text
            ORDER BY wrong_count DESC LIMIT 10
        """, (student_id, bank_id))
    else:
        cursor.execute("""
            SELECT q.question_text, COUNT(*) AS wrong_count
            FROM exam_answers ea
            JOIN questions q      ON ea.question_id = q.id
            JOIN exam_sessions es ON ea.session_id  = es.id
            WHERE es.student_id=%s AND ea.is_correct=0
            GROUP BY q.id, q.question_text
            ORDER BY wrong_count DESC LIMIT 10
        """, (student_id,))
    rows = cursor.fetchall(); conn.close()
    return [r["question_text"] for r in rows]


def get_weak_subjects(student_id: int) -> list:
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT qb.subject, qb.name AS bank_name,
               ROUND(AVG(es.score),1) AS avg_score,
               COUNT(es.id) AS attempts
        FROM exam_sessions es
        JOIN question_banks qb ON es.bank_id = qb.id
        WHERE es.student_id=%s AND es.completed_at IS NOT NULL
        GROUP BY qb.id, qb.subject, qb.name
        ORDER BY avg_score ASC LIMIT 5
    """, (student_id,))
    rows = cursor.fetchall(); conn.close()
    return rows


def get_students_for_bank(bank_id: int) -> list:
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT DISTINCT u.id, u.username, u.full_name, u.email,
               es.score, es.correct_q, es.total_q, es.passed, es.completed_at
        FROM users u
        JOIN exam_sessions es ON es.student_id = u.id
        WHERE es.bank_id=%s AND es.completed_at IS NOT NULL
        ORDER BY es.score DESC
    """, (bank_id,))
    rows = cursor.fetchall(); conn.close()
    return rows


def get_all_student_emails() -> list:
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT id, username, full_name, email FROM users
        WHERE role='student' AND is_active=1 AND email IS NOT NULL
    """)
    rows = cursor.fetchall(); conn.close()
    return rows
