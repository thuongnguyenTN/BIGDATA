"""
pages/crud.py — Quản lý danh mục mã ngân hàng
CRUD: Thêm / Sửa / Xóa / Bật-Tắt mã cổ phiếu trong tbl_bank_list
Kết nối: MySQL trực tiếp (qua DatabaseManager) hoặc dummy mode
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from database import DatabaseManager
from utils import render_topbar, section_label, info_box

# ── Constants ────────────────────────────────────────────────────────────────

SOURCES = ["CafeF", "TCBS", "FireAnt", "vnstock"]

STATUS_MAP = {1: ("badge-green",  "● Đang cào"),
              0: ("badge-amber",  "○ Tạm ngưng")}

# ── DB helpers (abstracted so drill/mysql/dummy all work) ─────────────────────

def _load_bank_list(db: DatabaseManager) -> pd.DataFrame:
    """Đọc toàn bộ tbl_bank_list. Fallback dummy nếu bảng chưa có."""
    if db.mode == "dummy":
        return _dummy_bank_list()

    from sqlalchemy import text
    try:
        with db._engine.connect() as conn:
            df = pd.read_sql(
                text("SELECT id, symbol, bank_name, source, status "
                     "FROM tbl_bank_list ORDER BY id"),
                conn,
            )
        return df
    except Exception:
        st.warning("⚠ Không đọc được tbl_bank_list — hiển thị dữ liệu mẫu.")
        return _dummy_bank_list()


def _dummy_bank_list() -> pd.DataFrame:
    return pd.DataFrame([
        {"id": 1,  "symbol": "VCB", "bank_name": "Vietcombank",      "source": "CafeF",   "status": 1},
        {"id": 2,  "symbol": "BID", "bank_name": "BIDV",             "source": "CafeF",   "status": 1},
        {"id": 3,  "symbol": "CTG", "bank_name": "VietinBank",       "source": "CafeF",   "status": 1},
        {"id": 4,  "symbol": "MBB", "bank_name": "MBBank",           "source": "CafeF",   "status": 1},
        {"id": 5,  "symbol": "TCB", "bank_name": "Techcombank",      "source": "CafeF",   "status": 1},
        {"id": 6,  "symbol": "VPB", "bank_name": "VPBank",           "source": "CafeF",   "status": 1},
        {"id": 7,  "symbol": "ACB", "bank_name": "ACB",              "source": "CafeF",   "status": 1},
        {"id": 8,  "symbol": "STB", "bank_name": "Sacombank",        "source": "CafeF",   "status": 1},
        {"id": 9,  "symbol": "SHB", "bank_name": "SHB",              "source": "TCBS",    "status": 1},
        {"id": 10, "symbol": "HDB", "bank_name": "HDBank",           "source": "TCBS",    "status": 1},
        {"id": 11, "symbol": "VIB", "bank_name": "VIB",              "source": "TCBS",    "status": 0},
        {"id": 12, "symbol": "TPB", "bank_name": "TPBank",           "source": "TCBS",    "status": 1},
        {"id": 13, "symbol": "EIB", "bank_name": "Eximbank",         "source": "TCBS",    "status": 0},
        {"id": 14, "symbol": "MSB", "bank_name": "MSB",              "source": "TCBS",    "status": 1},
        {"id": 15, "symbol": "SSB", "bank_name": "SeABank",          "source": "TCBS",    "status": 1},
        {"id": 16, "symbol": "LPB", "bank_name": "LPBank",           "source": "TCBS",    "status": 1},
        {"id": 17, "symbol": "OCB", "bank_name": "OCB",              "source": "FireAnt", "status": 1},
        {"id": 18, "symbol": "NAB", "bank_name": "NamA Bank",        "source": "FireAnt", "status": 0},
        {"id": 19, "symbol": "KLB", "bank_name": "KienLong Bank",    "source": "FireAnt", "status": 1},
        {"id": 20, "symbol": "BVB", "bank_name": "Bao Viet Bank",    "source": "FireAnt", "status": 0},
    ])


def _exec(db: DatabaseManager, sql: str, params: dict) -> bool:
    """Thực thi INSERT / UPDATE / DELETE. Trả về True nếu thành công."""
    if db.mode == "dummy":
        return True  # demo: không ghi thật
    from sqlalchemy import text
    try:
        with db._engine.begin() as conn:
            conn.execute(text(sql), params)
        return True
    except Exception as exc:
        st.error(f"❌ Lỗi DB: {exc}")
        return False


# ── Sub-components ────────────────────────────────────────────────────────────

def _kpi_row(df: pd.DataFrame) -> None:
    total   = len(df)
    active  = int((df["status"] == 1).sum())
    paused  = total - active
    sources = df["source"].nunique()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Tổng mã quản lý",  total)
    k2.metric("Đang kích hoạt",   active,  delta=f"+{active} mã")
    k3.metric("Tạm ngưng",        paused)
    k4.metric("Nguồn dữ liệu",    sources)


def _table_view(df: pd.DataFrame) -> None:
    """Render bảng danh sách với badge HTML."""

    # Build display rows
    rows_html = ""
    for _, r in df.iterrows():
        badge_cls, badge_lbl = STATUS_MAP.get(int(r["status"]), ("badge-amber", "—"))
        src_cls = {
            "CafeF": "badge-blue", "TCBS": "badge-purple",
            "FireAnt": "badge-cyan", "vnstock": "badge-green",
        }.get(r["source"], "badge-blue")

        rows_html += f"""
        <tr>
          <td style="font-family:var(--font-mono);font-size:.76rem;color:var(--text-muted);
                     padding:10px 14px;border-bottom:1px solid var(--border-soft);">
            #{int(r['id'])}</td>
          <td style="padding:10px 14px;border-bottom:1px solid var(--border-soft);">
            <span style="font-family:var(--font-mono);font-size:.88rem;font-weight:700;
                         color:var(--accent-bright);letter-spacing:.06em;">{r['symbol']}</span>
          </td>
          <td style="padding:10px 14px;border-bottom:1px solid var(--border-soft);
                     font-size:.80rem;color:var(--text-secondary);">{r['bank_name']}</td>
          <td style="padding:10px 14px;border-bottom:1px solid var(--border-soft);">
            <span class="badge {src_cls}">{r['source']}</span></td>
          <td style="padding:10px 14px;border-bottom:1px solid var(--border-soft);">
            <span class="badge {badge_cls}">{badge_lbl}</span></td>
        </tr>"""

    table_html = f"""
    <div style="overflow-x:auto;border-radius:var(--radius-md);
                border:1px solid var(--border);box-shadow:var(--shadow-sm);">
      <table style="width:100%;border-collapse:collapse;background:var(--bg-card);">
        <thead>
          <tr style="border-bottom:1px solid rgba(59,130,246,.15);">
            <th style="padding:10px 14px;text-align:left;font-size:.62rem;font-weight:700;
                       text-transform:uppercase;letter-spacing:.12em;color:var(--text-muted);
                       font-family:var(--font);">ID</th>
            <th style="padding:10px 14px;text-align:left;font-size:.62rem;font-weight:700;
                       text-transform:uppercase;letter-spacing:.12em;color:var(--text-muted);
                       font-family:var(--font);">Mã CP</th>
            <th style="padding:10px 14px;text-align:left;font-size:.62rem;font-weight:700;
                       text-transform:uppercase;letter-spacing:.12em;color:var(--text-muted);
                       font-family:var(--font);">Tên ngân hàng</th>
            <th style="padding:10px 14px;text-align:left;font-size:.62rem;font-weight:700;
                       text-transform:uppercase;letter-spacing:.12em;color:var(--text-muted);
                       font-family:var(--font);">Nguồn cào</th>
            <th style="padding:10px 14px;text-align:left;font-size:.62rem;font-weight:700;
                       text-transform:uppercase;letter-spacing:.12em;color:var(--text-muted);
                       font-family:var(--font);">Trạng thái</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>"""
    st.markdown(table_html, unsafe_allow_html=True)


def _form_add(db: DatabaseManager) -> None:
    """Form Thêm mã mới."""
    st.markdown("""
    <div class="card" style="border-left:3px solid var(--green);">
      <div class="card-header">
        <span class="card-title">Thêm mã ngân hàng mới</span>
        <span class="badge badge-green">INSERT</span>
      </div>
    </div>""", unsafe_allow_html=True)

    with st.form("form_add", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            new_sym  = st.text_input("Mã CP *", placeholder="VD: TCB",
                                     max_chars=10).strip().upper()
        with c2:
            new_name = st.text_input("Tên ngân hàng *",
                                     placeholder="VD: Techcombank").strip()
        with c3:
            new_src  = st.selectbox("Nguồn cào *", SOURCES)

        submitted = st.form_submit_button("➕  Thêm mã", use_container_width=True)

    if submitted:
        if not new_sym or not new_name:
            st.error("Vui lòng điền đủ Mã CP và Tên ngân hàng.")
            return

        existing = _load_bank_list(db)
        if new_sym in existing["symbol"].values:
            st.error(f"Mã **{new_sym}** đã tồn tại trong danh sách.")
            return

        ok = _exec(db,
                   "INSERT INTO tbl_bank_list (symbol, bank_name, source, status) "
                   "VALUES (:sym, :name, :src, 1)",
                   {"sym": new_sym, "name": new_name, "src": new_src})
        if ok:
            st.success(f"✅ Đã thêm mã **{new_sym} — {new_name}** (nguồn: {new_src}).")
            st.cache_resource.clear()
            st.rerun()


def _form_edit(db: DatabaseManager, df: pd.DataFrame) -> None:
    """Form Sửa thông tin mã."""
    st.markdown("""
    <div class="card" style="border-left:3px solid var(--accent-light);">
      <div class="card-header">
        <span class="card-title">Cập nhật thông tin mã</span>
        <span class="badge badge-blue">UPDATE</span>
      </div>
    </div>""", unsafe_allow_html=True)

    sym_options = df["symbol"].tolist()
    if not sym_options:
        info_box("Chưa có mã nào trong danh sách.")
        return

    sel = st.selectbox("Chọn mã cần sửa", sym_options,
                       format_func=lambda s: f"{s} — {df.loc[df['symbol']==s,'bank_name'].values[0]}",
                       key="edit_select")

    row = df[df["symbol"] == sel].iloc[0]

    with st.form("form_edit"):
        c1, c2 = st.columns([2, 1])
        with c1:
            upd_name = st.text_input("Tên ngân hàng", value=row["bank_name"])
        with c2:
            upd_src  = st.selectbox("Nguồn cào", SOURCES,
                                    index=SOURCES.index(row["source"])
                                    if row["source"] in SOURCES else 0)

        upd_status = st.radio(
            "Trạng thái",
            options=[1, 0],
            format_func=lambda x: "● Kích hoạt cào" if x == 1 else "○ Tạm ngưng",
            index=0 if int(row["status"]) == 1 else 1,
            horizontal=True,
        )
        submitted = st.form_submit_button("💾  Lưu thay đổi", use_container_width=True)

    if submitted:
        ok = _exec(db,
                   "UPDATE tbl_bank_list SET bank_name=:name, source=:src, status=:st "
                   "WHERE symbol=:sym",
                   {"name": upd_name.strip(), "src": upd_src,
                    "st": upd_status, "sym": sel})
        if ok:
            st.success(f"✅ Đã cập nhật mã **{sel}**.")
            st.rerun()


def _form_toggle(db: DatabaseManager, df: pd.DataFrame) -> None:
    """Bật / Tắt hàng loạt trạng thái cào."""
    st.markdown("""
    <div class="card" style="border-left:3px solid var(--amber);">
      <div class="card-header">
        <span class="card-title">Bật / Tắt trạng thái cào nhanh</span>
        <span class="badge badge-amber">TOGGLE</span>
      </div>
    </div>""", unsafe_allow_html=True)

    info_box(
        "🔁 Tắt một mã sẽ báo cho Oozie <b>bỏ qua</b> mã đó trong lần cào tiếp theo "
        "(script scrape_and_insert.py đọc <code>status=1</code> trước khi cào)."
    )

    col_on, col_off = st.columns(2)
    with col_on:
        paused_syms = df[df["status"] == 0]["symbol"].tolist()
        sel_on = st.multiselect("Kích hoạt lại", paused_syms,
                                placeholder="Chọn mã đang tắt...")
        if st.button("▶ Kích hoạt", disabled=not sel_on, key="btn_on",
                     use_container_width=True):
            for s in sel_on:
                _exec(db, "UPDATE tbl_bank_list SET status=1 WHERE symbol=:sym",
                      {"sym": s})
            st.success(f"✅ Đã kích hoạt: {', '.join(sel_on)}")
            st.rerun()

    with col_off:
        active_syms = df[df["status"] == 1]["symbol"].tolist()
        sel_off = st.multiselect("Tạm ngưng", active_syms,
                                 placeholder="Chọn mã đang bật...")
        if st.button("⏸ Tạm ngưng", disabled=not sel_off, key="btn_off",
                     use_container_width=True):
            for s in sel_off:
                _exec(db, "UPDATE tbl_bank_list SET status=0 WHERE symbol=:sym",
                      {"sym": s})
            st.success(f"⏸ Đã tạm ngưng: {', '.join(sel_off)}")
            st.rerun()


def _form_delete(db: DatabaseManager, df: pd.DataFrame) -> None:
    """Form Xóa mã — yêu cầu xác nhận gõ lại tên."""
    st.markdown("""
    <div class="card" style="border-left:3px solid var(--red);">
      <div class="card-header">
        <span class="card-title">Xóa mã khỏi danh sách</span>
        <span class="badge badge-red">DELETE</span>
      </div>
    </div>""", unsafe_allow_html=True)

    st.markdown(
        '<div class="info-box" style="border-left-color:var(--red);'
        'color:#F87171;background:var(--red-dim);">'
        '⚠ Thao tác này xóa vĩnh viễn mã khỏi <code>tbl_bank_list</code>. '
        'Dữ liệu lịch sử trong <code>tbl_raw_stock</code> <b>không bị ảnh hưởng</b>.'
        '</div>',
        unsafe_allow_html=True,
    )

    sym_del = st.selectbox(
        "Chọn mã cần xóa",
        df["symbol"].tolist(),
        format_func=lambda s: f"{s} — {df.loc[df['symbol']==s,'bank_name'].values[0]}",
        key="del_select",
    )
    confirm = st.text_input(
        f'Gõ lại mã **{sym_del}** để xác nhận xóa',
        placeholder=sym_del,
        key="del_confirm",
    )
    if st.button("🗑  Xóa vĩnh viễn", type="primary",
                 disabled=(confirm.strip().upper() != sym_del),
                 key="btn_delete"):
        ok = _exec(db,
                   "DELETE FROM tbl_bank_list WHERE symbol=:sym",
                   {"sym": sym_del})
        if ok:
            st.success(f"🗑 Đã xóa mã **{sym_del}** khỏi danh sách.")
            st.rerun()


# ── Main render ───────────────────────────────────────────────────────────────

def render(db: DatabaseManager) -> None:
    render_topbar(
        "Quản lý danh mục",
        "CRUD · tbl_bank_list — Thêm / Sửa / Xóa / Bật-Tắt mã ngân hàng cào dữ liệu",
        breadcrumb="Quản lý danh mục",
    )

    if db.mode == "dummy":
        info_box(
            "ℹ <b>Demo Mode</b> — Các thao tác CRUD hiển thị thông báo nhưng "
            "<b>không ghi vào database thật</b>. "
            "Đặt <code>DB_MODE=mysql</code> trong <code>.env</code> để ghi thật."
        )

    # ── Load data ─────────────────────────────────────────────
    df = _load_bank_list(db)

    # ── KPI summary ───────────────────────────────────────────
    section_label("Tổng quan danh mục")
    _kpi_row(df)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Source breakdown chips ────────────────────────────────
    src_counts = df.groupby("source")["symbol"].count().to_dict()
    chips_html = "".join(
        f'<span class="badge badge-blue" style="font-size:.72rem;padding:4px 12px;">'
        f'{src} &nbsp;<span style="opacity:.6">({cnt})</span></span> '
        for src, cnt in src_counts.items()
    )
    st.markdown(
        f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:1rem;">'
        f'{chips_html}</div>',
        unsafe_allow_html=True,
    )

    # ── Table ─────────────────────────────────────────────────
    section_label("Danh sách mã ngân hàng — tbl_bank_list")
    _table_view(df)

    # Search / filter bar
    st.markdown("<br>", unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns([2, 2, 1])
    with fc1:
        q = st.text_input("🔍 Tìm mã / tên", placeholder="VD: ACB, Vietcombank…")
    with fc2:
        src_filter = st.multiselect("Lọc nguồn", SOURCES, default=[])
    with fc3:
        status_filter = st.selectbox("Trạng thái", ["Tất cả", "Đang cào", "Tạm ngưng"])

    df_view = df.copy()
    if q.strip():
        mask = (df_view["symbol"].str.contains(q.strip(), case=False) |
                df_view["bank_name"].str.contains(q.strip(), case=False))
        df_view = df_view[mask]
    if src_filter:
        df_view = df_view[df_view["source"].isin(src_filter)]
    if status_filter == "Đang cào":
        df_view = df_view[df_view["status"] == 1]
    elif status_filter == "Tạm ngưng":
        df_view = df_view[df_view["status"] == 0]

    if not df_view.empty:
        _table_view(df_view)
        st.markdown(
            f'<div class="pag-info">{len(df_view)} / {len(df)} mã</div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("Không tìm thấy mã nào khớp.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── CRUD Tabs ─────────────────────────────────────────────
    section_label("Thao tác CRUD")

    tab_add, tab_edit, tab_toggle, tab_del = st.tabs([
        "➕  Thêm mã",
        "✏️  Sửa thông tin",
        "🔁  Bật / Tắt",
        "🗑  Xóa mã",
    ])

    with tab_add:
        _form_add(db)

    with tab_edit:
        _form_edit(db, df)

    with tab_toggle:
        _form_toggle(db, df)

    with tab_del:
        _form_delete(db, df)

    # ── Export ────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    section_label("Xuất danh sách")

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label     = "⬇ Download CSV — tbl_bank_list",
        data      = csv,
        file_name = "tbl_bank_list.csv",
        mime      = "text/csv",
    )