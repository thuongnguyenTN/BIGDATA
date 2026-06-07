"""
pages/system.py — System Status
Hiển thị trạng thái pipeline Oozie 5 bước + kết nối DB.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from database import DatabaseManager
from utils import render_topbar, section_label


def _step_card(
    step:    str,
    title:   str,
    detail:  str,
    owner:   str,
    status:  str = "done",          # done | running | pending | error
) -> None:
    color_map = {
        "done":    ("#22C55E", "badge-green", "✓ Hoàn thành"),
        "running": ("#3B82F6", "badge-blue",  "⟳ Đang chạy"),
        "pending": ("#F59E0B", "badge-amber", "⌛ Chờ"),
        "error":   ("#EF4444", "badge-red",   "✗ Lỗi"),
    }
    color, badge_cls, label = color_map.get(status, color_map["pending"])
    st.markdown(f"""
    <div class="card" style="border-left: 3px solid {color}; padding-left:1.2rem;">
      <div class="card-header">
        <span style="font-family:'IBM Plex Mono',monospace; font-size:.78rem;
                     color:#475569; margin-right:8px;">{step}</span>
        <span class="card-title" style="flex:1;">{title}</span>
        <span class="badge {badge_cls}">{label}</span>
      </div>
      <div style="font-size:.8rem; color:#94A3B8; margin-bottom:5px;">{detail}</div>
      <div style="font-size:.7rem; color:#475569;">
        <span class="badge badge-blue">Owner: {owner}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)


def render(db: DatabaseManager) -> None:
    render_topbar(
        "System Status",
        "Trạng thái pipeline Oozie · Kết nối cơ sở dữ liệu",
    )

    # ── DB Connection ─────────────────────────────────────────
    section_label("Kết nối database")
    connected = db.connect()

    c1, c2, c3 = st.columns(3)
    mode_label = {
        "dummy": "Demo Mode",
        "mysql": "MySQL · bigdata_stock",
        "drill": "Apache Drill",
    }.get(db.mode, db.mode)

    dot = "🟢" if connected else "🔴"
    c1.metric("Chế độ",    mode_label)
    c2.metric("Trạng thái", f"{dot} {'Online' if connected else 'Offline'}")
    c3.metric("Thời gian",  datetime.now().strftime("%H:%M:%S  %d/%m/%Y"))

    if db.mode == "dummy":
        st.markdown(
            '<div class="info-box">ℹ Đang dùng <b>Dummy Data</b>. '
            'Để kết nối MySQL: đặt <code>DB_MODE=mysql</code> trong <code>.env</code>.<br>'
            'Để kết nối Drill: đặt <code>DB_MODE=drill</code> và cung cấp '
            '<code>DRILL_HOST</code>, <code>DRILL_PORT</code> từ BiMi.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Oozie Pipeline Steps ──────────────────────────────────
    section_label("Oozie Workflow — 5 bước pipeline")
    st.markdown(
        '<div class="info-box">📌 Workflow được định nghĩa trong '
        '<b>oozie_workflow/workflow.xml</b>. '
        'Chạy: <code>oozie job -config job.properties -run</code></div>',
        unsafe_allow_html=True,
    )

    steps = [
        {
            "step":   "Bước 1",
            "title":  "Sqoop Import — MySQL → HDFS",
            "detail": ("Sqoop kéo toàn bộ tbl_raw_stock từ MySQL (bigdata_stock) "
                       "vào HDFS tại /user/hadoop/stock_raw. "
                       "Xóa thư mục cũ trước khi chạy (prepare delete)."),
            "owner":  "Phúc An",
            "status": "done",
        },
        {
            "step":   "Bước 2",
            "title":  "Hive Clean — /stock_raw → /stock_cleaned",
            "detail": ("Oozie gọi clean_data.hql. "
                       "Hive đọc stock_raw, xử lý null/format ngày/ép kiểu, "
                       "ghi ra /user/hadoop/stock_cleaned."),
            "owner":  "Quang Duy",
            "status": "done",
        },
        {
            "step":   "Bước 3",
            "title":  "MapReduce Python — /stock_cleaned → /stock_result",
            "detail": ("Hadoop Streaming chạy mapper.py + reducer.py. "
                       "Tính: avg_close_price, total_volume, price_variance "
                       "theo từng symbol × calc_date. "
                       "Ghi kết quả ra /user/hadoop/stock_result."),
            "owner":  "Cả nhóm",
            "status": "done",
        },
        {
            "step":   "Bước 4",
            "title":  "Sqoop Export — /stock_result → tbl_stock_analysis",
            "detail": ("Sqoop Export đẩy kết quả MapReduce từ HDFS vào "
                       "tbl_stock_analysis (MySQL). "
                       "Dùng --update-mode allowinsert để tránh trùng lặp."),
            "owner":  "Phúc An",
            "status": "done",
        },
        {
            "step":   "Bước 5",
            "title":  "Sqoop Import Backup — tbl_stock_analysis → HDFS",
            "detail": ("Sqoop Import ngược: kéo tbl_stock_analysis từ MySQL "
                       "về /user/hadoop/stock_backup trên HDFS. "
                       "Phòng trường hợp MySQL/Streamlit gặp sự cố."),
            "owner":  "Phúc An",
            "status": "done",
        },
    ]

    for s in steps:
        _step_card(**s)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Middleware section ────────────────────────────────────
    section_label("Middleware & Frontend (chạy 24/7)")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("""
        <div class="card" style="border-left: 3px solid #A78BFA;">
          <div class="card-header">
            <span class="card-title">Apache Drill — Middleware</span>
            <span class="badge badge-blue">BiMi</span>
          </div>
          <div style="font-size:.8rem;color:#94A3B8;margin-bottom:8px;">
            Drillbit chạy ngầm liên tục. Cấu hình Storage Plugin kết nối
            HDFS (<code>dfs</code>) và MySQL (<code>mysql</code>).
            Cấp JDBC/REST API cho Thưởng dùng.
          </div>
          <div class="stat-row">
            <span class="stat-label">Host</span>
            <span class="stat-value">localhost:8047</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Storage</span>
            <span class="stat-value">HDFS · MySQL · S3</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Phiên bản</span>
            <span class="stat-value">Drill 1.21.1</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with col_b:
        st.markdown("""
        <div class="card" style="border-left: 3px solid #3B82F6;">
          <div class="card-header">
            <span class="card-title">Streamlit Web — Frontend</span>
            <span class="badge badge-blue">Thưởng</span>
          </div>
          <div style="font-size:.8rem;color:#94A3B8;margin-bottom:8px;">
            Web GUI đọc dữ liệu qua Apache Drill (production) hoặc
            trực tiếp MySQL (fallback). Không tính toán — chỉ hiển thị
            kết quả từ tbl_stock_analysis.
          </div>
          <div class="stat-row">
            <span class="stat-label">URL</span>
            <span class="stat-value">http://&lt;server-ip&gt;:8501</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">DB Mode</span>
            <span class="stat-value">Drill → MySQL fallback</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Phiên bản</span>
            <span class="stat-value">Streamlit 1.32.2</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # ── HDFS Paths ────────────────────────────────────────────
    section_label("HDFS Path Map")
    st.markdown("""
    <div class="card">
      <div style="font-family:'IBM Plex Mono',monospace; font-size:.78rem; line-height:2;
                  color:#94A3B8;">
        <span style="color:#3B82F6;">/user/hadoop/stock_raw</span>
          &nbsp;&nbsp;&nbsp;← Sqoop Import từ tbl_raw_stock<br>
        <span style="color:#22C55E;">/user/hadoop/stock_cleaned</span>
          &nbsp;← Hive clean output<br>
        <span style="color:#F59E0B;">/user/hadoop/stock_result</span>
          &nbsp;&nbsp;← MapReduce output<br>
        <span style="color:#A78BFA;">/user/hadoop/stock_backup</span>
          &nbsp;&nbsp;← Sqoop Import backup từ tbl_stock_analysis<br>
        <span style="color:#94A3B8;">/user/hadoop/scripts/</span>
          &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;← workflow.xml · clean_data.hql ·
          mapper.py · reducer.py · hive-site.xml
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Yêu cầu bắt buộc ─────────────────────────────────────
    section_label("Yêu cầu bắt buộc để Oozie chạy")
    st.markdown("""
    <div class="info-box">
      <b>[1]</b> Toàn bộ file workflow.xml, clean_data.hql, mapper.py,
      reducer.py, hive-site.xml phải đưa lên
      <code>/user/hadoop/scripts/</code> trên HDFS.<br><br>
      <b>[2]</b> Copy <code>mysql-connector-java.jar</code> vào thư mục
      <code>lib/</code> của Oozie trên HDFS
      (<code>hdfs dfs -put mysql-connector-java.jar
      /user/oozie/share/lib/sqoop/</code>).
    </div>
    """, unsafe_allow_html=True)