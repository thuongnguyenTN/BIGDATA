"""
database.py — DatabaseManager (v2 — fix kết nối thực tế)
Kết nối: Apache Drill REST (production) | MySQL trực tiếp (fallback) | Dummy

Tên bảng theo bigdata_stock.sql:
  - tbl_raw_stock        : dữ liệu thô (cột viết hoa chữ cái đầu: Symbol, Close, ...)
  - tbl_stock_daily_analysis  : kết quả MapReduce theo ngày
  - tbl_stock_monthly_analysis: kết quả MapReduce theo tháng
  - tbl_bank_list        : danh mục mã ngân hàng (CRUD từ Web)

Thay đổi so với v1:
  1. Sửa tên cột tbl_raw_stock (Close, Open, High, Low, Volume, Trading_Date)
  2. Drill dùng REST API /query.json thay vì sqlalchemy-drill (khớp data_access.py)
  3. Thêm method execute() public cho crud.py
  4. Đổi sang tbl_stock_daily_analysis + tbl_stock_monthly_analysis
"""

from __future__ import annotations

import os
import logging
import requests
from typing import Optional
from datetime import date, timedelta, datetime

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── Chế độ kết nối ─────────────────────────────────────────
# "dummy"  → sinh data giả, dev offline (mặc định)
# "drill"  → Apache Drill REST API :8047 (production — BiMi cấp VM IP)
# "mysql"  → MySQL Local 127.0.0.1:3306/bigdata_stock (fallback)
DB_MODE: str = os.getenv("DB_MODE", "drill")

# ── Danh sách mã theo đề bài ─────────────────────────────
BANK_META: dict[str, dict] = {
    "ACB": {"name": "Asia Commercial Bank",   "base": 24_500},
    "STB": {"name": "Sacombank",              "base": 32_100},
    "OCB": {"name": "Orient Commercial Bank", "base": 13_800},
    "LPB": {"name": "LienVietPostBank",       "base": 16_200},
    "VCB": {"name": "Vietcombank",            "base": 82_500},
    "BID": {"name": "BIDV",                   "base": 47_300},
    "CTG": {"name": "VietinBank",             "base": 38_900},
    "MBB": {"name": "MB Bank",               "base": 24_600},
    "TCB": {"name": "Techcombank",            "base": 35_200},
}


class DatabaseManager:
    """
    Quản lý kết nối và truy vấn dữ liệu.
    Swap backend: chỉ đổi DB_MODE trong .env, code GUI không đổi.
    """

    def __init__(self) -> None:
        self._mode   = DB_MODE
        self._engine = None        # SQLAlchemy engine (mysql mode)
        self._drill_url: str = ""  # Drill REST endpoint (drill mode)

        if self._mode == "mysql":
            self._engine = self._create_mysql_engine()
        elif self._mode == "drill":
            host = os.getenv("DRILL_HOST", "localhost")
            port = os.getenv("DRILL_PORT", "8047")
            self._drill_url = f"http://{host}:{port}/query.json"

    # ── Engine (mysql only) ──────────────────────────────────

    def _create_mysql_engine(self):
        try:
            from sqlalchemy import create_engine
            url = (
                f"mysql+pymysql://{os.getenv('DB_USER','root')}:"
                f"{os.getenv('DB_PASSWORD','password123')}@"
                f"{os.getenv('DB_HOST','127.0.0.1')}:"
                f"{os.getenv('DB_PORT','3306')}/"
                f"{os.getenv('DB_NAME','bigdata_stock')}?charset=utf8mb4"
            )
            return create_engine(url, pool_pre_ping=True, pool_recycle=1800)
        except Exception as exc:
            logger.error("MySQL engine init failed: %s → fallback to dummy", exc)
            self._mode = "dummy"
            return None

    # ── Health check ─────────────────────────────────────────

    def connect(self) -> bool:
        if self._mode == "dummy":
            return True
        if self._mode == "drill":
            try:
                r = requests.post(
                    self._drill_url,
                    json={"queryType": "SQL", "query": "SELECT 1"},
                    headers={"Content-Type": "application/json"},
                    timeout=5,
                )
                return r.status_code == 200
            except Exception as exc:
                logger.warning("Drill connect failed: %s", exc)
                return False
        if self._mode == "mysql":
            try:
                from sqlalchemy import text
                with self._engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return True
            except Exception as exc:
                logger.warning("MySQL connect failed: %s", exc)
                return False
        return False

    # ── Drill REST query ─────────────────────────────────────

    def _drill_query(self, sql: str) -> pd.DataFrame:
        """Thực thi SQL qua Drill REST API, trả về DataFrame."""
        try:
            r = requests.post(
                self._drill_url,
                json={"queryType": "SQL", "query": sql},
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            if r.status_code != 200:
                logger.error("Drill query error %s: %s", r.status_code, r.text[:200])
                return pd.DataFrame()
            rows = r.json().get("rows", [])
            return pd.DataFrame(rows) if rows else pd.DataFrame()
        except Exception as exc:
            logger.error("Drill request failed: %s", exc)
            return pd.DataFrame()

    # ── MySQL query ──────────────────────────────────────────

    def _mysql_query(self, sql: str, params: dict | None = None) -> pd.DataFrame:
        from sqlalchemy import text
        try:
            with self._engine.connect() as conn:
                return pd.read_sql(text(sql), conn, params=params or {})
        except Exception as exc:
            logger.error("MySQL query error: %s", exc)
            return pd.DataFrame()

    # ── Public execute (cho crud.py INSERT/UPDATE/DELETE) ────

    def execute(self, sql: str, params: dict | None = None) -> bool:
        """
        Thực thi câu lệnh ghi (INSERT / UPDATE / DELETE).
        - drill mode: Drill không hỗ trợ DML → ghi thẳng MySQL qua engine phụ
        - mysql mode: dùng engine chính
        - dummy mode: trả True nhưng không ghi thật
        """
        if self._mode == "dummy":
            logger.info("[dummy] execute skipped: %s", sql[:60])
            return True
        if self._mode in ("mysql", "drill"):
            # Drill là read-only middleware; DML luôn ghi thẳng MySQL
            engine = self._engine
            if engine is None:
                # drill mode mà chưa có engine phụ → tạo
                engine = self._create_mysql_engine()
            if engine is None:
                return False
            from sqlalchemy import text
            try:
                with engine.begin() as conn:
                    conn.execute(text(sql), params or {})
                return True
            except Exception as exc:
                logger.error("Execute error: %s", exc)
                return False
        return False

    # ── Helper: build WHERE clauses ─────────────────────────

    @staticmethod
    def _sym_ph(symbols: list[str]) -> tuple[str, dict]:
        if not symbols:
            return "", {}
        ph  = ",".join(f":s{i}" for i in range(len(symbols)))
        par = {f"s{i}": s for i, s in enumerate(symbols)}
        return f"AND Symbol IN ({ph})", par

    @staticmethod
    def _date_ph(
        params: dict,
        start:  Optional[date],
        end:    Optional[date],
        col:    str = "Trading_Date",
    ) -> tuple[str, dict]:
        clause = ""
        if start:
            clause += f" AND {col} >= :start"
            params["start"] = start
        if end:
            clause += f" AND {col} <= :end"
            params["end"] = end
        return clause, params

    # ── get_raw_data ─────────────────────────────────────────

    def get_raw_data(
        self,
        symbols:    Optional[list[str]] = None,
        start_date: Optional[date]      = None,
        end_date:   Optional[date]      = None,
    ) -> pd.DataFrame:
        """
        Đọc tbl_raw_stock.
        Tên cột trả về chuẩn hóa: symbol, date, open, high, low, close, volume, source.
        """
        if self._mode == "dummy":
            return self._gen_raw(symbols, start_date, end_date)

        w, p = self._sym_ph(symbols or [])
        d, p = self._date_ph(p, start_date, end_date, col="Trading_Date")

        # Tên cột theo bigdata_stock.sql (viết hoa chữ cái đầu)
        sql = f"""
            SELECT Symbol        AS symbol,
                   Trading_Date  AS date,
                   Open          AS open,
                   High          AS high,
                   Low           AS low,
                   Close         AS close,
                   Volume        AS volume,
                   Source        AS source
            FROM tbl_raw_stock
            WHERE 1=1 {w} {d}
            ORDER BY Symbol, Trading_Date ASC
        """

        if self._mode == "drill":
            # Drill: inject tên bảng đầy đủ nếu dùng storage plugin mysql
            db_name = os.getenv("DB_NAME", "bigdata_stock")
            sql = sql.replace(
                "FROM tbl_raw_stock",
                f"FROM mysql_db.`{db_name}`.tbl_raw_stock",
            )
            # Drill không hỗ trợ named params — thay thủ công
            sql = self._bind_params(sql, p)
            return self._drill_query(sql)

        return self._mysql_query(sql, p)

    # ── get_analysis_data ────────────────────────────────────

    def get_analysis_data(
        self,
        symbols:    Optional[list[str]] = None,
        start_date: Optional[date]      = None,
        end_date:   Optional[date]      = None,
    ) -> pd.DataFrame:
        """
        Đọc tbl_stock_daily_analysis — kết quả MapReduce theo ngày.
        Cột: symbol, date, total_volume, max_close_price, min_close_price,
             up_days_count, down_days_count, max_intraday_volatility,
             liquidity_status, max_intraday_drop, sma_price.
        """
        if self._mode == "dummy":
            return self._gen_analysis(symbols, start_date, end_date)

        w, p = self._sym_ph(symbols or [])
        d, p = self._date_ph(p, start_date, end_date, col="calc_date")

        sql = f"""
            SELECT symbol,
                   calc_date                AS date,
                   total_volume,
                   max_close_price,
                   min_close_price,
                   up_days_count,
                   down_days_count,
                   max_intraday_volatility  AS price_variance,
                   liquidity_status,
                   max_intraday_drop,
                   sma_price
            FROM tbl_stock_daily_analysis
            WHERE 1=1 {w} {d}
            ORDER BY symbol, calc_date ASC
        """

        if self._mode == "drill":
            db_name = os.getenv("DB_NAME", "bigdata_stock")
            sql = sql.replace(
                "FROM tbl_stock_daily_analysis",
                f"FROM mysql_db.`{db_name}`.tbl_stock_daily_analysis",
            )
            sql = self._bind_params(sql, p)
            return self._drill_query(sql)

        return self._mysql_query(sql, p)

    # ── get_monthly_analysis ─────────────────────────────────

    def get_monthly_analysis(
        self,
        symbols:    Optional[list[str]] = None,
        year:       Optional[int]       = None,
    ) -> pd.DataFrame:
        """
        Đọc tbl_stock_monthly_analysis — kết quả MapReduce theo tháng.
        Cột: symbol, calc_year, calc_month, monthly_avg_close, monthly_total_volume.
        """
        if self._mode == "dummy":
            return self._gen_monthly(symbols)

        w, p = self._sym_ph(symbols or [])
        year_clause = ""
        if year:
            year_clause = " AND calc_year = :year"
            p["year"] = year

        sql = f"""
            SELECT symbol, calc_year, calc_month,
                   monthly_avg_close, monthly_total_volume
            FROM tbl_stock_monthly_analysis
            WHERE 1=1 {w} {year_clause}
            ORDER BY symbol, calc_year, calc_month
        """

        if self._mode == "drill":
            db_name = os.getenv("DB_NAME", "bigdata_stock")
            sql = sql.replace(
                "FROM tbl_stock_monthly_analysis",
                f"FROM mysql_db.`{db_name}`.tbl_stock_monthly_analysis",
            )
            sql = self._bind_params(sql, p)
            return self._drill_query(sql)

        return self._mysql_query(sql, p)

    # ── get_summary ──────────────────────────────────────────

    def get_summary(self) -> pd.DataFrame:
        """Tóm tắt mỗi mã: giá gần nhất, % thay đổi, volume — từ tbl_stock_daily_analysis."""
        if self._mode == "dummy":
            return self._gen_summary()

        sql = """
            SELECT a.symbol,
                   a.max_close_price  AS price,
                   a.total_volume,
                   a.max_intraday_volatility AS price_variance,
                   a.calc_date
            FROM tbl_stock_daily_analysis a
            INNER JOIN (
                SELECT symbol, MAX(calc_date) AS latest
                FROM tbl_stock_daily_analysis
                GROUP BY symbol
            ) latest ON a.symbol = latest.symbol
                     AND a.calc_date = latest.latest
            ORDER BY a.symbol
        """

        if self._mode == "drill":
            db_name = os.getenv("DB_NAME", "bigdata_stock")
            sql = sql.replace(
                "FROM tbl_stock_daily_analysis",
                f"FROM mysql_db.`{db_name}`.tbl_stock_daily_analysis",
            ).replace(
                "tbl_stock_daily_analysis\n            ) latest",
                f"mysql_db.`{db_name}`.tbl_stock_daily_analysis\n            ) latest",
            )
            return self._drill_query(sql)

        return self._mysql_query(sql)

    # ── Alias methods (compat với dashboard.py / analytics.py) ─

    def get_stock_by_ticker(
        self, symbol: str, days: int = 365, use_analysis: bool = False,
    ) -> pd.DataFrame:
        end   = date.today()
        start = end - timedelta(days=days)
        if use_analysis:
            return self.get_analysis_data([symbol], start, end)
        return self.get_raw_data([symbol], start, end)

    def get_all_data(
        self,
        symbols:    Optional[list[str]] = None,
        start_date: Optional[date]      = None,
        end_date:   Optional[date]      = None,
    ) -> pd.DataFrame:
        df = self.get_raw_data(symbols, start_date, end_date)
        if "symbol" in df.columns:
            df = df.rename(columns={"symbol": "ticker"})
        return df

    def get_volatility_top(self, n: int = 10) -> pd.DataFrame:
        if self._mode == "dummy":
            raw = self._gen_raw()
            raw["pct"] = raw.groupby("symbol")["close"].pct_change().abs()
            return raw.nlargest(n, "pct")[["date","symbol","close","pct"]].reset_index(drop=True)

        sql = f"""
            SELECT calc_date AS date, symbol,
                   max_close_price AS close,
                   max_intraday_volatility / max_close_price AS pct
            FROM tbl_stock_daily_analysis
            ORDER BY max_intraday_volatility DESC
            LIMIT {int(n)}
        """
        if self._mode == "drill":
            db_name = os.getenv("DB_NAME", "bigdata_stock")
            sql = sql.replace(
                "FROM tbl_stock_daily_analysis",
                f"FROM mysql_db.`{db_name}`.tbl_stock_daily_analysis",
            )
            return self._drill_query(sql)
        return self._mysql_query(sql)

    # ── Drill param binder (named → literal) ─────────────────

    @staticmethod
    def _bind_params(sql: str, params: dict) -> str:
        """
        Drill REST không hỗ trợ named params.
        Thay :key bằng giá trị literal đã escape.
        CHỈ dùng cho string và date — không dùng cho dữ liệu user input.
        """
        for k, v in params.items():
            if isinstance(v, str):
                escaped = v.replace("'", "''")
                sql = sql.replace(f":{k}", f"'{escaped}'")
            elif isinstance(v, (date, datetime)):
                sql = sql.replace(f":{k}", f"'{v}'")
            else:
                sql = sql.replace(f":{k}", str(v))
        return sql

    # ── Dummy generators ─────────────────────────────────────

    def _gen_raw(
        self,
        symbols:    Optional[list[str]] = None,
        start_date: Optional[date]      = None,
        end_date:   Optional[date]      = None,
    ) -> pd.DataFrame:
        target = symbols or list(BANK_META.keys())
        end    = end_date   or date.today()
        start  = start_date or (end - timedelta(days=365 * 5))
        frames = []
        for sym in target:
            meta = BANK_META.get(sym, {"base": 20_000})
            np.random.seed(abs(hash(sym)) % 99_999)
            dates = pd.bdate_range(str(start), str(end))
            n     = len(dates)
            if n == 0:
                continue
            ret    = np.random.normal(0.00025, 0.015, n)
            prices = meta["base"] * np.exp(np.cumsum(ret))
            prices = np.maximum(prices, 1_000)
            vol    = np.random.randint(500_000, 6_000_000, n).astype(float)
            vol    = (vol * (1 + np.abs(ret) * 4)).astype(int)
            high   = prices * (1 + np.abs(np.random.normal(0, 0.007, n)))
            low    = prices * (1 - np.abs(np.random.normal(0, 0.007, n)))
            op     = np.roll(prices, 1); op[0] = prices[0]
            frames.append(pd.DataFrame({
                "symbol": sym, "date": dates,
                "open": op.round(0), "high": high.round(0),
                "low":  low.round(0), "close": prices.round(0),
                "volume": vol, "source": "dummy",
                "scrape_time": datetime.now(),
            }))
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def _gen_analysis(
        self,
        symbols:    Optional[list[str]] = None,
        start_date: Optional[date]      = None,
        end_date:   Optional[date]      = None,
    ) -> pd.DataFrame:
        raw = self._gen_raw(symbols, start_date, end_date)
        if raw.empty:
            return raw
        result = (
            raw.groupby(["symbol", "date"])
            .agg(
                total_volume         = ("volume", "sum"),
                max_close_price      = ("close",  "max"),
                min_close_price      = ("close",  "min"),
                max_intraday_volatility = ("high", "max"),
            )
            .reset_index()
        )
        low_df = raw.groupby(["symbol","date"])["low"].min().reset_index()
        result = result.merge(low_df, on=["symbol","date"], how="left")
        result["max_intraday_volatility"] = (
            result["max_intraday_volatility"] - result["low"]
        )
        result["price_variance"] = result["max_intraday_volatility"]
        result["sma_price"] = result["max_close_price"].rolling(20, min_periods=1).mean()
        result["up_days_count"]   = 0
        result["down_days_count"] = 0
        result["liquidity_status"] = result["total_volume"].apply(
            lambda v: "Cao" if v > 3_000_000 else ("Vừa" if v > 1_000_000 else "Thấp")
        )
        result["max_intraday_drop"] = result["max_intraday_volatility"] * 0.6
        return result.drop(columns=["low"]).rename(columns={"date": "calc_date"})

    def _gen_monthly(self, symbols: Optional[list[str]] = None) -> pd.DataFrame:
        raw = self._gen_raw(symbols)
        if raw.empty:
            return raw
        raw["calc_year"]  = pd.to_datetime(raw["date"]).dt.year
        raw["calc_month"] = pd.to_datetime(raw["date"]).dt.month
        return (
            raw.groupby(["symbol", "calc_year", "calc_month"])
            .agg(
                monthly_avg_close    = ("close",  "mean"),
                monthly_total_volume = ("volume", "sum"),
            )
            .reset_index()
        )

    def _gen_summary(self) -> pd.DataFrame:
        rows = []
        for sym, meta in BANK_META.items():
            np.random.seed(abs(hash(sym)) % 99_999)
            price   = meta["base"] * (1 + np.random.normal(0, 0.012))
            pct_chg = round(np.random.normal(0.4, 2.2), 2)
            rows.append({
                "symbol":          sym,
                "name":            meta["name"],
                "price":           round(price, 0),
                "pct_change":      pct_chg,
                "total_volume":    int(np.random.randint(800_000, 5_000_000)),
                "price_variance":  round(price * np.random.uniform(0.01, 0.04), 0),
                "sma20":           round(price * np.random.uniform(0.97, 1.03), 0),
                "sma50":           round(price * np.random.uniform(0.95, 1.05), 0),
                "max_close":       round(price * np.random.uniform(1.05, 1.22), 0),
                "min_close":       round(price * np.random.uniform(0.78, 0.95), 0),
            })
        return pd.DataFrame(rows)

    # ── Properties ───────────────────────────────────────────

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def bank_meta(self) -> dict:
        return BANK_META

    @property
    def available_symbols(self) -> list[str]:
        return list(BANK_META.keys())