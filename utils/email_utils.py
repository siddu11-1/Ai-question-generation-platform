"""
=============================================================================
utils/email_utils.py
Description:
    Handles ALL email sending in the system using Gmail SMTP.
    Emails sent:
      1. Welcome email with username/password after student registration
      2. Exam result email with weak topic analysis after test
      3. Scheduled result email (admin triggers on chosen date)
      4. Question bank request notification to trainer

SETUP:
    In your .env file add:
        EMAIL_ADDRESS=your_gmail@gmail.com
        EMAIL_PASSWORD=your_gmail_app_password

    Gmail App Password (NOT your normal Gmail password):
    → Go to https://myaccount.google.com/security
    → Enable 2-Step Verification
    → Search "App Passwords" → Generate one for "Mail"
    → Use that 16-character password in EMAIL_PASSWORD
=============================================================================
"""

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime


def get_email_config():
    """Returns sender email and password from environment variables."""
    return {
        "address":  os.environ.get("EMAIL_ADDRESS", ""),
        "password": os.environ.get("EMAIL_PASSWORD", ""),
    }


def send_email(to_address: str, subject: str, html_body: str) -> tuple:
    """
    Core email sender using Gmail SMTP with TLS.

    Args:
        to_address : Recipient email address
        subject    : Email subject line
        html_body  : HTML formatted email body

    Returns:
        (True, "Sent") on success
        (False, error_message) on failure
    """
    cfg = get_email_config()
    if not cfg["address"] or not cfg["password"]:
        return False, "Email not configured. Add EMAIL_ADDRESS and EMAIL_PASSWORD to .env"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = cfg["address"]
        msg["To"]      = to_address
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(cfg["address"], cfg["password"])
            server.sendmail(cfg["address"], to_address, msg.as_string())

        return True, "Email sent successfully"
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail authentication failed. Check EMAIL_ADDRESS and EMAIL_PASSWORD in .env"
    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────
# EMAIL 1 — WELCOME / ACCOUNT CREATED
# ─────────────────────────────────────────────

def send_welcome_email(to_email: str, full_name: str, username: str, password: str) -> tuple:
    """
    Sends a welcome email with login credentials after student self-registration.
    """
    subject = "🎓 Your Account is Ready — AI Learning System"
    body = f"""
    <html><body style="font-family:Arial,sans-serif;background:#f4f6f9;padding:20px">
    <div style="max-width:600px;margin:auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.1)">
      <div style="background:linear-gradient(135deg,#1a3c5e,#2c7be5);padding:2rem;text-align:center;color:white">
        <h1 style="margin:0;font-size:1.8rem">🧠 AI Question System</h1>
        <p style="margin:0.5rem 0 0;opacity:0.9">Your account has been created!</p>
      </div>
      <div style="padding:2rem">
        <p style="font-size:1.1rem">Hello <strong>{full_name}</strong>,</p>
        <p>Welcome to the AI-Powered Question Generation & Learning System. Your account is ready!</p>
        <div style="background:#f0f4f8;border-radius:10px;padding:1.5rem;margin:1.5rem 0;border-left:4px solid #2c7be5">
          <h3 style="margin:0 0 1rem;color:#1a3c5e">🔐 Your Login Credentials</h3>
          <p><strong>Username:</strong> <code style="background:#e8edf2;padding:2px 8px;border-radius:4px">{username}</code></p>
          <p><strong>Password:</strong> <code style="background:#e8edf2;padding:2px 8px;border-radius:4px">{password}</code></p>
        </div>
        <p style="color:#e74c3c"><strong>⚠️ Please change your password after first login.</strong></p>
        <div style="text-align:center;margin:2rem 0">
          <a href="http://localhost:8501" style="background:linear-gradient(135deg,#1a3c5e,#2c7be5);color:white;padding:0.8rem 2rem;border-radius:8px;text-decoration:none;font-weight:bold">
            🚀 Login Now
          </a>
        </div>
        <p style="color:#666;font-size:0.9rem">You can take adaptive exams, chat with AI tutor, and download certificates after passing!</p>
      </div>
      <div style="background:#f4f6f9;padding:1rem;text-align:center;color:#888;font-size:0.8rem">
        AI Question Generation & Learning System · Auto-generated email
      </div>
    </div>
    </body></html>
    """
    return send_email(to_email, subject, body)


# ─────────────────────────────────────────────
# EMAIL 2 — EXAM RESULT WITH WEAK TOPIC ANALYSIS
# ─────────────────────────────────────────────

def send_result_email(to_email: str, student_name: str, bank_name: str,
                      score: float, correct: int, total: int,
                      weak_topics: list, passed: bool) -> tuple:
    """
    Sends exam result email immediately after test completion.
    Includes weak topic analysis so student knows what to study.

    Args:
        weak_topics: list of question texts the student got wrong
    """
    status_color = "#27ae60" if passed else "#e74c3c"
    status_text  = "✅ PASSED" if passed else "❌ Not Passed Yet"
    badge_color  = "#e8f8f0" if passed else "#fdecea"

    weak_html = ""
    if weak_topics:
        items = "".join(f"<li style='margin-bottom:0.4rem;color:#555'>{t}</li>" for t in weak_topics[:10])
        weak_html = f"""
        <div style="background:#fff8e1;border-radius:10px;padding:1.2rem;margin:1.2rem 0;border-left:4px solid #f39c12">
          <h3 style="color:#7d6608;margin:0 0 0.8rem">📚 Topics to Revise</h3>
          <p style="color:#666;margin-bottom:0.8rem">You got these questions wrong — focus on these areas:</p>
          <ul style="padding-left:1.5rem">{items}</ul>
        </div>
        """

    subject = f"📊 Your Exam Result — {bank_name} | Score: {score:.1f}%"
    body = f"""
    <html><body style="font-family:Arial,sans-serif;background:#f4f6f9;padding:20px">
    <div style="max-width:600px;margin:auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.1)">
      <div style="background:linear-gradient(135deg,#1a3c5e,#2c7be5);padding:2rem;text-align:center;color:white">
        <h1 style="margin:0;font-size:1.6rem">📊 Exam Result</h1>
        <p style="margin:0.5rem 0 0;opacity:0.9">{bank_name}</p>
      </div>
      <div style="padding:2rem">
        <p>Hello <strong>{student_name}</strong>, here are your results:</p>
        <div style="display:flex;gap:1rem;margin:1.5rem 0;flex-wrap:wrap">
          <div style="flex:1;background:{badge_color};border-radius:10px;padding:1.2rem;text-align:center;min-width:120px">
            <div style="font-size:2.5rem;font-weight:700;color:{status_color}">{score:.1f}%</div>
            <div style="color:#666;font-size:0.9rem">Your Score</div>
          </div>
          <div style="flex:1;background:#f0f4f8;border-radius:10px;padding:1.2rem;text-align:center;min-width:120px">
            <div style="font-size:2.5rem;font-weight:700;color:#1a3c5e">{correct}/{total}</div>
            <div style="color:#666;font-size:0.9rem">Correct Answers</div>
          </div>
          <div style="flex:1;background:{badge_color};border-radius:10px;padding:1.2rem;text-align:center;min-width:120px">
            <div style="font-size:1.5rem;font-weight:700;color:{status_color}">{status_text}</div>
            <div style="color:#666;font-size:0.9rem">Status</div>
          </div>
        </div>
        {weak_html}
        {"<p style='color:#27ae60;font-weight:bold'>🎉 Congratulations! Log in to download your certificate.</p>" if passed else "<p style='color:#e74c3c'>Keep practicing! You need 60% to pass. Review the topics above and try again.</p>"}
      </div>
      <div style="background:#f4f6f9;padding:1rem;text-align:center;color:#888;font-size:0.8rem">
        AI Question Generation & Learning System · Result generated {datetime.now().strftime('%d %b %Y %H:%M')}
      </div>
    </div>
    </body></html>
    """
    return send_email(to_email, subject, body)


# ─────────────────────────────────────────────
# EMAIL 3 — SCHEDULED RESULT EMAIL (Admin triggers)
# ─────────────────────────────────────────────

def send_scheduled_result_email(to_email: str, student_name: str,
                                 results_summary: list, scheduled_date: str) -> tuple:
    """
    Sends a scheduled results report email on admin-defined date.
    results_summary = list of dicts: {bank_name, score, passed, date}
    """
    rows = ""
    for r in results_summary:
        color = "#27ae60" if r.get("passed") else "#e74c3c"
        rows += f"""
        <tr>
          <td style="padding:0.6rem 1rem;border-bottom:1px solid #eee">{r.get('bank_name','')}</td>
          <td style="padding:0.6rem 1rem;border-bottom:1px solid #eee;text-align:center;font-weight:700;color:{color}">{r.get('score', 0):.1f}%</td>
          <td style="padding:0.6rem 1rem;border-bottom:1px solid #eee;text-align:center">{'✅ Pass' if r.get('passed') else '❌ Fail'}</td>
          <td style="padding:0.6rem 1rem;border-bottom:1px solid #eee;color:#888;font-size:0.85rem">{str(r.get('date',''))[:10]}</td>
        </tr>"""

    subject = f"📅 Scheduled Results Report — {scheduled_date}"
    body = f"""
    <html><body style="font-family:Arial,sans-serif;background:#f4f6f9;padding:20px">
    <div style="max-width:650px;margin:auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.1)">
      <div style="background:linear-gradient(135deg,#1a3c5e,#2c7be5);padding:2rem;text-align:center;color:white">
        <h1 style="margin:0">📅 Scheduled Results Report</h1>
        <p style="margin:0.5rem 0 0;opacity:0.9">Sent on: {scheduled_date}</p>
      </div>
      <div style="padding:2rem">
        <p>Hello <strong>{student_name}</strong>,</p>
        <p>Here is your scheduled performance report:</p>
        <table style="width:100%;border-collapse:collapse;margin:1rem 0">
          <thead>
            <tr style="background:#1a3c5e;color:white">
              <th style="padding:0.7rem 1rem;text-align:left">Exam Topic</th>
              <th style="padding:0.7rem 1rem;text-align:center">Score</th>
              <th style="padding:0.7rem 1rem;text-align:center">Status</th>
              <th style="padding:0.7rem 1rem;text-align:left">Date Taken</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
        <p style="color:#666;font-size:0.9rem">Login to the platform to view detailed analytics and download certificates.</p>
      </div>
      <div style="background:#f4f6f9;padding:1rem;text-align:center;color:#888;font-size:0.8rem">
        This report was scheduled by your administrator.
      </div>
    </div>
    </body></html>
    """
    return send_email(to_email, subject, body)


# ─────────────────────────────────────────────
# EMAIL 4 — QUESTION BANK REQUEST NOTIFICATION
# ─────────────────────────────────────────────

def send_bank_request_email(to_email: str, trainer_name: str,
                             student_name: str, subject_requested: str,
                             message: str) -> tuple:
    """Notifies a trainer that a student has requested a new question bank."""
    email_subject = f"📚 New Question Bank Request from {student_name}"
    body = f"""
    <html><body style="font-family:Arial,sans-serif;background:#f4f6f9;padding:20px">
    <div style="max-width:600px;margin:auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.1)">
      <div style="background:linear-gradient(135deg,#1a3c5e,#2c7be5);padding:2rem;text-align:center;color:white">
        <h1 style="margin:0;font-size:1.5rem">📚 Question Bank Request</h1>
      </div>
      <div style="padding:2rem">
        <p>Hello <strong>{trainer_name}</strong>,</p>
        <p>A student has requested a new question bank:</p>
        <div style="background:#f0f4f8;border-radius:10px;padding:1.2rem;margin:1rem 0;border-left:4px solid #2c7be5">
          <p><strong>Student:</strong> {student_name}</p>
          <p><strong>Subject Requested:</strong> {subject_requested}</p>
          <p><strong>Message:</strong> {message}</p>
        </div>
        <p>Please log in to the trainer portal to create this question bank.</p>
      </div>
    </div>
    </body></html>
    """
    return send_email(to_email, email_subject, body)
