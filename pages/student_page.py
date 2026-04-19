"""pages/student_page.py — complete student portal"""
import streamlit as st
import pandas as pd
from utils.ui_theme import apply_theme, stars_html
from utils.gemini_ai import chatbot_answer
from database.db_setup import get_connection, dict_cursor
from database.exams_db import (get_student_sessions, get_session_answers,
                                submit_query, get_student_queries, submit_feedback)
from database.registration_db import (get_weak_topics, get_weak_subjects,
                                       submit_bank_request, get_student_bank_requests)
from database.links_db import (compute_star_rating, get_student_star_ratings,
                                update_star_ratings_for_student)
from certificates.certificate_gen import generate_certificate
from utils.analytics import score_trend_chart, pass_fail_donut


def render():
    apply_theme()
    uid   = st.session_state.user_id
    uname = st.session_state.username

    # Update star ratings
    try:
        update_star_ratings_for_student(uid)
    except Exception:
        pass

    # Get profile
    conn = get_connection(); cursor = dict_cursor(conn)
    cursor.execute("SELECT full_name, email, roll_number, phone FROM users WHERE id=%s", (uid,))
    profile = cursor.fetchone() or {}
    conn.close()
    fname = profile.get("full_name") or uname

    # Header
    st.markdown(f"""
    <div style='background:linear-gradient(135deg,#0f2744,#2c7be5);
                padding:1.5rem 2rem;border-radius:14px;color:white;margin-bottom:1rem'>
        <h2 style='color:white!important;border:none!important;margin:0;font-size:1.5rem'>
            📖 Welcome, {fname}!
        </h2>
        <p style='margin:.3rem 0 0;opacity:.85;font-size:.9rem'>
            Roll: <b>{profile.get("roll_number","—")}</b> &nbsp;|&nbsp;
            {profile.get("email","—")} &nbsp;|&nbsp; {profile.get("phone","—")}
        </p>
    </div>""", unsafe_allow_html=True)

    # Quick stats
    sessions = get_student_sessions(uid)
    if sessions:
        df  = pd.DataFrame(sessions)
        avg = df['score'].mean()
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("📝 Exams",      len(sessions))
        c2.metric("📊 Avg Score",  f"{avg:.1f}%")
        c3.metric("✅ Passed",     int(df['passed'].sum()))
        c4.metric("🏆 Best",       f"{df['score'].max():.1f}%")
        c5.metric("⭐ Stars",      stars_html(compute_star_rating(avg)))

    st.markdown("---")

    # ── TABS ─────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🏠 Dashboard",
        "📈 My Results",
        "📚 Request Question Bank",   # ← clearly visible
        "🤖 AI Study Chat",
        "📬 My Queries",
        "💬 Feedback"
    ])

    with tab1: _dashboard(uid, sessions, profile)
    with tab2: _results(uid, sessions)
    with tab3: _request_bank(uid)        # ← request tab
    with tab4: _ai_chat()
    with tab5: _queries(uid)
    with tab6: _feedback(uid)


# ── DASHBOARD ────────────────────────────────────────────────────────────────
def _dashboard(uid, sessions, profile):
    st.subheader("🏠 Your Learning Overview")

    # Weak vs Strong
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### ⚠️ Topics to Improve")
        weak = get_weak_subjects(uid)
        if weak:
            for w in weak:
                pct   = w.get('avg_score') or 0
                color = "#e74c3c" if pct < 50 else "#f39c12"
                st.markdown(f"""
                <div style='background:#fff8e1;border-radius:8px;padding:.6rem 1rem;
                            margin-bottom:.4rem;border-left:3px solid {color}'>
                    📖 <b>{w['bank_name']}</b> — <b style='color:{color}'>{pct:.1f}%</b>
                    ({w['attempts']} attempt{'s' if w['attempts']>1 else ''})
                </div>""", unsafe_allow_html=True)
        else:
            st.info("Take an exam to see your weak areas.")

    with col2:
        st.markdown("##### 🏆 Your Strong Topics")
        stars_data = get_student_star_ratings(uid)
        strong = [s for s in stars_data if (s.get('stars') or 0) >= 4]
        if strong:
            for s in sorted(strong, key=lambda x: x.get('avg_score') or 0, reverse=True):
                st.markdown(f"""
                <div style='background:#f0faf4;border-radius:8px;padding:.6rem 1rem;
                            margin-bottom:.4rem;border-left:3px solid #27ae60'>
                    📗 <b>{s['bank_name']}</b> — {stars_html(s.get('stars') or 0)}
                    <b style='color:#27ae60'>{(s.get('avg_score') or 0):.1f}%</b>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("Score 75%+ to unlock strong topic badges.")

    # Charts
    if sessions and len(sessions) >= 2:
        st.markdown("---")
        c1, c2 = st.columns([2, 1])
        with c1:
            st.plotly_chart(score_trend_chart(sessions), use_container_width=True)
        with c2:
            st.plotly_chart(pass_fail_donut(sessions), use_container_width=True)

    # Recent results
    st.markdown("---")
    st.markdown("##### 📋 Recent Results")
    if sessions:
        for s in sessions[:5]:
            icon  = "✅" if s['passed'] else "❌"
            color = "#27ae60" if s['passed'] else "#e74c3c"
            bg    = "#f0faf4"  if s['passed'] else "#fef5f5"
            st.markdown(f"""
            <div style='background:{bg};border-radius:8px;padding:.6rem 1rem;
                        margin-bottom:.3rem;border-left:3px solid {color}'>
                {icon} <b>{s['bank_name']}</b> — <b style='color:{color}'>{s['score']:.1f}%</b>
                &nbsp;|&nbsp; {str(s['started_at'])[:10]}
            </div>""", unsafe_allow_html=True)
    else:
        st.info("No exams yet. Use an exam link from your trainer to start.")


# ── RESULTS ──────────────────────────────────────────────────────────────────
def _results(uid, sessions):
    st.subheader("📈 My Exam Results")
    if not sessions:
        st.info("No exams completed yet.")
        return

    df = pd.DataFrame(sessions)
    disp = df[["bank_name","subject","score","correct_q","total_q","passed","started_at"]].copy()
    disp.columns = ["Topic","Subject","Score(%)","Correct","Total","Passed","Date"]
    disp["Passed"] = disp["Passed"].map({1:"✅","0":"❌",0:"❌"})
    disp["Date"]   = disp["Date"].astype(str).str[:16]
    st.dataframe(disp, use_container_width=True, hide_index=True)

    # Review wrong answers
    st.markdown("---")
    st.markdown("#### 🔍 Review a Specific Exam")
    opts = {f"{s['bank_name']} — {str(s['started_at'])[:10]} — {s['score']:.1f}%": s['id']
            for s in sessions}
    sel  = st.selectbox("Pick exam to review:", list(opts.keys()))
    answers = get_session_answers(opts[sel])
    if answers:
        wrong = [a for a in answers if not a['is_correct']]
        correct = [a for a in answers if a['is_correct']]
        c1,c2 = st.columns(2)
        c1.metric("✅ Correct", len(correct))
        c2.metric("❌ Wrong",   len(wrong))
        if wrong:
            st.markdown("**❌ Questions you got wrong — focus on these:**")
            for a in wrong:
                with st.expander(f"❌ {a['question_text'][:65]}..."):
                    st.markdown(f"**Your answer:** {a['selected_option']}  |  **Correct:** {a['correct_option']}")
                    if a.get('explanation'):
                        st.info(f"💡 {a['explanation']}")

    # Certificates
    st.markdown("---")
    st.markdown("#### 🎓 Download Certificates")
    passed_s = [s for s in sessions if s['passed']]
    if passed_s:
        for s in passed_s:
            c1, c2 = st.columns([3,1])
            c1.markdown(f"**{s['bank_name']}** — {s['score']:.1f}% — {str(s['started_at'])[:10]}")
            with c2:
                cert = generate_certificate(
                    st.session_state.username, s['bank_name'], s['score'],
                    str(s.get('completed_at',''))[:10])
                st.download_button("📥 Download", data=cert,
                                   file_name=f"cert_{s['bank_name']}.pdf",
                                   mime="application/pdf", key=f"cert_{s['id']}")
    else:
        st.info("Pass an exam (score ≥ 60%) to get a certificate.")


# ── REQUEST QUESTION BANK ─────────────────────────────────────────────────────
def _request_bank(uid):
    st.subheader("📚 Request a New Question Bank from Trainer")

    # Big visible info box
    st.markdown("""
    <div style='background:#e8f4fd;border:2px solid #2c7be5;border-radius:12px;
                padding:1.2rem 1.5rem;margin-bottom:1.5rem'>
        <h4 style='color:#0f2744;margin:0 0 .5rem'>ℹ️ How this works</h4>
        <p style='margin:0;color:#444'>
            Fill the form below and click <b>Send Request</b>.<br>
            Your trainer will see it instantly in their portal under
            <b>📬 Requests → Bank Requests</b> tab and create the questions for you.
        </p>
    </div>""", unsafe_allow_html=True)

    with st.form("bank_req_form", clear_on_submit=True):
        subject = st.text_input(
            "📖 Subject / Topic you need *",
            placeholder="e.g. Python Functions, Database Normalization, Thermodynamics"
        )
        description = st.text_area(
            "📝 Why do you need this? (optional)",
            placeholder="e.g. I have an exam next week on this topic and need more practice questions...",
            height=100
        )
        submitted = st.form_submit_button(
            "📤 Send Request to Trainer",
            type="primary",
            use_container_width=True
        )

    if submitted:
        if subject.strip():
            # Save to database
            req_id = submit_bank_request(uid, subject.strip(), description.strip())

            # Email trainers
            try:
                conn   = get_connection()
                cursor = dict_cursor(conn)
                cursor.execute("SELECT email, full_name FROM users WHERE role='trainer' AND is_active=1")
                trainers = cursor.fetchall()
                cursor.execute("SELECT full_name FROM users WHERE id=%s", (uid,))
                me   = cursor.fetchone()
                conn.close()
                sname = me['full_name'] if me else st.session_state.username
                from utils.email_utils import send_bank_request_email
                for t in trainers:
                    if t.get('email'):
                        send_bank_request_email(
                            t['email'], t.get('full_name', 'Trainer'),
                            sname, subject.strip(), description.strip()
                        )
            except Exception:
                pass

            st.success(f"✅ Request for **'{subject}'** sent to trainer! They will see it immediately.")
            st.balloons()
        else:
            st.error("❌ Please enter a subject / topic name.")

    # My request history
    st.markdown("---")
    st.markdown("#### 📋 My Request History")
    reqs = get_student_bank_requests(uid)
    if reqs:
        for r in reqs:
            color  = {"pending":"#f39c12","approved":"#27ae60","rejected":"#e74c3c"}.get(r['status'],"#888")
            icon   = {"pending":"⏳","approved":"✅","rejected":"❌"}.get(r['status'],"•")
            bg     = {"pending":"#fff8e1","approved":"#f0faf4","rejected":"#fef5f5"}.get(r['status'],"#f5f5f5")
            st.markdown(f"""
            <div style='background:{bg};border-radius:8px;padding:.8rem 1.2rem;
                        margin-bottom:.5rem;border-left:4px solid {color}'>
                {icon} <b>{r['subject']}</b>
                &nbsp;|&nbsp; Status: <b style='color:{color}'>{r['status'].upper()}</b>
                &nbsp;|&nbsp; {str(r['requested_at'])[:10]}
                {f"<br><small>Trainer note: {r['trainer_note']}</small>" if r.get('trainer_note') else ""}
            </div>""", unsafe_allow_html=True)
    else:
        st.info("No requests yet. Use the form above to request topics from your trainer.")


# ── AI CHAT ──────────────────────────────────────────────────────────────────
def _ai_chat():
    st.subheader("🤖 AI Study Assistant (Gemini)")
    st.caption("Ask anything about your studies — free AI tutor")

    if "chat_hist" not in st.session_state:
        st.session_state.chat_hist = []

    for msg in st.session_state.chat_hist:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_input = st.chat_input("Ask a study question...")
    if user_input:
        with st.chat_message("user"):
            st.write(user_input)
        st.session_state.chat_hist.append({"role":"user","content":user_input})
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                resp = chatbot_answer(user_input)
            st.write(resp)
        st.session_state.chat_hist.append({"role":"assistant","content":resp})

    if st.session_state.chat_hist:
        if st.button("🗑️ Clear Chat"):
            st.session_state.chat_hist = []
            st.rerun()


# ── QUERIES ──────────────────────────────────────────────────────────────────
def _queries(uid):
    st.subheader("📬 Send a Query to Trainer / Admin")

    with st.form("query_form", clear_on_submit=True):
        to_role = st.selectbox("Send to", ["trainer","admin"])
        subject = st.text_input("Subject", placeholder="e.g. Question about exam schedule")
        message = st.text_area("Your Message", placeholder="Type your question here...", height=100)
        if st.form_submit_button("📤 Send Query", type="primary", use_container_width=True):
            if message.strip():
                submit_query(uid, to_role, subject.strip(), message.strip())
                st.success("✅ Query sent!")
                st.rerun()
            else:
                st.warning("Please type a message.")

    st.markdown("---")
    st.markdown("#### 📋 My Query History")
    queries = get_student_queries(uid)
    if queries:
        for q in queries:
            icon = "✅" if q.get('reply') else "⏳"
            with st.expander(f"{icon} {q.get('subject') or 'General'} → {q['to_role']} | {str(q['asked_at'])[:10]}"):
                st.markdown(f"**Your question:** {q['message']}")
                if q.get('reply'):
                    st.success(f"**Reply:** {q['reply']}")
                else:
                    st.info("⏳ Awaiting reply...")
    else:
        st.info("No queries yet.")


# ── FEEDBACK ─────────────────────────────────────────────────────────────────
def _feedback(uid):
    st.subheader("💬 Give Feedback")
    with st.form("fb_form", clear_on_submit=True):
        category = st.selectbox("Category", [
            "User Experience", "Question Bank Feedback",
            "Assessment Feedback", "General"
        ])
        rating   = st.slider("Rating ⭐", 1, 5, 4)
        st.markdown(f"Your rating: {'⭐'*rating}{'☆'*(5-rating)}")
        comments = st.text_area("Comments", placeholder="Your thoughts...")
        if st.form_submit_button("Submit Feedback ⭐", type="primary", use_container_width=True):
            submit_feedback(uid, category, rating, comments)
            st.success("✅ Thank you for your feedback!")
            st.balloons()
