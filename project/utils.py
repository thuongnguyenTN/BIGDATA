"""
utils.py — Hàm tiện ích dùng chung toàn GUI
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ── CSS loader ───────────────────────────────────────────────────────────────

def load_css(path: str = "style.css") -> None:
    """Inject file CSS vào Streamlit."""
    p = Path(path)
    if p.exists():
        st.markdown(f"<style>{p.read_text(encoding='utf-8')}</style>",
                    unsafe_allow_html=True)
    else:
        st.warning(f"⚠ Không tìm thấy style.css tại {p.resolve()}")


# ── Plotly base layout ───────────────────────────────────────────────────────

_PLOTLY = dict(
    paper_bgcolor = "rgba(0,0,0,0)",
    plot_bgcolor  = "rgba(0,0,0,0)",
    font          = dict(family="Space Grotesk, Segoe UI, sans-serif",
                         color="#7A92B8", size=11),
    margin        = dict(l=8, r=8, t=40, b=8),
    hovermode     = "x unified",
    hoverlabel    = dict(bgcolor="#0D1520", bordercolor="#2563EB",
                         font_size=12, font_color="#E8F0FE"),
    xaxis = dict(
        showgrid        = False,
        showline        = False,
        zeroline        = False,
        gridcolor       = "rgba(59,130,246,0.04)",
    ),
    yaxis = dict(
        showgrid        = True,
        gridcolor       = "rgba(255,255,255,0.035)",
        showline        = False,
        zeroline        = False,
    ),
    legend = dict(
        bgcolor       = "rgba(13,21,32,0.90)",
        bordercolor   = "rgba(255,255,255,0.05)",
        borderwidth   = 1,
        font          = dict(size=11, color="#7A92B8"),
        orientation   = "h",
        yanchor       = "bottom",
        y             = -0.24,
        xanchor       = "left",
        x             = 0,
    ),
)

# Màu palette
PALETTE = [
    "#3B82F6", "#10B981", "#F59E0B", "#EF4444",
    "#8B5CF6", "#06B6D4", "#F97316", "#EC4899", "#14B8A6",
]

def _color(i: int) -> str:
    return PALETTE[i % len(PALETTE)]


# ── Chart builders ───────────────────────────────────────────────────────────

def build_line_chart(
    df:        pd.DataFrame,
    symbols:   list[str],
    title:     str  = "Giá đóng cửa",
    height:    int  = 380,
    normalize: bool = False,
) -> go.Figure:
    """
    Line chart nhiều mã.
    normalize=True → chuẩn hóa base=100 để so sánh tương đối.
    Cột bắt buộc: symbol/ticker, date, close.
    """
    fig = go.Figure()
    col = "symbol" if "symbol" in df.columns else "ticker"

    for i, sym in enumerate(symbols):
        sub = df[df[col] == sym].copy().sort_values("date")
        if sub.empty:
            continue
        y = sub["close"].to_numpy(dtype=float)
        if normalize and y[0] > 0:
            y = y / y[0] * 100

        fig.add_trace(go.Scatter(
            x    = sub["date"],
            y    = y,
            name = sym,
            mode = "lines",
            line = dict(color=_color(i), width=2.2),
            hovertemplate=(
                f"<b>{sym}</b><br>%{{x|%d/%m/%Y}}<br>"
                + ("Norm: %{y:.2f}<extra></extra>" if normalize
                   else "Giá: %{y:,.0f}₫<extra></extra>")
            ),
        ))

    fig.update_layout(**_PLOTLY, height=height,
                      title=dict(text=title, font=dict(size=13, color="#3D5478")))
    fig.update_xaxes(tickfont=dict(size=10, color="#3D5478"), rangeslider_visible=False)
    fig.update_yaxes(tickfont=dict(size=10, color="#3D5478"))
    return fig


def build_volume_chart(
    df:     pd.DataFrame,
    symbol: str,
    height: int = 200,
) -> go.Figure:
    """Bar chart khối lượng giao dịch, màu xanh/đỏ theo chiều giá."""
    col = "symbol" if "symbol" in df.columns else "ticker"
    sub = df[df[col] == symbol].copy().sort_values("date")
    if sub.empty:
        return go.Figure()

    colors = np.where(sub["close"].diff().fillna(0) >= 0, "#10B981", "#EF4444")

    fig = go.Figure(go.Bar(
        x             = sub["date"],
        y             = sub["volume"],
        marker_color  = colors,
        opacity       = 0.70,
        hovertemplate = "%{x|%d/%m/%Y}<br>Vol: %{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(**_PLOTLY, height=height, bargap=0.15,
                      title=dict(text="Khối lượng giao dịch",
                                 font=dict(size=13, color="#3D5478")))
    fig.update_xaxes(tickfont=dict(size=10, color="#3D5478"), rangeslider_visible=False)
    fig.update_yaxes(tickfont=dict(size=10, color="#3D5478"))
    return fig


def build_sma_chart(
    df:      pd.DataFrame,
    symbol:  str,
    windows: tuple[int, ...] = (20, 50),
    height:  int = 420,
) -> go.Figure:
    """
    Giá đóng cửa + đường SMA overlay.
    """
    col = "symbol" if "symbol" in df.columns else "ticker"
    sub = df[df[col] == symbol].copy().sort_values("date")

    if "avg_close_price" in sub.columns and "close" not in sub.columns:
        sub = sub.rename(columns={"avg_close_price": "close"})

    if sub.empty:
        return go.Figure()

    for w in windows:
        sub[f"sma{w}"] = sub["close"].rolling(w).mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x             = sub["date"],
        y             = sub["close"],
        name          = "Close",
        mode          = "lines",
        line          = dict(color="#3B82F6", width=2.2),
        fill          = "tozeroy",
        fillcolor     = "rgba(37,99,235,0.045)",
        hovertemplate = "Giá: %{y:,.0f}₫<extra></extra>",
    ))

    sma_style = {
        20:  dict(color="#10B981", dash="solid", width=1.6),
        50:  dict(color="#F59E0B", dash="dot",   width=1.6),
        200: dict(color="#EF4444", dash="dash",  width=1.6),
    }
    for w in windows:
        if f"sma{w}" not in sub.columns:
            continue
        fig.add_trace(go.Scatter(
            x             = sub["date"],
            y             = sub[f"sma{w}"],
            name          = f"SMA {w}",
            mode          = "lines",
            line          = sma_style.get(w, dict(color="#8B5CF6", dash="dot", width=1.6)),
            hovertemplate = f"SMA{w}: %{{y:,.0f}}₫<extra></extra>",
        ))

    fig.update_layout(
        **_PLOTLY, height=height,
        title=dict(text=f"{symbol} — Close & SMA",
                   font=dict(size=13, color="#3D5478")),
    )
    fig.update_xaxes(tickfont=dict(size=10, color="#3D5478"), rangeslider_visible=False)
    fig.update_yaxes(tickfont=dict(size=10, color="#3D5478"))
    return fig


def build_analysis_bar(
    df:     pd.DataFrame,
    symbol: str,
    height: int = 280,
) -> go.Figure:
    """
    Bar chart avg_close_price theo thời gian từ tbl_stock_analysis.
    """
    col = "symbol" if "symbol" in df.columns else "ticker"
    sub = df[df[col] == symbol].copy().sort_values(
        "calc_date" if "calc_date" in df.columns else "date"
    )
    date_col  = "calc_date" if "calc_date" in sub.columns else "date"
    price_col = "avg_close_price" if "avg_close_price" in sub.columns else "close"

    fig = go.Figure(go.Bar(
        x             = sub[date_col],
        y             = sub[price_col],
        marker_color  = "#3B82F6",
        opacity       = 0.78,
        hovertemplate = "%{x|%d/%m/%Y}<br>Avg Close: %{y:,.0f}₫<extra></extra>",
    ))
    fig.update_layout(
        **_PLOTLY, height=height,
        title=dict(text=f"{symbol} — avg_close_price (MapReduce result)",
                   font=dict(size=13, color="#3D5478")),
    )
    fig.update_xaxes(tickfont=dict(size=10, color="#3D5478"), rangeslider_visible=False)
    fig.update_yaxes(tickfont=dict(size=10, color="#3D5478"))
    return fig


def build_volatility_heatmap(df: pd.DataFrame, height: int = 260) -> go.Figure:
    """Heatmap biến động hàng tháng theo mã."""
    col  = "symbol" if "symbol" in df.columns else "ticker"
    df2  = df.copy()
    df2["month"] = pd.to_datetime(df2["date"]).dt.to_period("M").astype(str)
    df2["pct"]   = (
        df2.groupby(col)["close"].pct_change().abs() * 100
        if "close" in df2.columns else 0
    )

    pivot = (
        df2.groupby([col, "month"])["pct"]
        .mean().reset_index()
        .pivot(index=col, columns="month", values="pct")
        .iloc[:, -18:]
    )

    fig = go.Figure(go.Heatmap(
        z          = pivot.values,
        x          = pivot.columns.tolist(),
        y          = pivot.index.tolist(),
        colorscale = [
            [0,   "#080D14"],
            [0.3, "#0F2C5A"],
            [0.6, "#1D4ED8"],
            [1,   "#60A5FA"],
        ],
        hovertemplate = "<b>%{y}</b> | %{x}<br>Volatility: %{z:.3f}%<extra></extra>",
        showscale     = True,
        colorbar      = dict(
            len          = 0.85,
            thickness    = 10,
            # tickfont     = dict(size=9, color="#3D5478"),
            outlinecolor = "rgba(0,0,0,0)",
        ),
    ))
    fig.update_layout(
        **_PLOTLY, height=height,
        title=dict(text="Heatmap biến động trung bình hàng tháng (%)",
                   font=dict(size=13, color="#3D5478")),
    )
    fig.update_xaxes(tickangle=-40, tickfont=dict(size=9, color="#3D5478"),
                     rangeslider_visible=False)
    fig.update_yaxes(tickfont=dict(size=9, color="#3D5478"))
    return fig


# ── Formatters ───────────────────────────────────────────────────────────────

def fmt_price(v: float) -> str:
    return f"{v:,.0f}₫"

def fmt_volume(v: float) -> str:
    if v >= 1_000_000: return f"{v / 1_000_000:.1f}M"
    if v >= 1_000:     return f"{v / 1_000:.0f}K"
    return str(int(v))

def fmt_pct(v: float) -> str:
    return f"+{v:.2f}%" if v >= 0 else f"{v:.2f}%"


# ── SMA helper ───────────────────────────────────────────────────────────────

def add_sma(df: pd.DataFrame, windows: tuple[int, ...] = (20, 50)) -> pd.DataFrame:
    """Thêm cột SMAxx vào dataframe, group theo symbol/ticker."""
    col    = "symbol" if "symbol" in df.columns else "ticker"
    frames = []
    for sym in df[col].unique():
        sub = df[df[col] == sym].copy().sort_values("date")
        for w in windows:
            sub[f"sma{w}"] = sub["close"].rolling(w).mean()
        frames.append(sub)
    return pd.concat(frames, ignore_index=True) if frames else df


def compute_stats(df: pd.DataFrame, symbol: str) -> dict:
    """Tính chỉ số thống kê 1 mã — dùng cho trang Analytics."""
    col = "symbol" if "symbol" in df.columns else "ticker"
    sub = df[df[col] == symbol].copy().sort_values("date")
    if sub.empty:
        return {}

    sub     = add_sma(sub, (20, 50))
    last    = sub.iloc[-1]
    ret     = (sub["close"].iloc[-1] / sub["close"].iloc[0] - 1) * 100
    vol_ann = sub["close"].pct_change().std() * np.sqrt(252) * 100

    vol_idx = sub["volume"].idxmax() if "volume" in sub.columns else None
    var_idx = sub["close"].pct_change().abs().idxmax()

    return {
        "symbol":       symbol,
        "price":        last["close"],
        "sma20":        last.get("sma20", float("nan")),
        "sma50":        last.get("sma50", float("nan")),
        "return_pct":   ret,
        "volatility":   vol_ann,
        "max_close":    sub["close"].max(),
        "min_close":    sub["close"].min(),
        "max_volume":   sub["volume"].max() if "volume" in sub.columns else 0,
        "max_vol_date": (sub.loc[vol_idx, "date"].strftime("%d/%m/%Y")
                         if vol_idx is not None else "N/A"),
        "max_var_date": sub.loc[var_idx, "date"].strftime("%d/%m/%Y"),
    }


# ── HTML component builders ──────────────────────────────────────────────────

def render_topbar(title: str, subtitle: str, breadcrumb: str = "") -> None:
    now = datetime.now().strftime("%H:%M  %d/%m/%Y")
    bc  = breadcrumb or "Đồ án Dữ liệu Lớn"
    st.markdown(f"""
    <div class="topbar">
      <div class="topbar-left">
        <div class="t-breadcrumb">📊 BigData Stock &nbsp;›&nbsp; {bc}</div>
        <div class="t-title">{title}</div>
        <div class="t-sub">{subtitle}</div>
      </div>
      <div class="topbar-right">
        <span class="live-pill">
          <span class="dot dot-green dot-pulse"></span>LIVE
        </span>
        <span class="timestamp">{now}</span>
      </div>
    </div>
    <div class="accent-line"></div>
    """, unsafe_allow_html=True)


def render_kpi_card(
    symbol:  str,
    name:    str,
    price:   float,
    pct_chg: float,
    volume:  float,
) -> None:
    arrow = "▲" if pct_chg >= 0 else "▼"
    cls   = "pos" if pct_chg >= 0 else "neg"
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-ticker">{symbol}</div>
      <div class="kpi-name">{name}</div>
      <div class="kpi-price">{fmt_price(price)}</div>
      <div class="kpi-change {cls}">{arrow} {abs(pct_chg):.2f}%</div>
      <div class="kpi-vol">Vol &nbsp;{fmt_volume(volume)}</div>
    </div>
    """, unsafe_allow_html=True)


# Giữ lại cho compat với app.py cũ nếu cần
def render_sidebar_logo() -> None:
    st.markdown("""
    <div class="sb-brand">
      <div class="sb-brand-row">
        <div class="sb-icon">📊</div>
        <div>
          <div class="sb-title">BigData Stock<br>Dashboard</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def render_sidebar_footer(db_mode: str, connected: bool) -> None:
    dot    = "dot-green" if connected else "dot-red"
    status = "Online" if connected else "Offline"
    source = {
        "dummy": "Demo / Dummy Data",
        "mysql": "MySQL · bigdata_stock",
        "drill": "Apache Drill",
    }.get(db_mode, db_mode)
    st.markdown(f"""
    <div class="sb-footer">
      <div class="sb-footer-row">
        <span>Data Source</span>
        <span class="sb-footer-val">{source}</span>
      </div>
      <div class="sb-footer-row">
        <span>Connection</span>
        <span class="sb-footer-val">
          <span class="dot {dot}"></span>&nbsp;{status}
        </span>
      </div>
    </div>
    """, unsafe_allow_html=True)


def card_open(title: str, badge: str = "", badge_cls: str = "badge-blue") -> None:
    badge_html = f'<span class="badge {badge_cls}">{badge}</span>' if badge else ""
    st.markdown(f"""
    <div class="card">
      <div class="card-header">
        <span class="card-title">{title}</span>
        {badge_html}
      </div>
    """, unsafe_allow_html=True)


def card_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def section_label(text: str) -> None:
    st.markdown(f'<div class="section-label">{text}</div>', unsafe_allow_html=True)


def info_box(text: str) -> None:
    st.markdown(f'<div class="info-box">{text}</div>', unsafe_allow_html=True)