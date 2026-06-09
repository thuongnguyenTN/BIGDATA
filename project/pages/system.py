"""
pages/system.py — System Status
Hiển thị trạng thái pipeline Oozie 5 bước + kết nối DB.
Đồng hồ thực: HTML/JS nhảy giây liên tục, không reload trang.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from database import DatabaseManager
from utils import render_topbar, section_label, info_box


# ── Live clock component ──────────────────────────────────────────────────────

_LIVE_CLOCK_HTML = """
<div style="
  display: flex;
  align-items: center;
  gap: 14px;
  background: rgba(13,21,32,0.95);
  border: 1px solid rgba(59,130,246,0.12);
  border-radius: 12px;
  padding: 14px 20px;
  margin-bottom: 1rem;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
">
  <div style="
    width: 44px; height: 44px;
    background: linear-gradient(135deg, #1D4ED8, #0EA5E9);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.4rem;
    box-shadow: 0 4px 14px rgba(37,99,235,0.35);
    flex-shrink: 0;
  ">⏱</div>
  <div>
    <div style="font-size:0.60rem; text-transform:uppercase; letter-spacing:0.12em;
                color:#3D5478; margin-bottom:3px;">Thời gian thực — Server Time</div>
    <div id="live-clock" style="font-size:1.35rem; font-weight:700;
                                  color:#E8F0FE; letter-spacing:0.04em;">--:--:--</div>
    <div id="live-date" style="font-size:0.70rem; color:#7A92B8; margin-top:1px;"></div>
  </div>
  <div style="margin-left:auto; display:flex; flex-direction:column; gap:5px; text-align:right;">
    <span style="
      display:inline-flex; align-items:center; gap:5px;
      background:rgba(16,185,129,0.10); border:1px solid rgba(16,185,129,0.18);
      border-radius:99px; padding:3px 10px;
      font-size:0.62rem; font-weight:700;
      color:#34D399; text-transform:uppercase; letter-spacing:0.08em;
    ">
      <span id="pulse-dot" style="
        display:inline-block; width:6px; height:6px; background:#10B981;
        border-radius:50%; box-shadow:0 0 5px #10B981;
      "></span>SYSTEM LIVE
    </span>
    <span style="font-size:0.64rem; color:#3D5478;">Dashboard v1.0</span>
  </div>
</div>

<script>
(function() {
  const DAYS_VI   = ['CN','T2','T3','T4','T5','T6','T7'];
  const MONTHS_VI = ['Tháng 1','Tháng 2','Tháng 3','Tháng 4','Tháng 5','Tháng 6',
                     'Tháng 7','Tháng 8','Tháng 9','Tháng 10','Tháng 11','Tháng 12'];

  function pad2(n) { return String(n).padStart(2, '0'); }

  function tick() {
    const now  = new Date();
    const hms  = `${pad2(now.getHours())}:${pad2(now.getMinutes())}:${pad2(now.getSeconds())}`;
    const day  = DAYS_VI[now.getDay()];
    const date = `${day}, ${pad2(now.getDate())} ${MONTHS_VI[now.getMonth()]} ${now.getFullYear()}`;
    const cEl = document.getElementById('live-clock');
    const dEl = document.getElementById('live-date');
    if (cEl) cEl.textContent = hms;
    if (dEl) dEl.textContent = date;
  }

  tick();
  setInterval(tick, 1000);

  // Pulse dot animation
  let visible = true;
  setInterval(() => {
    const dot = document.getElementById('pulse-dot');
    if (dot) { dot.style.opacity = visible ? '0.3' : '1'; visible = !visible; }
  }, 800);
})();
</script>
"""


# ── Step card ────────────────────────────────────────────────────────────────

def _step_card(
    step:   str,
    title:  str,
    detail: str,
    owner:  str,
    tool:   str,
    status: str = "done",
) -> None:
    status_map = {
        "done":    ("#10B981", "badge-green",  "✓ Hoàn thành"),
        "running": ("#3B82F6", "badge-blue",   "⟳ Đang chạy"),
        "pending": ("#F59E0B", "badge-amber",  "⌛ Chờ"),
        "error":   ("#EF4444", "badge-red",    "✗ Lỗi"),
    }
    color, badge_cls, label = status_map.get(status, status_map["pending"])

    st.markdown(f"""
    <div class="card" style="border-left: 3px solid {color}; padding-left: 1.3rem;">
      <div class="card-header">
        <div style="display:flex; align-items:center; gap:10px; flex:1;">
          <span style="
            font-family:'JetBrains Mono',monospace;
            font-size:0.65rem; font-weight:600;
            color:{color}; background:rgba(0,0,0,0.2);
            padding:2px 8px; border-radius:5px; letter-spacing:0.06em;
            white-space:nowrap;
          ">{step}</span>
          <span style="font-size:0.86rem; font-weight:600;
                       color:var(--text-primary);">{title}</span>
        </div>
        <div style="display:flex; align-items:center; gap:6px;">
          <span class="badge badge-cyan" style="white-space:nowrap;">{tool}</span>
          <span class="badge {badge_cls}" style="white-space:nowrap;">{label}</span>
        </div>
      </div>
      <div style="font-size:0.77rem; color:#7A92B8; line-height:1.55;
                  font-family:'Inter',sans-serif; margin-bottom:8px;">{detail}</div>
      <div style="display:flex; align-items:center; gap:6px;">
        <span style="font-size:0.65rem; color:#3D5478;">Owner:</span>
        <span class="badge badge-blue">{owner}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ── Main render ───────────────────────────────────────────────────────────────

def render(db: DatabaseManager) -> None:
    render_topbar(
        "System Status",
        "Trạng thái pipeline Oozie · Kết nối cơ sở dữ liệu · Giám sát hệ thống",
        breadcrumb="System Status",
    )

    # Live clock
    st.components.v1.html(_LIVE_CLOCK_HTML, height=90)

    # ── DB Connection ─────────────────────────────────────────
    section_label("Kết nối Database")

    connected = db.connect()
    mode_label = {
        "dummy": "Demo / Dummy Data",
        "mysql": "MySQL · bigdata_stock",
        "drill": "Apache Drill",
    }.get(db.mode, db.mode)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Chế độ kết nối",  mode_label)
    c2.metric("Trạng thái DB",   "🟢 Online" if connected else "🔴 Offline")
    c3.metric("Database",        "bigdata_stock")
    c4.metric("Phiên bản",       "MySQL 8.0 / Drill 1.21")

    if db.mode == "dummy":
        info_box(
            "ℹ Đang chạy <b>Demo Mode</b> với dữ liệu giả (Dummy Data). "
            "Để kết nối MySQL thật: đặt <code>DB_MODE=mysql</code> trong <code>.env</code>. "
            "Để dùng Apache Drill: đặt <code>DB_MODE=drill</code> cùng <code>DRILL_HOST</code>, "
            "<code>DRILL_PORT</code>."
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Oozie Pipeline ────────────────────────────────────────
    section_label("Oozie Workflow — 5 bước pipeline tự động")

    info_box(
        "📌 Workflow điều phối bởi <b>Apache Oozie</b> — định nghĩa trong "
        "<code>oozie_workflow/workflow.xml</code>. "
        "Khởi chạy: <code>oozie job -config job.properties -run</code>"
    )

    STEPS = [
        dict(
            step   = "Bước 1",
            title  = "Sqoop Import — MySQL → HDFS",
            detail = (
                "Sqoop kéo toàn bộ <b>tbl_raw_stock</b> từ MySQL (bigdata_stock) vào HDFS "
                "tại <code>/user/hadoop/stock_raw</code>. "
                "Cấu hình <i>prepare delete</i> để xóa thư mục cũ trước khi import, "
                "đảm bảo dữ liệu luôn mới nhất."
            ),
            owner  = "Quang Duy",
            tool   = "Sqoop",
            status = "done",
        ),
        dict(
            step   = "Bước 2",
            title  = "Hive Clean — /stock_raw → /stock_cleaned",
            detail = (
                "Oozie gọi script <code>clean_data.hql</code>. "
                "Hive đọc từ <code>/stock_raw</code>, xử lý giá trị null, "
                "chuẩn hóa định dạng ngày tháng, ép kiểu dữ liệu đúng schema, "
                "ghi dữ liệu sạch ra <code>/user/hadoop/stock_cleaned</code>."
            ),
            owner  = "Quang Duy",
            tool   = "Hive HQL",
            status = "done",
        ),
        dict(
            step   = "Bước 3",
            title  = "MapReduce Python — /stock_cleaned → /stock_result",
            detail = (
                "Hadoop Streaming thực thi <code>mapper.py</code> + <code>reducer.py</code>. "
                "Tính song song: <b>avg_close_price</b>, <b>total_volume</b>, <b>price_variance</b> "
                "nhóm theo <i>symbol × calc_date</i>. "
                "Kết quả ghi ra <code>/user/hadoop/stock_result</code>."
            ),
            owner  = "Cả nhóm",
            tool   = "MapReduce",
            status = "done",
        ),
        dict(
            step   = "Bước 4",
            title  = "Sqoop Export — /stock_result → tbl_stock_analysis",
            detail = (
                "Sqoop Export đẩy kết quả MapReduce từ HDFS vào "
                "<b>tbl_stock_analysis</b> trên MySQL. "
                "Dùng <code>--update-mode allowinsert</code> để tránh trùng lặp "
                "khi pipeline chạy lại nhiều lần."
            ),
            owner  = "Phúc An",
            tool   = "Sqoop",
            status = "done",
        ),
        dict(
            step   = "Bước 5",
            title  = "Sqoop Import Backup — tbl_stock_analysis → HDFS",
            detail = (
                "Sqoop Import ngược: kéo <b>tbl_stock_analysis</b> từ MySQL về "
                "<code>/user/hadoop/stock_backup</code> trên HDFS. "
                "Đảm bảo dữ liệu phân tích luôn có bản dự phòng phân tán, "
                "phòng khi MySQL gặp sự cố."
            ),
            owner  = "Phúc An",
            tool   = "Sqoop",
            status = "done",
        ),
    ]

    for s in STEPS:
        _step_card(**s)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Middleware & Frontend ─────────────────────────────────
    section_label("Middleware & Frontend")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("""
        <div class="card" style="border-left: 3px solid #8B5CF6;">
          <div class="card-header">
            <span class="card-title">Apache Drill — Query Middleware</span>
            <span class="badge badge-purple">BiMi</span>
          </div>
          <div style="font-size:.78rem; color:#7A92B8; margin-bottom:10px;
                      font-family:'Inter',sans-serif; line-height:1.55;">
            Drillbit chạy ngầm liên tục làm lớp middleware truy vấn SQL phân tán.
            Cấu hình Storage Plugin kết nối đồng thời HDFS (<code>dfs</code>)
            và MySQL (<code>mysql</code>). Cấp JDBC/REST API cho Serving Layer.
          </div>
          <div class="stat-row">
            <span class="stat-label">Endpoint</span>
            <span class="stat-value">localhost:8047</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Storage Plugins</span>
            <span class="stat-value">HDFS · MySQL</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Phiên bản</span>
            <span class="stat-value">Drill 1.21.1</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Giao thức</span>
            <span class="stat-value">JDBC · REST API</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with col_b:
        st.markdown("""
        <div class="card" style="border-left: 3px solid #3B82F6;">
          <div class="card-header">
            <span class="card-title">Streamlit — Serving Layer</span>
            <span class="badge badge-blue">Thưởng</span>
          </div>
          <div style="font-size:.78rem; color:#7A92B8; margin-bottom:10px;
                      font-family:'Inter',sans-serif; line-height:1.55;">
            Web GUI đóng vai trò Serving Layer — chỉ đọc và hiển thị kết quả
            từ <b>tbl_stock_analysis</b>. Không tự tính toán. Truy vấn qua
            Apache Drill (production) hoặc MySQL trực tiếp (fallback).
          </div>
          <div class="stat-row">
            <span class="stat-label">URL</span>
            <span class="stat-value">:8501</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">DB Fallback</span>
            <span class="stat-value">Drill → MySQL</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Phiên bản</span>
            <span class="stat-value">Streamlit 1.32.2</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Visualization</span>
            <span class="stat-value">Plotly 5.x</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── HDFS Path Map ─────────────────────────────────────────
    section_label("HDFS Path Map")

    HDFS_PATHS = [
        ("/user/hadoop/stock_raw",      "#3B82F6", "← Sqoop Import từ tbl_raw_stock (MySQL)"),
        ("/user/hadoop/stock_cleaned",  "#10B981", "← Hive clean output (clean_data.hql)"),
        ("/user/hadoop/stock_result",   "#F59E0B", "← MapReduce output (mapper.py + reducer.py)"),
        ("/user/hadoop/stock_backup",   "#8B5CF6", "← Sqoop Import backup từ tbl_stock_analysis"),
        ("/user/hadoop/scripts/",       "#7A92B8", "← workflow.xml · clean_data.hql · mapper.py · reducer.py"),
    ]

    rows_html = "".join(f"""
      <div class="hdfs-row">
        <span class="hdfs-path" style="color:{color};">{path}</span>
        <span class="hdfs-arrow">→</span>
        <span class="hdfs-desc">{desc}</span>
      </div>
    """ for path, color, desc in HDFS_PATHS)

    st.markdown(f'<div class="hdfs-table">{rows_html}</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Yêu cầu deploy ───────────────────────────────────────
    section_label("Yêu cầu triển khai Oozie")

    st.markdown("""
    <div class="card">
      <div style="font-size:.80rem; color:#7A92B8; line-height:1.75;
                  font-family:'Inter',sans-serif;">
        <div style="margin-bottom:8px;">
          <span class="badge badge-blue" style="margin-right:8px;">[1] HDFS Upload</span>
          Đưa toàn bộ <code>workflow.xml</code>, <code>clean_data.hql</code>,
          <code>mapper.py</code>, <code>reducer.py</code>, <code>hive-site.xml</code>
          lên <code>/user/hadoop/scripts/</code> trên HDFS.
        </div>
        <div>
          <span class="badge badge-amber" style="margin-right:8px;">[2] JDBC Driver</span>
          Copy <code>mysql-connector-java.jar</code> vào Oozie share lib:<br>
          <code style="font-size:0.76rem; display:block; margin-top:4px; padding:6px 10px;
                       background:rgba(0,0,0,0.25); border-radius:6px;">
            hdfs dfs -put mysql-connector-java.jar /user/oozie/share/lib/sqoop/
          </code>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)