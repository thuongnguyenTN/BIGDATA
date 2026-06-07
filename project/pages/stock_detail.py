"""
pages/stock_detail.py — Phân tích chi tiết 1 mã
Biểu đồ: Candlestick / Line, Volume, SMA
Dữ liệu: tbl_raw_stock
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
    build_volume_chart, build_sma_chart,
    fmt_price, fmt_volume, fmt_pct, add_sma,
    _PLOTLY,
)


def _candlestick(df: pd.DataFrame, symbol: str, height: int = 420) -> go.Figure:
    col = "symbol" if "symbol" in df.columns else "ticker"
    sub = df[df[col] == symbol].copy().sort_values("date")

    fig = go.Figure(go.Candlestick(
        x     = sub["date"],
        open  = sub["open"],
        high  = sub["high"],
        low   = sub["low"],
        close = sub["close"],
        increasing_line_color  = "#22C55E",
        decreasing_line_color  = "#EF4444",
        increasing_fillcolor   = "#22C55E",
        decreasing_fillcolor   = "#EF4444",
        hovertext = pd.to_datetime(sub["date"]).dt.strftime("%d/%m/%Y"),
    ))
    fig.update_layout(
        **_PLOTLY, height=height,
        title=dict(text=f"{symbol} — Candlestick",
                   font=dict(size=13, color="#64748B")),
        xaxis=dict(**_PLOTLY["xaxis"], rangeslider=dict(visible=False)),
    )
    return fig


def render(db: DatabaseManager) -> None:
    render_topbar(
        "Stock Detail",
        "Phân tích chi tiết từng mã cổ phiếu ngân hàng",
    )

    # ── Bộ lọc ────────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-header"><span class="card-title">Chọn cổ phiếu</span></div>',
                unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([2, 2, 2, 2])

    with c1:
        symbol = st.selectbox(
            "Mã cổ phiếu",
            options       = list(BANK_META.keys()),
            format_func   = lambda s: f"{s} — {BANK_META[s]['name']}",
        )
    with c2:
        period = st.selectbox(
            "Khoảng thời gian",
            ["1 tháng", "3 tháng", "6 tháng", "1 năm", "2 năm", "5 năm"],
            index=3,
        )
    with c3:
        chart_mode = st.selectbox(
            "Loại biểu đồ",
            ["Candlestick", "Line Chart"],
        )
    with c4:
        sma_windows = st.multiselect(
            "SMA",
            options = [20, 50, 200],
            default = [20, 50],
        )

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Load data ─────────────────────────────────────────────
    days_map = {
        "1 tháng": 30, "3 tháng": 90, "6 tháng": 180,
        "1 năm": 365, "2 năm": 730, "5 năm": 1825,
    }
    n_days = days_map.get(period, 365)
    end    = date.today()
    start  = end - timedelta(days=n_days)

    with st.spinner(f"Đang tải dữ liệu {symbol}..."):
        df = db.get_raw_data([symbol], start, end)

    if df.empty:
        st.warning("Không có dữ liệu.")
        return

    if "trading_date" in df.columns:
        df = df.rename(columns={"trading_date": "date"})

    last    = df.iloc[-1]
    first   = df.iloc[0]
    ret     = (last["close"] / first["close"] - 1) * 100
    vol_ann = df["close"].pct_change().std() * np.sqrt(252) * 100

    # ── KPI row ───────────────────────────────────────────────
    section_label("Chỉ số chính")
    k1, k2, k3, k4, k5 = st.columns(5)

    k1.metric("Giá hiện tại",   fmt_price(last["close"]),
              delta=fmt_pct(ret))
    k2.metric("Giá cao nhất",   fmt_price(df["close"].max()))
    k3.metric("Giá thấp nhất",  fmt_price(df["close"].min()))
    k4.metric("Volume cao nhất",fmt_volume(df["volume"].max())
              if "volume" in df.columns else "N/A")
    k5.metric("Volatility (ann.)", f"{vol_ann:.2f}%")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Main chart ────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="card-header">'
        f'<span class="card-title">{symbol} — {BANK_META.get(symbol,{}).get("name","")} | {chart_mode}</span>'
        f'<span class="badge badge-blue">{period}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if chart_mode == "Candlestick":
        fig_main = _candlestick(df, symbol, height=440)
    else:
        from utils import build_line_chart
        fig_main = build_line_chart(df, [symbol], height=440)

    st.plotly_chart(fig_main, use_container_width=True,
                    config={"displayModeBar": True, "scrollZoom": True})
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Volume + SMA ──────────────────────────────────────────
    col_a, col_b = st.columns([1, 1])

    with col_a:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header"><span class="card-title">Khối lượng giao dịch</span></div>',
                    unsafe_allow_html=True)
        st.plotly_chart(build_volume_chart(df, symbol, height=230),
                        use_container_width=True,
                        config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with col_b:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-header">'
            '<span class="card-title">Đường trung bình động (SMA)</span>'
            '<span class="badge badge-green">Moving Avg</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        if sma_windows:
            fig_sma = build_sma_chart(df, symbol,
                                      windows=tuple(sma_windows), height=230)
            st.plotly_chart(fig_sma, use_container_width=True,
                            config={"displayModeBar": False})
        else:
            info_box("Chọn ít nhất 1 SMA để hiển thị.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Recent data preview ───────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-header">'
        '<span class="card-title">Dữ liệu gần nhất (20 phiên)</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    preview = df.tail(20).sort_values("date", ascending=False).copy()
    if "date" in preview.columns:
        preview["date"] = pd.to_datetime(preview["date"]).dt.strftime("%d/%m/%Y")
    preview["close"] = preview["close"].map(lambda x: f"{x:,.0f}")
    if "volume" in preview.columns:
        preview["volume"] = preview["volume"].map(fmt_volume)

    st.dataframe(
        preview[["date","open","high","low","close","volume"]
                if all(c in preview.columns for c in ["open","high","low"])
                else ["date","close","volume"]],
        use_container_width=True,
        hide_index=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)