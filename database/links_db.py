"""
database/links_db.py — MySQL version
Exam links, access requests, star ratings, question plans, analytics
"""
import mysql.connector
from database.db_setup import (get_connection, dict_cursor,
                                hash_password, generate_password, generate_exam_token)
import os

BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8501")

PLAN_LIMITS = {"basic": 200, "standard": 500, "premium": 2000, "unlimited": 999999}

# ── STAR RATING ───────────────────────────────────────────────────────────────

def compute_star_rating(avg_score) -> int:
    s = avg_score or 0
    if s >= 90: return 5
    if s >= 75: return 4
    if s >= 60: return 3
    if s >= 40: return 2
    return 1


# ── EXAM LINKS ────────────────────────────────────────────────────────────────

def create_exam_link(bank_id, trainer_id, title, description, time_limit, expires_at=None):
    token = generate_exam_token()
    conn  = get_connection(); cursor = dict_cursor(conn)
    cursor.execute("""
        INSERT INTO exam_links (bank_id, trainer_id, token, title, description,
                                time_limit_mins, expires_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (bank_id, trainer_id, token, title, description, time_limit, expires_at))
    conn.commit(); conn.close()
    return token, f"{BASE_URL}/?exam_token={token}"


def get_link_by_token(token: str):
    conn  = get_connection(); cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT el.*, qb.name AS bank_name, qb.subject, u.username AS trainer_name
        FROM exam_links el
        JOIN question_banks qb ON el.bank_id    = qb.id
        JOIN users u           ON el.trainer_id = u.id
        WHERE el.token=%s AND el.is_active=1
    """, (token,))
    row = cursor.fetchone(); conn.close()
    return row


def get_trainer_links(trainer_id: int):
    conn  = get_connection(); cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT el.*, qb.name AS bank_name,
               COUNT(DISTINCT lar.id) AS total_requests,
               SUM(CASE WHEN lar.status='approved' THEN 1 ELSE 0 END) AS approved
        FROM exam_links el
        JOIN question_banks qb ON el.bank_id = qb.id
        LEFT JOIN link_access_requests lar ON lar.link_id = el.id
        WHERE el.trainer_id=%s
        GROUP BY el.id, el.bank_id, el.trainer_id, el.token, el.title,
                 el.description, el.is_active, el.time_limit_mins,
                 el.created_at, el.expires_at, qb.name
        ORDER BY el.created_at DESC
    """, (trainer_id,))
    rows = cursor.fetchall(); conn.close()
    return rows


def deactivate_link(link_id: int):
    conn  = get_connection(); cursor = dict_cursor(conn)
    cursor.execute("UPDATE exam_links SET is_active=0 WHERE id=%s", (link_id,))
    conn.commit(); conn.close()


# ── ACCESS REQUESTS ───────────────────────────────────────────────────────────

def submit_access_request(link_id: int, roll_number: str, full_name: str):
    conn  = get_connection(); cursor = dict_cursor(conn)
    cursor.execute(
        "SELECT id FROM link_access_requests WHERE link_id=%s AND roll_number=%s",
        (link_id, roll_number)
    )
    if cursor.fetchone():
        conn.close()
        return None, "You already submitted a request for this exam."
    cursor.execute("""
        INSERT INTO link_access_requests (link_id, roll_number, full_name)
        VALUES (%s,%s,%s)
    """, (link_id, roll_number, full_name))
    req_id = cursor.lastrowid
    conn.commit(); conn.close()
    return req_id, "Request submitted! Wait for trainer approval."


def get_link_requests(link_id: int = None, trainer_id: int = None):
    conn  = get_connection(); cursor = dict_cursor(conn)
    if link_id:
        cursor.execute("""
            SELECT lar.*, el.title AS exam_title, el.bank_id
            FROM link_access_requests lar
            JOIN exam_links el ON lar.link_id = el.id
            WHERE lar.link_id=%s ORDER BY lar.requested_at DESC
        """, (link_id,))
    else:
        cursor.execute("""
            SELECT lar.*, el.title AS exam_title, el.bank_id, el.token
            FROM link_access_requests lar
            JOIN exam_links el ON lar.link_id = el.id
            WHERE el.trainer_id=%s ORDER BY lar.requested_at DESC
        """, (trainer_id,))
    rows = cursor.fetchall(); conn.close()
    return rows


def approve_access_request(req_id: int):
    conn  = get_connection(); cursor = dict_cursor(conn)
    cursor.execute("SELECT * FROM link_access_requests WHERE id=%s", (req_id,))
    req = cursor.fetchone()
    if not req:
        conn.close(); return None, "Request not found."

    roll  = req["roll_number"]
    fname = req["full_name"]
    uname = fname.lower().strip().replace(" ", "_")[:14]

    # Ensure unique username
    base = uname; i = 1
    while True:
        cursor.execute("SELECT id FROM users WHERE username=%s", (uname,))
        if not cursor.fetchone(): break
        uname = f"{base}{i}"; i += 1

    # Check roll already registered
    cursor.execute("SELECT id, username FROM users WHERE roll_number=%s", (roll,))
    existing = cursor.fetchone()

    if not existing:
        cursor.execute("""
            INSERT INTO users (username, password, role, full_name, roll_number, is_active)
            VALUES (%s,%s,%s,%s,%s,1)
        """, (uname, hash_password(roll), "student", fname, roll))
        student_id = cursor.lastrowid
    else:
        student_id = existing["id"]
        uname      = existing["username"]

    cursor.execute(
        "UPDATE link_access_requests SET status='approved', student_id=%s WHERE id=%s",
        (student_id, req_id)
    )
    conn.commit(); conn.close()
    return {"username": uname, "password": roll,
            "student_id": student_id, "full_name": fname, "roll_number": roll}, "Approved"


def reject_access_request(req_id: int):
    conn  = get_connection(); cursor = dict_cursor(conn)
    cursor.execute("UPDATE link_access_requests SET status='rejected' WHERE id=%s", (req_id,))
    conn.commit(); conn.close()


def check_student_approved(link_id: int, student_id: int) -> bool:
    conn  = get_connection(); cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT id FROM link_access_requests
        WHERE link_id=%s AND student_id=%s AND status='approved'
    """, (link_id, student_id))
    row = cursor.fetchone(); conn.close()
    return row is not None


# ── STAR RATINGS ──────────────────────────────────────────────────────────────

def update_star_ratings_for_student(student_id: int):
    conn  = get_connection(); cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT bank_id, ROUND(AVG(score),2) AS avg_score
        FROM exam_sessions
        WHERE student_id=%s AND completed_at IS NOT NULL
        GROUP BY bank_id
    """, (student_id,))
    rows = cursor.fetchall()
    for row in rows:
        stars = compute_star_rating(row["avg_score"])
        cursor.execute("""
            INSERT INTO star_ratings (student_id, bank_id, stars, avg_score)
            VALUES (%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
            stars=VALUES(stars), avg_score=VALUES(avg_score), computed_at=NOW()
        """, (student_id, row["bank_id"], stars, row["avg_score"]))
    conn.commit(); conn.close()


def get_bank_star_leaderboard(bank_id: int):
    conn  = get_connection(); cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT sr.stars, sr.avg_score, u.username, u.full_name, u.roll_number, u.email
        FROM star_ratings sr
        JOIN users u ON sr.student_id = u.id
        WHERE sr.bank_id=%s ORDER BY sr.avg_score DESC
    """, (bank_id,))
    rows = cursor.fetchall(); conn.close()
    return rows


# ── QUESTION PLANS ────────────────────────────────────────────────────────────

def get_trainer_plan(trainer_id: int) -> dict:
    conn  = get_connection(); cursor = dict_cursor(conn)
    cursor.execute("SELECT * FROM question_plans WHERE trainer_id=%s", (trainer_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("""
            INSERT IGNORE INTO question_plans (trainer_id, plan_type, questions_limit)
            VALUES (%s,'basic',200)
        """, (trainer_id,))
        conn.commit()
        cursor.execute("SELECT * FROM question_plans WHERE trainer_id=%s", (trainer_id,))
        row = cursor.fetchone()
    conn.close()
    return row


def can_generate(trainer_id: int, count: int):
    plan      = get_trainer_plan(trainer_id)
    remaining = plan["questions_limit"] - plan["questions_used"]
    return remaining >= count, remaining


def use_quota(trainer_id: int, count: int):
    conn  = get_connection(); cursor = dict_cursor(conn)
    cursor.execute(
        "UPDATE question_plans SET questions_used=questions_used+%s WHERE trainer_id=%s",
        (count, trainer_id)
    )
    conn.commit(); conn.close()


def upgrade_plan(trainer_id: int, plan_type: str):
    limit = PLAN_LIMITS.get(plan_type, 200)
    conn  = get_connection(); cursor = dict_cursor(conn)
    cursor.execute("""
        UPDATE question_plans
        SET plan_type=%s, questions_limit=%s, questions_used=0
        WHERE trainer_id=%s
    """, (plan_type, limit, trainer_id))
    conn.commit(); conn.close()


# ── ANALYTICS FOR ADMIN ───────────────────────────────────────────────────────

def get_trainer_exam_report(trainer_id: int):
    conn  = get_connection(); cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT qb.name AS bank_name, qb.subject,
               u.username, u.full_name, u.roll_number, u.email,
               COUNT(es.id)            AS attempts,
               ROUND(AVG(es.score),2)  AS avg_score,
               MAX(es.score)           AS highest_score,
               MIN(es.score)           AS lowest_score,
               SUM(es.passed)          AS passed_count
        FROM question_banks qb
        JOIN exam_sessions es ON es.bank_id    = qb.id
        JOIN users u          ON es.student_id = u.id
        WHERE qb.created_by=%s AND es.completed_at IS NOT NULL
        GROUP BY qb.id, qb.name, qb.subject, u.id, u.username, u.full_name, u.roll_number, u.email
        ORDER BY qb.name, avg_score DESC
    """, (trainer_id,))
    rows = cursor.fetchall(); conn.close()
    return rows


def get_trainer_bank_summary(trainer_id: int):
    conn  = get_connection(); cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT qb.id, qb.name AS bank_name, qb.subject,
               COUNT(DISTINCT es.student_id) AS total_students,
               COUNT(es.id)                  AS total_attempts,
               ROUND(AVG(es.score),2)         AS avg_score,
               MAX(es.score)                  AS highest_score,
               MIN(es.score)                  AS lowest_score,
               SUM(es.passed)                 AS total_passed
        FROM question_banks qb
        LEFT JOIN exam_sessions es ON es.bank_id=qb.id AND es.completed_at IS NOT NULL
        WHERE qb.created_by=%s
        GROUP BY qb.id, qb.name, qb.subject
        ORDER BY qb.created_at DESC
    """, (trainer_id,))
    rows = cursor.fetchall(); conn.close()
    return rows


def get_student_by_roll(roll_number: str):
    conn  = get_connection(); cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT u.*,
               COUNT(DISTINCT es.bank_id) AS banks_attempted,
               COUNT(es.id)               AS total_exams,
               ROUND(AVG(es.score),2)     AS overall_avg,
               SUM(es.passed)             AS total_passed
        FROM users u
        LEFT JOIN exam_sessions es ON es.student_id=u.id AND es.completed_at IS NOT NULL
        WHERE u.roll_number=%s AND u.role='student'
        GROUP BY u.id
    """, (roll_number,))
    row = cursor.fetchone(); conn.close()
    return row


def get_students_sorted_by_subject(subject: str = None):
    conn  = get_connection(); cursor = dict_cursor(conn)
    if subject:
        cursor.execute("""
            SELECT u.id, u.username, u.full_name, u.roll_number, u.email,
                   qb.subject, qb.name AS bank_name,
                   ROUND(AVG(es.score),2) AS avg_score,
                   MAX(es.score)          AS best_score,
                   COUNT(es.id)           AS attempts,
                   SUM(es.passed)         AS passed
            FROM users u
            JOIN exam_sessions es  ON es.student_id = u.id
            JOIN question_banks qb ON es.bank_id    = qb.id
            WHERE u.role='student' AND es.completed_at IS NOT NULL
              AND LOWER(qb.subject) LIKE LOWER(%s)
            GROUP BY u.id, u.username, u.full_name, u.roll_number, u.email, qb.id, qb.subject, qb.name
            ORDER BY avg_score DESC
        """, (f"%{subject}%",))
    else:
        cursor.execute("""
            SELECT u.id, u.username, u.full_name, u.roll_number, u.email,
                   ROUND(AVG(es.score),2)      AS avg_score,
                   MAX(es.score)               AS best_score,
                   COUNT(DISTINCT es.bank_id)  AS banks_attempted,
                   SUM(es.passed)              AS passed
            FROM users u
            JOIN exam_sessions es ON es.student_id = u.id
            WHERE u.role='student' AND es.completed_at IS NOT NULL
            GROUP BY u.id, u.username, u.full_name, u.roll_number, u.email
            ORDER BY avg_score DESC
        """)
    rows = cursor.fetchall(); conn.close()
    return rows


def get_student_star_ratings(student_id: int) -> list:
    """Returns star ratings for all banks this student has attempted."""
    conn   = get_connection(); cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT sr.stars, sr.avg_score, sr.computed_at,
               qb.name AS bank_name, qb.subject
        FROM star_ratings sr
        JOIN question_banks qb ON sr.bank_id = qb.id
        WHERE sr.student_id = %s
        ORDER BY sr.avg_score DESC
    """, (student_id,))
    rows = cursor.fetchall(); conn.close()
    return rows
