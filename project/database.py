"""
database.py — DatabaseManager
Kết nối: Apache Drill (production) hoặc MySQL trực tiếp (fallback)

Tên bảng & cột theo quy ước bigdata_stock_tutorial.txt:
  - tbl_raw_stock      : dữ liệu thô từ Quang Duy
  - tbl_stock_analysis : kết quả MapReduce từ Phúc An (Sqoop Export)

Luồng:  MySQL → Sqoop → HDFS → Hive → MapReduce → Sqoop Export → MySQL
        Streamlit → Apache Drill → MySQL/HDFS (đọc tbl_stock_analysis)
"""


from __future__ import annotations

import os
import logging
from typing import Optional
from datetime import date, timedelta, datetime

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── Chế độ kết nối ─────────────────────────────────────────
# "dummy"  → sinh data giả, dev offline (mặc định)
# "drill"  → Apache Drill qua REST/JDBC (thiếu cấp endpoint)
# "mysql"  → MySQL Local 127.0.0.1:3306/bigdata_stock
DB_MODE: str = os.getenv("DB_MODE", "drill")

# ── Danh sách 4 mã theo đề bài ─────────────────────────────
BANK_META: dict[str, dict] = {
    "ACB": {"name": "Asia Commercial Bank",  "base": 24_500},
    "STB": {"name": "Sacombank",             "base": 32_100},
    "OCB": {"name": "Orient Commercial Bank","base": 13_800},
    "LPB": {"name": "LienVietPostBank",      "base": 16_200},
    "VCB": {"name": "Vietcombank",           "base": 82_500},
    "BID": {"name": "BIDV",                  "base": 47_300},
    "CTG": {"name": "VietinBank",            "base": 38_900},
    "MBB": {"name": "MB Bank",               "base": 24_600},
    "TCB": {"name": "Techcombank",           "base": 35_200},
}


class DatabaseManager:
    """
    Quản lý kết nối và truy vấn dữ liệu.
    Swap backend: chỉ đổi DB_MODE trong .env, code GUI không đổi.
    """

    def __init__(self) -> None:
        self._mode   = DB_MODE
        self._engine = None
        if self._mode != "dummy":
            self._engine = self._create_engine()

    # ── Engine ───────────────────────────────────────────────

    def _create_engine(self):
        try:
            from sqlalchemy import create_engine

            if self._mode == "mysql":
                # MySQL local → bigdata_stock (theo quy ước tutorial)
                url = (
                    f"mysql+pymysql://{os.getenv('DB_USER','root')}:"
                    f"{os.getenv('DB_PASSWORD','password123')}@"
                    f"{os.getenv('DB_HOST','127.0.0.1')}:"
                    f"{os.getenv('DB_PORT','3306')}/"
                    f"{os.getenv('DB_NAME','bigdata_stock')}?charset=utf8mb4"
                )
                return create_engine(url, pool_pre_ping=True, pool_recycle=1800)

            elif self._mode == "drill":
                # Apache Drill REST → BiMi cấp DRILL_HOST & DRILL_PORT
                # Dùng sqlalchemy-drill hoặc REST API trực tiếp
                host = os.getenv("DRILL_HOST", "localhost")
                port = os.getenv("DRILL_PORT", "8047")
                url  = f"drill+sadrill://{host}:{port}/dfs"
                return create_engine(url)

        except Exception as exc:
            logger.error("Engine init failed: %s → fallback to dummy", exc)
            self._mode = "dummy"
            return None

    # ── Health check ─────────────────────────────────────────

    def connect(self) -> bool:
        """Kiểm tra kết nối. True = OK."""
        if self._mode == "dummy":
            return True
        try:
            from sqlalchemy import text
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            logger.warning("DB connect failed: %s", exc)
            return False

    # ── Main queries ─────────────────────────────────────────

    def get_raw_data(
        self,
        symbols:    Optional[list[str]] = None,
        start_date: Optional[date]      = None,
        end_date:   Optional[date]      = None,
    ) -> pd.DataFrame:
        """
        Đọc từ tbl_raw_stock — dữ liệu thô Quang Duy cào.
        Dùng để vẽ biểu đồ giá OHLCV.
        """
        if self._mode == "dummy":
            return self._gen_raw(symbols, start_date, end_date)

        w, p = self._symbol_where(symbols)
        d_clause, p = self._date_where(p, start_date, end_date,
                                        col="trading_date")
        sql = f"""
            SELECT symbol, trading_date AS date,
                   open_price  AS open,
                   high_price  AS high,
                   low_price   AS low,
                   close_price AS close,
                   volume
            FROM tbl_raw_stock
            WHERE 1=1 {w} {d_clause}
            ORDER BY symbol, trading_date ASC
        """
        return self._query(sql, p)

    def get_analysis_data(
        self,
        symbols:    Optional[list[str]] = None,
        start_date: Optional[date]      = None,
        end_date:   Optional[date]      = None,
    ) -> pd.DataFrame:
        """
        Đọc từ tbl_stock_analysis — kết quả MapReduce.
        Cột: symbol, calc_date, avg_close_price, total_volume, price_variance.
        """
        if self._mode == "dummy":
            return self._gen_analysis(symbols, start_date, end_date)

        w, p = self._symbol_where(symbols)
        d_clause, p = self._date_where(p, start_date, end_date,
                                        col="calc_date")
        sql = f"""
            SELECT symbol, calc_date AS date,
                   avg_close_price, total_volume, price_variance
            FROM tbl_stock_analysis
            WHERE 1=1 {w} {d_clause}
            ORDER BY symbol, calc_date ASC
        """
        return self._query(sql, p)

    def get_stock_by_ticker(
        self,
        symbol: str,
        days:   int = 365,
        use_analysis: bool = False,
    ) -> pd.DataFrame:
        """
        Lấy dữ liệu 1 mã trong N ngày gần nhất.
        use_analysis=True → dùng tbl_stock_analysis (MapReduce result).
        """
        end   = date.today()
        start = end - timedelta(days=days)
        if use_analysis:
            return self.get_analysis_data([symbol], start, end)
        return self.get_raw_data([symbol], start, end)

    def get_summary(self) -> pd.DataFrame:
        """
        Tóm tắt mỗi mã: giá gần nhất, % thay đổi, volume.
        Tính từ tbl_stock_analysis (avg_close_price, total_volume).
        """
        if self._mode == "dummy":
            return self._gen_summary()

        sql = """
            SELECT a.symbol,
                   a.avg_close_price AS price,
                   a.total_volume,
                   a.price_variance,
                   a.calc_date
            FROM tbl_stock_analysis a
            INNER JOIN (
                SELECT symbol, MAX(calc_date) AS latest
                FROM tbl_stock_analysis
                GROUP BY symbol
            ) latest ON a.symbol = latest.symbol
                     AND a.calc_date = latest.latest
            ORDER BY a.symbol
        """
        return self._query(sql)

    def get_volatility_top(self, n: int = 10) -> pd.DataFrame:
        """
        Top N ngày biến động cao nhất từ tbl_raw_stock.
        price_variance = high_price - low_price (Phúc An đã tính sẵn trong analysis).
        """
        if self._mode == "dummy":
            raw = self._gen_raw()
            raw["pct"] = raw.groupby("symbol")["close"].pct_change().abs()
            top = raw.nlargest(n, "pct")[["date","symbol","close","pct"]]
            return top.reset_index(drop=True)

        sql = f"""
            SELECT calc_date AS date, symbol,
                   avg_close_price AS close,
                   price_variance / avg_close_price AS pct
            FROM tbl_stock_analysis
            ORDER BY price_variance DESC
            LIMIT {int(n)}
        """
        return self._query(sql)

    def get_all_data(
        self,
        symbols: Optional[list[str]] = None,
        start_date: Optional[date]   = None,
        end_date:   Optional[date]   = None,
    ) -> pd.DataFrame:
        """Alias tổng hợp — dùng tbl_raw_stock, rename 'symbol' → 'ticker' cho GUI."""
        df = self.get_raw_data(symbols, start_date, end_date)
        if "symbol" in df.columns:
            df = df.rename(columns={"symbol": "ticker"})
        if "date" not in df.columns and "trading_date" in df.columns:
            df = df.rename(columns={"trading_date": "date"})
        return df

    # ── Helpers ──────────────────────────────────────────────

    def _query(self, sql: str, params: dict | None = None) -> pd.DataFrame:
        from sqlalchemy import text
        try:
            with self._engine.connect() as conn:
                return pd.read_sql(text(sql), conn, params=params or {})
        except Exception as exc:
            logger.error("Query error: %s", exc)
            return pd.DataFrame()

    @staticmethod
    def _symbol_where(symbols: Optional[list[str]]) -> tuple[str, dict]:
        if not symbols:
            return "", {}
        ph  = ",".join(f":s{i}" for i in range(len(symbols)))
        par = {f"s{i}": s for i, s in enumerate(symbols)}
        return f"AND symbol IN ({ph})", par

    @staticmethod
    def _date_where(
        params: dict,
        start:  Optional[date],
        end:    Optional[date],
        col:    str = "trading_date",
    ) -> tuple[str, dict]:
        clause = ""
        if start:
            clause += f" AND {col} >= :start"
            params["start"] = start
        if end:
            clause += f" AND {col} <= :end"
            params["end"] = end
        return clause, params

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

            vol   = np.random.randint(500_000, 6_000_000, n).astype(float)
            vol   = (vol * (1 + np.abs(ret) * 4)).astype(int)
            high  = prices * (1 + np.abs(np.random.normal(0, 0.007, n)))
            low   = prices * (1 - np.abs(np.random.normal(0, 0.007, n)))
            op    = np.roll(prices, 1); op[0] = prices[0]

            frames.append(pd.DataFrame({
                "symbol":       sym,
                "date":         dates,
                "open":         op.round(0),
                "high":         high.round(0),
                "low":          low.round(0),
                "close":        prices.round(0),
                "volume":       vol,
                "source":       "dummy",
                "scrape_time":  datetime.now(),
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
                avg_close_price = ("close",  "mean"),
                total_volume    = ("volume", "sum"),
                price_variance  = ("high",   "max"),
            )
            .reset_index()
        )
        # price_variance = high - low (quy ước tutorial)
        low_df = raw.groupby(["symbol","date"])["low"].min().reset_index()
        result = result.merge(low_df, on=["symbol","date"], how="left")
        result["price_variance"] = result["price_variance"] - result["low"]
        result = result.drop(columns=["low"]).rename(columns={"date": "calc_date"})
        return result

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
                "avg_close_price": round(price, 0),
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