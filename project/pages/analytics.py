"""
pages/analytics.py — Trang phân tích chuyên sâu
Hiển thị kết quả MapReduce từ tbl_stock_analysis:
  - SMA20, SMA50
  - Ngày biến động lớn nhất
  - Khối lượng giao dịch lớn nhất
  - Giá cao nhất / thấp nhất
Dữ liệu: tbl_raw_stock + tbl_stock_analysis
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from database import DatabaseManager, BANK_META
from utils import (
    render_topbar, section_label, info_box,
    build_line_chart, build_volatility_heatmap,
    build_analysis_bar, add_sma, compute_stats,
    fmt_price, fmt_volume, fmt_pct, _PLOTLY,
)

PRIMARY = ["ACB", "STB", "OCB", "LPB"]


def _risk_return_scatter(summary: pd.DataFrame, height: int = 320) -> go.Figure:
    """Risk vs Return scatter (price_variance làm proxy risk)."""
    palette = ["#3B82F6","#22C55E","#F59E0B","#EF4444",
               "#A78BFA","#06B6D4","#F97316","#EC4899"]
    fig = go.Figure()
    for i, row in summary.iterrows():
        risk = (row.get("price_variance", 0) / row["price"] * 100
                if row["price"] > 0 else 0)
        pct  = row.get("pct_change", 0)
        c    = palette[i % len(palette)]
        fig.add_trace(go.Scatter(
            x    = [risk], y = [pct],
            mode = "markers+text",
            name = row["symbol"],
            text = [row["symbol"]],
            textposition  = "top center",
            textfont      = dict(size=11, color=c,
                                 family="IBM Plex Mono, Consolas"),
            marker        = dict(size=16, color=c, opacity=0.9,
                                 line=dict(color="rgba(255,255,255,0.2)",
                                           width=1.5)),
            hovertemplate = (
                f"<b>{row['symbol']}</b><br>"
                f"Return: {pct:+.2f}%<br>"
                f"Risk: {risk:.2f}%<extra></extra>"
            ),
        ))
    fig.add_hline(y=0, line_dash="dot",
                  line_color="rgba(255,255,255,0.1)", line_width=1)
    fig.update_layout(
        **_PLOTLY,
        height=height,
        showlegend=False,
        title=dict(
            text="Risk vs Return",
            font=dict(size=13, color="#64748B")
        ),
    )

    fig.update_xaxes(
        title_text="Risk (price_variance %)",
        title_font=dict(size=11),
        tickfont=dict(size=10, color="#3D5478")
    )

    fig.update_yaxes(
        title_text="Return (%)",
        title_font=dict(size=11),
        tickfont=dict(size=10, color="#3D5478")
    )
    return fig


def render(db: DatabaseManager) -> None:
    render_topbar(
        "Analytics",
        "Kết quả phân tích Big Data — MapReduce · tbl_stock_analysis",
    )

    # ── Selector ──────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-header"><span class="card-title">Cấu hình phân tích</span></div>',
                unsafe_allow_html=True)
    c1, c2 = st.columns([2, 2])

    with c1:
        symbol = st.selectbox(
            "Mã cổ phiếu",
            PRIMARY,
            format_func=lambda s: f"{s} — {BANK_META.get(s,{}).get('name',s)}",
        )
    with c2:
        period = st.selectbox(
            "Khoảng thời gian",
            ["6 tháng", "1 năm", "2 năm", "5 năm"],
            index=1,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    days_map = {"6 tháng": 180, "1 năm": 365, "2 năm": 730, "5 năm": 1825}
    n_days   = days_map.get(period, 365)
    end      = date.today()
    start    = end - timedelta(days=n_days)

    with st.spinner("Đang tính toán..."):
        raw_df  = db.get_raw_data([symbol], start, end)
        anal_df = db.get_analysis_data([symbol], start, end)

    if raw_df.empty:
        st.warning("Không có dữ liệu.")
        return

    if "trading_date" in raw_df.columns:
        raw_df = raw_df.rename(columns={"trading_date": "date"})

    stats = compute_stats(raw_df, symbol)

    # ── KPI Cards ─────────────────────────────────────────────
    section_label("Chỉ số tổng hợp")

    k1, k2, k3, k4, k5, k6 = st.columns(6)

    k1.metric("SMA 20",
              fmt_price(stats.get("sma20", 0)) if stats.get("sma20") else "—")
    k2.metric("SMA 50",
              fmt_price(stats.get("sma50", 0)) if stats.get("sma50") else "—")
    k3.metric("Ngày biến động lớn nhất", stats.get("max_var_date","—"))
    k4.metric("KL giao dịch lớn nhất",  fmt_volume(stats.get("max_volume",0)),
              delta=f"ngày {stats.get('max_vol_date','—')}")
    k5.metric("Giá cao nhất",  fmt_price(stats.get("max_close",0)))
    k6.metric("Giá thấp nhất", fmt_price(stats.get("min_close",0)))

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Detailed stat card ────────────────────────────────────
    col_l, col_r = st.columns([1, 2])

    with col_l:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="card-header">'
            f'<span class="card-title">Thống kê {symbol}</span>'
            f'<span class="badge badge-blue">{period}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        def stat_row(label: str, value: str, cls: str = "") -> None:
            st.markdown(
                f'<div class="stat-row">'
                f'<span class="stat-label">{label}</span>'
                f'<span class="stat-value {cls}">{value}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        stat_row("Giá hiện tại",     fmt_price(stats.get("price", 0)))
        stat_row("SMA 20",           fmt_price(stats.get("sma20", 0)) if stats.get("sma20") else "—")
        stat_row("SMA 50",           fmt_price(stats.get("sma50", 0)) if stats.get("sma50") else "—")
        ret_val = stats.get("return_pct", 0)
        stat_row("Sinh lời",         fmt_pct(ret_val),
                 cls="pos" if ret_val >= 0 else "neg")
        stat_row("Volatility (ann.)",f"{stats.get('volatility',0):.2f}%")
        stat_row("Giá cao nhất",     fmt_price(stats.get("max_close",0)))
        stat_row("Giá thấp nhất",    fmt_price(stats.get("min_close",0)))
        stat_row("KL lớn nhất",      fmt_volume(stats.get("max_volume",0)))
        stat_row("Ngày KL lớn nhất", stats.get("max_vol_date","—"))
        stat_row("Ngày biến động",   stats.get("max_var_date","—"))

        st.markdown("</div>", unsafe_allow_html=True)

    with col_r:
        # SMA Chart
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-header">'
            '<span class="card-title">SMA 20 & SMA 50</span>'
            '<span class="badge badge-green">Moving Average</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        from utils import build_sma_chart
        fig_sma = build_sma_chart(raw_df, symbol,
                                  windows=(20, 50), height=300)
        st.plotly_chart(fig_sma, use_container_width=True,
                        config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    # ── MapReduce result: avg_close_price từ tbl_stock_analysis ──
    if not anal_df.empty:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-header">'
            '<span class="card-title">avg_close_price — Kết quả MapReduce</span>'
            '<span class="badge badge-amber">tbl_stock_analysis</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        info_box(
            "📌 Dữ liệu này đọc trực tiếp từ <b>tbl_stock_analysis</b> "
            "— bảng được Sqoop Export đẩy vào sau khi MapReduce chạy xong."
        )
        fig_anal = build_analysis_bar(anal_df, symbol, height=260)
        st.plotly_chart(fig_anal, use_container_width=True,
                        config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Heatmap ───────────────────────────────────────────────
    with st.spinner("Đang vẽ heatmap tất cả mã..."):
        all_df = db.get_raw_data(PRIMARY, start, end)
    if "trading_date" in all_df.columns:
        all_df = all_df.rename(columns={"trading_date": "date"})

    if not all_df.empty:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-header">'
            '<span class="card-title">Heatmap biến động hàng tháng</span>'
            '<span class="badge badge-blue">ACB · STB · OCB · LPB</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            build_volatility_heatmap(all_df, height=240),
            use_container_width=True,
            config={"displayModeBar": False},
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Risk vs Return scatter ────────────────────────────────
    summary = db.get_summary()
    primary_sum = summary[summary["symbol"].isin(PRIMARY)]
    if not primary_sum.empty:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-header">'
            '<span class="card-title">Risk vs Return — 4 ngân hàng</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            _risk_return_scatter(primary_sum, height=300),
            use_container_width=True,
            config={"displayModeBar": False},
        )
        st.markdown("</div>", unsafe_allow_html=True)   