"""
pages/exam_link_page.py
========================
Public exam page opened via shared link.

Flow:
  Student opens link →
    Option A: Login (existing account)
    Option B: 📤 Request Access (new student - name + roll number)
              → Trainer sees request INSTANTLY with name/roll details
              → Trainer clicks Approve → student gets credentials
              → Student logs in → takes exam
"""
import streamlit as st
from database.db_setup import get_connection, dict_cursor
from database.links_db import (get_link_by_token, submit_access_request,
                                check_student_approved, update_star_ratings_for_student)
from database.auth import authenticate_user
from database.questions_db import get_questions_by_bank
from database.exams_db import (start_exam_session, complete_exam_session, save_exam_answers)
from database.registration_db import get_weak_topics
from certificates.certificate_gen import generate_certificate
from utils.ui_theme import apply_theme
from utils.email_utils import send_result_email


def render(token: str):
    apply_theme()

    # Load exam link info
    link = get_link_by_token(token)
    if not link:
        st.markdown("""
        <div style='background:#fee2e2;border:2px solid #e74c3c;border-radius:14px;
                    padding:2.5rem;text-align:center;margin-top:3rem'>
            <div style='font-size:3rem'>⛔</div>
            <h2 style='color:#991b1b'>Invalid or Expired Link</h2>
            <p style='color:#555'>This exam link is no longer active.<br>
            Please contact your trainer for a new link.</p>
        </div>""", unsafe_allow_html=True)
        if st.button("← Back to Home"):
            st.session_state.exam_token = None
            st.rerun()
        return

    # Exam header
    st.markdown(f"""
    <div style='background:linear-gradient(135deg,#0f2744,#2c7be5);
                padding:2rem 2.5rem;border-radius:16px;color:white;
                text-align:center;margin-bottom:2rem'>
        <div style='font-size:2.5rem'>📝</div>
        <h1 style='color:white!important;border:none!important;
                   font-size:1.8rem;margin:.5rem 0'>
            {link.get('title') or link['bank_name']}
        </h1>
        <p style='opacity:.85;margin:.3rem 0'>
            {link.get('description') or ''}&nbsp;
            {('&nbsp;|&nbsp; Subject: <b>' + link.get('subject','') + '</b>') if link.get('subject') else ''}
        </p>
        <small>Conducted by: <b>{link.get('trainer_name','Trainer')}</b>
        {' &nbsp;|&nbsp; ⏱️ Time limit: ' + str(link['time_limit_mins']) + ' min'
         if link.get('time_limit_mins') else ''}
        </small>
    </div>""", unsafe_allow_html=True)

    # Already authenticated via link
    if st.session_state.get("link_student_id"):
        sid      = st.session_state.link_student_id
        approved = check_student_approved(link['id'], sid)
        if not approved:
            _pending_screen()
            return
        _run_exam(link, sid)
        return

    # ── CHOICE: Login OR Request Access ──────────────────────────────────────
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:

        # Big Request Access button first (for new students)
        st.markdown("""
        <div style='background:#fff;border:2px solid #2c7be5;border-radius:14px;
                    padding:2rem;box-shadow:0 4px 20px rgba(44,123,229,.1)'>
        """, unsafe_allow_html=True)

        choice = st.radio(
            "**How would you like to access this exam?**",
            options=["📝 New Student — Request Access with Roll Number",
                     "🔐 Login (I already have an account)"],
            index=0   # default to Request Access for new students
        )
        st.markdown("---")

        if "Request Access" in choice:
            _request_access_panel(link)
        else:
            _login_panel()

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← Back to Main Login"):
            st.session_state.exam_token = None
            st.rerun()


# ── REQUEST ACCESS PANEL ─────────────────────────────────────────────────────
def _request_access_panel(link: dict):
    """
    New student fills Name + Roll Number.
    Trainer sees the request IMMEDIATELY in their portal.
    """
    st.markdown("""
    <div style='background:#e8f4fd;border-radius:10px;padding:1rem 1.2rem;margin-bottom:1rem'>
        <b>ℹ️ How this works:</b><br>
        1. Fill your Name and Roll Number below<br>
        2. Click <b>📤 Send Access Request</b><br>
        3. Your trainer sees your request immediately and approves it<br>
        4. Come back here and login with:<br>
        &nbsp;&nbsp;&nbsp;Username = your name (lowercase)<br>
        &nbsp;&nbsp;&nbsp;Password = your roll number
    </div>""", unsafe_allow_html=True)

    with st.form("request_form", clear_on_submit=False):
        fname = st.text_input(
            "👤 Your Full Name *",
            placeholder="e.g. Pradeep Meesala"
        )
        roll = st.text_input(
            "🎫 Your Roll Number *",
            placeholder="e.g. 24CS001"
        )

        submitted = st.form_submit_button(
            "📤 Send Access Request to Trainer",
            type="primary",
            use_container_width=True
        )

    if submitted:
        if not fname.strip():
            st.error("❌ Please enter your full name.")
        elif not roll.strip():
            st.error("❌ Please enter your roll number.")
        else:
            req_id, msg = submit_access_request(link['id'], roll.strip(), fname.strip())
            if req_id:
                # Notify trainer by email
                try:
                    conn = get_connection(); cur = dict_cursor(conn)
                    cur.execute("""
                        SELECT u.email, u.full_name
                        FROM exam_links el JOIN users u ON el.trainer_id=u.id
                        WHERE el.id=%s
                    """, (link['id'],))
                    trainer = cur.fetchone(); conn.close()
                    if trainer and trainer.get('email'):
                        from utils.email_utils import send_bank_request_email
                        send_bank_request_email(
                            trainer['email'],
                            trainer.get('full_name','Trainer'),
                            fname.strip(),
                            f"Exam Access Request: {link.get('title', link['bank_name'])}",
                            f"Roll Number: {roll.strip()}"
                        )
                except Exception:
                    pass

                st.markdown(f"""
                <div style='background:#f0faf4;border:2px solid #27ae60;border-radius:12px;
                            padding:1.5rem;margin-top:1rem'>
                    <h4 style='color:#166534;margin:0 0 .8rem'>✅ Request Sent Successfully!</h4>
                    <p style='margin:.3rem 0'><b>Your Name:</b> {fname.strip()}</p>
                    <p style='margin:.3rem 0'><b>Roll Number:</b> {roll.strip()}</p>
                    <hr style='margin:.8rem 0'>
                    <p style='margin:.3rem 0'><b>What happens next:</b></p>
                    <p style='margin:.2rem 0'>⏳ Wait for your trainer to approve</p>
                    <p style='margin:.2rem 0'>Then come back and login with:</p>
                    <p style='margin:.2rem 0'><b>Username:</b> {fname.strip().lower().replace(' ','_')[:14]}</p>
                    <p style='margin:.2rem 0'><b>Password:</b> {roll.strip()}</p>
                </div>""", unsafe_allow_html=True)
            else:
                # Already requested — just show login info
                st.warning(f"ℹ️ {msg}")
                st.info(f"Already requested? Login with Username = your name (lowercase) | Password = {roll.strip()}")


# ── LOGIN PANEL ───────────────────────────────────────────────────────────────
def _login_panel():
    st.markdown("#### 🔐 Login with Your Credentials")
    with st.form("link_login_form"):
        uname = st.text_input("Username", placeholder="Your username")
        pwd   = st.text_input("Password", type="password", placeholder="Your password (roll number)")
        if st.form_submit_button("Login & Enter Exam →", type="primary", use_container_width=True):
            if uname and pwd:
                user = authenticate_user(uname, pwd)
                if user:
                    st.session_state.link_student_id   = user['id']
                    st.session_state.link_student_name = user['username']
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password. Make sure trainer approved your request.")
            else:
                st.warning("Enter both username and password.")


# ── PENDING APPROVAL SCREEN ───────────────────────────────────────────────────
def _pending_screen():
    st.markdown("""
    <div style='background:#fff8e1;border:2px solid #f39c12;border-radius:14px;
                padding:2rem;text-align:center;margin:2rem 0'>
        <div style='font-size:3rem'>⏳</div>
        <h3 style='color:#7d4e00'>Waiting for Trainer Approval</h3>
        <p style='color:#555'>Your request has been sent to the trainer.<br>
        Please wait for approval, then refresh this page and login.</p>
    </div>""", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    if c1.button("🔄 Refresh / I've been approved", use_container_width=True, type="primary"):
        st.rerun()
    if c2.button("← Try Login Instead", use_container_width=True):
        st.session_state.link_student_id = None
        st.rerun()


# ── RUN EXAM ─────────────────────────────────────────────────────────────────
def _run_exam(link: dict, student_id: int):
    bank_id = link['bank_id']

    # Show result if already submitted
    if "lx_result" in st.session_state:
        _show_result(student_id)
        return

    if not st.session_state.get("lx_active"):
        questions = get_questions_by_bank(bank_id)
        if not questions:
            st.error("❌ No questions in this exam yet. Contact your trainer.")
            return

        st.markdown(f"""
        <div style='background:#f0f6ff;border:2px solid #2c7be5;border-radius:12px;
                    padding:1.5rem;margin-bottom:1.5rem'>
            <h3 style='color:#0f2744;margin:0 0 .8rem'>📋 Exam Ready</h3>
            <p>📚 <b>Topic:</b> {link['bank_name']}</p>
            <p>❓ <b>Questions:</b> {len(questions)}</p>
            <p>⏱️ <b>Time Limit:</b> {"No limit" if not link.get('time_limit_mins') else str(link['time_limit_mins']) + " minutes"}</p>
            <p>✅ <b>Pass Mark:</b> 60%</p>
        </div>""", unsafe_allow_html=True)

        if st.button("🚀 Start Exam Now", type="primary", use_container_width=True):
            st.session_state.lx_active    = True
            st.session_state.lx_questions = questions
            st.session_state.lx_answers   = {}
            st.session_state.lx_session   = start_exam_session(student_id, bank_id)
            st.rerun()
        return

    # Active exam
    questions = st.session_state.lx_questions
    answers   = st.session_state.get("lx_answers", {})
    total_q   = len(questions)
    answered  = len(answers)

    st.markdown(f"### 📘 {link['bank_name']}")
    st.progress(answered / total_q, text=f"Answered: {answered} / {total_q}")
    st.markdown("---")

    for i, q in enumerate(questions):
        diff_icon = {"easy":"🟢","moderate":"🟡","hard":"🔴"}.get(q.get('difficulty',''), "•")
        st.markdown(f"**{diff_icon} Q{i+1}. {q['question_text']}**")
        opts = {"A": q['option_a'], "B": q['option_b'],
                "C": q['option_c'], "D": q['option_d']}
        choice = st.radio(
            f"Answer Q{i+1}:",
            list(opts.keys()),
            format_func=lambda x: f"  {x})  {opts[x]}",
            key=f"lxq_{i}",
            index=None,
            label_visibility="collapsed"
        )
        if choice:
            answers[i] = {
                "question_id":     q['id'],
                "selected_option": choice,
                "is_correct":      1 if choice == q['correct_option'] else 0
            }
            st.session_state.lx_answers = answers
        st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Submit Exam", type="primary", use_container_width=True):
            if len(answers) < total_q:
                st.warning(f"⚠️ Please answer all {total_q} questions first.")
            else:
                _submit(link, student_id, questions, answers)
    with c2:
        if st.button("← Exit", use_container_width=True):
            for k in ["lx_active","lx_questions","lx_answers","lx_session"]:
                st.session_state.pop(k, None)
            st.rerun()


def _submit(link, student_id, questions, answers):
    total   = len(questions)
    correct = sum(1 for a in answers.values() if a['is_correct'])
    score   = (correct / total) * 100

    save_exam_answers(st.session_state.lx_session, list(answers.values()))
    passed = complete_exam_session(st.session_state.lx_session, score, total, correct)

    try:
        update_star_ratings_for_student(student_id)
    except Exception:
        pass

    # Send result email
    try:
        conn = get_connection(); cur = dict_cursor(conn)
        cur.execute("SELECT email, full_name FROM users WHERE id=%s", (student_id,))
        row = cur.fetchone(); conn.close()
        if row and row.get('email'):
            weak = get_weak_topics(student_id, link['bank_id'])
            send_result_email(row['email'], row.get('full_name','Student'),
                              link['bank_name'], score, correct, total, weak, bool(passed))
    except Exception:
        pass

    st.session_state.lx_result = {
        "score": score, "correct": correct,
        "total": total, "passed": passed,
        "bank_name": link['bank_name']
    }
    st.session_state.lx_active = False
    st.rerun()


def _show_result(student_id: int):
    r = st.session_state.lx_result

    if r['passed']:
        st.markdown("""
        <div style='background:linear-gradient(135deg,#f0faf4,#dcfce7);border:2px solid #27ae60;
                    border-radius:14px;padding:2rem;text-align:center'>
            <div style='font-size:3rem'>🎉</div>
            <h2 style='color:#166534'>Congratulations! You Passed!</h2>
        </div>""", unsafe_allow_html=True)
        st.balloons()
    else:
        st.markdown("""
        <div style='background:#fff8e1;border:2px solid #f39c12;border-radius:14px;
                    padding:1.5rem;text-align:center'>
            <div style='font-size:2rem'>💪</div>
            <h3 style='color:#7d4e00'>Keep Practicing! Score 60%+ to pass.</h3>
        </div>""", unsafe_allow_html=True)

    c1,c2,c3 = st.columns(3)
    c1.metric("📊 Score",   f"{r['score']:.1f}%")
    c2.metric("✅ Correct", f"{r['correct']}/{r['total']}")
    c3.metric("🏆 Result",  "PASSED ✅" if r['passed'] else "Not Passed ❌")

    if r['passed']:
        cert = generate_certificate(
            st.session_state.get("link_student_name","Student"),
            r['bank_name'], r['score']
        )
        st.download_button("📄 Download Your Certificate (PDF)",
                           data=cert,
                           file_name=f"certificate_{r['bank_name'].replace(' ','_')}.pdf",
                           mime="application/pdf",
                           use_container_width=True)

    st.info("📧 Your result has been emailed to you with topic analysis.")

    if st.button("🔄 Done / Exit"):
        for k in ["lx_active","lx_questions","lx_answers","lx_session","lx_result"]:
            st.session_state.pop(k, None)
        st.session_state.exam_token = None
        st.rerun()
