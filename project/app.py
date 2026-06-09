"""
app.py — Entry point chính
Chạy: streamlit run app.py --server.port 8501 --server.address 0.0.0.0

Đồ án môn Dữ liệu lớn — Hệ thống phân tích cổ phiếu ngân hàng Việt Nam
Stack: Hadoop · Hive · MapReduce · Sqoop · Oozie · Apache Drill · Streamlit
"""

import streamlit as st

# ── Page config (phải là lệnh Streamlit đầu tiên) ────────────────────────────
st.set_page_config(
    page_title            = "BigData Stock Dashboard",
    page_icon             = "📊",
    layout                = "wide",
    initial_sidebar_state = "expanded",
)

# ── Imports sau set_page_config ──────────────────────────────────────────────
from database import DatabaseManager
from utils    import load_css, render_sidebar_logo, render_sidebar_footer

from pages.dashboard    import render as page_dashboard
from pages.stock_detail import render as page_stock_detail
from pages.analytics    import render as page_analytics
from pages.data_table   import render as page_data_table
from pages.system       import render as page_system

# ── Load CSS ─────────────────────────────────────────────────────────────────
load_css("style.css")

# ── DB singleton ─────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_db() -> DatabaseManager:
    return DatabaseManager()

db        = get_db()
connected = db.connect()

# ── Nav config ───────────────────────────────────────────────────────────────
NAV_ITEMS = [
    ("🏠", "Dashboard",     "Tổng quan thị trường"),
    ("📈", "Stock Detail",  "Phân tích kỹ thuật"),
    ("📊", "Analytics",     "Phân tích chuyên sâu"),
    ("🗄", "Data Table",    "Dữ liệu & Xuất CSV"),
    ("⚙", "System Status", "Pipeline & Hệ thống"),
]
PAGE_KEYS = [label for _, label, _ in NAV_ITEMS]

ROUTE_MAP = {
    "Dashboard":     page_dashboard,
    "Stock Detail":  page_stock_detail,
    "Analytics":     page_analytics,
    "Data Table":    page_data_table,
    "System Status": page_system,
}

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:

    # Brand / Logo
    mode_label = {
        "dummy": "Demo Mode",
        "mysql": "MySQL · Local",
        "drill": "Apache Drill",
    }.get(db.mode, db.mode)

    conn_chip_cls = "sb-chip-green" if connected else "sb-chip-amber"
    conn_text     = "Connected" if connected else "Offline"

    st.markdown(f"""
    <div class="sb-brand">
      <div class="sb-brand-row">
        <div class="sb-icon">📊</div>
        <div>
          <div class="sb-title">BigData Stock<br>Dashboard</div>
        </div>
      </div>
      <div class="sb-meta-row">
        <span class="sb-chip sb-chip-blue">Hadoop · Hive</span>
        <span class="sb-chip sb-chip-blue">MapReduce</span>
        <span class="sb-chip {conn_chip_cls}">{conn_text}</span>
      </div>
      <div class="sb-meta-row" style="margin-top:5px;">
        <span class="sb-chip sb-chip-amber">ACB · STB · OCB · LPB</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Nav section header
    st.markdown('<div class="sb-section">Navigation</div>', unsafe_allow_html=True)

    # Radio navigation (ẩn radio bullet, dùng label style)
    page = st.radio(
        "nav",
        PAGE_KEYS,
        format_func=lambda k: next(
            f"{icon}  {label}" for icon, label, _ in NAV_ITEMS if label == k
        ),
        label_visibility="collapsed",
    )

    # Spacer
    st.markdown("<div style='min-height:120px'></div>", unsafe_allow_html=True)

    # DB / Pipeline info section
    st.markdown('<div class="sb-section">Hệ thống</div>', unsafe_allow_html=True)

    dot_cls    = "dot-green" if connected else "dot-red"
    status_txt = "Online" if connected else "Offline"

    st.markdown(f"""
    <div style="padding: 0 12px;">
      <div class="sb-footer">
        <div class="sb-footer-row">
          <span>DB Mode</span>
          <span class="sb-footer-val">{mode_label}</span>
        </div>
        <div class="sb-footer-row">
          <span>Connection</span>
          <span class="sb-footer-val">
            <span class="dot {dot_cls} dot-pulse" style="margin-right:5px;"></span>{status_txt}
          </span>
        </div>
        <div class="sb-divider"></div>
        <div class="sb-footer-row">
          <span>Pipeline</span>
          <span class="sb-footer-val">Oozie · 5 bước</span>
        </div>
        <div class="sb-footer-row">
          <span>Middleware</span>
          <span class="sb-footer-val">Apache Drill</span>
        </div>
        <div class="sb-footer-row">
          <span>Frontend</span>
          <span class="sb-footer-val">Streamlit 1.32</span>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── Route ─────────────────────────────────────────────────────────────────────
handler = ROUTE_MAP.get(page, page_dashboard)
handler(db)