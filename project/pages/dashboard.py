"""
pages/dashboard.py — Trang Dashboard chính
Hiển thị: KPI 4 mã (ACB/STB/OCB/LPB) + Line Chart + Volume + SMA
Dữ liệu:  tbl_raw_stock (OHLCV) + tbl_stock_analysis (MapReduce result)
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st
import pandas as pd

from database import DatabaseManager, BANK_META
from utils import (
    render_topbar, render_kpi_card, section_label, info_box,
    build_line_chart, build_volume_chart, build_sma_chart,
    add_sma, fmt_price, fmt_volume,
)

# 4 mã sample
PRIMARY_SYMBOLS = ["ACB", "STB", "OCB", "LPB"]


def render(db: DatabaseManager) -> None:
    # ── Header ────────────────────────────────────────────────
    render_topbar(
        "Financial Big Data Dashboard",
        "Big Data Analytics for Vietnamese Banking Stocks",
    )

    # ── Summary data ──────────────────────────────────────────
    summary = db.get_summary()
    primary = summary[summary["symbol"].isin(PRIMARY_SYMBOLS)]

    # ── KPI Cards (4 mã ACB STB OCB LPB) ─────────────────────
    section_label("Tổng quan thị trường")

    cols = st.columns(4)
    for i, sym in enumerate(PRIMARY_SYMBOLS):
        row = primary[primary["symbol"] == sym]
        if row.empty:
            cols[i].empty()
            continue
        r = row.iloc[0]
        with cols[i]:
            render_kpi_card(
                symbol  = sym,
                name    = BANK_META.get(sym, {}).get("name", sym),
                price   = r["price"],
                pct_chg = r.get("pct_change", 0.0),
                volume  = r.get("total_volume", 0),
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Bộ lọc ───────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-header"><span class="card-title">Bộ lọc</span></div>',
                unsafe_allow_html=True)

    fcol1, fcol2, fcol3 = st.columns([2, 2, 2])

    with fcol1:
        all_syms = [s for s in PRIMARY_SYMBOLS if s in summary["symbol"].tolist()]
        sel_syms = st.multiselect(
            "Ngân hàng",
            options    = all_syms,
            default    = all_syms[:2],
            label_visibility="visible",
        )

    with fcol2:
        period = st.selectbox(
            "Khoảng thời gian",
            ["3 tháng", "6 tháng", "1 năm", "2 năm", "5 năm"],
            index=2,
        )

    with fcol3:
        chart_type = st.selectbox(
            "Loại biểu đồ",
            ["Line Chart", "SMA Chart"],
        )

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Load data theo bộ lọc ─────────────────────────────────
    days_map = {
        "3 tháng": 90, "6 tháng": 180,
        "1 năm": 365, "2 năm": 730, "5 năm": 1825,
    }
    n_days = days_map.get(period, 365)
    end    = date.today()
    start  = end - timedelta(days=n_days)

    if not sel_syms:
        info_box("⬆ Chọn ít nhất 1 ngân hàng để hiển thị biểu đồ.")
        return

    with st.spinner("Đang tải dữ liệu..."):
        raw_df = db.get_raw_data(sel_syms, start, end)

    if raw_df.empty:
        st.warning("Không có dữ liệu trong khoảng thời gian đã chọn.")
        return

    # Đổi tên cột cho uniform
    if "trading_date" in raw_df.columns:
        raw_df = raw_df.rename(columns={"trading_date": "date"})

    # ── Chart 1: Line / SMA ───────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f'<div class="card-header"><span class="card-title">'
                f'{chart_type} — Giá đóng cửa</span>'
                f'<span class="badge badge-blue">{period}</span></div>',
                unsafe_allow_html=True)

    if chart_type == "Line Chart":
        fig = build_line_chart(raw_df, sel_syms,
                               title=f"Giá đóng cửa — {period}",
                               height=400)
    else:
        # SMA: chỉ lấy 1 mã (mã đầu tiên)
        sym1 = sel_syms[0]
        fig  = build_sma_chart(raw_df, sym1, windows=(20, 50), height=400)

    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": True, "scrollZoom": True})
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Chart 2 & 3: Volume + SMA side by side ────────────────
    c_left, c_right = st.columns(2)

    with c_left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header"><span class="card-title">'
                    'Khối lượng giao dịch</span>'
                    '<span class="badge badge-amber">Volume</span></div>',
                    unsafe_allow_html=True)
        sym_vol = sel_syms[0]
        fig_vol = build_volume_chart(raw_df, sym_vol, height=220)
        st.plotly_chart(fig_vol, use_container_width=True,
                        config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with c_right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header"><span class="card-title">'
                    'SMA 20 & SMA 50</span>'
                    '<span class="badge badge-green">Moving Avg</span></div>',
                    unsafe_allow_html=True)
        sym_sma = sel_syms[0]
        fig_sma = build_sma_chart(raw_df, sym_sma, windows=(20, 50), height=220)
        st.plotly_chart(fig_sma, use_container_width=True,
                        config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Quick stats row ───────────────────────────────────────
    section_label("Tóm tắt nhanh")
    stat_cols = st.columns(len(sel_syms))
    for i, sym in enumerate(sel_syms):
        sub = raw_df[raw_df["symbol"] == sym]
        if sub.empty:
            continue
        ret = (sub["close"].iloc[-1] / sub["close"].iloc[0] - 1) * 100
        with stat_cols[i]:
            st.metric(
                label = sym,
                value = fmt_price(sub["close"].iloc[-1]),
                delta = f"{ret:+.2f}%",
            )