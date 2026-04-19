"""
database/auth.py — MySQL version
MySQL differences: %s params, dict cursor, INSERT IGNORE
"""
import mysql.connector
from database.db_setup import get_connection, dict_cursor, hash_password


def authenticate_user(username: str, password: str):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute(
        "SELECT id, username, role FROM users WHERE username=%s AND password=%s AND is_active=1",
        (username, hash_password(password))
    )
    row = cursor.fetchone()
    conn.close()
    return row if row else None


def get_all_users():
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute(
        "SELECT id, username, role, full_name, email, is_active, created_at FROM users ORDER BY id"
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def create_user(username: str, password: str, role: str, full_name: str, email: str) -> bool:
    conn   = get_connection()
    cursor = dict_cursor(conn)
    try:
        cursor.execute(
            "INSERT INTO users (username, password, role, full_name, email) VALUES (%s,%s,%s,%s,%s)",
            (username, hash_password(password), role, full_name, email)
        )
        conn.commit()
        return True
    except mysql.connector.IntegrityError:
        return False
    finally:
        conn.close()


def deactivate_user(user_id: int):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("UPDATE users SET is_active=0 WHERE id=%s", (user_id,))
    conn.commit()
    conn.close()


def reset_password(user_id: int, new_password: str):
    conn   = get_connection()
    cursor = dict_cursor(conn)
    cursor.execute("UPDATE users SET password=%s WHERE id=%s", (hash_password(new_password), user_id))
    conn.commit()
    conn.close()
