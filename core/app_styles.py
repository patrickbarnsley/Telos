import streamlit as st

def apply_theme():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #0F1117; color: #FFFFFF; }
    [data-testid="stSidebar"] { background-color: #1A1D27; border-right: 1px solid #2D3148; }
    [data-testid="stSidebar"] * { color: #A0A7B8 !important; }
    [data-testid="stSidebar"] a:hover { color: #C9A84C !important; }
    h1 { color: #FFFFFF; font-weight: 700; }
    h2 { color: #FFFFFF; font-weight: 600; }
    h3 { color: #C9A84C; font-weight: 600; }
    [data-testid="stExpander"] { background-color: #1A1D27; border: 1px solid #2D3148; border-radius: 8px; }
    [data-testid="metric-container"] { background-color: #1A1D27; border: 1px solid #2D3148; border-radius: 8px; padding: 16px; }
    .stButton > button { background-color: #C9A84C; color: #0F1117; border: none; border-radius: 6px; font-weight: 600; padding: 8px 20px; transition: all 0.2s ease; }
    .stButton > button:hover { background-color: #E0BC5E; color: #0F1117; transform: translateY(-1px); }
    .stButton > button[kind="primary"] { background-color: #C9A84C; color: #0F1117; }
    .stTextInput > div > div > input, .stTextArea > div > div > textarea, .stSelectbox > div > div { background-color: #1A1D27; border: 1px solid #2D3148; color: #FFFFFF; border-radius: 6px; }
    .stTextInput > div > div > input:focus, .stTextArea > div > div > textarea:focus { border-color: #C9A84C; box-shadow: 0 0 0 2px rgba(201, 168, 76, 0.2); }
    [data-testid="metric-container"] label { color: #A0A7B8 !important; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
    [data-testid="metric-container"] [data-testid="stMetricValue"] { color: #FFFFFF; font-weight: 700; }
    hr { border-color: #2D3148; }
    .stAlert { border-radius: 8px; border: none; }
    [data-testid="stChatMessage"] { background-color: #1A1D27; border-radius: 8px; border: 1px solid #2D3148; }
    .stDataFrame { border: 1px solid #2D3148; border-radius: 8px; }
    [data-testid="stFileUploader"] { background-color: #1A1D27; border: 1px dashed #2D3148; border-radius: 8px; }
    .stSpinner > div { border-top-color: #C9A84C !important; }
    </style>
    """, unsafe_allow_html=True)

def show_help(page_name: str):
    from core.help_content import HELP_CONTENT
    content = HELP_CONTENT.get(page_name, HELP_CONTENT["app"])
    with st.sidebar:
        st.markdown("---")
        with st.expander("❓ Help — " + content["title"]):
            for i, step in enumerate(content["steps"], 1):
                st.markdown(f"**{i}.** {step}")
            st.markdown("---")
            st.info(f"💡 {content['tip']}")