"""
database/db_setup.py — MySQL + Cloud Ready
============================================
Supports TWO ways to configure MySQL:

WAY 1 — Local (.env file):
    DB_HOST=localhost
    DB_PORT=3306
    DB_NAME=ai_question_db
    DB_USER=root
    DB_PASSWORD=yourpassword

WAY 2 — Cloud (Streamlit Secrets / Railway / Render):
    Set secrets in your cloud dashboard or .streamlit/secrets.toml
    [mysql]
    host = "..."  port = 3306  database = "..."  user = "..."  password = "..."

The code auto-detects which method to use.
"""
import os, hashlib, random, string
import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv
load_dotenv()


def _get_db_config() -> dict:
    """
    MySQL connection config.
    Edit the values below directly if .env is not loading.
    """
    # ── EDIT THESE VALUES TO MATCH YOUR MYSQL SETUP ──────────────────
    DB_HOST     = os.getenv("DB_HOST",     "localhost")
    DB_PORT     = int(os.getenv("DB_PORT", "3306"))
    DB_NAME     = os.getenv("DB_NAME",     "ai_question_db")
    DB_USER     = os.getenv("DB_USER",     "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "root123")  # ← YOUR MYSQL PASSWORD
    # ─────────────────────────────────────────────────────────────────

    return {
        "host":               DB_HOST,
        "port":               DB_PORT,
        "database":           DB_NAME,
        "user":               DB_USER,
        "password":           DB_PASSWORD,
        "charset":            "utf8mb4",
        "use_unicode":        True,
        "connection_timeout": 30,
        "autocommit":         False,
    }


# Connection pool (reuses connections — much faster than reconnecting each time)
_pool = None

def _get_pool():
    global _pool
    if _pool is None:
        cfg = _get_db_config()
        _pool = pooling.MySQLConnectionPool(
            pool_name="ai_pool",
            pool_size=10,
            pool_reset_session=True,
            **cfg
        )
    return _pool


def get_connection():
    """Returns a MySQL connection from the pool."""
    try:
        return _get_pool().get_connection()
    except mysql.connector.Error as e:
        cfg = _get_db_config()
        raise RuntimeError(
            f"❌ Cannot connect to MySQL.\n\n"
            f"Error: {e}\n\n"
            f"Current config:\n"
            f"  Host: {cfg['host']}:{cfg['port']}\n"
            f"  DB:   {cfg['database']}\n"
            f"  User: {cfg['user']}\n\n"
            f"Fixes:\n"
            f"  1. Make sure MySQL is running\n"
            f"  2. Check your .env file values\n"
            f"  3. Create DB: CREATE DATABASE {cfg['database']};"
        )


def dict_cursor(conn):
    """Returns a cursor that returns rows as dicts."""
    return conn.cursor(dictionary=True)


# ── Helpers ──────────────────────────────────────────────────────────────────
def hash_password(p: str) -> str:
    return hashlib.sha256(p.encode()).hexdigest()

def generate_password(n: int = 8) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=n))

def generate_exam_token() -> str:
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))


def test_connection() -> tuple:
    """Returns (True, version_string) or (False, error_message)."""
    try:
        conn   = get_connection()
        cursor = dict_cursor(conn)
        cursor.execute("SELECT VERSION() AS v")
        row    = cursor.fetchone()
        cursor.close(); conn.close()
        return True, f"MySQL {row['v']}"
    except Exception as e:
        return False, str(e)


# ── Schema ────────────────────────────────────────────────────────────────────
def initialize_database():
    """Creates all 13 tables if they don't exist. Seeds default users."""
    conn   = get_connection()
    cursor = dict_cursor(conn)

    tables = [
        """CREATE TABLE IF NOT EXISTS users (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            username    VARCHAR(100) UNIQUE NOT NULL,
            password    VARCHAR(255) NOT NULL,
            role        VARCHAR(20)  NOT NULL,
            full_name   VARCHAR(200),
            email       VARCHAR(200) UNIQUE,
            phone       VARCHAR(20),
            roll_number VARCHAR(50)  UNIQUE,
            is_active   TINYINT DEFAULT 1,
            created_at  DATETIME DEFAULT NOW()
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS question_banks (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            name       VARCHAR(200) NOT NULL,
            subject    VARCHAR(200),
            topic      VARCHAR(200),
            created_by INT,
            created_at DATETIME DEFAULT NOW(),
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS questions (
            id             INT AUTO_INCREMENT PRIMARY KEY,
            bank_id        INT NOT NULL,
            question_text  TEXT NOT NULL,
            option_a       TEXT NOT NULL,
            option_b       TEXT NOT NULL,
            option_c       TEXT NOT NULL,
            option_d       TEXT NOT NULL,
            correct_option VARCHAR(1) NOT NULL,
            difficulty     VARCHAR(10) DEFAULT 'moderate',
            explanation    TEXT,
            created_at     DATETIME DEFAULT NOW(),
            FOREIGN KEY (bank_id) REFERENCES question_banks(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS exam_sessions (
            id           INT AUTO_INCREMENT PRIMARY KEY,
            student_id   INT NOT NULL,
            bank_id      INT NOT NULL,
            score        FLOAT,
            total_q      INT,
            correct_q    INT,
            passed       TINYINT DEFAULT 0,
            started_at   DATETIME DEFAULT NOW(),
            completed_at DATETIME,
            email_sent   TINYINT DEFAULT 0,
            link_token   VARCHAR(32),
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (bank_id)    REFERENCES question_banks(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS exam_answers (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            session_id      INT NOT NULL,
            question_id     INT NOT NULL,
            selected_option VARCHAR(1),
            is_correct      TINYINT,
            FOREIGN KEY (session_id)  REFERENCES exam_sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (question_id) REFERENCES questions(id)     ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS queries (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            from_user  INT NOT NULL,
            to_role    VARCHAR(20) NOT NULL,
            subject    VARCHAR(200),
            message    TEXT NOT NULL,
            reply      TEXT,
            replied_by INT,
            asked_at   DATETIME DEFAULT NOW(),
            replied_at DATETIME,
            FOREIGN KEY (from_user) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS feedback (
            id           INT AUTO_INCREMENT PRIMARY KEY,
            student_id   INT NOT NULL,
            category     VARCHAR(100),
            rating       INT,
            comments     TEXT,
            submitted_at DATETIME DEFAULT NOW(),
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS result_schedules (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            bank_id    INT,
            send_date  DATE NOT NULL,
            send_time  VARCHAR(5) DEFAULT '08:00',
            message    TEXT,
            created_by INT,
            sent       TINYINT DEFAULT 0,
            created_at DATETIME DEFAULT NOW()
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS bank_requests (
            id           INT AUTO_INCREMENT PRIMARY KEY,
            student_id   INT NOT NULL,
            subject      VARCHAR(200) NOT NULL,
            description  TEXT,
            status       VARCHAR(20) DEFAULT 'pending',
            trainer_note TEXT,
            requested_at DATETIME DEFAULT NOW(),
            updated_at   DATETIME,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS exam_links (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            bank_id         INT NOT NULL,
            trainer_id      INT NOT NULL,
            token           VARCHAR(32) UNIQUE NOT NULL,
            title           VARCHAR(200),
            description     TEXT,
            is_active       TINYINT DEFAULT 1,
            time_limit_mins INT DEFAULT 0,
            created_at      DATETIME DEFAULT NOW(),
            expires_at      DATETIME,
            FOREIGN KEY (bank_id)    REFERENCES question_banks(id) ON DELETE CASCADE,
            FOREIGN KEY (trainer_id) REFERENCES users(id)          ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS link_access_requests (
            id           INT AUTO_INCREMENT PRIMARY KEY,
            link_id      INT NOT NULL,
            student_id   INT,
            roll_number  VARCHAR(50),
            full_name    VARCHAR(200),
            status       VARCHAR(20) DEFAULT 'pending',
            requested_at DATETIME DEFAULT NOW(),
            FOREIGN KEY (link_id)    REFERENCES exam_links(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(id)      ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS star_ratings (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            student_id  INT NOT NULL,
            bank_id     INT NOT NULL,
            stars       INT,
            avg_score   FLOAT,
            computed_at DATETIME DEFAULT NOW(),
            UNIQUE KEY uq_student_bank (student_id, bank_id),
            FOREIGN KEY (student_id) REFERENCES users(id)          ON DELETE CASCADE,
            FOREIGN KEY (bank_id)    REFERENCES question_banks(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS question_plans (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            trainer_id      INT UNIQUE NOT NULL,
            plan_type       VARCHAR(20) DEFAULT 'basic',
            questions_limit INT DEFAULT 200,
            questions_used  INT DEFAULT 0,
            FOREIGN KEY (trainer_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    ]

    for sql in tables:
        cursor.execute(sql)
    conn.commit()

    # Seed default users
    cursor.execute("SELECT COUNT(*) AS cnt FROM users")
    if cursor.fetchone()["cnt"] == 0:
        rows = [
            ("admin",   hash_password("admin123"),   "admin",   "System Admin",    "admin@edu.com",   None, None),
            ("trainer", hash_password("trainer123"), "trainer", "Default Trainer", "trainer@edu.com", None, None),
            ("student", hash_password("student123"), "student", "Test Student",    "student@edu.com", "9999999999", "ROLL001"),
        ]
        cursor.executemany("""
            INSERT IGNORE INTO users (username,password,role,full_name,email,phone,roll_number)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, rows)
        cursor.execute("SELECT id FROM users WHERE username='trainer'")
        t = cursor.fetchone()
        if t:
            cursor.execute("""
                INSERT IGNORE INTO question_plans (trainer_id,plan_type,questions_limit)
                VALUES (%s,'basic',200)
            """, (t["id"],))
        conn.commit()

    cursor.close(); conn.close()
