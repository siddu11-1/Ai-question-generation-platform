"""pages/trainer_page.py — v6 Gemini powered"""
import streamlit as st, pandas as pd, time, os
from utils.ui_theme import apply_theme, stars_html, badge
from utils.gemini_ai import (generate_mcqs_from_topic, generate_mcqs_from_text,
                              extract_topics_locally, is_configured)
from utils.pdf_utils import extract_text_from_pdf, extract_topics_from_excel
from database.questions_db import (create_question_bank, get_all_banks, insert_question,
                                    get_questions_by_bank, delete_question, delete_bank,
                                    get_question_count_by_difficulty)
from database.exams_db import get_trainer_bank_stats, get_queries_for_role, reply_to_query
from database.registration_db import get_all_bank_requests, update_bank_request_status
from database.links_db import (create_exam_link, get_trainer_links, deactivate_link,
                                get_link_requests, approve_access_request, reject_access_request,
                                get_trainer_plan, can_generate, use_quota, upgrade_plan,
                                get_trainer_bank_summary, get_student_by_roll,
                                get_students_sorted_by_subject, get_bank_star_leaderboard,
                                update_star_ratings_for_student, compute_star_rating)
from utils.analytics import difficulty_pie_chart

BASE_URL = os.environ.get("APP_BASE_URL","http://localhost:8501")


def render():
    apply_theme()
    st.title("🎓 Trainer Dashboard")

    # Gemini status banner
    if not is_configured():
        st.error("⚠️ Gemini API key not configured. Go to the login page to set it up.")
        return

    st.markdown("""
    <div style='background:linear-gradient(135deg,#eef7ee,#d4edda);border:1px solid #b2dfdb;
                border-radius:10px;padding:.7rem 1.2rem;margin-bottom:1rem;
                display:flex;align-items:center;gap:.6rem'>
        <span style='font-size:1.3rem'>🤖</span>
        <span><b>AI Engine: Google Gemini 1.5 Flash</b> &nbsp;|&nbsp; FREE &nbsp;|&nbsp;
        Fast batches of 5 questions (~6 sec each)</span>
    </div>""", unsafe_allow_html=True)

    # Live pending request count
    try:
        from database.db_setup import get_connection, dict_cursor as _dc
        _conn = get_connection(); _cur = _dc(_conn)
        _cur.execute("SELECT COUNT(*) as c FROM bank_requests WHERE status='pending'")
        _pb = _cur.fetchone()["c"]
        _cur.execute("""SELECT COUNT(*) as c FROM link_access_requests lar
                        JOIN exam_links el ON lar.link_id=el.id
                        WHERE lar.status='pending' AND el.trainer_id=%s""",
                     (st.session_state.user_id,))
        _pl = _cur.fetchone()["c"]
        _conn.close()
        _total = _pb + _pl
        _req_label = f"📬 Requests 🔴{_total}" if _total > 0 else "📬 Requests"
    except Exception:
        _req_label = "📬 Requests"

    tabs = st.tabs(["🧠 Generate (Topic)","📄 Generate (Document)","📥 Bulk Import",
                    "🔗 Exam Links","📊 Student Analytics","👤 Student Lookup",
                    "📚 My Banks", _req_label])
    with tabs[0]: tab_generate_topic()
    with tabs[1]: tab_generate_doc()
    with tabs[2]: tab_bulk_import()
    with tabs[3]: tab_exam_links()
    with tabs[4]: tab_analytics()
    with tabs[5]: tab_student_lookup()
    with tabs[6]: tab_banks()
    with tabs[7]: tab_requests()


# ── PLAN BAR ──────────────────────────────────────────────────────────────────
def _plan_bar(tid, key_suffix=""):
    plan  = get_trainer_plan(tid)
    used  = plan['questions_used']; limit = plan['questions_limit']
    pct   = min(used/limit, 1.0) if limit else 1.0
    rem   = limit - used
    color = "#27ae60" if pct < 0.7 else "#f39c12" if pct < 0.9 else "#e74c3c"
    st.markdown(f"""
    <div style='background:#f0f8f0;border:1px solid #b2dfdb;border-radius:10px;
                padding:.7rem 1.1rem;border-left:4px solid {color};margin-bottom:.5rem'>
        <b>📊 Question Plan: {plan['plan_type'].upper()}</b>
        &nbsp;&nbsp; Used: <b>{used}</b>/{limit}
        &nbsp;&nbsp; Remaining: <b style='color:{color}'>{rem}</b>
    </div>""", unsafe_allow_html=True)
    st.progress(pct)
    with st.expander("⬆️ Upgrade Plan"):
        opts = ["basic","standard","premium","unlimited"]
        labels = {"basic":"Basic (200 Q)","standard":"Standard (500 Q)",
                  "premium":"Premium (2000 Q)","unlimited":"Unlimited"}
        idx = opts.index(plan['plan_type']) if plan['plan_type'] in opts else 0
        new = st.selectbox("Select Plan", opts, index=idx,
                           format_func=lambda x: labels[x],
                           key=f"plan_{key_suffix}")
        if st.button("Apply Upgrade", key=f"upg_{key_suffix}"):
            upgrade_plan(tid, new); st.success(f"Upgraded to {labels[new]}!"); st.rerun()


# ── BANK SELECTOR ─────────────────────────────────────────────────────────────
def _bank_sel(px=""):
    banks = get_all_banks()
    new   = st.checkbox("➕ Create New Bank", key=f"{px}_newb")
    if new:
        with st.form(f"{px}_bform"):
            n = st.text_input("Bank Name*"); s = st.text_input("Subject"); t = st.text_input("Topic")
            if st.form_submit_button("Create Bank", type="primary"):
                if n:
                    bid = create_question_bank(n, s, t, st.session_state.user_id)
                    st.success(f"✅ Bank '{n}' created!")
                    st.session_state[f"{px}_bid"] = bid; st.rerun()
        return st.session_state.get(f"{px}_bid")
    if not banks: st.info("No banks yet. Create one above."); return None
    opts = {b['name']: b['id'] for b in banks}
    sel  = st.selectbox("Select Question Bank", list(opts.keys()), key=f"{px}_bsel")
    return opts[sel]


# ── REVIEW & SAVE ─────────────────────────────────────────────────────────────
def _review_save(key, bank_id):
    if key not in st.session_state or not st.session_state[key]: return
    qs = st.session_state[key]
    st.markdown("---")
    st.markdown(f"#### 📋 Review {len(qs)} Generated Questions")
    st.caption("Edit any question below, then save all to the question bank.")

    for i, q in enumerate(qs):
        diff_color = {"easy":"green","moderate":"orange","hard":"red"}.get(q.get("difficulty","moderate"),"blue")
        with st.expander(f"Q{i+1} {badge(q.get('difficulty','moderate').upper(), diff_color)} — {str(q.get('question',''))[:55]}...",
                         expanded=False):
            st.markdown(q.get('question',''), unsafe_allow_html=False)
            q["question"]       = st.text_area("Question Text", q.get("question",""), key=f"{key}q{i}", height=80)
            c1,c2 = st.columns(2)
            with c1:
                q["option_a"] = st.text_input("A)", q.get("option_a",""), key=f"{key}a{i}")
                q["option_b"] = st.text_input("B)", q.get("option_b",""), key=f"{key}b{i}")
            with c2:
                q["option_c"] = st.text_input("C)", q.get("option_c",""), key=f"{key}c{i}")
                q["option_d"] = st.text_input("D)", q.get("option_d",""), key=f"{key}d{i}")
            col1,col2 = st.columns(2)
            with col1:
                q["correct_option"] = st.selectbox("✅ Correct Answer", ["A","B","C","D"],
                    index=["A","B","C","D"].index(q.get("correct_option","A")), key=f"{key}co{i}")
            with col2:
                q["difficulty"] = st.selectbox("📊 Difficulty", ["easy","moderate","hard"],
                    index=["easy","moderate","hard"].index(q.get("difficulty","moderate")), key=f"{key}df{i}")
            q["explanation"] = st.text_area("💡 Explanation", q.get("explanation",""), key=f"{key}ex{i}", height=60)

    st.markdown("---")
    c1,c2,c3 = st.columns([2,1,1])
    with c1:
        if st.button("💾 Save All to Question Bank", type="primary", use_container_width=True, key=f"{key}_saveall"):
            if bank_id:
                for q in qs:
                    insert_question(bank_id, q.get("question",""), q.get("option_a",""),
                                    q.get("option_b",""), q.get("option_c",""), q.get("option_d",""),
                                    q.get("correct_option","A"), q.get("difficulty","moderate"),
                                    q.get("explanation",""))
                use_quota(st.session_state.user_id, len(qs))
                st.success(f"✅ {len(qs)} questions saved to bank!")
                del st.session_state[key]; st.rerun()
            else: st.error("No bank selected.")
    with c2:
        if st.button("🗑️ Discard All", use_container_width=True, key=f"{key}_disc"):
            del st.session_state[key]; st.rerun()


# ── TAB 1: GENERATE FROM TOPIC ────────────────────────────────────────────────
def tab_generate_topic():
    st.subheader("🧠 Generate MCQs from Topic")
    st.caption("Type any topic → Gemini generates high-quality MCQs instantly")
    _plan_bar(st.session_state.user_id, "t")
    st.markdown("---")
    bank_id = _bank_sel("t")
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        topic   = st.text_input("📚 Topic *", placeholder="e.g. Binary Search Trees")
        subject = st.text_input("📖 Subject", placeholder="e.g. Data Structures")
    with col2:
        n    = st.slider("Number of Questions", 3, 20, 5, key="tn")
        diff = st.selectbox("Difficulty Level", ["easy","moderate","hard"], key="td",
                            format_func=lambda x: {"easy":"🟢 Easy","moderate":"🟡 Moderate","hard":"🔴 Hard"}[x])

    if st.button("⚡ Generate Questions with Gemini", type="primary", use_container_width=True):
        ok, rem = can_generate(st.session_state.user_id, n)
        if not ok:
            st.error(f"❌ Plan quota exceeded. Only {rem} questions remaining. Upgrade your plan above.")
        elif not topic.strip():
            st.warning("Please enter a topic.")
        elif not bank_id:
            st.warning("Please select or create a question bank.")
        else:
            prog = st.progress(0, text=f"🤖 Generating {n} {diff} questions on '{topic}'...")
            try:
                qs = generate_mcqs_from_topic(topic.strip(), subject.strip(), n, diff)
                prog.progress(1.0, text=f"✅ Done! {len(qs)} questions ready.")
                st.session_state["gen_t"] = qs
                st.success(f"✅ {len(qs)} questions generated! Review them below.")
            except Exception as e:
                prog.empty()
                st.error(f"❌ {e}")

    _review_save("gen_t", bank_id)


# ── TAB 2: GENERATE FROM DOCUMENT ────────────────────────────────────────────
def tab_generate_doc():
    st.subheader("📄 Generate MCQs from Uploaded Document")
    st.markdown("""
    <div style='background:#e8f4fd;border-radius:10px;padding:1rem 1.2rem;margin-bottom:1rem'>
        <b>⚡ How it works (Fast — no timeout):</b><br>
        1️⃣ Upload your PDF, Excel, or CSV<br>
        2️⃣ Key topics extracted <b>locally</b> from document (instant, no API)<br>
        3️⃣ Gemini generates questions from extracted topics (~6 sec per 5 questions)<br>
        ✅ Total time: <b>~10-15 seconds</b> for 10 questions
    </div>""", unsafe_allow_html=True)

    _plan_bar(st.session_state.user_id, "d")
    st.markdown("---")
    bank_id  = _bank_sel("d")
    st.markdown("---")
    uploaded = st.file_uploader("📎 Upload Document (PDF / Excel / CSV)",
                                 type=["pdf","xlsx","xls","csv"])
    col1, col2 = st.columns(2)
    with col1: n    = st.slider("Questions to Generate", 3, 15, 5, key="dn",
                                 help="5-10 recommended for fastest results")
    with col2: diff = st.selectbox("Difficulty", ["easy","moderate","hard"], key="dd",
                                    format_func=lambda x: {"easy":"🟢 Easy","moderate":"🟡 Moderate","hard":"🔴 Hard"}[x])

    if uploaded:
        st.success(f"📄 Loaded: **{uploaded.name}** ({round(uploaded.size/1024,1)} KB)")
        if st.button("⚡ Extract & Generate", type="primary", use_container_width=True):
            ok, rem = can_generate(st.session_state.user_id, n)
            if not ok:
                st.error(f"❌ Quota exceeded. {rem} remaining.")
            elif not bank_id:
                st.warning("Select a question bank first.")
            else:
                with st.spinner("📖 Step 1/3 — Reading document..."):
                    try:
                        if uploaded.name.lower().endswith(".pdf"):
                            text = extract_text_from_pdf(uploaded)
                        else:
                            text = "\n".join(extract_topics_from_excel(uploaded))
                        if not text or str(text).startswith("ERROR"):
                            st.error(f"Cannot read file: {text}"); st.stop()
                    except Exception as e:
                        st.error(f"File read error: {e}"); st.stop()

                with st.spinner("🔍 Step 2/3 — Extracting key topics..."):
                    topics = extract_topics_locally(text, max_topics=8)
                    if topics:
                        st.markdown("**📌 Key topics found:**")
                        for t in topics[:4]:
                            st.markdown(f"&nbsp;&nbsp;• {t[:90]}")
                    time.sleep(0.5)

                prog = st.progress(0, text="🤖 Step 3/3 — Gemini generating questions...")
                try:
                    qs = generate_mcqs_from_text(text, n, diff)
                    prog.progress(1.0, text=f"✅ Done! {len(qs)} questions ready.")
                    st.session_state["gen_d"] = qs
                    st.success(f"✅ {len(qs)} questions generated!")
                except Exception as e:
                    prog.empty()
                    st.error(f"❌ {e}")

    _review_save("gen_d", bank_id)


# ── TAB 3: BULK IMPORT ────────────────────────────────────────────────────────
def tab_bulk_import():
    from utils.bulk_import import import_questions_from_csv, get_csv_template
    st.subheader("📥 Bulk Import Questions from CSV")
    st.download_button("📄 Download CSV Template", data=get_csv_template(),
                        file_name="question_template.csv", mime="text/csv")
    st.caption("Required columns: question_text, option_a, option_b, option_c, option_d, correct_option (A/B/C/D), difficulty (easy/moderate/hard), explanation")
    banks = get_all_banks()
    if not banks: st.warning("Create a bank first."); return
    opts = {b['name']: b['id'] for b in banks}
    sel  = st.selectbox("Target Question Bank", list(opts.keys()))
    f    = st.file_uploader("Upload CSV", type=["csv"])
    if f and st.button("⬆️ Import All Questions", type="primary"):
        with st.spinner("Importing..."):
            r = import_questions_from_csv(f, opts[sel])
        st.success(f"✅ {r['success']} questions imported!")
        if r['failed']:
            st.warning(f"⚠️ {r['failed']} rows skipped:")
            for e in r['errors']: st.caption(f"  • {e}")


# ── TAB 4: EXAM LINKS ─────────────────────────────────────────────────────────
def tab_exam_links():
    st.subheader("🔗 Shareable Exam Links")
    st.caption("Generate a link → share with students → they open in browser → request access → you approve")
    banks = get_all_banks()
    if not banks: st.warning("Create a question bank first."); return

    with st.expander("➕ Create New Exam Link", expanded=True):
        with st.form("lf"):
            opts   = {b["name"]: b["id"] for b in banks}
            bank   = st.selectbox("Question Bank", list(opts.keys()))
            c1, c2 = st.columns(2)
            with c1: title = st.text_input("Exam Title", placeholder="e.g. Mid-Semester Test")
            with c2: tlim  = st.number_input("Time Limit (mins, 0=none)", 0, 180, 0)
            desc   = st.text_area("Instructions for students", height=60)
            if st.form_submit_button("🔗 Generate Shareable Link", type="primary"):
                token, url = create_exam_link(opts[bank], st.session_state.user_id, title, desc, tlim)
                st.success("✅ Link created! Share this with students:")
                st.code(url)
                st.caption("Students can open this in any browser, request access, and take the exam after you approve.")
                st.session_state["last_link"] = url

    if "last_link" in st.session_state:
        st.info(f"📋 Last generated link: `{st.session_state['last_link']}`")

    # ── ACCESS REQUESTS (NEW vs EXISTING USER) ─────────────────────────────
    st.markdown("---")
    st.subheader("📬 Student Access Requests")
    st.caption("Review each request — see if it is a NEW or EXISTING user — then approve or reject")

    all_reqs = get_link_requests(trainer_id=st.session_state.user_id)
    pending  = [r for r in all_reqs if r["status"] == "pending"]
    approved = [r for r in all_reqs if r["status"] == "approved"]
    rejected = [r for r in all_reqs if r["status"] == "rejected"]

    col1, col2, col3 = st.columns(3)
    col1.metric("⏳ Pending",  len(pending))
    col2.metric("✅ Approved", len(approved))
    col3.metric("❌ Rejected", len(rejected))

    if pending:
        st.markdown(f"#### ⏳ Pending Requests ({len(pending)})")
        for r in pending:
            # Check if roll number already exists in DB
            from database.db_setup import get_connection, dict_cursor
            conn   = get_connection(); cursor = dict_cursor(conn)
            cursor.execute("SELECT id, username FROM users WHERE roll_number=%s", (r["roll_number"],))
            existing_user = cursor.fetchone(); conn.close()

            user_type = "🟡 EXISTING USER" if existing_user else "🆕 NEW USER"
            user_color = "#f39c12" if existing_user else "#2c7be5"

            with st.expander(
                f"👤 {r['full_name']} | Roll: {r['roll_number']} | "
                f"{r['exam_title']} | {user_type}",
                expanded=True
            ):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Name:** {r['full_name']}")
                    st.markdown(f"**Roll Number:** `{r['roll_number']}`")
                    st.markdown(f"**Exam:** {r['exam_title']}")
                    st.markdown(f"**Requested:** {str(r['requested_at'])[:16]}")
                with col2:
                    st.markdown(f"<b style='color:{user_color};font-size:1rem'>{user_type}</b>",
                                unsafe_allow_html=True)
                    if existing_user:
                        st.markdown(f"Existing username: `{existing_user['username']}`")
                        st.info("This student already has an account. Approving links their request.")
                    else:
                        st.info("New user — approving creates account with:\nUsername = name\nPassword = roll number")

                c1, c2 = st.columns(2)
                if c1.button("✅ Approve Access", key=f"apr_{r['id']}", type="primary"):
                    creds, msg = approve_access_request(r["id"])
                    if creds:
                        st.success(f"✅ Approved!")
                        st.markdown(f"""
                        <div style='background:#f0faf4;border:1px solid #27ae60;
                                    border-radius:8px;padding:1rem;margin-top:.5rem'>
                            <b>Student credentials:</b><br>
                            Username: <code>{creds["username"]}</code><br>
                            Password: <code>{creds["roll_number"]}</code>
                        </div>""", unsafe_allow_html=True)
                    else: st.error(msg)
                    st.rerun()
                if c2.button("❌ Reject", key=f"rjt_{r['id']}"):
                    reject_access_request(r["id"]); st.rerun()
    else:
        st.info("No pending access requests.")

    # Approved requests history
    if approved:
        with st.expander(f"✅ Approved Students ({len(approved)})"):
            for r in approved:
                st.markdown(f"✅ **{r['full_name']}** | Roll: `{r['roll_number']}` | {r['exam_title']}")

    # ── ALL MY LINKS ──────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📋 All My Exam Links")
    for lnk in get_trainer_links(st.session_state.user_id):
        s = "🟢 Active" if lnk["is_active"] else "🔴 Inactive"
        with st.expander(f"{s} | {lnk['title'] or lnk['bank_name']} | {lnk['approved']}/{lnk['total_requests']} approved"):
            url = f"{BASE_URL}/?exam_token={lnk['token']}"
            st.code(url)
            st.caption("Share this URL — students open it in browser, click Request Access")
            if lnk["is_active"]:
                if st.button("🔴 Deactivate Link", key=f"dact_{lnk['id']}"):
                    deactivate_link(lnk["id"]); st.rerun()




# ── TAB 5: STUDENT ANALYTICS ──────────────────────────────────────────────────
def tab_analytics():
    st.subheader("📊 Student Performance Analytics")
    st.caption("🔴 Live — data updates in real time from MySQL database")

    # Live counters
    from database.db_setup import get_connection, dict_cursor
    conn   = get_connection(); cursor = dict_cursor(conn)
    cursor.execute("SELECT COUNT(DISTINCT student_id) as c FROM exam_sessions WHERE completed_at IS NOT NULL")
    total_students = cursor.fetchone()["c"]
    cursor.execute("SELECT COUNT(*) as c FROM exam_sessions WHERE completed_at IS NOT NULL")
    total_attempts = cursor.fetchone()["c"]
    cursor.execute("SELECT COUNT(*) as c FROM questions")
    total_questions = cursor.fetchone()["c"]
    cursor.execute("SELECT COUNT(*) as c FROM link_access_requests WHERE status='pending'")
    pending_requests = cursor.fetchone()["c"]
    conn.close()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👥 Students Attempted", total_students)
    col2.metric("📝 Total Exam Attempts", total_attempts)
    col3.metric("❓ Questions in DB",     total_questions)
    col4.metric("⏳ Pending Requests",   pending_requests)
    st.markdown("---")

    banks = get_all_banks()
    if not banks: st.info("No question banks yet."); return

    summary = get_trainer_bank_summary(st.session_state.user_id)
    if summary:
        df = pd.DataFrame(summary)[["bank_name","subject","total_students","total_attempts",
                                     "avg_score","highest_score","lowest_score","total_passed"]]
        df.columns = ["Bank","Subject","Students","Attempts","Avg %","Highest %","Lowest %","Passed"]
        st.markdown("#### 📋 All Banks Overview")
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")
    opts = {b['name']: b['id'] for b in banks}
    sel  = st.selectbox("Select Bank for Detailed Report", list(opts.keys()))
    bid  = opts[sel]

    from database.registration_db import get_rankings_for_bank
    rankings = get_rankings_for_bank(bid)
    if not rankings:
        st.info("No students have taken this exam yet."); return

    df = pd.DataFrame(rankings)
    disp = df[["rank","username","full_name","avg_score","best_score","total_passed","total_exams"]].copy()
    disp.columns = ["Rank","Username","Name","Avg %","Best %","Passed","Attempts"]
    disp.insert(4, "Stars", disp["Avg %"].apply(lambda x: stars_html(compute_star_rating(x or 0))))

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 🥇 Top 5 Students")
        st.dataframe(disp.head(5), use_container_width=True, hide_index=True)
    with col2:
        st.markdown("#### ⚠️ Bottom 5 (Need Support)")
        st.dataframe(disp.tail(5), use_container_width=True, hide_index=True)

    st.markdown("---")
    scores = [r['avg_score'] for r in rankings if r.get('avg_score')]
    if scores:
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("📊 Class Avg", f"{sum(scores)/len(scores):.1f}%")
        c2.metric("🏆 Highest",   f"{max(scores):.1f}%")
        c3.metric("📉 Lowest",    f"{min(scores):.1f}%")
        c4.metric("👥 Students",  len(rankings))

    # Download Excel
    try:
        import io
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as wr:
            disp.to_excel(wr, index=False, sheet_name="Rankings")
        buf.seek(0)
        st.download_button("📥 Download Full Report (.xlsx)", data=buf.getvalue(),
                           file_name=f"report_{sel}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception: pass


# ── TAB 6: STUDENT LOOKUP ─────────────────────────────────────────────────────
def tab_student_lookup():
    st.subheader("👤 Student Lookup")
    t1, t2 = st.tabs(["🔍 Search by Roll Number","📊 Sort by Subject %"])

    with t1:
        col1, col2 = st.columns([3,1])
        with col1: roll = st.text_input("Roll Number", placeholder="e.g. ROLL2024001")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            search = st.button("🔍 Search", type="primary")
        if search and roll:
            s = get_student_by_roll(roll.strip())
            if s:
                stars = compute_star_rating(s.get('overall_avg') or 0)
                st.markdown(f"""
                <div style='background:#f0f6ff;border-radius:12px;padding:1.5rem;
                            border-left:5px solid #2c7be5;margin-top:1rem'>
                    <h3 style='color:#0f2744;margin:0 0 .8rem'>👤 {s.get('full_name','—')}</h3>
                    <div style='display:grid;grid-template-columns:1fr 1fr;gap:.5rem'>
                        <p>🎫 <b>Roll No:</b> {s.get('roll_number','—')}</p>
                        <p>📧 <b>Email:</b> {s.get('email','—')}</p>
                        <p>📱 <b>Phone:</b> {s.get('phone','—')}</p>
                        <p>📝 <b>Total Exams:</b> {s.get('total_exams',0)}</p>
                        <p>✅ <b>Passed:</b> {s.get('total_passed',0)}</p>
                        <p>📊 <b>Avg Score:</b> <b style='color:#2c7be5'>{(s.get('overall_avg') or 0):.1f}%</b></p>
                    </div>
                    <p style='font-size:1.3rem;margin:.5rem 0 0'>{stars_html(stars)} {stars}/5 Stars</p>
                </div>""", unsafe_allow_html=True)
            else:
                st.error(f"No student found with roll number '{roll}'")

    with t2:
        subj = st.text_input("Filter by Subject (leave blank for all subjects)",
                              placeholder="e.g. Python, Mathematics")
        if st.button("📊 Load Sorted Students", type="primary"):
            data = get_students_sorted_by_subject(subj.strip() or None)
            if data:
                df = pd.DataFrame(data)
                df['Stars'] = df['avg_score'].apply(
                    lambda x: stars_html(compute_star_rating(x or 0)))
                cols = [c for c in ["full_name","roll_number","email","avg_score","best_score","passed","Stars"] if c in df.columns]
                show = df[cols].copy()
                show.columns = [c.replace("_"," ").title() for c in cols]
                st.dataframe(show, use_container_width=True, hide_index=True)
                try:
                    import io
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf, engine='openpyxl') as wr:
                        show.to_excel(wr, index=False)
                    buf.seek(0)
                    st.download_button("📥 Download Excel", data=buf.getvalue(),
                                       file_name="students_by_score.xlsx",
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                except Exception: pass
            else:
                st.info("No data found.")


# ── TAB 7: BANKS ──────────────────────────────────────────────────────────────
def tab_banks():
    st.subheader("📚 My Question Banks")
    banks = get_all_banks()
    if not banks: st.info("No question banks yet."); return
    for b in banks:
        with st.expander(f"📘 {b['name']} — {b['subject']} — {b['question_count']} questions"):
            col1,col2 = st.columns([3,1])
            col1.markdown(f"**Created by:** {b['trainer_name']} | **Date:** {str(b['created_at'])[:10]}")
            bd = get_question_count_by_difficulty(b['id'])
            col1.markdown(f"🟢 Easy: `{bd.get('easy',0)}` &nbsp; 🟡 Moderate: `{bd.get('moderate',0)}` &nbsp; 🔴 Hard: `{bd.get('hard',0)}`")
            if any(bd.values()): st.plotly_chart(difficulty_pie_chart(bd), use_container_width=True)
            if col2.button("🗑️ Delete Bank", key=f"db_{b['id']}"):
                delete_bank(b['id']); st.rerun()
            qs = get_questions_by_bank(b['id'])
            for q in qs:
                qc1,qc2 = st.columns([4,1])
                diff_label = {"easy":"🟢","moderate":"🟡","hard":"🔴"}.get(q['difficulty'],"•")
                qc1.markdown(f"{diff_label} {q['question_text'][:80]}...")
                if qc2.button("Delete", key=f"dq_{q['id']}"): delete_question(q['id']); st.rerun()


# ── TAB 8: REQUESTS & QUERIES ─────────────────────────────────────────────────
def tab_requests():
    """Shows BOTH: exam link access requests AND question bank requests from students."""

    # ── Live counts ───────────────────────────────────────────────────────────
    bank_reqs = get_all_bank_requests()
    pending_bank = [r for r in bank_reqs if r['status'] == 'pending']

    # Exam link access requests for THIS trainer
    link_reqs = get_link_requests(trainer_id=st.session_state.user_id)
    pending_link = [r for r in link_reqs if r['status'] == 'pending']

    qs_all    = get_queries_for_role("trainer")
    pending_q = [q for q in qs_all if not q.get('reply')]

    total_pending = len(pending_bank) + len(pending_link)

    # Top alert banners
    if pending_link:
        st.error(f"🔴 {len(pending_link)} student(s) waiting for EXAM ACCESS approval — approve below!")
    if pending_bank:
        st.warning(f"📚 {len(pending_bank)} new question bank request(s) from students")
    if not total_pending and not pending_q:
        st.success("✅ All caught up! No pending requests.")

    # ── TABS ──────────────────────────────────────────────────────────────────
    t1, t2, t3 = st.tabs([
        f"🔗 Exam Access Requests {'🔴 ' + str(len(pending_link)) if pending_link else '(' + str(len(link_reqs)) + ')'}",
        f"📚 Bank Requests {'🔴 ' + str(len(pending_bank)) if pending_bank else '(' + str(len(bank_reqs)) + ')'}",
        f"📬 Queries {'⏳ ' + str(len(pending_q)) if pending_q else ''}"
    ])

    # ── TAB 1: EXAM LINK ACCESS REQUESTS ─────────────────────────────────────
    with t1:
        st.subheader("🔗 Student Exam Access Requests")
        st.caption("Students who clicked 'Request Access' on your exam link — approve to give them login credentials")

        if not link_reqs:
            st.info("No access requests yet. Share your exam link with students — they click 'Request Access' on it.")
        else:
            # Show pending first
            all_sorted = sorted(link_reqs, key=lambda x: 0 if x['status']=='pending' else 1)
            for r in all_sorted:
                bg    = {"pending":"#fff8e1","approved":"#f0faf4","rejected":"#fef5f5"}.get(r['status'],"#f5f5f5")
                color = {"pending":"#f39c12","approved":"#27ae60","rejected":"#e74c3c"}.get(r['status'],"#888")
                icon  = {"pending":"⏳","approved":"✅","rejected":"❌"}.get(r['status'],"•")

                # Check if new or existing user
                try:
                    conn2 = get_connection(); cur2 = dict_cursor(conn2)
                    cur2.execute("SELECT id, username FROM users WHERE roll_number=%s", (r.get('roll_number',''),))
                    existing = cur2.fetchone(); conn2.close()
                    user_type = f"🟡 EXISTING USER ({existing['username']})" if existing else "🆕 NEW USER"
                    utype_color = "#f39c12" if existing else "#2c7be5"
                except Exception:
                    user_type = ""; utype_color = "#888"

                with st.expander(
                    f"{icon} {r.get('full_name','?')} | Roll: {r.get('roll_number','?')} "
                    f"| {r.get('exam_title','Exam')} | {r['status'].upper()}",
                    expanded=(r['status'] == 'pending')
                ):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**👤 Name:** {r.get('full_name','—')}")
                        st.markdown(f"**🎫 Roll No:** `{r.get('roll_number','—')}`")
                        st.markdown(f"**📝 Exam:** {r.get('exam_title','—')}")
                        st.markdown(f"**📅 Requested:** {str(r.get('requested_at',''))[:16]}")
                    with col2:
                        st.markdown(f"<b style='color:{utype_color};font-size:1rem'>{user_type}</b>",
                                    unsafe_allow_html=True)
                        if "EXISTING" in user_type:
                            st.info("Student already has account. Approving links their exam access.")
                        else:
                            st.info("New student. Approving creates account:\nUsername = name\nPassword = roll number")

                    if r['status'] == 'pending':
                        c1, c2 = st.columns(2)
                        if c1.button("✅ Approve Access", key=f"link_apr_{r['id']}", type="primary"):
                            creds, msg = approve_access_request(r['id'])
                            if creds:
                                st.success("✅ Approved!")
                                st.markdown(f"""
                                <div style='background:#f0faf4;border:1px solid #27ae60;
                                            border-radius:8px;padding:1rem;margin-top:.5rem'>
                                    <b>Tell the student their login:</b><br>
                                    Username: <code>{creds['username']}</code><br>
                                    Password: <code>{creds['roll_number']}</code>
                                </div>""", unsafe_allow_html=True)
                            else:
                                st.error(msg)
                            st.rerun()
                        if c2.button("❌ Reject", key=f"link_rej_{r['id']}"):
                            reject_access_request(r['id']); st.rerun()

    # ── TAB 2: QUESTION BANK REQUESTS ─────────────────────────────────────────
    with t2:
        st.subheader("📚 Question Bank Requests")
        st.caption("Students requested new question topics — create questions for approved requests")

        if not bank_reqs:
            st.info("No bank requests yet. Students can request topics from their student portal.")
        else:
            all_sorted2 = sorted(bank_reqs, key=lambda x: 0 if x['status']=='pending' else 1)
            for r in all_sorted2:
                bg    = {"pending":"#fff8e1","approved":"#f0faf4","rejected":"#fef5f5"}.get(r['status'],"#f5f5f5")
                color = {"pending":"#f39c12","approved":"#27ae60","rejected":"#e74c3c"}.get(r['status'],"#888")
                icon  = {"pending":"⏳","approved":"✅","rejected":"❌"}.get(r['status'],"•")

                with st.expander(
                    f"{icon} [{r['status'].upper()}] {r['subject']} — {r.get('full_name','?')} — {str(r.get('requested_at',''))[:10]}",
                    expanded=(r['status'] == 'pending')
                ):
                    st.markdown(f"""
                    <div style='background:{bg};border-radius:8px;padding:.8rem 1rem;border-left:4px solid {color}'>
                        👤 <b>Student:</b> {r.get('full_name','—')} &nbsp;|&nbsp; 📧 {r.get('email','—')}<br>
                        📖 <b>Subject:</b> {r['subject']}<br>
                        📝 <b>Description:</b> {r.get('description') or '—'}
                    </div>""", unsafe_allow_html=True)

                    if r['status'] == 'pending':
                        note = st.text_input("Note to student:", key=f"bn_{r['id']}",
                                            placeholder="e.g. Will create by tomorrow")
                        c1, c2 = st.columns(2)
                        if c1.button("✅ Approve", key=f"bap_{r['id']}", type="primary"):
                            update_bank_request_status(r['id'], "approved", note)
                            st.success("Approved! Go to Generate tab to create questions for this topic.")
                            st.rerun()
                        if c2.button("❌ Reject", key=f"brj_{r['id']}"):
                            update_bank_request_status(r['id'], "rejected", note)
                            st.rerun()

    # ── TAB 3: QUERIES ────────────────────────────────────────────────────────
    with t3:
        st.subheader("📬 Student Queries")
        if not qs_all:
            st.info("No queries yet.")
        for q in qs_all:
            icon2 = "✅" if q.get('reply') else "⏳"
            with st.expander(
                f"{icon2} From: {q['from_username']} | {q.get('subject') or 'General'} | {str(q['asked_at'])[:10]}",
                expanded=not q.get('reply')
            ):
                st.markdown(f"**Question:** {q['message']}")
                if q.get('reply'):
                    st.success(f"✅ Your Reply: {q['reply']}")
                else:
                    rp = st.text_area("Write reply:", key=f"rp_{q['id']}")
                    if st.button("📤 Send Reply", key=f"sp_{q['id']}", type="primary"):
                        if rp.strip():
                            reply_to_query(q['id'], rp, st.session_state.user_id)
                            st.rerun()

