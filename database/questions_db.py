"""
database/questions_db.py — MySQL version
Uses %s params, dict_cursor, RAND() instead of RANDOM()
"""
from database.db_setup import get_connection, dict_cursor


def create_question_bank(name, subject, topic, trainer_id) -> int:
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute(
        "INSERT INTO question_banks (name, subject, topic, created_by) VALUES (%s,%s,%s,%s)",
        (name, subject, topic, trainer_id)
    )
    bank_id = cursor.lastrowid
    conn.commit(); conn.close()
    return bank_id


def get_all_banks():
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT qb.id, qb.name, qb.subject, qb.topic, qb.created_at,
               u.username AS trainer_name,
               COUNT(q.id) AS question_count
        FROM question_banks qb
        LEFT JOIN users u  ON qb.created_by = u.id
        LEFT JOIN questions q ON q.bank_id  = qb.id
        GROUP BY qb.id, qb.name, qb.subject, qb.topic, qb.created_at, u.username
        ORDER BY qb.created_at DESC
    """)
    rows = cursor.fetchall(); conn.close()
    return rows


def get_bank_by_id(bank_id: int):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("SELECT * FROM question_banks WHERE id=%s", (bank_id,))
    row = cursor.fetchone(); conn.close()
    return row


def delete_bank(bank_id: int):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    # ON DELETE CASCADE handles questions automatically
    cursor.execute("DELETE FROM question_banks WHERE id=%s", (bank_id,))
    conn.commit(); conn.close()


def insert_question(bank_id, question_text, option_a, option_b,
                    option_c, option_d, correct_option,
                    difficulty="moderate", explanation=""):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        INSERT INTO questions
        (bank_id, question_text, option_a, option_b, option_c, option_d,
         correct_option, difficulty, explanation)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (bank_id, question_text, option_a, option_b, option_c, option_d,
          correct_option, difficulty, explanation))
    conn.commit(); conn.close()


def get_questions_by_bank(bank_id: int, difficulty: str = None):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    if difficulty:
        cursor.execute(
            "SELECT * FROM questions WHERE bank_id=%s AND difficulty=%s ORDER BY RAND()",
            (bank_id, difficulty)
        )
    else:
        cursor.execute("SELECT * FROM questions WHERE bank_id=%s ORDER BY RAND()", (bank_id,))
    rows = cursor.fetchall(); conn.close()
    return rows


def get_adaptive_questions(bank_id: int, student_id: int, count: int = 10):
    """
    Selects questions adaptively based on student's last score.
    Score >=80 → hard | 50-79 → moderate | <50 or first time → easy
    """
    conn   = get_connection()
    cursor = dict_cursor(conn)

    cursor.execute("""
        SELECT score FROM exam_sessions
        WHERE student_id=%s AND bank_id=%s AND completed_at IS NOT NULL
        ORDER BY started_at DESC LIMIT 1
    """, (student_id, bank_id))
    last = cursor.fetchone()

    if   last is None:              difficulty = "easy"
    elif last["score"] >= 80:       difficulty = "hard"
    elif last["score"] >= 50:       difficulty = "moderate"
    else:                           difficulty = "easy"

    cursor.execute("""
        SELECT * FROM questions WHERE bank_id=%s AND difficulty=%s
        ORDER BY RAND() LIMIT %s
    """, (bank_id, difficulty, count))
    rows = list(cursor.fetchall())

    # Pad with other difficulties if not enough
    if len(rows) < count:
        existing_ids = [r["id"] for r in rows] or [0]
        fmt = ",".join(["%s"] * len(existing_ids))
        cursor.execute(f"""
            SELECT * FROM questions
            WHERE bank_id=%s AND id NOT IN ({fmt})
            ORDER BY RAND() LIMIT %s
        """, [bank_id] + existing_ids + [count - len(rows)])
        rows += list(cursor.fetchall())

    conn.close()
    return rows, difficulty


def delete_question(question_id: int):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("DELETE FROM questions WHERE id=%s", (question_id,))
    conn.commit(); conn.close()


def get_question_count_by_difficulty(bank_id: int) -> dict:
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("""
        SELECT difficulty, COUNT(*) AS cnt
        FROM questions WHERE bank_id=%s GROUP BY difficulty
    """, (bank_id,))
    rows = cursor.fetchall(); conn.close()
    return {r["difficulty"]: r["cnt"] for r in rows}
