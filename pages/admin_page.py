"""pages/admin_page.py — v6"""
import streamlit as st, pandas as pd, io
from utils.ui_theme import apply_theme, stars_html, badge
from database.auth import get_all_users, create_user, deactivate_user, reset_password
from database.questions_db import get_all_banks
from database.exams_db import (get_all_student_performance, get_queries_for_role,
                                reply_to_query, get_all_feedback, get_feedback_summary)
from database.db_setup import get_connection, dict_cursor
from database.registration_db import (get_rankings_for_bank, get_overall_rankings,
                                       create_result_schedule, get_all_schedules,
                                       get_pending_schedules, mark_schedule_sent,
                                       delete_schedule, get_students_for_bank,
                                       get_all_student_emails)
from database.links_db import (get_trainer_exam_report, get_trainer_bank_summary,
                                compute_star_rating, get_students_sorted_by_subject,
                                get_student_by_roll)
from utils.analytics import score_distribution_chart, leaderboard_chart, feedback_bar_chart
from utils.email_utils import send_scheduled_result_email
from datetime import date


def render():
    apply_theme()
    st.title("🛡️ Admin Dashboard")
    st.markdown("---")
    tabs = st.tabs(["📊 Overview","🏆 Rankings","👨‍🏫 Trainer Reports",
                    "🗄️ Student Database","📅 Schedule Emails",
                    "👥 Users","📬 Queries","💬 Feedback"])
    with tabs[0]: tab_overview()
    with tabs[1]: tab_rankings()
    with tabs[2]: tab_trainer_reports()
    with tabs[3]: tab_student_db()
    with tabs[4]: tab_schedule()
    with tabs[5]: tab_users()
    with tabs[6]: tab_queries()
    with tabs[7]: tab_feedback()


def tab_overview():
    st.subheader("📊 System Overview")
    conn = get_connection(); c = dict_cursor(conn)
    stats = {}
    queries = {
        "users":     "SELECT COUNT(*) as cnt FROM users WHERE is_active=1",
        "students":  "SELECT COUNT(*) as cnt FROM users WHERE role='student' AND is_active=1",
        "trainers":  "SELECT COUNT(*) as cnt FROM users WHERE role='trainer' AND is_active=1",
        "banks":     "SELECT COUNT(*) as cnt FROM question_banks",
        "questions": "SELECT COUNT(*) as cnt FROM questions",
        "exams":     "SELECT COUNT(*) as cnt FROM exam_sessions WHERE completed_at IS NOT NULL",
    }
    for key, sql in queries.items():
        c.execute(sql)
        row = c.fetchone()
        stats[key] = row["cnt"] if row else 0
    conn.close()

    cols = st.columns(6)
    for col, (icon, label, key) in zip(cols, [
        ("👥","Active Users","users"),("🎓","Students","students"),
        ("👨‍🏫","Trainers","trainers"),("📚","Banks","banks"),
        ("❓","Questions","questions"),("📝","Exams Taken","exams")
    ]):
        col.metric(f"{icon} {label}", stats[key])

    st.markdown("---")
    perf = get_all_student_performance()
    if perf:
        c1,c2 = st.columns(2)
        with c1: st.plotly_chart(leaderboard_chart(perf,8), use_container_width=True)
        with c2: st.plotly_chart(score_distribution_chart(perf), use_container_width=True)

        df = pd.DataFrame(perf)
        df.columns = ["Username","Full Name","Total Exams","Avg Score (%)","Passed","Best Score (%)"]
        def hl(row):
            return ["background:#ffe0e0"]*len(row) if row["Avg Score (%)"] and row["Avg Score (%)"]<50 else [""]*len(row)
        st.dataframe(df.style.apply(hl,axis=1), use_container_width=True, hide_index=True)
        st.caption("🔴 Red = avg below 50% — may need extra support")
    else:
        st.info("No exam data yet.")


def tab_rankings():
    st.subheader("🏆 Student Rankings")
    t1,t2 = st.tabs(["🌍 Overall Rankings","📘 By Question Bank"])

    with t1:
        data = get_overall_rankings()
        if data:
            df = pd.DataFrame(data)[["rank","username","full_name","email","total_exams","avg_score","best_score","total_passed"]]
            df.columns = ["Rank","Username","Name","Email","Exams","Avg %","Best %","Passed"]
            df.insert(5,"Stars",df["Avg %"].apply(lambda x: stars_html(compute_star_rating(x or 0))))
            def medal(row):
                r = row["Rank"]
                if r==1: return ["background:#fff9c4"]*len(row)
                if r==2: return ["background:#f5f5f5"]*len(row)
                if r==3: return ["background:#fbe9e7"]*len(row)
                return [""]*len(row)
            st.dataframe(df.style.apply(medal,axis=1), use_container_width=True, hide_index=True)
            try:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf,engine='openpyxl') as wr: df.to_excel(wr,index=False,sheet_name="Rankings")
                buf.seek(0)
                st.download_button("📥 Download Rankings (.xlsx)", data=buf.getvalue(),
                                   file_name="overall_rankings.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception: pass
        else: st.info("No exam data yet.")

    with t2:
        banks = get_all_banks()
        if not banks: st.info("No banks yet."); return
        opts = {b['name']: b['id'] for b in banks}
        sel  = st.selectbox("Select Bank", list(opts.keys()), key="rb_sel")
        data = get_rankings_for_bank(opts[sel])
        if data:
            df = pd.DataFrame(data)[["rank","username","full_name","avg_score","best_score","total_passed","total_exams"]]
            df.columns = ["Rank","Username","Name","Avg %","Best %","Passed","Attempts"]
            df.insert(4,"Stars",df["Avg %"].apply(lambda x: stars_html(compute_star_rating(x or 0))))
            st.dataframe(df, use_container_width=True, hide_index=True)
        else: st.info("No students have attempted this bank yet.")


def tab_trainer_reports():
    st.subheader("👨‍🏫 Trainer Exam Reports")
    st.caption("See each trainer's exams — top/bottom performers, avg/highest/lowest marks — downloadable Excel")
    conn = get_connection(); c = dict_cursor(conn)
    c.execute("SELECT id,username,full_name FROM users WHERE role='trainer' AND is_active=1")
    trainers = c.fetchall(); conn.close()
    if not trainers: st.info("No trainers."); return

    opts = {f"{t['full_name'] or t['username']}": t['id'] for t in trainers}
    sel  = st.selectbox("Select Trainer", list(opts.keys()))
    tid  = opts[sel]

    summary = get_trainer_bank_summary(tid)
    if not summary: st.info("This trainer has no question banks yet."); return

    df_sum = pd.DataFrame(summary)[["bank_name","subject","total_students","total_attempts",
                                     "avg_score","highest_score","lowest_score","total_passed"]]
    df_sum.columns = ["Bank","Subject","Students","Attempts","Avg %","Highest %","Lowest %","Passed"]
    st.markdown("#### 📋 Banks Summary")
    st.dataframe(df_sum, use_container_width=True, hide_index=True)

    report = get_trainer_exam_report(tid)
    if report:
        df = pd.DataFrame(report)
        df.columns = ["Bank","Subject","Username","Full Name","Roll No","Email",
                       "Attempts","Avg %","Highest %","Lowest %","Passed"]

        for bank in df["Bank"].unique():
            bdf = df[df["Bank"]==bank].sort_values("Avg %", ascending=False)
            st.markdown(f"---\n#### 📘 {bank}")
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Students",  len(bdf))
            c2.metric("Class Avg", f"{bdf['Avg %'].mean():.1f}%")
            c3.metric("Highest",   f"{bdf['Highest %'].max():.1f}%")
            c4.metric("Lowest",    f"{bdf['Lowest %'].min():.1f}%")
            col1,col2 = st.columns(2)
            with col1:
                st.markdown("**🥇 Top 5**")
                st.dataframe(bdf[["Full Name","Roll No","Avg %","Passed"]].head(5), use_container_width=True, hide_index=True)
            with col2:
                st.markdown("**⚠️ Bottom 5**")
                st.dataframe(bdf[["Full Name","Roll No","Avg %","Passed"]].tail(5), use_container_width=True, hide_index=True)

        try:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf,engine='openpyxl') as wr:
                df.to_excel(wr,index=False,sheet_name="Full Report")
                df_sum.to_excel(wr,index=False,sheet_name="Summary")
            buf.seek(0)
            st.download_button(f"📥 Download Full Report for {sel} (.xlsx)",
                               data=buf.getvalue(),
                               file_name=f"trainer_{sel.replace(' ','_')}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except ImportError: st.warning("Install openpyxl: pip install openpyxl")


def tab_student_db():
    st.subheader("🗄️ Student Database")
    t1,t2,t3 = st.tabs(["📋 All Students","🔍 Roll Number Search","📊 Sort by Subject"])

    with t1:
        conn = get_connection(); c = dict_cursor(conn)
        c.execute("""SELECT u.id,u.username,u.full_name,u.email,u.phone,u.roll_number,
                            u.created_at,COUNT(DISTINCT es.bank_id) as banks,
                            COUNT(es.id) as exams,ROUND(AVG(es.score),1) as avg,SUM(es.passed) as passed
                     FROM users u LEFT JOIN exam_sessions es ON es.student_id=u.id AND es.completed_at IS NOT NULL
                     WHERE u.role='student' GROUP BY u.id ORDER BY u.created_at DESC""")
        rows = c.fetchall(); conn.close()
        if rows:
            df = pd.DataFrame(rows)
            df['Stars'] = df['avg'].apply(lambda x: stars_html(compute_star_rating(x or 0)))
            df.columns = ["ID","Username","Full Name","Email","Phone","Roll No","Registered",
                           "Banks","Exams","Avg %","Passed","Stars"]
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"Total: {len(rows)} students")
            try:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf,engine='openpyxl') as wr: df.to_excel(wr,index=False)
                buf.seek(0)
                st.download_button("📥 Download All Students (.xlsx)", data=buf.getvalue(),
                                   file_name="all_students.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception: pass
        else: st.info("No students registered yet.")

    with t2:
        col1,col2 = st.columns([3,1])
        with col1: roll = st.text_input("Enter Roll Number", placeholder="ROLL2024001")
        with col2:
            st.markdown("<br>",unsafe_allow_html=True)
            search = st.button("🔍 Search", type="primary", key="admin_roll_search")
        if search and roll:
            s = get_student_by_roll(roll.strip())
            if s:
                stars = compute_star_rating(s.get('overall_avg') or 0)
                st.markdown(f"""
                <div style='background:#f0f6ff;border-radius:12px;padding:1.5rem;border-left:5px solid #2c7be5'>
                  <h3 style='color:#0f2744;margin:0 0 .8rem'>👤 {s.get('full_name','—')}</h3>
                  <p>🎫 Roll: <b>{s.get('roll_number','—')}</b> | 📧 {s.get('email','—')} | 📱 {s.get('phone','—')}</p>
                  <p>📝 Exams: <b>{s.get('total_exams',0)}</b> | ✅ Passed: <b>{s.get('total_passed',0)}</b>
                     | 📊 Avg: <b style='color:#2c7be5'>{(s.get('overall_avg') or 0):.1f}%</b>
                     | <span style='font-size:1.2rem'>{stars_html(stars)}</span></p>
                </div>""", unsafe_allow_html=True)
            else: st.error(f"No student found with roll number '{roll}'")

    with t3:
        subj = st.text_input("Subject filter (blank = all)", placeholder="e.g. Python")
        if st.button("📊 Load Sorted", type="primary", key="admin_sort"):
            data = get_students_sorted_by_subject(subj.strip() or None)
            if data:
                df = pd.DataFrame(data)
                df['Stars'] = df['avg_score'].apply(lambda x: stars_html(compute_star_rating(x or 0)))
                cols = [c for c in ["full_name","roll_number","email","avg_score","best_score","passed","Stars"] if c in df.columns]
                show = df[cols].copy(); show.columns=[c.replace("_"," ").title() for c in cols]
                st.dataframe(show, use_container_width=True, hide_index=True)
                try:
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf,engine='openpyxl') as wr: show.to_excel(wr,index=False)
                    buf.seek(0)
                    st.download_button("📥 Download (.xlsx)", data=buf.getvalue(), file_name="sorted.xlsx",
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                except Exception: pass
            else: st.info("No data.")


def tab_schedule():
    st.subheader("📅 Schedule Result Emails")
    today_str = str(date.today())
    pending   = get_pending_schedules(today_str)
    if pending:
        st.warning(f"⚠️ {len(pending)} scheduled email(s) due today!")
        if st.button("📧 Send All Now", type="primary"):
            count = 0
            for sched in pending:
                students = (get_students_for_bank(sched['bank_id'])
                            if sched.get('bank_id') else get_all_student_emails())
                for s in students:
                    if not s.get('email'): continue
                    send_scheduled_result_email(
                        s['email'], s.get('full_name') or s.get('username','Student'),
                        [{"bank_name":"Exam","score":s.get('score',0) or 0,
                          "passed":s.get('passed',0),"date":s.get('completed_at','')}],
                        today_str)
                    count += 1
                mark_schedule_sent(sched['id'])
            st.success(f"✅ Sent to {count} students!"); st.rerun()

    with st.form("sched_form"):
        banks = get_all_banks()
        opts  = {"All Students": None}
        opts.update({b['name']: b['id'] for b in banks})
        c1,c2 = st.columns(2)
        with c1:
            sel   = st.selectbox("Bank", list(opts.keys()))
            sdate = st.date_input("Send Date", min_value=date.today())
        with c2:
            stime = st.time_input("Send Time")
            msg   = st.text_area("Optional Message", height=80)
        if st.form_submit_button("📅 Create Schedule", type="primary"):
            create_result_schedule(opts[sel], str(sdate), str(stime)[:5], msg, st.session_state.user_id)
            st.success(f"✅ Scheduled for {sdate}!"); st.rerun()

    st.markdown("---")
    for s in get_all_schedules():
        status = "✅ Sent" if s['sent'] else "⏳ Pending"
        with st.expander(f"{status} | {s['send_date']} | Bank: {s.get('bank_name') or 'All'}"):
            st.write(f"Message: {s['message'] or '—'}")
            if not s['sent']:
                if st.button("🗑️ Delete", key=f"ds_{s['id']}"): delete_schedule(s['id']); st.rerun()


def tab_users():
    st.subheader("👥 User Management")
    with st.expander("➕ Create New User"):
        with st.form("cuf"):
            c1,c2 = st.columns(2)
            with c1:
                un=st.text_input("Username*"); pw=st.text_input("Password*",type="password")
                ro=st.selectbox("Role",["student","trainer","admin"])
            with c2:
                fn=st.text_input("Full Name"); em=st.text_input("Email")
            if st.form_submit_button("Create User",type="primary"):
                if un and pw:
                    if create_user(un,pw,ro,fn,em): st.success(f"✅ '{un}' created.")
                    else: st.error("Username already exists.")
    users = get_all_users()
    for u in users:
        c1,c2,c3,c4,c5 = st.columns([2,2,1,1,1])
        c1.write(f"**{u['username']}**"); c2.write(u.get('full_name') or "—")
        c3.write(f"`{u['role']}`"); c4.write("✅" if u['is_active'] else "🔴")
        if u['username']!=st.session_state.username and u['is_active']:
            if c5.button("Deactivate",key=f"dc_{u['id']}"):
                deactivate_user(u['id']); st.rerun()
    st.markdown("---")
    with st.form("rpf"):
        c1,c2 = st.columns(2)
        with c1: target=st.selectbox("User",[u['username'] for u in users])
        with c2: npw=st.text_input("New Password",type="password")
        if st.form_submit_button("🔑 Reset Password"):
            if npw:
                uid = next(u['id'] for u in users if u['username']==target)
                reset_password(uid,npw); st.success(f"Password reset for '{target}'.")


def tab_queries():
    st.subheader("📬 Queries")
    qs = get_queries_for_role("admin")
    if not qs: st.info("No queries."); return
    for q in qs:
        with st.expander(f"From: {q['from_username']} | {q['subject'] or 'General'} | {str(q['asked_at'])[:10]}"):
            st.markdown(f"**Message:** {q['message']}")
            if q['reply']: st.success(f"**Reply:** {q['reply']}")
            else:
                rt=st.text_area("Reply:",key=f"rq_{q['id']}")
                if st.button("📤 Send",key=f"sq_{q['id']}",type="primary"):
                    if rt.strip(): reply_to_query(q['id'],rt,st.session_state.user_id); st.rerun()


def tab_feedback():
    st.subheader("💬 Feedback Analytics")
    summary = get_feedback_summary(); all_fb = get_all_feedback()
    if summary:
        st.plotly_chart(feedback_bar_chart(summary), use_container_width=True)
        df=pd.DataFrame(summary); df.columns=["Category","Count","Avg Rating"]
        st.dataframe(df, use_container_width=True, hide_index=True)
    if all_fb:
        df2=pd.DataFrame(all_fb)[["username","category","rating","comments","submitted_at"]]
        df2.columns=["Student","Category","Rating","Comments","Date"]
        st.dataframe(df2, use_container_width=True, hide_index=True)
    else: st.info("No feedback yet.")
