"""
database/exams_db.py — MySQL version
All exam sessions, answers, queries, feedback operations.
MySQL: %s params, dict_cursor, NOW() for timestamps
"""
from database.db_setup import get_connection, dict_cursor


# ── EXAM SESSIONS ────────────────────────────────────────────────────────────

def start_exam_session(student_id: int, bank_id: int) -> int:
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute(
        "INSERT INTO exam_sessions (student_id, bank_id) VALUES (%s, %s)",
        (student_id, bank_id)
    )
    session_id = cursor.lastrowid
    conn.commit(); conn.close()
    return session_id


def complete_exam_session(session_id: int, score: float, total_q: int, correct_q: int) -> int:
    passed = 1 if score >= 60.0 else 0
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        UPDATE exam_sessions
        SET score=%s, total_q=%s, correct_q=%s, passed=%s, completed_at=NOW()
        WHERE id=%s
    """, (score, total_q, correct_q, passed, session_id))
    conn.commit(); conn.close()
    return passed


def save_exam_answers(session_id: int, answers: list):
    """answers = list of dicts: {question_id, selected_option, is_correct}"""
    conn   = get_connection()
    cursor = dict_cursor(conn)
    for ans in answers:
        cursor.execute("""
            INSERT INTO exam_answers (session_id, question_id, selected_option, is_correct)
            VALUES (%s, %s, %s, %s)
        """, (session_id, ans["question_id"], ans["selected_option"], ans["is_correct"]))
    conn.commit(); conn.close()


def get_student_sessions(student_id: int):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT es.*, qb.name AS bank_name, qb.subject
        FROM exam_sessions es
        JOIN question_banks qb ON es.bank_id = qb.id
        WHERE es.student_id=%s AND es.completed_at IS NOT NULL
        ORDER BY es.started_at DESC
    """, (student_id,))
    rows = cursor.fetchall(); conn.close()
    return rows


def get_session_answers(session_id: int):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT ea.*, q.question_text, q.option_a, q.option_b, q.option_c, q.option_d,
               q.correct_option, q.explanation, q.difficulty
        FROM exam_answers ea
        JOIN questions q ON ea.question_id = q.id
        WHERE ea.session_id=%s
    """, (session_id,))
    rows = cursor.fetchall(); conn.close()
    return rows


# ── PERFORMANCE ANALYTICS ────────────────────────────────────────────────────

def get_all_student_performance():
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT u.username, u.full_name,
               COUNT(es.id)           AS total_exams,
               ROUND(AVG(es.score),2) AS avg_score,
               SUM(es.passed)         AS total_passed,
               MAX(es.score)          AS best_score
        FROM users u
        LEFT JOIN exam_sessions es
            ON u.id = es.student_id AND es.completed_at IS NOT NULL
        WHERE u.role = 'student'
        GROUP BY u.id, u.username, u.full_name
        ORDER BY avg_score DESC
    """)
    rows = cursor.fetchall(); conn.close()
    return rows


def get_trainer_bank_stats(trainer_id: int):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT qb.name, qb.subject,
               COUNT(DISTINCT q.id)  AS question_count,
               COUNT(DISTINCT es.id) AS exam_attempts,
               ROUND(AVG(es.score),2) AS avg_score
        FROM question_banks qb
        LEFT JOIN questions q    ON q.bank_id  = qb.id
        LEFT JOIN exam_sessions es ON es.bank_id = qb.id AND es.completed_at IS NOT NULL
        WHERE qb.created_by=%s
        GROUP BY qb.id, qb.name, qb.subject
    """, (trainer_id,))
    rows = cursor.fetchall(); conn.close()
    return rows


# ── QUERIES ──────────────────────────────────────────────────────────────────

def submit_query(from_user: int, to_role: str, subject: str, message: str):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute(
        "INSERT INTO queries (from_user, to_role, subject, message) VALUES (%s,%s,%s,%s)",
        (from_user, to_role, subject, message)
    )
    conn.commit(); conn.close()


def get_queries_for_role(role: str):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT q.*, u.username AS from_username
        FROM queries q
        JOIN users u ON q.from_user = u.id
        WHERE q.to_role=%s
        ORDER BY q.asked_at DESC
    """, (role,))
    rows = cursor.fetchall(); conn.close()
    return rows


def reply_to_query(query_id: int, reply: str, replied_by: int):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        UPDATE queries SET reply=%s, replied_by=%s, replied_at=NOW()
        WHERE id=%s
    """, (reply, replied_by, query_id))
    conn.commit(); conn.close()


def get_student_queries(student_id: int):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute(
        "SELECT * FROM queries WHERE from_user=%s ORDER BY asked_at DESC",
        (student_id,)
    )
    rows = cursor.fetchall(); conn.close()
    return rows


# ── FEEDBACK ──────────────────────────────────────────────────────────────────

def submit_feedback(student_id: int, category: str, rating: int, comments: str):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute(
        "INSERT INTO feedback (student_id, category, rating, comments) VALUES (%s,%s,%s,%s)",
        (student_id, category, rating, comments)
    )
    conn.commit(); conn.close()


def get_all_feedback():
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT f.*, u.username
        FROM feedback f
        JOIN users u ON f.student_id = u.id
        ORDER BY f.submitted_at DESC
    """)
    rows = cursor.fetchall(); conn.close()
    return rows


def get_feedback_summary():
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT category, COUNT(*) AS cnt, ROUND(AVG(rating),2) AS avg_rating
        FROM feedback GROUP BY category
    """)
    rows = cursor.fetchall(); conn.close()
    return rows
