"""pages/signup_page.py — v6"""
import streamlit as st
from database.registration_db import register_student
from utils.email_utils import send_welcome_email
from utils.ui_theme import apply_theme


def render():
    apply_theme()
    st.markdown("""
    <div style='background:linear-gradient(135deg,#0f2744,#2c7be5);
                padding:2.5rem;border-radius:16px;text-align:center;color:white;margin-bottom:2rem'>
        <div style='font-size:2.5rem'>📝</div>
        <h1 style='color:white!important;border:none!important;font-size:1.9rem;margin:.5rem 0'>
            Create Your Student Account
        </h1>
        <p style='opacity:.85;margin:0'>Free · Instant · Credentials sent to your email</p>
    </div>""", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        full_name = st.text_input("Full Name *", placeholder="e.g. Pradeep Meesala")
        email     = st.text_input("Email Address *", placeholder="your@email.com")
        phone     = st.text_input("Phone Number *", placeholder="e.g. 9876543210")
        st.markdown("---")

        if st.button("🚀 Create My Account", type="primary", use_container_width=True):
            if not full_name.strip():
                st.error("Please enter your full name.")
            elif not email.strip() or "@" not in email:
                st.error("Please enter a valid email address.")
            elif not phone.strip():
                st.error("Please enter your phone number.")
            else:
                with st.spinner("Creating account..."):
                    result = register_student(full_name.strip(), email.strip(), phone.strip())
                if result["success"]:
                    ok, _ = send_welcome_email(result["email"], result["full_name"],
                                               result["username"], result["password"])
                    st.success("✅ Account created!")
                    st.markdown(f"""
                    <div style='background:#f0f6ff;border:2px solid #2c7be5;border-radius:12px;padding:1.5rem;margin:1rem 0'>
                        <h4 style='color:#0f2744;margin:0 0 .8rem'>🔐 Your Login Credentials</h4>
                        <p><b>Username:</b> <code>{result['username']}</code></p>
                        <p><b>Password:</b> <code>{result['password']}</code></p>
                        <p style='color:#666;font-size:.85rem;margin-top:.5rem'>
                            {'📧 Also sent to ' + email if ok else '⚠️ Save these — email could not be sent.'}
                        </p>
                    </div>""", unsafe_allow_html=True)
                    st.balloons()
                else:
                    st.error(f"❌ {result['error']}")

        if st.button("← Back to Login", use_container_width=True):
            st.session_state.show_signup = False
            st.rerun()
