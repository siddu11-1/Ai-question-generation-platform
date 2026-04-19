"""
app.py — v6  Gemini-powered AI Question System
"""
import streamlit as st, os
from dotenv import load_dotenv
load_dotenv()

from database.db_setup import initialize_database
from database.auth import authenticate_user
from pages import admin_page, trainer_page, student_page
from pages.signup_page import render as signup_render
from pages.exam_link_page import render as link_render
from utils.ui_theme import apply_theme
from utils.gemini_ai import is_configured, get_gemini_key
from database.db_setup import test_connection

st.set_page_config(
    page_title="AI Question System",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)
apply_theme()
initialize_database()

for k, v in [("logged_in",False),("username",""),("role",""),
             ("user_id",None),("show_signup",False),
             ("exam_token",None),("link_student_id",None)]:
    if k not in st.session_state:
        st.session_state[k] = v

# Check URL param for exam token
try:
    params = st.query_params
    if "exam_token" in params and not st.session_state.exam_token:
        st.session_state.exam_token = params["exam_token"]
except Exception:
    pass


def show_login():
    # Hero header
    st.markdown("""
    <div style='background:linear-gradient(135deg,#0f2744 0%,#2c7be5 100%);
                padding:3rem 2rem;border-radius:16px;text-align:center;
                color:white;margin-bottom:2rem'>
        <div style='font-size:3rem'>🧠</div>
        <h1 style='color:white!important;border:none!important;font-size:2.2rem;margin:.5rem 0'>
            AI Question Generation System
        </h1>
        <p style='opacity:.85;font-size:1.1rem;margin:0'>
            Powered by Google Gemini · Smart MCQ Generation · Adaptive Learning
        </p>
    </div>""", unsafe_allow_html=True)

    # MySQL connection status
    db_ok, db_msg = test_connection()
    if not db_ok:
        st.markdown(f"""
        <div style='background:#fee2e2;border:2px solid #e74c3c;border-radius:12px;
                    padding:1.5rem;margin-bottom:1.5rem'>
            <h3 style='color:#991b1b;margin:0 0 .8rem'>🔴 MySQL Not Connected</h3>
            <p style='margin:0;color:#555'>Error: <code>{db_msg}</code></p>
            <p style='margin:.5rem 0 0;color:#555'>
                <b>Fix:</b> Open your <code>.env</code> file and set correct
                DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD values.
            </p>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style='background:#dcfce7;border:1px solid #b2dfdb;border-radius:8px;
                    padding:.5rem 1rem;margin-bottom:1rem;font-size:.9rem'>
            🟢 <b>MySQL Connected</b> — {db_msg}
        </div>""", unsafe_allow_html=True)

    # Gemini key setup
    if not is_configured():
        st.markdown("""
        <div style='background:#fff8e1;border:2px solid #f39c12;border-radius:12px;
                    padding:1.5rem;margin-bottom:1.5rem'>
            <h3 style='color:#7d4e00;margin:0 0 .8rem'>⚙️ One-Time Setup Required</h3>
            <p style='margin:0;color:#555'>
                Enter your <b>free</b> Google Gemini API key to enable AI features.
                Get it at <b>https://aistudio.google.com/app/apikey</b> (no credit card needed).
            </p>
        </div>""", unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            key_input = st.text_input(
                "🔑 Gemini API Key",
                placeholder="AIzaSy...",
                type="password",
                help="Go to https://aistudio.google.com/app/apikey → Create API Key → Copy it here"
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Save Key & Continue", type="primary", use_container_width=True):
                    if key_input and len(key_input) > 10:
                        os.environ["GEMINI_API_KEY"] = key_input.strip()
                        # Also write to .env file for persistence
                        try:
                            env_path = os.path.join(os.path.dirname(__file__), ".env")
                            lines = []
                            if os.path.exists(env_path):
                                with open(env_path) as f:
                                    lines = f.readlines()
                            updated = False
                            for i, line in enumerate(lines):
                                if line.startswith("GEMINI_API_KEY"):
                                    lines[i] = f"GEMINI_API_KEY={key_input.strip()}\n"
                                    updated = True
                                    break
                            if not updated:
                                lines.append(f"\nGEMINI_API_KEY={key_input.strip()}\n")
                            with open(env_path, "w") as f:
                                f.writelines(lines)
                        except Exception:
                            pass
                        st.success("✅ Key saved! You can now login.")
                        st.rerun()
                    else:
                        st.error("Please enter a valid Gemini API key.")
            with c2:
                if st.link_button("🔗 Get Free Key", "https://aistudio.google.com/app/apikey",
                                   use_container_width=True):
                    pass
        st.markdown("---")

    # Login form
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("""
        <div style='background:#fff;border:1px solid #d0dce8;border-radius:14px;
                    padding:2rem;box-shadow:0 4px 20px rgba(44,123,229,.08)'>
            <h3 style='color:#0f2744;margin:0 0 1.2rem;text-align:center'>🔐 Login to Your Account</h3>
        """, unsafe_allow_html=True)

        uname = st.text_input("👤 Username", placeholder="Enter your username")
        pwd   = st.text_input("🔒 Password", type="password", placeholder="Enter your password")

        if st.button("Login →", use_container_width=True, type="primary"):
            if uname and pwd:
                user = authenticate_user(uname, pwd)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.username  = uname
                    st.session_state.role      = user["role"]
                    st.session_state.user_id   = user["id"]
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password.")
            else:
                st.warning("Please enter both username and password.")

        st.markdown("<hr style='margin:1rem 0'>", unsafe_allow_html=True)

        if st.button("📝 New Student? Create Account", use_container_width=True):
            st.session_state.show_signup = True
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        # Default accounts info
        with st.expander("ℹ️ Default Test Accounts"):
            st.markdown("""
            | Role | Username | Password |
            |------|----------|----------|
            | 🛡️ Admin | `admin` | `admin123` |
            | 🎓 Trainer | `trainer` | `trainer123` |
            | 📖 Student | `student` | `student123` |
            """)


def show_sidebar():
    with st.sidebar:
        # User avatar card
        role_icon = {"admin":"🛡️","trainer":"🎓","student":"📖"}.get(st.session_state.role,"👤")
        role_color = {"admin":"#e74c3c","trainer":"#2c7be5","student":"#27ae60"}.get(st.session_state.role,"#888")
        st.markdown(f"""
        <div style='background:rgba(255,255,255,0.1);border-radius:12px;
                    padding:1rem;margin-bottom:1rem;text-align:center'>
            <div style='font-size:2.5rem'>{role_icon}</div>
            <div style='font-size:1.1rem;font-weight:700;margin:.3rem 0'>
                {st.session_state.username}
            </div>
            <div style='background:{role_color};color:white;border-radius:20px;
                        padding:2px 12px;font-size:.8rem;font-weight:700;display:inline-block'>
                {st.session_state.role.upper()}
            </div>
        </div>""", unsafe_allow_html=True)

        # Gemini status
        if is_configured():
            key = get_gemini_key()
            st.markdown(f"""
            <div style='background:rgba(39,174,96,.15);border-radius:8px;
                        padding:.5rem .8rem;margin-bottom:.5rem;font-size:.8rem'>
                🟢 <b>Gemini AI Active</b><br>
                <span style='opacity:.8'>Key: {key[:8]}...{key[-4:]}</span>
            </div>""", unsafe_allow_html=True)
        else:
            st.warning("⚠️ No AI key set")

        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()


def main():
    if st.session_state.exam_token:
        link_render(st.session_state.exam_token)
        return
    if st.session_state.show_signup:
        signup_render()
        return
    if not st.session_state.logged_in:
        show_login()
    else:
        show_sidebar()
        role = st.session_state.role
        if role == "admin":
            admin_page.render()
        elif role == "trainer":
            trainer_page.render()
        elif role == "student":
            student_page.render()
        else:
            st.error("Unknown role. Please contact admin.")


if __name__ == "__main__":
    main()
