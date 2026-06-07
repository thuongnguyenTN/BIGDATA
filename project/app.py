"""
app.py — Entry point chính
Chạy: streamlit run app.py --server.port 8501 --server.address 0.0.0.0
"""

import streamlit as st

# ── Page config (phải là lệnh Streamlit đầu tiên) ────────────────────────────
st.set_page_config(
    page_title = "Financial Big Data Dashboard",
    page_icon  = "📊",
    layout     = "wide",
    initial_sidebar_state = "expanded",
)

# ── Imports sau set_page_config ──────────────────────────────────────────────
from database import DatabaseManager
from utils    import load_css, render_sidebar_logo, render_sidebar_footer

# Import các page modules
from pages.dashboard   import render as page_dashboard
from pages.stock_detail import render as page_stock_detail
from pages.analytics   import render as page_analytics
from pages.data_table  import render as page_data_table
from pages.system      import render as page_system

# ── Load CSS ─────────────────────────────────────────────────────────────────
load_css("style.css")

# ── DB singleton (cache toàn session) ────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_db() -> DatabaseManager:
    return DatabaseManager()

db        = get_db()
connected = db.connect()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar_logo()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=False)

    page = st.radio(
        "Navigation",
        [
            "🏠  Dashboard",
            "📈  Stock Detail",
            "📊  Analytics",
            "🗄  Data Table",
            "⚙  System Status",
        ],
        label_visibility = "collapsed",
    )

    # Đẩy footer xuống đáy
    st.markdown(
        "<div style='flex:1; min-height:160px'></div>",
        unsafe_allow_html=False,
    )
    render_sidebar_footer(db.mode, connected)

# ── Route ─────────────────────────────────────────────────────────────────────
route_map = {
    "🏠  Dashboard":    page_dashboard,
    "📈  Stock Detail": page_stock_detail,
    "📊  Analytics":   page_analytics,
    "🗄  Data Table":  page_data_table,
    "⚙  System Status": page_system,
}

handler = route_map.get(page, page_dashboard)
handler(db)