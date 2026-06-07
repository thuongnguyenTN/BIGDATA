"""
pages/data_table.py — Xem dữ liệu thô & kết quả phân tích
Bảng: tbl_raw_stock  (tab 1)
      tbl_stock_analysis  (tab 2 — MapReduce result)
Tính năng: Search, Filter, Pagination, Download CSV
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from database import DatabaseManager, BANK_META
from utils import (
    render_topbar, section_label, info_box,
    fmt_price, fmt_volume,
)

PRIMARY = ["ACB", "STB", "OCB", "LPB"]
PAGE_SIZE = 25


def _paginate(df: pd.DataFrame, page: int, size: int = PAGE_SIZE
              ) -> tuple[pd.DataFrame, int]:
    total = len(df)
    n_pages = max(1, (total + size - 1) // size)
    page    = max(1, min(page, n_pages))
    start   = (page - 1) * size
    return df.iloc[start:start+size], n_pages


def _render_raw(db: DatabaseManager) -> None:
    """Tab 1: tbl_raw_stock."""
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-header"><span class="card-title">Bộ lọc</span></div>',
                unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
    with c1:
        search = st.text_input("🔍  Tìm theo mã / nguồn",
                               placeholder="VD: ACB, CafeF...")
    with c2:
        syms = st.multiselect("Mã cổ phiếu",
                              options=PRIMARY, default=PRIMARY)
    with c3:
        period = st.selectbox("Khoảng thời gian",
                              ["1 tháng","3 tháng","6 tháng","1 năm","5 năm"],
                              index=2)
    with c4:
        st.markdown("<br>", unsafe_allow_html=True)
        show_all = st.checkbox("Tất cả cột", value=False)

    st.markdown("</div>", unsafe_allow_html=True)

    days_map = {"1 tháng":30,"3 tháng":90,"6 tháng":180,"1 năm":365,"5 năm":1825}
    n = days_map.get(period, 180)
    end, start = date.today(), date.today() - timedelta(days=n)

    with st.spinner("Đang tải tbl_raw_stock..."):
        df = db.get_raw_data(syms or PRIMARY, start, end)

    if df.empty:
        st.warning("Không có dữ liệu.")
        return

    if "trading_date" in df.columns:
        df = df.rename(columns={"trading_date": "date"})

    # Search
    if search.strip():
        mask = df.astype(str).apply(
            lambda col: col.str.contains(search.strip(), case=False)
        ).any(axis=1)
        df = df[mask]

    # Cột hiển thị
    display_cols = (["symbol","date","open","high","low","close","volume","source"]
                    if show_all else ["symbol","date","close","volume"])
    display_cols = [c for c in display_cols if c in df.columns]

    st.markdown(
        f'<div class="info-box">📋 <b>tbl_raw_stock</b> — '
        f'{len(df):,} dòng | Nhập bởi Quang Duy (vnstock / CafeF)</div>',
        unsafe_allow_html=True,
    )

    # Pagination
    if "raw_page" not in st.session_state:
        st.session_state.raw_page = 1

    page_df, n_pages = _paginate(df.sort_values("date", ascending=False),
                                 st.session_state.raw_page)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.dataframe(
        page_df[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "date":   st.column_config.DateColumn("Ngày", format="DD/MM/YYYY"),
            "close":  st.column_config.NumberColumn("Giá đóng cửa", format="%,.0f ₫"),
            "open":   st.column_config.NumberColumn("Mở cửa",       format="%,.0f ₫"),
            "high":   st.column_config.NumberColumn("Cao nhất",     format="%,.0f ₫"),
            "low":    st.column_config.NumberColumn("Thấp nhất",    format="%,.0f ₫"),
            "volume": st.column_config.NumberColumn("Khối lượng",   format="%,d"),
        },
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # Pagination controls
    st.markdown(f'<div class="pag-info">Trang {st.session_state.raw_page} / {n_pages} '
                f'({len(df):,} dòng)</div>', unsafe_allow_html=True)

    p1, p2, p3 = st.columns([1,3,1])
    with p1:
        if st.button("◀ Trước", key="raw_prev",
                     disabled=st.session_state.raw_page <= 1):
            st.session_state.raw_page -= 1
            st.rerun()
    with p3:
        if st.button("Sau ▶", key="raw_next",
                     disabled=st.session_state.raw_page >= n_pages):
            st.session_state.raw_page += 1
            st.rerun()

    # Download
    csv = df[display_cols].to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label    = "⬇ Download CSV — tbl_raw_stock",
        data     = csv,
        file_name= f"tbl_raw_stock_{date.today()}.csv",
        mime     = "text/csv",
    )


def _render_analysis(db: DatabaseManager) -> None:
    """Tab 2: tbl_stock_analysis (kết quả MapReduce)."""
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-header"><span class="card-title">Bộ lọc</span></div>',
                unsafe_allow_html=True)

    c1, c2 = st.columns([2, 2])
    with c1:
        syms2  = st.multiselect("Mã cổ phiếu",
                                options=PRIMARY, default=PRIMARY,
                                key="anal_sym")
    with c2:
        period2 = st.selectbox("Khoảng thời gian",
                               ["1 tháng","3 tháng","6 tháng","1 năm","5 năm"],
                               index=2, key="anal_period")

    st.markdown("</div>", unsafe_allow_html=True)

    days_map = {"1 tháng":30,"3 tháng":90,"6 tháng":180,"1 năm":365,"5 năm":1825}
    n = days_map.get(period2, 180)
    end, start = date.today(), date.today() - timedelta(days=n)

    with st.spinner("Đang tải tbl_stock_analysis..."):
        df2 = db.get_analysis_data(syms2 or PRIMARY, start, end)

    if df2.empty:
        st.warning("Không có dữ liệu.")
        return

    if "calc_date" in df2.columns:
        df2 = df2.rename(columns={"calc_date": "date"})

    st.markdown(
        '<div class="info-box">📊 <b>tbl_stock_analysis</b> — '
        'Kết quả MapReduce (avg_close_price, total_volume, price_variance). '
        'Được Sqoop Export đẩy vào sau khi pipeline Oozie chạy xong.</div>',
        unsafe_allow_html=True,
    )

    # Pagination
    if "anal_page" not in st.session_state:
        st.session_state.anal_page = 1

    page_df2, n_pages2 = _paginate(df2.sort_values("date", ascending=False),
                                   st.session_state.anal_page)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.dataframe(
        page_df2,
        use_container_width=True,
        hide_index=True,
        column_config={
            "symbol":          st.column_config.TextColumn("Mã CP"),
            "date":            st.column_config.DateColumn("Ngày tính", format="DD/MM/YYYY"),
            "avg_close_price": st.column_config.NumberColumn("avg_close_price ₫", format="%,.0f"),
            "total_volume":    st.column_config.NumberColumn("total_volume",       format="%,d"),
            "price_variance":  st.column_config.NumberColumn("price_variance ₫",  format="%,.0f"),
        },
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(f'<div class="pag-info">Trang {st.session_state.anal_page} / {n_pages2} '
                f'({len(df2):,} dòng)</div>', unsafe_allow_html=True)

    pa1, _, pa3 = st.columns([1,3,1])
    with pa1:
        if st.button("◀ Trước", key="anal_prev",
                     disabled=st.session_state.anal_page <= 1):
            st.session_state.anal_page -= 1
            st.rerun()
    with pa3:
        if st.button("Sau ▶", key="anal_next",
                     disabled=st.session_state.anal_page >= n_pages2):
            st.session_state.anal_page += 1
            st.rerun()

    csv2 = df2.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label    = "⬇ Download CSV — tbl_stock_analysis",
        data     = csv2,
        file_name= f"tbl_stock_analysis_{date.today()}.csv",
        mime     = "text/csv",
    )


def render(db: DatabaseManager) -> None:
    render_topbar(
        "Data Table",
        "Xem và xuất dữ liệu từ MySQL · tbl_raw_stock & tbl_stock_analysis",
    )

    tab1, tab2 = st.tabs([
        "📋 tbl_raw_stock  (dữ liệu thô)",
        "📊 tbl_stock_analysis  (kết quả MapReduce)",
    ])

    with tab1:
        _render_raw(db)

    with tab2:
        _render_analysis(db)