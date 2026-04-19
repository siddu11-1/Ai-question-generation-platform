"""utils/ui_theme.py — Premium blue theme v6"""
import streamlit as st

def apply_theme():
    st.markdown("""<style>
    html,body,[class*="css"]{font-family:'Segoe UI',sans-serif}
    #MainMenu,footer,header{visibility:hidden}
    [data-testid="stSidebar"]{background:linear-gradient(180deg,#0f2744 0%,#1a3c5e 100%)}
    [data-testid="stSidebar"] *{color:#fff!important}
    [data-testid="stSidebar"] .stButton button{background:rgba(255,255,255,0.12)!important;color:#fff!important;border:1px solid rgba(255,255,255,0.25)!important;border-radius:8px!important;font-weight:600!important}
    [data-testid="stSidebar"] .stButton button:hover{background:rgba(255,255,255,0.22)!important}
    h1{color:#0f2744!important;border-bottom:3px solid #2c7be5;padding-bottom:.4rem;font-size:1.8rem!important}
    h2,h3{color:#1a3c5e!important}
    [data-testid="stMetric"]{background:linear-gradient(135deg,#f0f6ff,#fff);border:1px solid #c8d8f0;border-left:4px solid #2c7be5;border-radius:12px;padding:1rem 1.2rem;box-shadow:0 2px 8px rgba(44,123,229,.1)}
    [data-testid="stMetricValue"]{color:#0f2744!important;font-weight:700}
    [data-testid="stMetricLabel"]{color:#5a7a9a!important;font-size:.82rem}
    .stButton button[kind="primary"]{background:linear-gradient(135deg,#2c7be5,#1a3c5e)!important;color:#fff!important;border:none!important;border-radius:8px!important;font-weight:700!important;box-shadow:0 3px 10px rgba(44,123,229,.35)!important}
    .stButton button[kind="primary"]:hover{transform:translateY(-1px);box-shadow:0 5px 15px rgba(44,123,229,.45)!important}
    .stButton button{border-radius:8px!important;font-weight:500!important}
    .stTabs [data-baseweb="tab-list"]{gap:3px;background:#eef3fb;border-radius:10px;padding:4px}
    .stTabs [data-baseweb="tab"]{border-radius:7px!important;font-weight:600!important;color:#5a7a9a!important;padding:.45rem .9rem!important}
    .stTabs [aria-selected="true"]{background:#fff!important;color:#0f2744!important;box-shadow:0 2px 8px rgba(0,0,0,.1)}
    [data-testid="stExpander"]{border:1px solid #d0dce8!important;border-radius:10px!important;overflow:hidden}
    [data-testid="stExpander"] summary{background:#f5f8fc!important;font-weight:600!important;color:#1a3c5e!important}
    input,textarea{border-radius:8px!important}
    [data-testid="stProgress"]>div>div{background:linear-gradient(90deg,#2c7be5,#27ae60)!important;border-radius:10px}
    [data-testid="stAlert"]{border-radius:10px!important;border-left-width:4px!important}
    code{background:#e8f0fe;color:#1a3c5e;padding:2px 7px;border-radius:5px;font-size:.88em}
    </style>""", unsafe_allow_html=True)

def stars_html(n):
    n = max(0,min(5,int(n or 0)))
    return "⭐"*n+"☆"*(5-n)

def badge(text, color="blue"):
    c={"blue":("#dbeafe","#1e40af"),"green":("#dcfce7","#166534"),
       "red":("#fee2e2","#991b1b"),"orange":("#ffedd5","#9a3412"),"gray":("#f3f4f6","#374151")}
    bg,fg=c.get(color,c["blue"])
    return f'<span style="background:{bg};color:{fg};padding:2px 10px;border-radius:12px;font-size:.8rem;font-weight:700">{text}</span>'
