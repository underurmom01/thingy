import streamlit as st
import pandas as pd
import numpy as np

from pathlib import Path
import json
import os
import re
import tempfile
import time
import shutil


st.set_page_config(page_title="Stock Signal Lab v12", page_icon="📈", layout="wide")



# =========================================================
# LOCAL / DISK CACHE
# =========================================================
#
# On a normal local computer this survives app restarts.
# On Streamlit Community Cloud the filesystem is temporary, so it normally
# survives reruns while the app instance is alive but can disappear after a
# reboot/redeploy. st.cache_data still gives an additional in-memory layer.
# =========================================================

PRICE_CACHE_TTL = 6 * 60 * 60
FUNDAMENTAL_CACHE_TTL = 12 * 60 * 60
EARNINGS_CACHE_TTL = 6 * 60 * 60
NEWS_CACHE_TTL = 60 * 60
FAST_SCREEN_CACHE_TTL = 30 * 60


def _make_cache_root():
    candidates = [
        Path.cwd() / ".stock_signal_cache_v10",
        Path(tempfile.gettempdir()) / "stock_signal_cache_v10",
    ]

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            test_file = candidate / ".write_test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)
            return candidate
        except Exception:
            continue

    return Path(tempfile.gettempdir())


LOCAL_CACHE_ROOT = _make_cache_root()

for _folder in ["prices", "json", "screens"]:
    try:
        (LOCAL_CACHE_ROOT / _folder).mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _safe_cache_name(value):
    return re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        str(value),
    )[:180]


def _is_fresh(path, ttl_seconds):
    try:
        if not path.exists():
            return False

        age = time.time() - path.stat().st_mtime
        return age <= ttl_seconds
    except Exception:
        return False


def _price_cache_path(ticker):
    return (
        LOCAL_CACHE_ROOT
        / "prices"
        / ("{}.pkl".format(_safe_cache_name(ticker)))
    )


def _read_price_cache(ticker, ttl_seconds=PRICE_CACHE_TTL):
    path = _price_cache_path(ticker)

    if not _is_fresh(path, ttl_seconds):
        return None

    try:
        data = pd.read_pickle(path)

        if (
            isinstance(data, pd.DataFrame)
            and not data.empty
            and "Close" in data.columns
        ):
            return data

    except Exception:
        pass

    return None


def _write_price_cache(ticker, data):
    if (
        data is None
        or not isinstance(data, pd.DataFrame)
        or data.empty
        or "Close" not in data.columns
    ):
        return

    path = _price_cache_path(ticker)
    temp_path = path.with_suffix(".tmp")

    try:
        data.to_pickle(temp_path)
        os.replace(temp_path, path)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


def _json_cache_path(kind, ticker):
    return (
        LOCAL_CACHE_ROOT
        / "json"
        / (
            "{}__{}.json".format(
                _safe_cache_name(kind),
                _safe_cache_name(ticker),
            )
        )
    )


def _read_json_cache(kind, ticker, ttl_seconds):
    path = _json_cache_path(kind, ticker)

    if not _is_fresh(path, ttl_seconds):
        return None

    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return None


def _write_json_cache(kind, ticker, value):
    path = _json_cache_path(kind, ticker)
    temp_path = path.with_suffix(".tmp")

    try:
        temp_path.write_text(
            json.dumps(value),
            encoding="utf-8",
        )
        os.replace(temp_path, path)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


def _screen_cache_path(sector_focus):
    return (
        LOCAL_CACHE_ROOT
        / "screens"
        / (
            "{}.pkl".format(
                _safe_cache_name(sector_focus)
            )
        )
    )


def _read_screen_cache(sector_focus):
    path = _screen_cache_path(sector_focus)

    if not _is_fresh(
        path,
        FAST_SCREEN_CACHE_TTL,
    ):
        return None

    try:
        data = pd.read_pickle(path)

        if isinstance(data, pd.DataFrame):
            return data

    except Exception:
        pass

    return None


def _write_screen_cache(sector_focus, data):
    if (
        data is None
        or not isinstance(data, pd.DataFrame)
        or data.empty
    ):
        return

    path = _screen_cache_path(sector_focus)
    temp_path = path.with_suffix(".tmp")

    try:
        data.to_pickle(temp_path)
        os.replace(temp_path, path)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


def clear_local_disk_cache():
    """
    Clear the on-disk cache as well as Streamlit's in-memory cache.
    Useful after code/schema changes or if Yahoo returned malformed data.
    """
    try:
        shutil.rmtree(
            LOCAL_CACHE_ROOT,
            ignore_errors=True,
        )
    except Exception:
        pass

    try:
        for folder in [
            "prices",
            "json",
            "screens",
        ]:
            (
                LOCAL_CACHE_ROOT
                / folder
            ).mkdir(
                parents=True,
                exist_ok=True,
            )
    except Exception:
        pass


@st.cache_resource(show_spinner=False)
def get_yfinance():
    """
    Import yfinance only after the user actually requests market data.
    This keeps the initial Streamlit page render lighter.
    """
    import yfinance as yf
    return yf


# =========================================================
# VISUAL DESIGN ONLY — backend/model logic below is unchanged
# =========================================================

st.markdown(
    """
    <style>
        :root {
            --ink: #111111;
            --muted: #6f6f6f;
            --surface: rgba(255,255,255,0.96);
            --line: rgba(0,0,0,0.14);
            --blue: #111111;
            --blue-hover: #2b2b2b;
            --shadow: 0 4px 14px rgba(0,0,0,0.05);
            --radius: 8px;
        }

        html, body, [class*="css"] {
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display",
                         "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
        }

        .stApp {
            background:
                
                
                #f3f3f3;
            color: var(--ink);
        }

        .block-container {
            max-width: 1240px;
            padding-top: 2.4rem;
            padding-bottom: 5rem;
        }

        .app-hero {
            padding: 2rem 2.1rem 1.9rem;
            margin: 0 0 1.6rem;
            border-radius: 8px;
            background: rgba(255,255,255,0.98);
            border: 1px solid rgba(0,0,0,0.14);
            box-shadow: 0 4px 16px rgba(0,0,0,0.05);
            backdrop-filter: blur(24px);
            -webkit-backdrop-filter: blur(24px);
        }

        .app-eyebrow {
            display: inline-flex;
            align-items: center;
            gap: .45rem;
            margin-bottom: .8rem;
            padding: .35rem .65rem;
            border-radius: 5px;
            background: #e9e9e9;
            color: #111111;
            font-size: .72rem;
            font-weight: 750;
            letter-spacing: .08em;
            text-transform: uppercase;
        }

        .app-hero h1 {
            margin: 0;
            color: var(--ink);
            font-size: clamp(2.1rem, 4.5vw, 3.8rem);
            line-height: .98;
            letter-spacing: -0.035em;
            font-weight: 760;
        }

        .app-hero h1 span {
            color: #707070;
            font-weight: 600;
        }

        .app-hero p {
            max-width: 760px;
            margin: 1rem 0 0;
            color: var(--muted);
            font-size: 1.06rem;
            line-height: 1.55;
        }

        .stock-hero {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 1.25rem;
            padding: 1.55rem 1.7rem;
            margin: 1.55rem 0 1rem;
            border-radius: 8px;
            background: rgba(255,255,255,0.9);
            border: 1px solid rgba(0,0,0,0.14);
            box-shadow: var(--shadow);
        }

        .stock-kicker {
            margin-bottom: .3rem;
            color: #707070;
            font-size: .72rem;
            font-weight: 750;
            letter-spacing: .08em;
            text-transform: uppercase;
        }

        .stock-name {
            margin: 0;
            color: var(--ink);
            font-size: 2rem;
            line-height: 1.08;
            letter-spacing: -0.04em;
            font-weight: 730;
        }

        .stock-company {
            margin-top: .34rem;
            color: var(--muted);
            font-size: .94rem;
        }

        .signal-pill {
            flex: 0 0 auto;
            padding: .55rem .9rem;
            border-radius: 5px;
            font-size: .8rem;
            font-weight: 760;
            letter-spacing: .035em;
            border: 1px solid transparent;
        }

        .signal-strong-buy,
        .signal-buy {
            color: #111111;
            background: #e7e7e7;
            border-color: #bdbdbd;
        }

        .signal-hold {
            color: #111111;
            background: #d9d9d9;
            border-color: #ababab;
        }

        .signal-sell,
        .signal-strong-sell {
            color: #ffffff;
            background: #2f2f2f;
            border-color: #2f2f2f;
        }

        h1, h2, h3, h4 {
            color: var(--ink) !important;
            letter-spacing: -0.035em;
        }

        h2 {
            margin-top: 2.15rem !important;
            margin-bottom: .85rem !important;
            font-size: 1.48rem !important;
            font-weight: 710 !important;
        }

        h3 {
            font-size: 1.12rem !important;
            font-weight: 680 !important;
        }

        p, label, .stCaption {
            color: var(--muted);
        }

        [data-testid="stMetric"] {
            min-height: 108px;
            padding: 1rem 1.05rem;
            border-radius: var(--radius);
            background: var(--surface);
            border: 1px solid rgba(0,0,0,0.14);
            box-shadow: 0 2px 8px rgba(0,0,0,0.035);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
        }

        [data-testid="stMetricLabel"] {
            color: #75757a !important;
            font-size: .79rem !important;
            font-weight: 620 !important;
        }

        [data-testid="stMetricValue"] {
            color: var(--ink) !important;
            font-size: 1.72rem !important;
            font-weight: 710 !important;
            letter-spacing: -0.04em;
        }

        [data-testid="stTextInput"] input {
            min-height: 48px;
            border-radius: 6px !important;
            border: 1px solid rgba(0,0,0,0.11) !important;
            background: rgba(255,255,255,0.93) !important;
            color: var(--ink) !important;
        }

        [data-testid="stTextInput"] input:focus {
            border-color: rgba(0,0,0,0.55) !important;
            box-shadow: 0 0 0 3px rgba(0,0,0,0.08) !important;
        }

        .stButton > button {
            min-height: 43px;
            border-radius: 6px !important;
            border: 1px solid rgba(0,0,0,0.08) !important;
            background: rgba(255,255,255,0.88) !important;
            color: #2c2c2e !important;
            font-weight: 640 !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.025);
            transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease;
        }

        .stButton > button:hover {
            transform: translateY(-1px);
            border-color: rgba(0,0,0,0.32) !important;
            box-shadow: 0 6px 18px rgba(0,0,0,0.06);
        }

        .stButton > button[kind="primary"] {
            background: var(--blue) !important;
            color: white !important;
            border-color: var(--blue) !important;
            box-shadow: 0 4px 10px rgba(0,0,0,0.10);
        }

        .stButton > button[kind="primary"]:hover {
            background: var(--blue-hover) !important;
            border-color: var(--blue-hover) !important;
        }

        [data-testid="stSidebar"] {
            background: #ededed;
            border-right: 1px solid rgba(0,0,0,0.065);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
        }

        [data-testid="stSidebar"] .stButton > button {
            justify-content: flex-start;
            padding-left: .95rem;
        }

        [data-testid="stAlert"] {
            border-radius: 6px !important;
            border: 1px solid rgba(0,0,0,0.07) !important;
            box-shadow: none !important;
        }

        [data-testid="stVegaLiteChart"],
        [data-testid="stArrowVegaLiteChart"] {
            padding: .85rem;
            border-radius: 8px;
            background: rgba(255,255,255,0.86);
            border: 1px solid rgba(0,0,0,0.14);
            box-shadow: 0 5px 22px rgba(0,0,0,0.035);
        }

        hr {
            margin: 2rem 0 !important;
            border: none !important;
            border-top: 1px solid rgba(0,0,0,0.075) !important;
        }

        a {
            color: #222222;
            text-decoration: none;
            font-weight: 600;
        }

        a:hover {
            text-decoration: underline;
        }

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}

        @media (max-width: 760px) {
            .block-container {
                padding-top: 1rem;
            }

            .app-hero {
                padding: 1.65rem 1.35rem;
                border-radius: 8px;
            }

            .stock-hero {
                align-items: flex-start;
                flex-direction: column;
            }
        }
    </style>

    <div class="app-hero">
        <div class="app-eyebrow">Signal research · v12</div>
        <h1>Stock Signal Lab <span>v12</span></h1>
        <p>
            Technicals, fundamentals, earnings context, market-reaction signals,
            and historical machine-learning forecasts — presented in one clean view.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


STRONG_BUY_THRESHOLD = 80
BUY_THRESHOLD = 65
HOLD_THRESHOLD = 45
SELL_THRESHOLD = 30

HORIZONS = {"1 Month": 21, "3 Months": 63, "6 Months": 126}
FEATURE_COLUMNS = [
    "return_1m", "return_3m", "return_6m", "rsi",
    "distance_ma20", "distance_ma50", "distance_ma200",
    "volatility_21d", "volume_change_21d",
]

FEATURED_STOCKS = [
    ("MU", "Micron"),
    ("AMD", "AMD"),
    ("NVDA", "NVIDIA"),
    ("META", "Meta"),
    ("AAPL", "Apple"),
    ("TSM", "TSMC"),
]

POSITIVE_WORDS = {
    "beat", "beats", "upgrade", "upgraded", "raises", "raised", "record",
    "strong", "growth", "profit", "bullish", "outperform", "approval",
    "partnership", "contract", "surge", "surges",
}
NEGATIVE_WORDS = {
    "miss", "misses", "cut", "cuts", "downgrade", "downgraded", "lawsuit",
    "probe", "investigation", "weak", "decline", "loss", "warning", "recall",
    "layoff", "layoffs", "bearish", "underperform", "restriction", "restrictions",
}


if "ticker_input" not in st.session_state:
    st.session_state["ticker_input"] = ""
if "auto_analyze" not in st.session_state:
    st.session_state["auto_analyze"] = False


def choose_ticker(symbol):
    st.session_state["ticker_input"] = symbol
    st.session_state["auto_analyze"] = True


def safe_float(value):
    try:
        if value is None:
            return None
        value = float(value)
        return value if np.isfinite(value) else None
    except Exception:
        return None


def normalize_fraction(value):
    value = safe_float(value)
    if value is None:
        return None
    if abs(value) > 2:
        return value / 100.0
    return value


def clamp(value, low=0.0, high=100.0):
    return float(np.clip(value, low, high))


def _clean_price_frame(data, ticker=None):
    """
    Normalize the several DataFrame shapes yfinance can return.

    yfinance may return:
      - normal columns: Close, Open, High, Low, Volume
      - MultiIndex: (Price, Ticker)
      - MultiIndex: (Ticker, Price)

    v10 assumed normal columns for single-ticker downloads, which caused
    valid symbols to appear "missing" when yfinance returned a MultiIndex.
    """
    if (
        data is None
        or not isinstance(
            data,
            pd.DataFrame,
        )
        or data.empty
    ):
        return None

    frame = data.copy()

    if isinstance(
        frame.columns,
        pd.MultiIndex,
    ):
        ticker_upper = (
            str(ticker).upper()
            if ticker
            else None
        )

        level0 = [
            str(x).upper()
            for x in frame.columns.get_level_values(0)
        ]
        level1 = [
            str(x).upper()
            for x in frame.columns.get_level_values(1)
        ]

        # Shape: (Ticker, Price)
        if (
            ticker_upper
            and ticker_upper in level0
        ):
            try:
                frame = frame.xs(
                    ticker,
                    axis=1,
                    level=0,
                    drop_level=True,
                )
            except Exception:
                # Case-insensitive fallback.
                matching = [
                    x
                    for x in frame.columns.get_level_values(0).unique()
                    if str(x).upper()
                    == ticker_upper
                ]
                if matching:
                    frame = frame.xs(
                        matching[0],
                        axis=1,
                        level=0,
                        drop_level=True,
                    )

        # Shape: (Price, Ticker)
        elif (
            ticker_upper
            and ticker_upper in level1
        ):
            try:
                frame = frame.xs(
                    ticker,
                    axis=1,
                    level=1,
                    drop_level=True,
                )
            except Exception:
                matching = [
                    x
                    for x in frame.columns.get_level_values(1).unique()
                    if str(x).upper()
                    == ticker_upper
                ]
                if matching:
                    frame = frame.xs(
                        matching[0],
                        axis=1,
                        level=1,
                        drop_level=True,
                    )

        # Single-symbol MultiIndex. Detect which level contains OHLCV names.
        else:
            price_names = {
                "OPEN",
                "HIGH",
                "LOW",
                "CLOSE",
                "ADJ CLOSE",
                "VOLUME",
            }

            unique0 = {
                str(x).upper()
                for x in frame.columns.get_level_values(0).unique()
            }
            unique1 = {
                str(x).upper()
                for x in frame.columns.get_level_values(1).unique()
            }

            if unique0.intersection(
                price_names
            ):
                try:
                    frame.columns = (
                        frame.columns
                        .get_level_values(0)
                    )
                except Exception:
                    return None

            elif unique1.intersection(
                price_names
            ):
                try:
                    frame.columns = (
                        frame.columns
                        .get_level_values(1)
                    )
                except Exception:
                    return None

            else:
                return None

    # Clean duplicate columns after flattening.
    if frame.columns.duplicated().any():
        frame = frame.loc[
            :,
            ~frame.columns.duplicated(),
        ]

    # Normalize column names while preserving expected capitalization.
    rename_map = {}

    for col in frame.columns:
        text = str(col).strip()
        upper = text.upper()

        canonical = {
            "OPEN": "Open",
            "HIGH": "High",
            "LOW": "Low",
            "CLOSE": "Close",
            "ADJ CLOSE": "Adj Close",
            "VOLUME": "Volume",
        }.get(upper)

        if canonical:
            rename_map[col] = canonical

    if rename_map:
        frame = frame.rename(
            columns=rename_map
        )

    if "Close" not in frame.columns:
        return None

    try:
        if (
            getattr(
                frame.index,
                "tz",
                None,
            )
            is not None
        ):
            frame.index = (
                frame.index
                .tz_localize(None)
            )
    except Exception:
        pass

    frame = (
        frame
        .sort_index()
    )

    frame = frame[
        ~frame.index.duplicated(
            keep="last"
        )
    ]

    frame = frame[
        frame["Close"].notna()
    ]

    if frame.empty:
        return None

    if "Volume" not in frame.columns:
        frame["Volume"] = np.nan

    return frame


def _fetch_single_history(ticker):
    yf = get_yfinance()

    symbol = normalize_yahoo_symbol(
        ticker
    )

    if symbol is None:
        return None

    # First use Ticker.history because it normally returns simple OHLCV
    # columns for a single symbol.
    for attempt in range(2):
        try:
            data = (
                yf.Ticker(symbol)
                .history(
                    period="10y",
                    interval="1d",
                    auto_adjust=True,
                )
            )

            data = _clean_price_frame(
                data,
                ticker=symbol,
            )

            if data is not None:
                _write_price_cache(
                    symbol,
                    data,
                )
                return data

        except Exception:
            pass

        if attempt == 0:
            time.sleep(0.25)

    # Fallback to yf.download. Some yfinance versions return a MultiIndex
    # even for one ticker; _clean_price_frame handles that shape now.
    for attempt in range(2):
        try:
            data = yf.download(
                tickers=symbol,
                period="10y",
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=False,
                group_by="column",
            )

            data = _clean_price_frame(
                data,
                ticker=symbol,
            )

            if data is not None:
                _write_price_cache(
                    symbol,
                    data,
                )
                return data

        except Exception:
            pass

        if attempt == 0:
            time.sleep(0.25)

    return None


def download_data(ticker, force_refresh=False):
    """
    Read normalized price history from disk first, then Yahoo if needed.
    """
    symbol = normalize_yahoo_symbol(
        ticker
    )

    if symbol is None:
        return None

    if not force_refresh:
        cached = _read_price_cache(
            symbol
        )

        if cached is not None:
            return _clean_price_frame(
                cached,
                ticker=symbol,
            )

    return _fetch_single_history(
        symbol
    )


def download_fundamentals(ticker):
    cached = _read_json_cache(
        "fundamentals",
        ticker,
        FUNDAMENTAL_CACHE_TTL,
    )

    if cached is not None:
        return cached

    yf = get_yfinance()
    result = {}

    for attempt in range(2):
        try:
            info = yf.Ticker(
                ticker
            ).get_info()

            if not isinstance(info, dict):
                info = {}

            result = {
                "company_name":
                    info.get("longName")
                    or info.get("shortName"),
                "sector":
                    info.get("sector"),
                "revenue_growth":
                    normalize_fraction(
                        info.get(
                            "revenueGrowth"
                        )
                    ),
                "earnings_growth":
                    normalize_fraction(
                        info.get(
                            "earningsGrowth"
                        )
                    ),
                "profit_margin":
                    normalize_fraction(
                        info.get(
                            "profitMargins"
                        )
                    ),
                "forward_pe":
                    safe_float(
                        info.get(
                            "forwardPE"
                        )
                    ),
                "debt_to_equity":
                    safe_float(
                        info.get(
                            "debtToEquity"
                        )
                    ),
                "free_cash_flow":
                    safe_float(
                        info.get(
                            "freeCashflow"
                        )
                    ),
            }

            break

        except Exception:
            if attempt == 0:
                time.sleep(0.25)

    _write_json_cache(
        "fundamentals",
        ticker,
        result,
    )

    return result


def download_latest_earnings(ticker):
    cached = _read_json_cache(
        "earnings",
        ticker,
        EARNINGS_CACHE_TTL,
    )

    if cached is not None:
        return cached

    yf = get_yfinance()
    result = None

    for attempt in range(2):
        try:
            earnings = (
                yf.Ticker(ticker)
                .get_earnings_dates(
                    limit=8
                )
            )

            if (
                earnings is None
                or earnings.empty
            ):
                break

            reported_col = None
            estimate_col = None
            surprise_col = None

            for col in earnings.columns:
                name = (
                    str(col)
                    .lower()
                    .replace(" ", "")
                )

                if "reportedeps" in name:
                    reported_col = col
                elif "epsestimate" in name:
                    estimate_col = col
                elif "surprise" in name:
                    surprise_col = col

            if reported_col is None:
                break

            past = earnings[
                earnings[
                    reported_col
                ].notna()
            ]

            if past.empty:
                break

            row = past.iloc[0]

            reported = safe_float(
                row.get(reported_col)
            )

            estimate = (
                safe_float(
                    row.get(
                        estimate_col
                    )
                )
                if estimate_col is not None
                else None
            )

            surprise = (
                normalize_fraction(
                    row.get(
                        surprise_col
                    )
                )
                if surprise_col is not None
                else None
            )

            if (
                surprise is None
                and reported is not None
                and estimate not in (
                    None,
                    0,
                )
            ):
                surprise = (
                    reported - estimate
                ) / abs(estimate)

            try:
                date_text = str(
                    past.index[0].date()
                )
            except Exception:
                date_text = str(
                    past.index[0]
                )

            result = {
                "date": date_text,
                "reported_eps": reported,
                "estimate_eps": estimate,
                "eps_surprise": surprise,
            }

            break

        except Exception:
            if attempt == 0:
                time.sleep(0.25)

    _write_json_cache(
        "earnings",
        ticker,
        result,
    )

    return result




def parse_news_item(item):
    if not isinstance(item, dict):
        return None

    if item.get("title"):
        return {
            "title": str(item.get("title", "")),
            "publisher": str(item.get("publisher", "")),
            "url": str(item.get("link", "")),
        }

    content = item.get("content")
    if isinstance(content, dict):
        provider = content.get("provider")
        publisher = provider.get("displayName", "") if isinstance(provider, dict) else ""
        canonical = content.get("canonicalUrl")
        url = canonical.get("url", "") if isinstance(canonical, dict) else ""
        if not url:
            click = content.get("clickThroughUrl")
            url = click.get("url", "") if isinstance(click, dict) else ""
        title = str(content.get("title", ""))
        if title:
            return {"title": title, "publisher": str(publisher), "url": str(url)}

    return None


def download_news(ticker):
    cached = _read_json_cache(
        "news",
        ticker,
        NEWS_CACHE_TTL,
    )

    if cached is not None:
        return cached

    yf = get_yfinance()
    out = []

    for attempt in range(2):
        try:
            raw = (
                yf.Ticker(ticker)
                .news
            )

            if not raw:
                break

            for item in raw[:12]:
                parsed = parse_news_item(
                    item
                )

                if parsed:
                    out.append(parsed)

            break

        except Exception:
            if attempt == 0:
                time.sleep(0.25)

    _write_json_cache(
        "news",
        ticker,
        out,
    )

    return out


def headline_sentiment(news_items):
    if not news_items:
        return None
    total = 0.0
    counted = 0
    for item in news_items:
        words = set(item["title"].lower().replace("/", " ").replace("-", " ").split())
        pos = len(words & POSITIVE_WORDS)
        neg = len(words & NEGATIVE_WORDS)
        diff = pos - neg
        if diff != 0:
            total += np.clip(diff, -2, 2)
            counted += 1
    if counted == 0:
        return 0.0
    return float(np.clip(total / (counted * 2.0), -1, 1))


def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100)
    rsi = rsi.mask((avg_gain == 0) & (avg_loss > 0), 0)
    rsi = rsi.mask((avg_gain == 0) & (avg_loss == 0), 50)
    return rsi


def pct_return(close, days):
    if len(close) <= days:
        return np.nan
    return float(close.iloc[-1] / close.iloc[-days - 1] - 1)


def max_drawdown(close):
    peak = close.cummax()
    return float((close / peak - 1).min())


def scaled_points(value, bad_value, good_value, points):
    if pd.isna(value):
        return 0.0
    if value <= bad_value:
        return 0.0
    if value >= good_value:
        return float(points)
    return float(((value - bad_value) / (good_value - bad_value)) * points)


def rsi_points(rsi):
    if pd.isna(rsi):
        return 0
    if 50 <= rsi <= 65:
        return 12
    if 45 <= rsi < 50:
        return 9
    if 65 < rsi <= 72:
        return 8
    if 40 <= rsi < 45:
        return 6
    if 30 <= rsi < 40:
        return 3
    if 72 < rsi <= 80:
        return 4
    return 0


def volatility_points(vol):
    if vol <= 0.18:
        return 8
    if vol <= 0.28:
        return 6
    if vol <= 0.40:
        return 3
    if vol <= 0.55:
        return 1
    return 0


def drawdown_points(dd):
    if dd >= -0.10:
        return 8
    if dd >= -0.20:
        return 6
    if dd >= -0.30:
        return 3
    if dd >= -0.45:
        return 1
    return 0


def technical_analysis_from_data(data):
    data = _clean_price_frame(
        data
    )

    if data is None:
        return None

    close = data["Close"].dropna()

    # v9 required 200 trading days and therefore rejected every newer
    # listing. 63 sessions is enough for a useful partial technical view.
    if len(close) < 63:
        return None

    price = safe_float(
        close.iloc[-1]
    )

    if price is None:
        return None

    ma20_series = (
        close.rolling(20).mean()
    )
    ma50_series = (
        close.rolling(50).mean()
    )
    ma200_series = (
        close.rolling(200).mean()
    )

    ma20 = (
        safe_float(
            ma20_series.iloc[-1]
        )
        if len(close) >= 20
        else None
    )

    ma50 = (
        safe_float(
            ma50_series.iloc[-1]
        )
        if len(close) >= 50
        else None
    )

    ma200 = (
        safe_float(
            ma200_series.iloc[-1]
        )
        if len(close) >= 200
        else None
    )

    r1 = (
        pct_return(close, 21)
        if len(close) > 21
        else None
    )

    r3 = (
        pct_return(close, 63)
        if len(close) > 63
        else None
    )

    r6 = (
        pct_return(close, 126)
        if len(close) > 126
        else None
    )

    rsi = safe_float(
        calculate_rsi(
            close
        ).iloc[-1]
    )

    daily = (
        close
        .pct_change()
        .dropna()
    )

    annualized_vol = (
        safe_float(
            daily.std()
            * np.sqrt(252)
        )
        if len(daily) >= 20
        else None
    )

    dd = (
        safe_float(
            max_drawdown(close)
        )
        if len(close) >= 20
        else None
    )

    score = 0.0
    possible = 0.0

    def add_points(
        value,
        bad,
        good,
        points,
    ):
        nonlocal score, possible

        if value is None:
            return

        score += scaled_points(
            value,
            bad,
            good,
            points,
        )
        possible += points

    add_points(
        r1,
        -0.10,
        0.10,
        8,
    )
    add_points(
        r3,
        -0.20,
        0.20,
        12,
    )
    add_points(
        r6,
        -0.30,
        0.30,
        16,
    )

    if ma20 is not None:
        possible += 6

        if price > ma20:
            score += 6

    if ma50 is not None:
        possible += 10

        if price > ma50:
            score += 10

    if ma200 is not None:
        possible += 10

        if price > ma200:
            score += 10

    if (
        ma50 is not None
        and ma200 is not None
    ):
        possible += 10

        if ma50 > ma200:
            score += 10

    if rsi is not None:
        score += rsi_points(rsi)
        possible += 12

    if annualized_vol is not None:
        score += volatility_points(
            annualized_vol
        )
        possible += 8

    if dd is not None:
        score += drawdown_points(dd)
        possible += 8

    if possible <= 0:
        return None

    normalized_score = clamp(
        score / possible * 100.0
    )

    chart = pd.DataFrame(
        {
            "Price": close,
            "MA 20": ma20_series,
            "MA 50": ma50_series,
            "MA 200": ma200_series,
        }
    )

    return {
        "data": data,
        "price": price,
        "technical_score":
            normalized_score,
        "return_1m": r1,
        "return_3m": r3,
        "return_6m": r6,
        "ma20": ma20,
        "ma50": ma50,
        "ma200": ma200,
        "rsi": (
            rsi
            if rsi is not None
            else 50.0
        ),
        "annualized_volatility": (
            annualized_vol
            if annualized_vol is not None
            else 0.50
        ),
        "max_drawdown": dd,
        "chart": chart,
    }


def technical_analysis(ticker):
    return technical_analysis_from_data(
        download_data(ticker)
    )


def weighted_available(parts):
    if not parts:
        return None
    total_weight = sum(weight for score, weight in parts)
    return clamp(sum(score * weight for score, weight in parts) / total_weight)


def fundamental_score(fund):
    if not fund:
        return None, []

    parts = []
    notes = []

    rev = fund.get("revenue_growth")
    if rev is not None:
        parts.append((clamp((rev + 0.10) / 0.35 * 100), 25))
        notes.append("Revenue growth: {:+.1%}".format(rev))

    earn = fund.get("earnings_growth")
    if earn is not None:
        parts.append((clamp((earn + 0.20) / 0.55 * 100), 25))
        notes.append("Earnings growth: {:+.1%}".format(earn))

    margin = fund.get("profit_margin")
    if margin is not None:
        parts.append((clamp((margin - 0.01) / 0.24 * 100), 20))
        notes.append("Profit margin: {:.1%}".format(margin))

    pe = fund.get("forward_pe")
    if pe is not None:
        if pe <= 0:
            pe_score = 0
        elif 8 <= pe <= 25:
            pe_score = 100
        elif pe <= 35:
            pe_score = 75
        elif pe <= 50:
            pe_score = 45
        elif pe < 8:
            pe_score = 65
        else:
            pe_score = 20
        parts.append((pe_score, 15))
        notes.append("Forward P/E: {:.1f}".format(pe))

    debt = fund.get("debt_to_equity")
    if debt is not None:
        ratio = debt / 100.0 if debt > 10 else debt
        if ratio <= 0.30:
            debt_score = 100
        elif ratio <= 0.70:
            debt_score = 75
        elif ratio <= 1.20:
            debt_score = 45
        else:
            debt_score = 20
        parts.append((debt_score, 10))
        notes.append("Debt/equity: {:.2f}".format(ratio))

    fcf = fund.get("free_cash_flow")
    if fcf is not None:
        parts.append((100 if fcf > 0 else 20, 5))
        notes.append("Free cash flow: {}".format("positive" if fcf > 0 else "negative"))

    return weighted_available(parts), notes


def event_score(earnings, news_items):
    parts = []
    notes = []

    if earnings is not None and earnings.get("eps_surprise") is not None:
        surprise = earnings["eps_surprise"]
        surprise_score = clamp(50 + (surprise / 0.10) * 50)
        parts.append((surprise_score, 60))
        notes.append("Latest EPS surprise: {:+.1%}".format(surprise))

    sentiment = headline_sentiment(news_items)
    if sentiment is not None:
        sentiment_score = clamp(50 + sentiment * 50)
        parts.append((sentiment_score, 40))
        label = "positive" if sentiment > 0.15 else "negative" if sentiment < -0.15 else "mixed / neutral"
        notes.append("Recent headline tone: {}".format(label))

    return weighted_available(parts), notes


def market_reaction(technical, fund_score, evt_score):
    data = technical["data"]
    close = data["Close"].dropna()
    volume = (
        data["Volume"].dropna()
        if "Volume" in data.columns
        else pd.Series(dtype=float)
    )
    if len(close) < 25:
        return None

    ret1 = float(close.iloc[-1] / close.iloc[-2] - 1)
    ret3 = float(close.iloc[-1] / close.iloc[-4] - 1)
    vol20 = float(close.pct_change().rolling(20).std().iloc[-1])
    z = ret1 / vol20 if np.isfinite(vol20) and vol20 > 0 else 0.0

    if len(volume) >= 20:
        avg_volume = volume.rolling(20).mean().iloc[-1]
        volume_ratio = (
            float(
                volume.iloc[-1]
                / avg_volume
            )
            if (
                np.isfinite(avg_volume)
                and avg_volume > 0
            )
            else 1.0
        )
    else:
        volume_ratio = 1.0

    evt = evt_score if evt_score is not None else 50
    fund = fund_score if fund_score is not None else 50
    rsi = technical["rsi"]

    direction = "NONE"
    strength = "LOW"
    opportunity_score = 50.0
    notes = ["No clear event/price divergence detected"]

    if z <= -2.0 and (evt >= 55 or fund >= 60):
        direction = "NEGATIVE"
        raw = abs(z) * 15 + max(evt - 50, 0) * 0.5 + max(fund - 50, 0) * 0.25
        if rsi < 35:
            raw += 15
        if volume_ratio >= 1.5:
            raw += 10
        strength = "HIGH" if raw >= 70 else "MEDIUM" if raw >= 45 else "LOW"
        opportunity_score = 90 if strength == "HIGH" else 72 if strength == "MEDIUM" else 60
        notes = ["Large downside move relative to normal volatility"]
        if rsi < 35:
            notes.append("RSI is oversold")
        if evt >= 55:
            notes.append("Recent earnings/news context is not strongly negative")
        if fund >= 60:
            notes.append("Fundamental score remains relatively strong")

    elif z >= 2.0 and (evt <= 45 or fund <= 50 or rsi > 75):
        direction = "POSITIVE"
        raw = abs(z) * 15
        if rsi > 75:
            raw += 20
        if volume_ratio >= 1.5:
            raw += 10
        strength = "HIGH" if raw >= 70 else "MEDIUM" if raw >= 45 else "LOW"
        opportunity_score = 15 if strength == "HIGH" else 30 if strength == "MEDIUM" else 40
        notes = ["Large upside move relative to normal volatility"]
        if rsi > 75:
            notes.append("RSI is very high / potentially overbought")
        if evt <= 45:
            notes.append("Recent event/news context does not strongly support the move")

    return {
        "one_day_return": ret1,
        "three_day_return": ret3,
        "reaction_z": z,
        "volume_ratio": volume_ratio,
        "direction": direction,
        "strength": strength,
        "opportunity_score": opportunity_score,
        "notes": notes,
    }


def hybrid_score(technical_score_value, fundamental_score_value, event_score_value, reaction_score_value):
    """
    Legacy/non-ML hybrid score. Kept for compatibility with existing code.
    The displayed signal now uses ml_adjusted_hybrid_score() whenever a
    3-month forecast is available.
    """
    parts = [(technical_score_value, 40)]
    if fundamental_score_value is not None:
        parts.append((fundamental_score_value, 25))
    if event_score_value is not None:
        parts.append((event_score_value, 20))
    if reaction_score_value is not None:
        parts.append((reaction_score_value, 15))
    return weighted_available(parts)


def ml_forecast_component(forecast):
    """
    Converts the 3-month Random Forest forecast into a 0-100 score and
    discounts it when historical validation is weak.

    A 0% forecast is neutral (50).
    Roughly -20% maps toward 0 and +20% maps toward 100 before the
    reliability discount.
    """
    if forecast is None:
        return None, 0.0

    predicted_return = safe_float(
        forecast.get("predicted_return")
    )
    direction_accuracy = safe_float(
        forecast.get("directional_accuracy")
    )
    baseline_accuracy = safe_float(
        forecast.get("baseline_accuracy")
    )
    mae = safe_float(
        forecast.get("mae")
    )

    if predicted_return is None:
        return None, 0.0

    raw_ml_score = clamp(
        50.0
        + (
            predicted_return / 0.20
        ) * 50.0
    )

    # Start with moderate trust. Beating the always-up baseline raises
    # trust; failing to beat it lowers trust, but does not zero it out.
    reliability = 0.50

    if (
        direction_accuracy is not None
        and baseline_accuracy is not None
    ):
        edge = (
            direction_accuracy
            - baseline_accuracy
        )

        reliability = float(
            np.clip(
                0.50 + edge * 2.5,
                0.15,
                0.90,
            )
        )

    # Large historical error further reduces trust.
    if mae is not None:
        mae_penalty = float(
            np.clip(
                mae / 0.30,
                0.0,
                1.0,
            )
        )

        reliability *= (
            1.0
            - 0.35 * mae_penalty
        )

    reliability = float(
        np.clip(
            reliability,
            0.10,
            0.90,
        )
    )

    # Pull unreliable forecasts toward neutral rather than allowing them
    # to dominate the score.
    adjusted_ml_score = (
        50.0
        + (
            raw_ml_score - 50.0
        ) * reliability
    )

    return clamp(adjusted_ml_score), reliability


def ml_adjusted_hybrid_score(
    technical_score_value,
    fundamental_score_value,
    event_score_value,
    reaction_score_value,
    forecast_3m,
):
    """
    Final score used for BUY/HOLD/SELL.

    Target weights when every component is available:
      Technical       30%
      Fundamentals    20%
      Earnings/News   15%
      Market Reaction 10%
      3M ML Forecast  25%

    Missing components are reweighted automatically.
    """
    ml_score, ml_reliability = ml_forecast_component(
        forecast_3m
    )

    parts = [
        (
            technical_score_value,
            30,
        )
    ]

    if fundamental_score_value is not None:
        parts.append(
            (
                fundamental_score_value,
                20,
            )
        )

    if event_score_value is not None:
        parts.append(
            (
                event_score_value,
                15,
            )
        )

    if reaction_score_value is not None:
        parts.append(
            (
                reaction_score_value,
                10,
            )
        )

    if ml_score is not None:
        parts.append(
            (
                ml_score,
                25,
            )
        )

    score = weighted_available(parts)
    guardrail_note = None

    # Guardrails stop the UI from showing a strong bullish label while a
    # reasonably trustworthy 3M model is forecasting a meaningful decline.
    if forecast_3m is not None:
        predicted_return = safe_float(
            forecast_3m.get(
                "predicted_return"
            )
        )

        if predicted_return is not None:
            if (
                predicted_return <= -0.08
                and ml_reliability >= 0.45
            ):
                score = min(
                    score,
                    HOLD_THRESHOLD
                    + (
                        BUY_THRESHOLD
                        - HOLD_THRESHOLD
                    )
                    - 0.1,
                )

                guardrail_note = (
                    "3M ML forecast is {:.1%} with enough historical reliability "
                    "to cap the final signal at HOLD."
                ).format(
                    predicted_return
                )

            elif (
                predicted_return <= -0.05
                and ml_reliability >= 0.35
            ):
                score = min(
                    score,
                    STRONG_BUY_THRESHOLD
                    - 0.1,
                )

                guardrail_note = (
                    "3M ML forecast is {:.1%}, so the final signal cannot be "
                    "STRONG BUY unless the forecast becomes less negative."
                ).format(
                    predicted_return
                )

    return (
        clamp(score),
        ml_score,
        ml_reliability,
        guardrail_note,
    )


def label_from_score(score):
    if score >= STRONG_BUY_THRESHOLD:
        return "STRONG BUY"
    if score >= BUY_THRESHOLD:
        return "BUY"
    if score >= HOLD_THRESHOLD:
        return "HOLD"
    if score >= SELL_THRESHOLD:
        return "SELL"
    return "STRONG SELL"


def build_feature_frame(data):
    close = data["Close"].astype(float)
    volume = data["Volume"].astype(float)
    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()

    features = pd.DataFrame(index=data.index)
    features["return_1m"] = close.pct_change(21)
    features["return_3m"] = close.pct_change(63)
    features["return_6m"] = close.pct_change(126)
    features["rsi"] = calculate_rsi(close)
    features["distance_ma20"] = close / ma20 - 1
    features["distance_ma50"] = close / ma50 - 1
    features["distance_ma200"] = close / ma200 - 1
    features["volatility_21d"] = close.pct_change().rolling(21).std() * np.sqrt(252)
    features["volume_change_21d"] = volume / volume.rolling(21).mean() - 1
    return features


def build_training_dataset(data, horizon_days):
    features = build_feature_frame(data)
    close = data["Close"].astype(float)
    features["target"] = close.shift(-horizon_days) / close - 1
    return features.dropna()


def train_forecast_model(dataset, fast_mode=False):
    if len(dataset) < 300:
        return None

    # scikit-learn is one of the heavier imports in the app.
    # Delay it until a forecast is actually requested.
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error

    X = dataset[FEATURE_COLUMNS]
    y = dataset["target"]
    split = int(len(dataset) * 0.80)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    if len(X_train) < 200 or len(X_test) < 30:
        return None

    model = RandomForestRegressor(
        n_estimators=(
            80
            if fast_mode
            else 150
        ),
        max_depth=(
            7
            if fast_mode
            else 8
        ),
        min_samples_leaf=5,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    pred = model.predict(X_test)

    mae = float(mean_absolute_error(y_test, pred))
    direction_acc = float(np.mean(np.sign(y_test.to_numpy()) == np.sign(pred)))
    baseline_acc = float(np.mean(y_test.to_numpy() > 0))

    model.fit(X, y)
    return model, mae, direction_acc, baseline_acc


def predict_horizon(data, horizon_days, fast_mode=False):
    dataset = build_training_dataset(data, horizon_days)
    trained = train_forecast_model(dataset, fast_mode=fast_mode)
    if trained is None:
        return None

    model, mae, direction_acc, baseline_acc = trained
    current = build_feature_frame(data)[FEATURE_COLUMNS].dropna()
    if current.empty:
        return None

    row = current.iloc[[-1]]
    predicted_return = float(model.predict(row)[0])
    current_price = float(data["Close"].dropna().iloc[-1])

    return {
        "predicted_return": predicted_return,
        "estimated_price": current_price * (1 + predicted_return),
        "mae": mae,
        "directional_accuracy": direction_acc,
        "baseline_accuracy": baseline_acc,
    }


@st.cache_data(ttl=1800, show_spinner=False)
def run_all_forecasts(ticker):
    data = download_data(ticker)
    if data is None:
        return {}
    return {label: predict_horizon(data, days) for label, days in HORIZONS.items()}



# =========================================================
# AI PORTFOLIO BUILDER
# Automatically discovers stocks from the broad U.S.-listed market.
# Stage 1: fast price-based screening.
# Stage 2: deep hybrid + ML analysis only on finalists.
# =========================================================

SECTOR_OPTIONS = [
    "All US-listed stocks (all sectors)",
    "Information Technology",
    "Health Care",
    "Financials",
    "Consumer Discretionary",
    "Communication Services",
    "Industrials",
    "Consumer Staples",
    "Energy",
    "Utilities",
    "Real Estate",
    "Materials",
    "Other / Miscellaneous",
]

SECTOR_TO_NASDAQ = {
    "Information Technology": "Technology",
    "Health Care": "Health Care",
    "Financials": "Finance",
    "Consumer Discretionary": "Consumer Discretionary",
    "Communication Services": "Telecommunications",
    "Industrials": "Industrials",
    "Consumer Staples": "Consumer Staples",
    "Energy": "Energy",
    "Utilities": "Utilities",
    "Real Estate": "Real Estate",
    "Materials": "Basic Materials",
    "Other / Miscellaneous": "Miscellaneous",
}


def normalize_yahoo_symbol(symbol):
    if symbol is None:
        return None

    symbol = str(symbol).strip().upper()

    if not symbol:
        return None

    symbol = (
        symbol
        .replace(".", "-")
        .replace("/", "-")
    )

    if any(
        bad in symbol
        for bad in [
            "$",
            "^",
            "=",
            "+",
            "*",
        ]
    ):
        return None

    if len(symbol) > 12:
        return None

    return symbol


def looks_like_common_stock_name(name):
    """
    Used only for the Nasdaq Trader fallback directories, which contain
    stocks plus some other listed securities.
    """
    text = str(name or "").upper()

    excluded_terms = [
        " WARRANT",
        " WARRANTS",
        " RIGHT",
        " RIGHTS",
        " UNIT",
        " UNITS",
        " PREFERRED",
        " PREFERENCE",
        " ETF",
        " ETN",
        " EXCHANGE TRADED FUND",
        " CLOSED END FUND",
        " CLOSED-END FUND",
        " BOND",
        " NOTES DUE",
        " SENIOR NOTE",
        " DEBENTURE",
    ]

    return not any(
        term in text
        for term in excluded_terms
    )


@st.cache_data(ttl=21600, show_spinner=False)
def get_us_stock_universe():
    """
    Broad U.S.-listed stock universe.

    Primary source:
      Nasdaq's public stock screener, including sector metadata.

    Fallback:
      Nasdaq Trader's Nasdaq-listed and other-exchange-listed
      symbol directories.

    This is called only after Build Portfolio is pressed.
    """
    import requests

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/146.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/market-activity/stocks/screener",
    }

    # 1) Preferred source: Nasdaq stock screener
    try:
        endpoint = "https://api.nasdaq.com/api/screener/stocks"

        rows_out = []
        seen = set()
        page_size = 5000

        for offset in range(0, 20000, page_size):
            params = {
                "tableonly": "true",
                "limit": str(page_size),
                "offset": str(offset),
                "download": "true",
            }

            response = requests.get(
                endpoint,
                headers=headers,
                params=params,
                timeout=25,
            )
            response.raise_for_status()

            payload = response.json()
            data = payload.get("data") if isinstance(payload, dict) else None

            if not data:
                break

            rows = data.get("rows", []) or []

            if not rows:
                break

            new_count = 0

            for row in rows:
                symbol = normalize_yahoo_symbol(
                    row.get("symbol")
                )

                if symbol is None or symbol in seen:
                    continue

                seen.add(symbol)
                new_count += 1

                rows_out.append(
                    {
                        "Symbol": symbol,
                        "Company": row.get("name") or symbol,
                        "Sector": row.get("sector") or "Unknown",
                        "Industry": row.get("industry") or "",
                        "Country": row.get("country") or "",
                        "Exchange": "",
                        "Universe Source": "Nasdaq Stock Screener",
                    }
                )

            # Prevent looping forever if the endpoint ignores offset.
            if new_count == 0:
                break

            if len(rows) < page_size:
                break

        df = pd.DataFrame(rows_out)

        # A true full-market result should be much larger than an index.
        if len(df) >= 1000:
            return (
                df
                .drop_duplicates(subset=["Symbol"])
                .sort_values("Symbol")
                .reset_index(drop=True)
            )

    except Exception:
        pass

    # 2) Fallback: official Nasdaq Trader symbol directories
    try:
        from io import StringIO

        nasdaq_url = (
            "https://www.nasdaqtrader.com/"
            "dynamic/SymDir/nasdaqlisted.txt"
        )
        other_url = (
            "https://www.nasdaqtrader.com/"
            "dynamic/SymDir/otherlisted.txt"
        )

        basic_headers = {
            "User-Agent": headers["User-Agent"]
        }

        nasdaq_response = requests.get(
            nasdaq_url,
            headers=basic_headers,
            timeout=20,
        )
        other_response = requests.get(
            other_url,
            headers=basic_headers,
            timeout=20,
        )

        nasdaq_response.raise_for_status()
        other_response.raise_for_status()

        nasdaq_df = pd.read_csv(
            StringIO(nasdaq_response.text),
            sep="|",
            dtype=str,
        )
        other_df = pd.read_csv(
            StringIO(other_response.text),
            sep="|",
            dtype=str,
        )

        rows_out = []

        for _, row in nasdaq_df.iterrows():
            raw_symbol = row.get("Symbol")

            if (
                raw_symbol is None
                or str(raw_symbol).startswith("File Creation Time")
            ):
                continue

            if str(row.get("Test Issue", "N")).upper() == "Y":
                continue

            if str(row.get("ETF", "N")).upper() == "Y":
                continue

            name = row.get("Security Name", raw_symbol)

            if not looks_like_common_stock_name(name):
                continue

            symbol = normalize_yahoo_symbol(raw_symbol)

            if symbol is None:
                continue

            rows_out.append(
                {
                    "Symbol": symbol,
                    "Company": name,
                    "Sector": "Unknown",
                    "Industry": "",
                    "Country": "",
                    "Exchange": "NASDAQ",
                    "Universe Source": "Nasdaq Trader Directory",
                }
            )

        exchange_names = {
            "A": "NYSE American",
            "N": "NYSE",
            "P": "NYSE Arca",
            "Z": "Cboe/BATS",
            "V": "IEX",
        }

        for _, row in other_df.iterrows():
            raw_symbol = (
                row.get("NASDAQ Symbol")
                or row.get("ACT Symbol")
            )

            if (
                raw_symbol is None
                or str(raw_symbol).startswith("File Creation Time")
            ):
                continue

            if str(row.get("Test Issue", "N")).upper() == "Y":
                continue

            if str(row.get("ETF", "N")).upper() == "Y":
                continue

            name = row.get("Security Name", raw_symbol)

            if not looks_like_common_stock_name(name):
                continue

            symbol = normalize_yahoo_symbol(raw_symbol)

            if symbol is None:
                continue

            exchange_code = str(
                row.get("Exchange", "")
            ).strip()

            rows_out.append(
                {
                    "Symbol": symbol,
                    "Company": name,
                    "Sector": "Unknown",
                    "Industry": "",
                    "Country": "",
                    "Exchange": exchange_names.get(
                        exchange_code,
                        exchange_code,
                    ),
                    "Universe Source": "Nasdaq Trader Directory",
                }
            )

        df = pd.DataFrame(rows_out)

        if not df.empty:
            return (
                df
                .drop_duplicates(subset=["Symbol"])
                .sort_values("Symbol")
                .reset_index(drop=True)
            )

    except Exception:
        pass

    return pd.DataFrame(
        columns=[
            "Symbol",
            "Company",
            "Sector",
            "Industry",
            "Country",
            "Exchange",
            "Universe Source",
        ]
    )


def universe_for_sector(sector_focus, universe=None):
    if universe is None:
        universe = get_us_stock_universe()

    if universe.empty:
        return universe

    if sector_focus == "All US-listed stocks (all sectors)":
        return universe.copy()

    wanted_sector = SECTOR_TO_NASDAQ.get(
        sector_focus,
        sector_focus,
    )

    known_sectors = (
        universe["Sector"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    # The official directory fallback has no sector field.
    if int((known_sectors != "unknown").sum()) == 0:
        return pd.DataFrame(columns=universe.columns)

    return (
        universe[
            known_sectors
            == str(wanted_sector).strip().lower()
        ]
        .copy()
        .reset_index(drop=True)
    )


def quick_screen_score(close):
    """
    First-pass score for the whole market.

    Stocks with less than 200 trading days are still scanned. The score
    automatically reweights around the history that is available.
    """
    close = close.dropna()

    if len(close) < 21:
        return None

    price = safe_float(close.iloc[-1])

    if price is None or price <= 0:
        return None

    score = 0.0
    possible = 0.0

    def add_scaled(value, low, high, points):
        nonlocal score, possible

        if value is None:
            return

        score += scaled_points(
            value,
            low,
            high,
            points,
        )
        possible += points

    r1 = pct_return(close, 21) if len(close) > 21 else None
    r3 = pct_return(close, 63) if len(close) > 63 else None
    r6 = pct_return(close, 126) if len(close) > 126 else None

    add_scaled(r1, -0.10, 0.10, 14)
    add_scaled(r3, -0.20, 0.20, 18)
    add_scaled(r6, -0.30, 0.30, 22)

    for window, points in [
        (20, 8),
        (50, 10),
        (200, 12),
    ]:
        if len(close) >= window:
            ma_value = safe_float(
                close.rolling(window).mean().iloc[-1]
            )

            if ma_value is not None:
                possible += points

                if price > ma_value:
                    score += points

    if len(close) >= 200:
        ma50 = safe_float(
            close.rolling(50).mean().iloc[-1]
        )
        ma200 = safe_float(
            close.rolling(200).mean().iloc[-1]
        )

        if ma50 is not None and ma200 is not None:
            possible += 8

            if ma50 > ma200:
                score += 8

    if len(close) >= 15:
        rsi_value = safe_float(
            calculate_rsi(close).iloc[-1]
        )

        if rsi_value is not None:
            possible += 5

            if 45 <= rsi_value <= 68:
                score += 5
            elif (
                35 <= rsi_value < 45
                or 68 < rsi_value <= 75
            ):
                score += 3

    daily = close.pct_change().dropna()

    if len(daily) >= 20:
        vol = safe_float(
            daily.tail(63).std() * np.sqrt(252)
        )

        if vol is not None:
            possible += 3

            if vol <= 0.25:
                score += 3
            elif vol <= 0.45:
                score += 1

    if possible <= 0:
        return None

    return clamp(
        score / possible * 100.0
    )


def _select_fast_finalists(
    screened,
    sector_focus,
    finalist_limit,
):
    if screened is None or screened.empty:
        return pd.DataFrame()

    if sector_focus != "All US-listed stocks (all sectors)":
        return (
            screened
            .head(finalist_limit)
            .reset_index(drop=True)
        )

    real_sectors = [
        sector
        for sector in (
            screened["Sector"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        if (
            sector.strip()
            and sector.strip().lower()
            != "unknown"
        )
    ]

    if not real_sectors:
        return (
            screened
            .head(finalist_limit)
            .reset_index(drop=True)
        )

    selected_indices = []

    per_sector = max(
        6,
        int(
            np.ceil(
                finalist_limit
                / max(
                    len(real_sectors) * 2,
                    1,
                )
            )
        ),
    )

    for sector in real_sectors:
        sector_rows = screened[
            screened["Sector"]
            .astype(str)
            == sector
        ].head(per_sector)

        selected_indices.extend(
            sector_rows.index.tolist()
        )

    selected_indices = list(
        dict.fromkeys(
            selected_indices
        )
    )

    diversified = screened.loc[
        selected_indices
    ].copy()

    if len(diversified) < finalist_limit:
        remaining = screened.drop(
            index=selected_indices,
            errors="ignore",
        )

        need = (
            finalist_limit
            - len(diversified)
        )

        diversified = pd.concat(
            [
                diversified,
                remaining.head(need),
            ],
            ignore_index=True,
        )

    return (
        diversified
        .sort_values(
            "Quick Score",
            ascending=False,
        )
        .head(finalist_limit)
        .reset_index(drop=True)
    )


def _extract_close_series(
    batch,
    ticker,
):
    frame = _clean_price_frame(
        batch,
        ticker=ticker,
    )

    if (
        frame is None
        or "Close"
        not in frame.columns
    ):
        return None

    close = frame["Close"]

    if isinstance(
        close,
        pd.DataFrame,
    ):
        if close.shape[1] < 1:
            return None
        close = close.iloc[:, 0]

    return close.dropna()


@st.cache_data(ttl=1800, show_spinner=False)
def fast_screen_sector(
    sector_focus,
    finalist_limit=150,
):
    """
    Stage 1 still scans the broad selected U.S. universe, but the complete
    quick-score table is now also saved locally. Rebuilding a portfolio
    shortly afterward can therefore skip the full-market price scan.
    """
    disk_cached = _read_screen_cache(
        sector_focus
    )

    if (
        disk_cached is not None
        and not disk_cached.empty
    ):
        return _select_fast_finalists(
            disk_cached,
            sector_focus,
            finalist_limit,
        )

    yf = get_yfinance()

    full_universe = (
        get_us_stock_universe()
    )

    universe = universe_for_sector(
        sector_focus,
        universe=full_universe,
    )

    if universe.empty:
        return pd.DataFrame()

    tickers = (
        universe["Symbol"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    sector_map = dict(
        zip(
            universe["Symbol"],
            universe["Sector"],
        )
    )
    name_map = dict(
        zip(
            universe["Symbol"],
            universe["Company"],
        )
    )
    exchange_map = dict(
        zip(
            universe["Symbol"],
            universe["Exchange"],
        )
    )

    rows = []

    # A moderately large batch reduces Python/network overhead without
    # trying to make one enormous Yahoo request.
    chunk_size = 220

    for start_index in range(
        0,
        len(tickers),
        chunk_size,
    ):
        chunk = tickers[
            start_index:
            start_index + chunk_size
        ]

        try:
            batch = yf.download(
                tickers=chunk,
                period="1y",
                interval="1d",
                auto_adjust=True,
                progress=False,
                group_by="ticker",
                threads=True,
            )
        except Exception:
            continue

        for ticker in chunk:
            try:
                close = _extract_close_series(
                    batch,
                    ticker,
                )

                if close is None:
                    continue

                quick = quick_screen_score(
                    close
                )

                if quick is None:
                    continue

                rows.append(
                    {
                        "Ticker": ticker,
                        "Company":
                            name_map.get(
                                ticker,
                                ticker,
                            ),
                        "Sector":
                            sector_map.get(
                                ticker,
                                "Unknown",
                            ),
                        "Exchange":
                            exchange_map.get(
                                ticker,
                                "",
                            ),
                        "Quick Score":
                            quick,
                    }
                )

            except Exception:
                continue

    if not rows:
        return pd.DataFrame()

    screened = (
        pd.DataFrame(rows)
        .sort_values(
            "Quick Score",
            ascending=False,
        )
        .reset_index(drop=True)
    )

    _write_screen_cache(
        sector_focus,
        screened,
    )

    return _select_fast_finalists(
        screened,
        sector_focus,
        finalist_limit,
    )


def _extract_batch_history(
    batch,
    ticker,
    chunk_length,
):
    if (
        batch is None
        or not isinstance(
            batch,
            pd.DataFrame,
        )
        or batch.empty
    ):
        return None

    # Delegate all MultiIndex handling to the same normalizer used for
    # single-ticker downloads.
    return _clean_price_frame(
        batch,
        ticker=ticker,
    )


def prefetch_price_histories(tickers):
    """
    Batch-download 10-year history for the finalist pool and place each
    ticker into the local cache.

    v9 made one 10-year Yahoo request per finalist. This is the main fix for
    the large lists of valid symbols that randomly failed deep analysis.
    """
    tickers = list(
        dict.fromkeys(
            [
                str(t).strip().upper()
                for t in tickers
                if str(t).strip()
            ]
        )
    )

    missing = []

    for ticker in tickers:
        if _read_price_cache(
            ticker
        ) is None:
            missing.append(ticker)

    if not missing:
        return {
            "requested": len(tickers),
            "cached": len(tickers),
            "downloaded": 0,
            "failed": [],
        }

    yf = get_yfinance()
    downloaded = 0
    unresolved = []

    chunk_size = 55

    for start_index in range(
        0,
        len(missing),
        chunk_size,
    ):
        chunk = missing[
            start_index:
            start_index + chunk_size
        ]

        try:
            batch = yf.download(
                tickers=chunk,
                period="10y",
                interval="1d",
                auto_adjust=True,
                progress=False,
                group_by="ticker",
                threads=True,
            )

        except Exception:
            batch = None

        for ticker in chunk:
            frame = (
                _extract_batch_history(
                    batch,
                    ticker,
                    len(chunk),
                )
                if batch is not None
                else None
            )

            if frame is not None:
                _write_price_cache(
                    ticker,
                    frame,
                )
                downloaded += 1
            else:
                unresolved.append(
                    ticker
                )

    # Retry only the handful that failed the batch request.
    final_failed = []

    for ticker in unresolved:
        frame = download_data(
            ticker,
            force_refresh=True,
        )

        if frame is None:
            final_failed.append(
                ticker
            )

    return {
        "requested": len(tickers),
        "cached":
            len(tickers)
            - len(missing),
        "downloaded": downloaded,
        "failed": final_failed,
    }




def portfolio_snapshot(
    ticker,
    company_fallback=None,
    sector_fallback=None,
    fast_ml=True,
):
    data = download_data(
        ticker
    )

    technical = (
        technical_analysis_from_data(
            data
        )
    )

    if technical is None:
        return None

    # Metadata is optional. Price history is the only hard requirement.
    fundamentals = (
        download_fundamentals(
            ticker
        )
    )
    earnings = (
        download_latest_earnings(
            ticker
        )
    )
    news_items = (
        download_news(
            ticker
        )
    )

    fund_score, _ = (
        fundamental_score(
            fundamentals
        )
    )

    evt_score, _ = (
        event_score(
            earnings,
            news_items,
        )
    )

    reaction = market_reaction(
        technical,
        fund_score,
        evt_score,
    )

    reaction_score = (
        reaction["opportunity_score"]
        if reaction is not None
        else None
    )

    # Portfolio mode uses fewer trees than the one-stock detailed page.
    # It keeps the same features and historical train/test logic.
    ml = predict_horizon(
        technical["data"],
        HORIZONS["3 Months"],
        fast_mode=fast_ml,
    )

    (
        overall,
        ml_score,
        ml_reliability,
        ml_guardrail_note,
    ) = ml_adjusted_hybrid_score(
        technical["technical_score"],
        fund_score,
        evt_score,
        reaction_score,
        ml,
    )

    label = label_from_score(
        overall
    )

    predicted_return = None
    directional_accuracy = None
    baseline_accuracy = None
    mae = None

    if ml is not None:
        predicted_return = (
            ml["predicted_return"]
        )
        directional_accuracy = (
            ml["directional_accuracy"]
        )
        baseline_accuracy = (
            ml["baseline_accuracy"]
        )
        mae = ml["mae"]

    close = (
        technical["data"]
        ["Close"]
        .dropna()
    )

    daily_returns = (
        close
        .pct_change()
        .dropna()
        .tail(252)
    )

    company_name = (
        (
            fundamentals.get(
                "company_name"
            )
            if fundamentals
            else None
        )
        or company_fallback
        or ticker
    )

    sector = (
        (
            fundamentals.get(
                "sector"
            )
            if fundamentals
            else None
        )
        or sector_fallback
        or "Unknown"
    )

    return {
        "ticker": ticker,
        "company_name":
            company_name,
        "sector": sector,
        "price":
            technical["price"],
        "overall_score":
            overall,
        "signal": label,
        "technical_score":
            technical[
                "technical_score"
            ],
        "fundamental_score":
            fund_score,
        "event_score":
            evt_score,
        "reaction_score":
            reaction_score,
        "ml_score":
            ml_score,
        "ml_reliability":
            ml_reliability,
        "ml_guardrail_note":
            ml_guardrail_note,
        "volatility":
            technical[
                "annualized_volatility"
            ],
        "predicted_return_3m":
            predicted_return,
        "directional_accuracy":
            directional_accuracy,
        "baseline_accuracy":
            baseline_accuracy,
        "mae": mae,
        "daily_returns":
            daily_returns,
        "analysis_depth":
            "Full",
    }


def technical_fallback_snapshot(
    ticker,
    company_name,
    sector,
    technical,
    quick_score=None,
):
    """
    Build a portfolio-compatible snapshot from price data only.

    This is a fallback, not a replacement for full analysis. It is used when
    metadata/news/earnings/ML are unavailable or when a very large requested
    portfolio would otherwise take too long to fully analyze.
    """
    if technical is None:
        return None

    technical_score_value = safe_float(
        technical.get(
            "technical_score"
        )
    )

    quick_score_value = safe_float(
        quick_score
    )

    if technical_score_value is None:
        return None

    if quick_score_value is None:
        quick_score_value = (
            technical_score_value
        )

    # Conservative score: price-based evidence only.
    overall = clamp(
        0.70
        * technical_score_value
        + 0.30
        * quick_score_value
    )

    close = (
        technical["data"]
        ["Close"]
        .dropna()
    )

    daily_returns = (
        close
        .pct_change()
        .dropna()
        .tail(252)
    )

    return {
        "ticker": ticker,
        "company_name":
            company_name
            or ticker,
        "sector":
            sector
            or "Unknown",
        "price":
            technical["price"],
        "overall_score":
            overall,
        "signal":
            label_from_score(
                overall
            ),
        "technical_score":
            technical_score_value,
        "fundamental_score":
            None,
        "event_score":
            None,
        "reaction_score":
            None,
        "ml_score":
            None,
        "ml_reliability":
            0.0,
        "ml_guardrail_note":
            None,
        "volatility":
            technical[
                "annualized_volatility"
            ],
        "predicted_return_3m":
            None,
        "directional_accuracy":
            None,
        "baseline_accuracy":
            None,
        "mae":
            None,
        "daily_returns":
            daily_returns,
        "analysis_depth":
            "Technical fallback",
    }



PORTFOLIO_PROFILES = {
    "Conservative": {
        "score_weight": 0.50,
        "forecast_weight": 0.15,
        "risk_weight": 0.35,
        "correlation_penalty": 0.25,
        "volatility_power": 1.25,
        "strength_power": 1.0,
        "max_weight": 0.30,
    },
    "Balanced": {
        "score_weight": 0.50,
        "forecast_weight": 0.25,
        "risk_weight": 0.25,
        "correlation_penalty": 0.16,
        "volatility_power": 0.80,
        "strength_power": 1.15,
        "max_weight": 0.35,
    },
    "Aggressive": {
        "score_weight": 0.43,
        "forecast_weight": 0.42,
        "risk_weight": 0.15,
        "correlation_penalty": 0.08,
        "volatility_power": 0.35,
        "strength_power": 1.35,
        "max_weight": 0.45,
    },
}


def portfolio_base_strength(snapshot, profile):
    score_factor = clamp(snapshot["overall_score"]) / 100.0

    predicted = snapshot["predicted_return_3m"]
    if predicted is None:
        forecast_factor = 0.50
    else:
        # A -25% to +25% 3M forecast maps to 0..1.
        forecast_factor = float(
            np.clip(
                (predicted + 0.25) / 0.50,
                0.0,
                1.0,
            )
        )

    # Reduce how much confidence we place in a forecast that has weak
    # historical validation. This does not fully discard it.
    if (
        snapshot["directional_accuracy"] is not None
        and snapshot["baseline_accuracy"] is not None
    ):
        edge = (
            snapshot["directional_accuracy"]
            - snapshot["baseline_accuracy"]
        )
        reliability = float(
            np.clip(
                0.55 + edge * 2.0,
                0.25,
                0.90,
            )
        )
    else:
        reliability = 0.35

    if snapshot["mae"] is not None:
        error_penalty = float(
            np.clip(
                snapshot["mae"] / 0.35,
                0.0,
                1.0,
            )
        )
        reliability *= 1.0 - 0.30 * error_penalty

    # Pull uncertain forecasts toward neutral instead of treating them
    # as equally reliable.
    forecast_factor = (
        reliability * forecast_factor
        + (1.0 - reliability) * 0.50
    )

    volatility = snapshot["volatility"]
    risk_factor = 1.0 - float(
        np.clip(
            (volatility - 0.15) / 0.55,
            0.0,
            1.0,
        )
    )

    strength = (
        profile["score_weight"] * score_factor
        + profile["forecast_weight"] * forecast_factor
        + profile["risk_weight"] * risk_factor
    )

    return float(strength)


def max_positive_correlation(snapshot, selected):
    if not selected:
        return 0.0

    candidate = snapshot["daily_returns"]
    correlations = []

    for chosen in selected:
        other = chosen["daily_returns"]
        aligned = pd.concat(
            [candidate, other],
            axis=1,
            join="inner",
        ).dropna()

        if len(aligned) < 40:
            continue

        corr = safe_float(
            aligned.iloc[:, 0].corr(
                aligned.iloc[:, 1]
            )
        )

        if corr is not None:
            correlations.append(
                max(corr, 0.0)
            )

    if not correlations:
        return 0.0

    return float(max(correlations))


def cap_and_normalize_weights(raw_weights, max_weight):
    raw = np.asarray(raw_weights, dtype=float)
    raw = np.maximum(raw, 0.000001)

    if raw.sum() <= 0:
        raw = np.ones_like(raw)

    weights = raw / raw.sum()

    n = len(weights)
    if n == 0:
        return weights

    # A cap below 1/n is mathematically impossible.
    max_weight = max(
        float(max_weight),
        1.0 / n,
    )

    for _ in range(25):
        over = weights > max_weight + 1e-10
        if not np.any(over):
            break

        excess = float(
            np.sum(
                weights[over] - max_weight
            )
        )

        weights[over] = max_weight
        under = ~over

        if not np.any(under):
            break

        under_total = float(
            weights[under].sum()
        )

        if under_total <= 0:
            weights[under] += (
                excess
                / int(np.sum(under))
            )
        else:
            weights[under] += (
                excess
                * weights[under]
                / under_total
            )

    return weights / weights.sum()


def build_ai_portfolio(
    snapshots,
    holdings_count,
    risk_profile,
    diversify_sectors=False,
):
    profile = PORTFOLIO_PROFILES[
        risk_profile
    ]

    usable = [
        item
        for item in snapshots
        if item is not None
    ]

    if not usable:
        return None

    holdings_count = min(
        holdings_count,
        len(usable),
    )

    for item in usable:
        item["base_strength"] = (
            portfolio_base_strength(
                item,
                profile,
            )
        )

    selected = []
    remaining = list(usable)

    # Greedy selection: strong candidates are preferred, but highly
    # correlated candidates receive a diversification penalty.
    #
    # In "All sectors" mode, we also discourage sector concentration.
    known_sectors = {
        (
            item.get("sector")
            or "Unknown"
        )
        for item in usable
        if (
            item.get("sector")
            or "Unknown"
        ) != "Unknown"
    }

    sector_count = max(
        len(known_sectors),
        1,
    )

    # Small portfolios stay tightly diversified. Larger portfolios can
    # naturally hold more names per sector instead of hitting an arbitrary
    # 2- or 3-stock ceiling.
    max_per_sector = max(
        2,
        int(
            np.ceil(
                holdings_count
                / float(sector_count)
            )
        )
        + 1,
    )

    while (
        len(selected) < holdings_count
        and remaining
    ):
        best = None
        best_adjusted = -999

        for candidate in remaining:
            candidate_sector = (
                candidate.get("sector")
                or "Unknown"
            )

            same_sector_count = sum(
                1
                for item in selected
                if (
                    item.get("sector")
                    or "Unknown"
                ) == candidate_sector
            )

            if (
                diversify_sectors
                and candidate_sector != "Unknown"
                and same_sector_count >= max_per_sector
            ):
                continue

            corr = max_positive_correlation(
                candidate,
                selected,
            )

            sector_penalty = 0.0

            if (
                diversify_sectors
                and candidate_sector != "Unknown"
            ):
                sector_penalty = (
                    0.055
                    * same_sector_count
                )

            adjusted = (
                candidate["base_strength"]
                - profile[
                    "correlation_penalty"
                ]
                * corr
                - sector_penalty
            )

            if adjusted > best_adjusted:
                best = candidate
                best_adjusted = adjusted

        # If the sector cap blocks every remaining candidate, relax it
        # rather than returning too few holdings.
        if best is None and remaining:
            best = max(
                remaining,
                key=lambda item: item[
                    "base_strength"
                ],
            )
            best_adjusted = best[
                "base_strength"
            ]

        if best is None:
            break

        chosen = dict(best)
        chosen[
            "selection_strength"
        ] = best_adjusted

        selected.append(chosen)

        remaining = [
            item
            for item in remaining
            if item["ticker"]
            != best["ticker"]
        ]

    if not selected:
        return None

    raw_weights = []

    for item in selected:
        volatility = max(
            item["volatility"],
            0.08,
        )

        raw = (
            max(
                item["base_strength"],
                0.05,
            )
            ** profile["strength_power"]
        ) / (
            volatility
            ** profile["volatility_power"]
        )

        raw_weights.append(raw)

    weights = cap_and_normalize_weights(
        raw_weights,
        profile["max_weight"],
    )

    for index, item in enumerate(selected):
        item["weight"] = float(
            weights[index]
        )

    # Portfolio-level risk estimate from recent daily covariance.
    returns_frame = pd.DataFrame(
        {
            item["ticker"]:
                item["daily_returns"]
            for item in selected
        }
    ).dropna()

    portfolio_volatility = None

    if len(returns_frame) >= 40:
        covariance = (
            returns_frame.cov()
            * 252
        )

        weight_vector = np.array(
            [
                item["weight"]
                for item in selected
            ]
        )

        try:
            variance = float(
                weight_vector.T
                @ covariance.to_numpy()
                @ weight_vector
            )
            portfolio_volatility = (
                np.sqrt(
                    max(
                        variance,
                        0.0,
                    )
                )
            )
        except Exception:
            portfolio_volatility = None

    forecast_items = [
        item
        for item in selected
        if item[
            "predicted_return_3m"
        ] is not None
    ]

    weighted_forecast = None

    if forecast_items:
        forecast_weight_total = sum(
            item["weight"]
            for item in forecast_items
        )

        if forecast_weight_total > 0:
            weighted_forecast = sum(
                item["weight"]
                * item[
                    "predicted_return_3m"
                ]
                for item in forecast_items
            ) / forecast_weight_total

    weighted_score = sum(
        item["weight"]
        * item["overall_score"]
        for item in selected
    )

    return {
        "holdings": selected,
        "weighted_score": weighted_score,
        "weighted_forecast_3m":
            weighted_forecast,
        "portfolio_volatility":
            portfolio_volatility,
    }



with st.sidebar:
    st.markdown("### Featured Picks")
    st.caption("Quick-launch a stock from your watchlist.")
    for symbol, company in FEATURED_STOCKS:
        st.button(
            "{} — {}".format(symbol, company),
            key="featured_" + symbol,
            on_click=choose_ticker,
            args=(symbol,),
            use_container_width=True,
        )
    st.divider()
    if st.button("🔄 Refresh cached data", use_container_width=True):
        st.cache_data.clear()
        clear_local_disk_cache()
        st.success("In-memory and local disk caches cleared.")
    st.caption("Featured picks are a static watchlist, not guaranteed winners.")


ticker = st.text_input(
    "Ticker",
    placeholder="AAPL",
    max_chars=12,
    key="ticker_input",
).strip().upper()

ticker = (
    normalize_yahoo_symbol(
        ticker
    )
    if ticker
    else ""
)

analyze_clicked = st.button("Analyze", type="primary", use_container_width=True)
should_analyze = analyze_clicked or st.session_state.get("auto_analyze", False)


if should_analyze:
    st.session_state["auto_analyze"] = False

    if not ticker:
        st.warning("Enter a ticker first.")
    else:
        with st.spinner("Pulling price, fundamentals, earnings, and news..."):
            technical = technical_analysis(ticker)
            fundamentals = download_fundamentals(ticker)
            earnings = download_latest_earnings(ticker)
            news_items = download_news(ticker)

        if technical is None:
            st.error("Could not load usable price history for that ticker. Try Refresh cached data once; if it still fails, Yahoo may not currently expose that symbol.")
        else:
            fund_score, fund_notes = fundamental_score(fundamentals)
            evt_score, evt_notes = event_score(earnings, news_items)
            reaction = market_reaction(technical, fund_score, evt_score)
            reaction_score = reaction["opportunity_score"] if reaction is not None else None

            with st.spinner(
                "Training historical ML forecasts..."
            ):
                forecasts = run_all_forecasts(
                    ticker
                )

            forecast_3m = forecasts.get(
                "3 Months"
            )

            (
                overall,
                ml_score,
                ml_reliability,
                ml_guardrail_note,
            ) = ml_adjusted_hybrid_score(
                technical["technical_score"],
                fund_score,
                evt_score,
                reaction_score,
                forecast_3m,
            )

            label = label_from_score(
                overall
            )

            company_name = fundamentals.get("company_name") if fundamentals else None

            signal_class = "signal-" + label.lower().replace(" ", "-")
            display_company = company_name if company_name else "Market analysis"
            st.markdown(
                """
                <div class="stock-hero">
                    <div>
                        <div class="stock-kicker">Current analysis</div>
                        <div class="stock-name">{ticker}</div>
                        <div class="stock-company">{company}</div>
                    </div>
                    <div class="signal-pill {signal_class}">{label}</div>
                </div>
                """.format(
                    ticker=ticker,
                    company=display_company,
                    signal_class=signal_class,
                    label=label,
                ),
                unsafe_allow_html=True,
            )

            c1, c2, c3 = st.columns(3)
            c1.metric("Hybrid Signal", label)
            c2.metric("Overall Score", "{:.1f}/100".format(overall))
            c3.metric("Current Price", "${:.2f}".format(technical["price"]))
            st.caption("Final signal blends technicals, fundamentals, earnings/news, market reaction, and the reliability-adjusted 3M ML forecast.")

            st.divider()
            st.subheader("Score Breakdown")
            b1, b2, b3, b4, b5 = st.columns(5)
            b1.metric("Technical", "{:.0f}/100".format(technical["technical_score"]))
            b2.metric("Fundamentals", "{:.0f}/100".format(fund_score) if fund_score is not None else "N/A")
            b3.metric("Earnings / News", "{:.0f}/100".format(evt_score) if evt_score is not None else "N/A")
            b4.metric("Reaction", "{:.0f}/100".format(reaction_score) if reaction_score is not None else "N/A")
            b5.metric(
                "3M ML",
                "{:.0f}/100".format(ml_score)
                if ml_score is not None
                else "N/A",
            )

            if forecast_3m is not None:
                st.caption(
                    "3M ML forecast: {:+.1%} · ML reliability weight: {:.0%}".format(
                        forecast_3m["predicted_return"],
                        ml_reliability,
                    )
                )

            if ml_guardrail_note:
                st.warning(
                    ml_guardrail_note
                )

            st.subheader("Technical Picture")
            t1, t2, t3 = st.columns(3)
            t1.metric("1 Month", "{:+.1%}".format(technical["return_1m"]))
            t2.metric("3 Months", "{:+.1%}".format(technical["return_3m"]))
            t3.metric("6 Months", "{:+.1%}".format(technical["return_6m"]))
            t4, t5, t6 = st.columns(3)
            t4.metric("RSI", "{:.1f}".format(technical["rsi"]))
            t5.metric("Annualized Volatility", "{:.1%}".format(technical["annualized_volatility"]))
            t6.metric("Max Drawdown", "{:.1%}".format(technical["max_drawdown"]))
            st.line_chart(technical["chart"].tail(504), use_container_width=True)

            st.subheader("Fundamentals")
            if not fundamentals:
                st.warning("Fundamental data was unavailable.")
            else:
                f1, f2, f3, f4 = st.columns(4)
                rev = fundamentals.get("revenue_growth")
                eg = fundamentals.get("earnings_growth")
                pm = fundamentals.get("profit_margin")
                pe = fundamentals.get("forward_pe")
                f1.metric("Revenue Growth", "{:+.1%}".format(rev) if rev is not None else "N/A")
                f2.metric("Earnings Growth", "{:+.1%}".format(eg) if eg is not None else "N/A")
                f3.metric("Profit Margin", "{:.1%}".format(pm) if pm is not None else "N/A")
                f4.metric("Forward P/E", "{:.1f}".format(pe) if pe is not None else "N/A")
                for note in fund_notes:
                    st.write("• " + note)

            st.subheader("Earnings & News Context")
            if earnings is not None:
                e1, e2, e3 = st.columns(3)
                e1.metric("Latest Earnings", earnings.get("date", "N/A"))
                reported = earnings.get("reported_eps")
                surprise = earnings.get("eps_surprise")
                e2.metric("Reported EPS", "{:.2f}".format(reported) if reported is not None else "N/A")
                e3.metric("EPS Surprise", "{:+.1%}".format(surprise) if surprise is not None else "N/A")
            for note in evt_notes:
                st.write("• " + note)

            if news_items:
                st.markdown("#### Recent Headlines")
                for item in news_items[:6]:
                    suffix = " — " + item["publisher"] if item["publisher"] else ""
                    if item["url"]:
                        st.markdown("- [{}]({}){}".format(item["title"], item["url"], suffix))
                    else:
                        st.write("• " + item["title"] + suffix)
            else:
                st.caption("No recent headline data was returned.")

            st.subheader("Market Reaction / Overreaction Detector")
            if reaction is None:
                st.warning("Not enough data to evaluate the latest reaction.")
            else:
                r1, r2, r3, r4 = st.columns(4)
                r1.metric("1-Day Move", "{:+.1%}".format(reaction["one_day_return"]))
                r2.metric("3-Day Move", "{:+.1%}".format(reaction["three_day_return"]))
                r3.metric("Move vs Normal", "{:+.1f}×".format(reaction["reaction_z"]))
                r4.metric("Volume vs 20D Avg", "{:.1f}×".format(reaction["volume_ratio"]))

                if reaction["direction"] == "NEGATIVE":
                    st.warning("Possible NEGATIVE overreaction: {}".format(reaction["strength"]))
                elif reaction["direction"] == "POSITIVE":
                    st.warning("Possible POSITIVE overreaction: {}".format(reaction["strength"]))
                else:
                    st.info("No clear overreaction signal.")

                for note in reaction["notes"]:
                    st.write("• " + note)

            st.divider()
            st.subheader("Historical ML Forecasts")
            st.caption(
                "The ML model is trained on historical price/volume features. "
                "The 3-month forecast now contributes to the final signal, but current news/fundamentals still remain outside the historical ML training set."
            )

            for horizon_label in HORIZONS:
                forecast = forecasts.get(horizon_label)
                st.markdown("### " + horizon_label)
                if forecast is None:
                    st.warning("Not enough valid historical data for this forecast.")
                    continue

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Predicted Return", "{:+.1%}".format(forecast["predicted_return"]))
                m2.metric("Estimated Model Price", "${:.2f}".format(forecast["estimated_price"]))
                m3.metric("Historical Direction Accuracy", "{:.1%}".format(forecast["directional_accuracy"]))
                m4.metric("Historical MAE", "{:.1%}".format(forecast["mae"]))
                st.caption("Always-up baseline: {:.1%}".format(forecast["baseline_accuracy"]))
                if forecast["directional_accuracy"] <= forecast["baseline_accuracy"]:
                    st.caption("⚠️ This forecast did not beat the simple always-up baseline.")

            st.divider()
            st.info(
                "Research experiment only. The hybrid score combines technical, fundamental, "
                "earnings/news, and reaction heuristics. ML forecasts use historical price/volume patterns."
            )


# =========================================================
# PORTFOLIO BUILDER UI
# =========================================================

st.divider()
st.subheader("AI Portfolio Builder")
st.caption(
    "All-sector mode starts from the broad U.S.-listed stock market. "
    "v12 builds a complete price-based candidate pool first, then upgrades the strongest names with slower fundamentals/news/ML so temporary API failures cannot shrink the portfolio."
)

st.caption(
    "Local cache is enabled. On your own computer it persists across app restarts; "
    "on Streamlit Community Cloud it is temporary and can reset after the app sleeps, reboots, or redeploys."
)

with st.expander(
    "Build a portfolio",
    expanded=False,
):
    p1, p2, p3, p4 = st.columns(4)

    sector_focus = p1.selectbox(
        "Sector focus",
        SECTOR_OPTIONS,
        index=0,
        key="portfolio_sector_focus",
        help=(
            "Choose one sector, or scan the entire U.S.-listed stock universe across all sectors."
        ),
    )

    risk_profile = p2.selectbox(
        "Risk profile",
        [
            "Conservative",
            "Balanced",
            "Aggressive",
        ],
        index=1,
        key="portfolio_risk_profile",
    )

    # IMPORTANT: do not fetch the market universe during page render.
    # The input can accept up to 500; the real limit is checked only after
    # the user presses the build button.
    holdings_count = p3.number_input(
        "Holdings",
        min_value=1,
        max_value=500,
        value=5,
        step=1,
        key="portfolio_holdings_count",
        help=(
            "Choose how many stocks you want. The app checks the actual "
            "available sector universe only after you press Build Portfolio."
        ),
    )

    holdings_count = int(
        holdings_count
    )

    budget = p4.number_input(
        "Budget",
        min_value=0.0,
        value=10000.0,
        step=1000.0,
        help=(
            "Use 0 if you only want percentages. "
            "This version searches U.S.-listed stocks, so allocations are in USD."
        ),
        key="portfolio_budget",
    )

    if holdings_count > 25:
        st.caption(
            "Large portfolios are supported, but deep-analysis time rises with "
            "the number of holdings because each finalist gets fundamentals, "
            "news, overreaction analysis, and a Random Forest forecast."
        )

    build_portfolio_clicked = st.button(
        "Find Stocks & Build Portfolio",
        type="primary",
        use_container_width=True,
        key="build_ai_portfolio_button",
    )

    if build_portfolio_clicked:
        # Nothing above this point requires network access.
        # Only now do we load the stock universe.
        with st.spinner(
            "Loading the full U.S.-listed stock universe..."
        ):
            full_us_universe = get_us_stock_universe()

            selected_universe = universe_for_sector(
                sector_focus,
                universe=full_us_universe,
            )

        selected_universe_size = len(
            selected_universe
        )

        if selected_universe_size == 0:
            st.error(
                "Could not load stocks for that sector. If the sector feed is temporarily unavailable, choose All US-listed stocks; the official symbol-directory fallback still supports the full-market scan."
            )
            st.stop()

        requested_holdings = holdings_count
        holdings_count = min(
            holdings_count,
            selected_universe_size,
        )

        if requested_holdings > selected_universe_size:
            st.warning(
                "You requested {} holdings, but this universe currently has {} "
                "available stocks. Building with {} instead.".format(
                    requested_holdings,
                    selected_universe_size,
                    holdings_count,
                )
            )

        source_name = (
            selected_universe["Universe Source"].iloc[0]
            if (
                not selected_universe.empty
                and "Universe Source" in selected_universe.columns
            )
            else "market source"
        )

        st.caption(
            "Loaded {:,} stock symbols in the selected universe · source: {}.".format(
                selected_universe_size,
                source_name,
            )
        )

        if sector_focus == "All US-listed stocks (all sectors)":
            st.info(
                "Stage 1 will attempt a price-based screen of every symbol in the U.S.-listed stock universe. "
                "Only the strongest candidates move to the much slower deep-analysis stage."
            )

        with st.spinner(
            "Stage 1/2 — scanning every stock in the selected U.S. universe..."
        ):
            # Stage 1 candidate pool can be very broad because this stage is
            # only price-based. It is deliberately much larger than the later
            # fundamentals/news/ML pool.
            finalist_limit = min(
                selected_universe_size,
                max(
                    150,
                    holdings_count,
                    min(
                        500,
                        holdings_count * 5,
                    ),
                ),
            )

            finalists = fast_screen_sector(
                sector_focus,
                finalist_limit=finalist_limit,
            )

        if finalists.empty:
            st.error(
                "The stock universe could not be screened right now. Try refreshing the app."
            )

        else:
            st.caption(
                "Full-market screen selected {} deep-analysis finalists from {}.".format(
                    len(finalists),
                    sector_focus,
                )
            )

            with st.expander(
                "See first-pass finalists",
                expanded=False,
            ):
                st.dataframe(
                    finalists,
                    use_container_width=True,
                    hide_index=True,
                )

            # -------------------------------------------------
            # Stage 2A: one batched 10-year history prefetch
            # -------------------------------------------------
            candidate_tickers = (
                finalists[
                    "Ticker"
                ]
                .astype(str)
                .tolist()
            )

            with st.spinner(
                "Stage 2A/2 — batch-loading 10-year histories and using the local cache..."
            ):
                prefetch_stats = (
                    prefetch_price_histories(
                        candidate_tickers
                    )
                )

            st.caption(
                "10Y history · {} already cached · {} newly batch-loaded · {} unavailable.".format(
                    prefetch_stats[
                        "cached"
                    ],
                    prefetch_stats[
                        "downloaded"
                    ],
                    len(
                        prefetch_stats[
                            "failed"
                        ]
                    ),
                )
            )

            # -------------------------------------------------
            # Build a large pool of valid price-based candidates.
            # These are enough to construct a COMPLETE portfolio even
            # if some slower metadata/news/ML calls fail.
            # -------------------------------------------------
            technical_rows = []
            technical_map = {}
            technical_failures = []

            for _, row in finalists.iterrows():
                symbol = row[
                    "Ticker"
                ]

                data = download_data(
                    symbol
                )

                technical = (
                    technical_analysis_from_data(
                        data
                    )
                )

                if technical is None:
                    technical_failures.append(
                        symbol
                    )
                    continue

                technical_map[
                    symbol
                ] = technical

                shortlist_score = (
                    0.52
                    * float(
                        row[
                            "Quick Score"
                        ]
                    )
                    + 0.48
                    * float(
                        technical[
                            "technical_score"
                        ]
                    )
                )

                technical_rows.append(
                    {
                        "Ticker":
                            symbol,
                        "Company":
                            row.get(
                                "Company",
                                symbol,
                            ),
                        "Sector":
                            row.get(
                                "Sector",
                                "Unknown",
                            ),
                        "Exchange":
                            row.get(
                                "Exchange",
                                "",
                            ),
                        "Quick Score":
                            row[
                                "Quick Score"
                            ],
                        "Technical Score":
                            technical[
                                "technical_score"
                            ],
                        "Shortlist Score":
                            shortlist_score,
                    }
                )

            technical_table = (
                pd.DataFrame(
                    technical_rows
                )
                .sort_values(
                    "Shortlist Score",
                    ascending=False,
                )
                .reset_index(
                    drop=True
                )
                if technical_rows
                else pd.DataFrame()
            )

            if technical_table.empty:
                st.error(
                    "No candidates had enough usable price history for portfolio construction."
                )
                st.stop()

            if len(technical_table) < holdings_count:
                st.warning(
                    "You requested {} holdings, but only {} candidates currently have usable price history. "
                    "The portfolio will use all {} available candidates.".format(
                        holdings_count,
                        len(technical_table),
                        len(technical_table),
                    )
                )

            effective_holdings_count = min(
                holdings_count,
                len(
                    technical_table
                ),
            )

            # -------------------------------------------------
            # Create a technical fallback pool FIRST.
            # This is the key reliability change in v12.
            # -------------------------------------------------
            selection_pool_size = min(
                len(
                    technical_table
                ),
                max(
                    100,
                    effective_holdings_count
                    * 4,
                ),
            )

            selection_pool = (
                technical_table
                .head(
                    selection_pool_size
                )
                .reset_index(
                    drop=True
                )
            )

            snapshot_by_ticker = {}

            for _, row in selection_pool.iterrows():
                symbol = row[
                    "Ticker"
                ]

                fallback = technical_fallback_snapshot(
                    symbol,
                    row.get(
                        "Company",
                        symbol,
                    ),
                    row.get(
                        "Sector",
                        "Unknown",
                    ),
                    technical_map.get(
                        symbol
                    ),
                    quick_score=
                        row.get(
                            "Quick Score"
                        ),
                )

                if fallback is not None:
                    snapshot_by_ticker[
                        symbol
                    ] = fallback

            # -------------------------------------------------
            # Stage 2B: upgrade the strongest subset to FULL analysis.
            #
            # Small portfolios: enough fully analyzed names for choice.
            # Large portfolios: cap expensive work so the app can finish.
            # Any stock not upgraded remains a valid technical fallback.
            # -------------------------------------------------
            full_analysis_limit = min(
                len(
                    selection_pool
                ),
                max(
                    24,
                    min(
                        80,
                        effective_holdings_count
                        * 2,
                    ),
                ),
            )

            deep_finalists = (
                selection_pool
                .head(
                    full_analysis_limit
                )
                .reset_index(
                    drop=True
                )
            )

            st.caption(
                "{} valid price candidates → {} full fundamentals/news/ML upgrades → complete portfolio fallback pool of {}.".format(
                    len(
                        technical_table
                    ),
                    len(
                        deep_finalists
                    ),
                    len(
                        snapshot_by_ticker
                    ),
                )
            )

            with st.expander(
                "See full-analysis finalists",
                expanded=False,
            ):
                st.dataframe(
                    deep_finalists,
                    use_container_width=True,
                    hide_index=True,
                )

            failures = []

            progress = st.progress(0)
            status = st.empty()

            total = len(
                deep_finalists
            )

            for index, row in deep_finalists.iterrows():
                symbol = row[
                    "Ticker"
                ]

                status.caption(
                    "Stage 2B/2 — upgrading {} with fundamentals, news & ML ({}/{})...".format(
                        symbol,
                        index + 1,
                        total,
                    )
                )

                try:
                    snapshot = (
                        portfolio_snapshot(
                            symbol,
                            company_fallback=
                                row.get(
                                    "Company",
                                    symbol,
                                ),
                            sector_fallback=
                                row.get(
                                    "Sector",
                                    "Unknown",
                                ),
                            fast_ml=True,
                        )
                    )
                except Exception:
                    snapshot = None

                if snapshot is None:
                    failures.append(
                        symbol
                    )
                    # IMPORTANT: keep the already-created technical fallback.
                else:
                    snapshot_by_ticker[
                        symbol
                    ] = snapshot

                progress.progress(
                    (index + 1)
                    / max(
                        total,
                        1,
                    )
                )

            status.empty()
            progress.empty()

            # Preserve shortlist order while using upgraded snapshots where
            # available.
            snapshots = []

            for _, row in selection_pool.iterrows():
                symbol = row[
                    "Ticker"
                ]

                item = (
                    snapshot_by_ticker
                    .get(symbol)
                )

                if item is not None:
                    snapshots.append(
                        item
                    )

            diversify_sectors = (
                sector_focus
                == "All US-listed stocks (all sectors)"
            )

            # This should normally equal the user's requested number now.
            holdings_count = min(
                effective_holdings_count,
                len(
                    snapshots
                ),
            )

            result = build_ai_portfolio(
                snapshots,
                holdings_count,
                risk_profile,
                diversify_sectors=diversify_sectors,
            )

            if result is None:
                st.error(
                    "The portfolio builder could not get enough usable market data."
                )

            else:
                st.markdown(
                    "### Suggested {} Portfolio".format(
                        risk_profile
                    )
                )

                st.caption(
                    "Sector focus: {}".format(
                        sector_focus
                    )
                )

                built_count = len(
                    result[
                        "holdings"
                    ]
                )

                if built_count == requested_holdings:
                    st.success(
                        "Portfolio complete: {} of {} requested holdings.".format(
                            built_count,
                            requested_holdings,
                        )
                    )
                else:
                    st.warning(
                        "Portfolio contains {} of {} requested holdings because only {} usable candidates were available.".format(
                            built_count,
                            requested_holdings,
                            len(
                                snapshots
                            ),
                        )
                    )

                m1, m2, m3 = st.columns(3)

                m1.metric(
                    "Weighted Hybrid Score",
                    "{:.1f}/100".format(
                        result["weighted_score"]
                    ),
                )

                if result["weighted_forecast_3m"] is not None:
                    m2.metric(
                        "Weighted 3M ML Forecast",
                        "{:+.1%}".format(
                            result[
                                "weighted_forecast_3m"
                            ]
                        ),
                    )
                else:
                    m2.metric(
                        "Weighted 3M ML Forecast",
                        "N/A",
                    )

                if result["portfolio_volatility"] is not None:
                    m3.metric(
                        "Est. Annualized Volatility",
                        "{:.1%}".format(
                            result[
                                "portfolio_volatility"
                            ]
                        ),
                    )
                else:
                    m3.metric(
                        "Est. Annualized Volatility",
                        "N/A",
                    )

                rows = []

                for holding in result["holdings"]:
                    predicted = holding[
                        "predicted_return_3m"
                    ]

                    direction_accuracy = holding[
                        "directional_accuracy"
                    ]

                    baseline = holding[
                        "baseline_accuracy"
                    ]

                    allocation = (
                        holding["weight"]
                        * budget
                    )

                    approximate_shares = None

                    if (
                        budget > 0
                        and holding["price"] > 0
                    ):
                        approximate_shares = int(
                            np.floor(
                                allocation
                                / holding["price"]
                            )
                        )

                    rows.append(
                        {
                            "Ticker":
                                holding["ticker"],

                            "Company":
                                holding[
                                    "company_name"
                                ] or "",

                            "Sector":
                                holding.get(
                                    "sector"
                                ) or "",

                            "Weight":
                                "{:.1%}".format(
                                    holding["weight"]
                                ),

                            "Hybrid Score":
                                "{:.1f}".format(
                                    holding[
                                        "overall_score"
                                    ]
                                ),

                            "Signal":
                                holding["signal"],

                            "Analysis":
                                holding.get(
                                    "analysis_depth",
                                    "Full",
                                ),

                            "3M ML Score":
                                (
                                    "{:.0f}/100".format(
                                        holding["ml_score"]
                                    )
                                    if holding.get("ml_score") is not None
                                    else "N/A"
                                ),

                            "ML Reliability":
                                "{:.0%}".format(
                                    holding.get(
                                        "ml_reliability",
                                        0.0,
                                    )
                                ),

                            "3M ML Forecast":
                                (
                                    "{:+.1%}".format(
                                        predicted
                                    )
                                    if predicted is not None
                                    else "N/A"
                                ),

                            "Direction Accuracy":
                                (
                                    "{:.1%}".format(
                                        direction_accuracy
                                    )
                                    if direction_accuracy is not None
                                    else "N/A"
                                ),

                            "Always-Up Baseline":
                                (
                                    "{:.1%}".format(
                                        baseline
                                    )
                                    if baseline is not None
                                    else "N/A"
                                ),

                            "Volatility":
                                "{:.1%}".format(
                                    holding[
                                        "volatility"
                                    ]
                                ),

                            "Target Allocation":
                                (
                                    "${:,.0f}".format(
                                        allocation
                                    )
                                    if budget > 0
                                    else "—"
                                ),

                            "Approx. Shares":
                                (
                                    approximate_shares
                                    if approximate_shares is not None
                                    else "—"
                                ),
                        }
                    )

                portfolio_table = pd.DataFrame(rows)

                st.dataframe(
                    portfolio_table,
                    use_container_width=True,
                    hide_index=True,
                )

                st.markdown(
                    "#### How it chose the portfolio"
                )

                st.write(
                    "• First-pass screening scans every available stock in the selected U.S.-listed universe using momentum, trend, RSI, and volatility."
                )

                st.write(
                    "• The app batch-downloads and locally caches finalist price history, builds the full candidate pool first, then upgrades the strongest names with fundamentals/news/Random Forest analysis."
                )

                st.write(
                    "• If a Yahoo fundamentals/news/ML request fails, the stock no longer disappears. It stays available as a clearly labeled Technical fallback so the requested portfolio can still be completed."
                )

                st.write(
                    "• The 3-month ML forecast directly affects the final stock rating, but weaker historical validation reduces its influence."
                )

                st.write(
                    "• Correlated stocks are penalized so the portfolio is not just several versions of the same trade."
                )

                if diversify_sectors:
                    st.write(
                        "• All-sector mode also penalizes sector concentration and caps how many holdings can come from one sector."
                    )

                if technical_failures:
                    with st.expander(
                        "Stocks skipped for insufficient/unavailable price history ({})".format(
                            len(
                                technical_failures
                            )
                        ),
                        expanded=False,
                    ):
                        st.write(
                            ", ".join(
                                technical_failures
                            )
                        )

                if failures:
                    with st.expander(
                        "Full-analysis failures ({})".format(
                            len(failures)
                        ),
                        expanded=False,
                    ):
                        st.write(
                            ", ".join(
                                failures
                            )
                        )
                        st.caption(
                            "These names were NOT removed from the candidate pool. v12 keeps their technical fallback instead of shrinking the portfolio."
                        )

                st.info(
                    "This is a model-generated research portfolio, not a guarantee of returns. "
                    "The portfolio is selected from the current U.S.-listed stock universe. The broad first pass scans the market, while only the strongest finalists receive expensive fundamentals/news/ML analysis. Results can change as listings and market data change."
                )

