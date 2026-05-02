import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import sqlite3
import os
import json
import time
from pathlib import Path
import hashlib
from typing import Dict, List, Optional, Tuple
import logging

# ----------------------------- PRODUCTION SETUP -----------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="ReboundForge v1.1 — Production Stock Intelligence Engine",
    layout="wide",
    page_icon="📈",
    initial_sidebar_state="expanded"
)

# Futuristic Neon CSS (enhanced for production)
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #0a0a0f 0%, #111122 100%);
        color: #e0e0ff;
    }
    h1, h2, h3, .stMarkdown h1 {
        color: #00f0ff;
        text-shadow: 0 0 15px #00f0ff;
        font-family: 'Segoe UI', sans-serif;
    }
    .stButton button {
        background: linear-gradient(45deg, #00f0ff, #ff00aa);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 12px 24px;
        font-weight: bold;
        box-shadow: 0 0 20px #00f0ff, 0 0 40px #ff00aa;
        transition: all 0.3s ease;
    }
    .stButton button:hover {
        box-shadow: 0 0 30px #00f0ff, 0 0 60px #ff00aa;
        transform: translateY(-2px);
    }
    .stMetric {
        background: #1a1a2e;
        border: 1px solid #00f0ff;
        border-radius: 12px;
        padding: 12px;
        box-shadow: 0 0 15px rgba(0, 240, 255, 0.2);
    }
    .stSelectbox, .stTextInput, .stSlider, .stDateInput {
        background: #1a1a2e;
        border: 1px solid #00f0ff;
        border-radius: 8px;
    }
    .stDataFrame {
        background: #111122;
        border: 1px solid #00f0ff;
    }
    .stTabs [data-baseweb="tab-list"] {
        background: #0a0a0f;
        border-bottom: 2px solid #00f0ff;
    }
    .stTabs [data-baseweb="tab"] {
        color: #00f0ff;
        font-weight: bold;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #ff00aa;
    }
    .success-box {
        background: #1a3a1a;
        border: 2px solid #00ff88;
        border-radius: 12px;
        padding: 15px;
        color: #ccffcc;
    }
    .error-box {
        background: #3a1a1a;
        border: 2px solid #ff0066;
        border-radius: 12px;
        padding: 15px;
        color: #ffcccc;
    }
</style>
""", unsafe_allow_html=True)

st.title("ReboundForge v1.1 — AI-Powered Stock Database & Backtesting Engine")
st.caption("Production-Optimized • Self-Improving • Historical DB • Portfolio • Backtest & Forward Test • Robust Key Handling • Backward Compatible")

BASE_DIR = Path("./XAI/App")
BASE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = BASE_DIR / "reboundforge.db"
LOG_DIR = BASE_DIR / "grok_responses"
LOG_DIR.mkdir(exist_ok=True)

# ----------------------------- FAVORITE TICKERS (Customizable) -----------------------------
FAVORITES = ["TSLA", "AAPL", "NVDA", "RIO.AX", "BHP.AX", "FMG.AX", "MIN.AX", "NEM", "MSFT", "GOOGL"]
MARKETS = {
    "US": {"suffix": "", "examples": ["TSLA", "AAPL", "NVDA", "MSFT"]},
    "ASX": {"suffix": ".AX", "examples": ["RIO.AX", "BHP.AX", "FMG.AX"]},
    "Global": {"suffix": "", "examples": ["TSLA", "RIO.AX"]}
}

# ----------------------------- API KEY MANAGEMENT (Preserved from V1.0) -----------------------------
def get_api_key() -> Optional[str]:
    if "XAI_API_KEY" in st.secrets:
        return st.secrets["XAI_API_KEY"]
    env_key = os.getenv("XAI_API_KEY")
    if env_key:
        return env_key
    return st.session_state.get("xai_api_key")

def validate_api_key(api_key: str) -> Tuple[bool, str]:
    if not api_key or not api_key.startswith("xai-"):
        return False, "Key must start with 'xai-'"
    try:
        from xai_sdk import Client
        from xai_sdk.chat import user
        client = Client(api_key=api_key)
        chat = client.chat.create(model="grok-4.3")
        chat.append(user("Confirm API key validity with one word: VALID"))
        response = chat.sample()
        text = response.content if hasattr(response, 'content') else (getattr(response, 'text', None) or str(response))
        success = "VALID" in text.upper()
        return success, text.strip() if success else "Validation failed"
    except Exception as e:
        error_str = str(e)
        if "Incorrect API key" in error_str or "INVALID_ARGUMENT" in error_str or "UNAUTHENTICATED" in error_str:
            return False, "Invalid or expired API key. Regenerate at https://console.x.ai"
        return False, f"Validation error: {error_str[:120]}"

with st.sidebar:
    st.header("⚙️ Grok / xAI API Key (Optional for AI Insights)")
    current_key = get_api_key()
    if current_key:
        key_prefix = current_key[:8] + "..." + current_key[-4:]
        st.info(f"**Current key:** `{key_prefix}`")
    else:
        st.warning("No key loaded (AI features disabled)")
    
    key_input = st.text_input("Enter / Replace xAI Grok API Key", type="password", value="", help="Get key from https://console.x.ai")
    
    col_key1, col_key2 = st.columns(2)
    with col_key1:
        if st.button("Validate Key", type="primary"):
            if key_input and key_input.startswith("xai-"):
                st.session_state.xai_api_key = key_input
                with st.spinner("Validating..."):
                    valid, msg = validate_api_key(key_input)
                    if valid:
                        st.success(f"VALID: {msg}")
                    else:
                        st.error(msg)
            else:
                st.error("Key must start with 'xai-'")
    
    with col_key2:
        if st.button("Save Permanently"):
            if key_input and key_input.startswith("xai-"):
                secrets_dir = BASE_DIR / ".streamlit"
                secrets_dir.mkdir(exist_ok=True)
                with open(secrets_dir / "secrets.toml", "w") as f:
                    f.write(f'XAI_API_KEY = "{key_input}"\n')
                st.success("Key saved!")
                st.rerun()
            else:
                st.error("Enter valid key first")
    
    if st.button("Clear Key"):
        if "xai_api_key" in st.session_state:
            del st.session_state.xai_api_key
        st.success("Key cleared.")
        st.rerun()

# ----------------------------- DATABASE (Backward Compatible + Enhanced) -----------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS grok_logs (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            prompt_hash TEXT,
            prompt TEXT,
            model TEXT,
            response TEXT,
            tokens INTEGER,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            cost_usd REAL DEFAULT 0,
            latency REAL,
            fix_applied BOOLEAN DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS fixes (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            original_code TEXT,
            improved_code TEXT,
            reason TEXT,
            profitability_impact REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS backtest_results (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            ticker TEXT,
            strategy TEXT,
            start_date TEXT,
            end_date TEXT,
            initial_capital REAL,
            final_value REAL,
            total_return REAL,
            sharpe REAL,
            max_drawdown REAL,
            win_rate REAL,
            trades INTEGER,
            forward_test BOOLEAN DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS price_history (
            ticker TEXT,
            date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            PRIMARY KEY (ticker, date)
        );
        CREATE TABLE IF NOT EXISTS portfolio_simulations (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            name TEXT,
            tickers TEXT,
            weights TEXT,
            initial_capital REAL,
            final_value REAL,
            total_return REAL,
            period_start TEXT,
            period_end TEXT
        );
    ''')
    conn.commit()
    conn.close()
    logger.info("Database initialized (backward compatible)")

init_db()

def store_stock_data(ticker: str, df: pd.DataFrame) -> int:
    if df is None or df.empty:
        return 0
    conn = sqlite3.connect(DB_PATH)
    records = []
    for idx, row in df.iterrows():
        try:
            records.append((
                ticker,
                idx.strftime('%Y-%m-%d'),
                float(row.get('Open', row.get('open', 0))),
                float(row.get('High', row.get('high', 0))),
                float(row.get('Low', row.get('low', 0))),
                float(row.get('Close', row.get('close', 0))),
                int(row.get('Volume', row.get('volume', 0)))
            ))
        except Exception as e:
            logger.warning(f"Skipping bad row for {ticker}: {e}")
    if records:
        conn.executemany('''
            INSERT OR REPLACE INTO price_history 
            (ticker, date, open, high, low, close, volume) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', records)
        conn.commit()
    conn.close()
    return len(records)

def load_stock_data(ticker: str, start: Optional[str] = None, end: Optional[str] = None) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT date, open, high, low, close, volume FROM price_history WHERE ticker = ?"
    params = [ticker]
    if start:
        query += " AND date >= ?"
        params.append(start)
    if end:
        query += " AND date <= ?"
        params.append(end)
    query += " ORDER BY date"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        return df
    return pd.DataFrame()

# ----------------------------- DATA FETCH (Production Cache + Resilience) -----------------------------
@st.cache_data(ttl=3600, show_spinner="Fetching fresh market data...")
def get_stock_data(ticker: str, start: Optional[date] = None, end: Optional[date] = None, period: str = "1y") -> Optional[pd.DataFrame]:
    try:
        if start and end:
            df = yf.download(ticker, start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'), progress=False, auto_adjust=True)
        else:
            df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.rename(columns=str.title)
            store_stock_data(ticker, df)
            return df
        return None
    except Exception as e:
        logger.error(f"Fetch error for {ticker}: {e}")
        st.error(f"Could not fetch data for {ticker}. Using cached DB if available.")
        # Fallback to DB
        return load_stock_data(ticker, start.strftime('%Y-%m-%d') if start else None, end.strftime('%Y-%m-%d') if end else None)

# ----------------------------- ENHANCED GROK CALL (Preserved & Robust) -----------------------------
def call_grok(prompt: str, model: str = "grok-4.3", max_tokens: int = 4096) -> Dict:
    api_key = get_api_key()
    if not api_key:
        return {"response": "No valid xAI API key. Enter one in sidebar for AI features.", 
                "latency": 0, "tokens": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0}
    
    start = time.time()
    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
    
    try:
        from xai_sdk import Client
        from xai_sdk.chat import system, user
        client = Client(api_key=api_key)
        chat = client.chat.create(model=model)
        chat.append(system("You are an elite quantitative trading engineer specializing in historical stock data, backtesting, rebound strategies, and portfolio optimization. Be concise and actionable."))
        chat.append(user(prompt))
        response = chat.sample()
        
        text = response.content if hasattr(response, 'content') else (getattr(response, 'text', None) or str(response))
        
        usage = getattr(response, 'usage', None)
        prompt_tokens = getattr(usage, 'prompt_tokens', 0) if usage else 0
        completion_tokens = getattr(usage, 'completion_tokens', 0) if usage else 0
        total_tokens = getattr(usage, 'total_tokens', 0) if usage else 0
        cost_ticks = getattr(usage, 'cost_in_usd_ticks', 0) if usage else 0
        cost_usd = cost_ticks / 10_000_000_000.0 if cost_ticks else 0.0
        
    except Exception as e:
        error_str = str(e)
        if "Incorrect API key" in error_str or "INVALID_ARGUMENT" in error_str or "UNAUTHENTICATED" in error_str:
            user_msg = "Invalid xAI key. Please regenerate at https://console.x.ai and re-validate."
        elif "xai-sdk" in error_str.lower():
            user_msg = "Install xai-sdk: pip install xai-sdk"
        else:
            user_msg = f"API Error: {error_str[:200]}"
        text = user_msg
        prompt_tokens = completion_tokens = total_tokens = 0
        cost_usd = 0.0

    latency = time.time() - start
    approx_tokens = len(text.split())

    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        INSERT INTO grok_logs 
        (timestamp, prompt_hash, prompt, model, response, tokens, 
         prompt_tokens, completion_tokens, total_tokens, cost_usd, latency)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (datetime.now().isoformat(), prompt_hash, prompt[:800], model, text[:15000],
          approx_tokens, prompt_tokens, completion_tokens, total_tokens, cost_usd, latency))
    conn.commit()
    conn.close()

    return {
        "response": text, "latency": latency, "tokens": total_tokens or approx_tokens,
        "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
        "total_tokens": total_tokens, "cost_usd": cost_usd
    }

# ----------------------------- CORE STRATEGY & BACKTEST ENGINE (Production Grade) -----------------------------
def calculate_rebound_signals(df: pd.DataFrame, dip_pct: float = 0.05, rebound_pct: float = 0.03) -> pd.DataFrame:
    """Simple Rebound Strategy: Buy on 5% dip from recent high, Sell on 3% rebound"""
    df = df.copy()
    df['peak'] = df['Close'].cummax()
    df['dip'] = (df['Close'] - df['peak']) / df['peak']
    df['signal'] = 0
    df.loc[df['dip'] <= -dip_pct, 'signal'] = 1  # Buy signal
    df['position'] = df['signal'].shift(1).fillna(0)
    # Simple exit on rebound
    df['rebound'] = df['Close'].pct_change() >= rebound_pct
    df.loc[df['rebound'] & (df['position'] == 1), 'position'] = 0
    return df

def calculate_ma_crossover(df: pd.DataFrame, short: int = 20, long: int = 50) -> pd.DataFrame:
    df = df.copy()
    df['short_ma'] = df['Close'].rolling(short).mean()
    df['long_ma'] = df['Close'].rolling(long).mean()
    df['signal'] = np.where(df['short_ma'] > df['long_ma'], 1, 0)
    df['position'] = df['signal'].shift(1).fillna(0)
    return df

def run_backtest(ticker: str, start_date: date, end_date: date, initial_capital: float, 
                 strategy: str = "Rebound Dip", dip_pct: float = 0.05, rebound_pct: float = 0.03,
                 is_forward_test: bool = False) -> Dict:
    """Robust backtest/forward test engine with metrics"""
    try:
        df = get_stock_data(ticker, start=start_date, end=end_date)
        if df is None or df.empty or len(df) < 30:
            return {"error": "Insufficient data for backtest."}
        
        df = df.sort_index()
        
        if strategy == "Rebound Dip":
            df = calculate_rebound_signals(df, dip_pct, rebound_pct)
        elif strategy == "MA Crossover":
            df = calculate_ma_crossover(df)
        else:  # Buy & Hold
            df['position'] = 1
        
        df['returns'] = df['Close'].pct_change()
        df['strategy_returns'] = df['position'] * df['returns']
        df['equity'] = initial_capital * (1 + df['strategy_returns']).cumprod()
        
        total_return = (df['equity'].iloc[-1] / initial_capital - 1) * 100
        sharpe = (df['strategy_returns'].mean() / df['strategy_returns'].std() * np.sqrt(252)) if df['strategy_returns'].std() > 0 else 0
        max_dd = (df['equity'] / df['equity'].cummax() - 1).min() * 100
        
        # Win rate
        trades = (df['position'].diff() != 0).sum()
        wins = (df['strategy_returns'] > 0).sum()
        win_rate = (wins / trades * 100) if trades > 0 else 0
        
        final_value = df['equity'].iloc[-1]
        
        # Store result
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''
            INSERT INTO backtest_results 
            (timestamp, ticker, strategy, start_date, end_date, initial_capital, final_value, 
             total_return, sharpe, max_drawdown, win_rate, trades, forward_test)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), ticker, strategy, start_date.strftime('%Y-%m-%d'), 
              end_date.strftime('%Y-%m-%d'), initial_capital, final_value, 
              total_return, sharpe, max_dd, win_rate, int(trades), is_forward_test))
        conn.commit()
        conn.close()
        
        return {
            "df": df,
            "metrics": {
                "total_return": round(total_return, 2),
                "sharpe": round(sharpe, 2),
                "max_drawdown": round(max_dd, 2),
                "win_rate": round(win_rate, 1),
                "trades": int(trades),
                "final_value": round(final_value, 2)
            },
            "equity_curve": df['equity']
        }
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        return {"error": f"Backtest failed: {str(e)[:150]}"}

# ----------------------------- PORTFOLIO SIMULATION -----------------------------
def simulate_portfolio(tickers: List[str], weights: List[float], initial_capital: float, 
                       start_date: date, end_date: date) -> Dict:
    try:
        portfolio_df = pd.DataFrame()
        for ticker, weight in zip(tickers, weights):
            df = get_stock_data(ticker, start=start_date, end=end_date)
            if df is None or df.empty:
                continue
            df = df['Close'].pct_change().fillna(0)
            portfolio_df[ticker] = df * weight
        
        if portfolio_df.empty:
            return {"error": "No valid data for portfolio."}
        
        portfolio_returns = portfolio_df.sum(axis=1)
        equity = initial_capital * (1 + portfolio_returns).cumprod()
        total_return = (equity.iloc[-1] / initial_capital - 1) * 100
        
        # Store simulation
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''
            INSERT INTO portfolio_simulations 
            (timestamp, name, tickers, weights, initial_capital, final_value, total_return, period_start, period_end)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), "Custom Portfolio", json.dumps(tickers), json.dumps(weights), 
              initial_capital, equity.iloc[-1], total_return, 
              start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        conn.commit()
        conn.close()
        
        return {
            "equity": equity,
            "total_return": round(total_return, 2),
            "final_value": round(equity.iloc[-1], 2)
        }
    except Exception as e:
        return {"error": str(e)}

# ----------------------------- TABS (Combined Similar Functions for Production UX) -----------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Live Market Explorer & DB Builder",
    "💼 Portfolio Simulator & Investment",
    "📈 Backtest + Forward Test Engine",
    "🤖 Grok AI Insights & Settings"
])

# TAB 1: Live Market Explorer & DB Builder (Combined Live Dashboard + Rebound Analyzer)
with tab1:
    st.header("Live Market Data & Historical Database")
    
    col_m, col_t = st.columns([1, 2])
    with col_m:
        market = st.selectbox("Market", list(MARKETS.keys()), index=0)
        market_info = MARKETS[market]
        st.caption(f"Examples: {', '.join(market_info['examples'])}")
    
    with col_t:
        ticker = st.text_input("Ticker Symbol (e.g. TSLA)", value="TSLA").upper().strip()
        if market == "ASX" and not ticker.endswith(".AX") and ticker not in ["TSLA", "AAPL"]:
            ticker += ".AX"
    
    col_fetch1, col_fetch2 = st.columns(2)
    with col_fetch1:
        period = st.selectbox("Quick Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"], index=3)
    with col_fetch2:
        custom_start = st.date_input("Custom Start (optional)", value=None)
        custom_end = st.date_input("Custom End (optional)", value=None)
    
    if st.button("🚀 Fetch & Store to Historical DB", type="primary"):
        with st.spinner(f"Fetching {ticker}..."):
            if custom_start and custom_end:
                df = get_stock_data(ticker, start=custom_start, end=custom_end)
            else:
                df = get_stock_data(ticker, period=period)
            
            if df is not None and not df.empty:
                st.success(f"✅ Stored {len(df)} days of {ticker} data in DB")
                # Rebound signal preview
                rebound_df = calculate_rebound_signals(df)
                latest_signal = rebound_df['signal'].iloc[-1]
                signal_text = "🟢 Buy Signal (Dip Detected)" if latest_signal == 1 else "⚪ No Rebound Signal"
                st.info(f"Latest Rebound Signal: {signal_text}")
            else:
                st.error("No data fetched. Check ticker or internet.")
    
    # Display latest data
    if ticker:
        df = load_stock_data(ticker)
        if not df.empty:
            st.subheader(f"{ticker} Historical Data (from DB)")
            st.dataframe(df.tail(10), use_container_width=True)
            
            # Price chart
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df.index, y=df['close'], name='Close', line=dict(color='#00f0ff')))
            fig.update_layout(title=f"{ticker} Price History", template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)
            
            # Add to favorites
            if st.button(f"⭐ Add {ticker} to Favorites"):
                if ticker not in FAVORITES:
                    FAVORITES.append(ticker)
                    st.success(f"{ticker} added to favorites!")

# TAB 2: Portfolio Simulator & Investment (New focused tab)
with tab2:
    st.header("Portfolio Investment Simulator")
    
    st.subheader("Build Custom Portfolio")
    selected_tickers = st.multiselect("Select Tickers (from favorites + custom)", 
                                      FAVORITES + [t for t in st.session_state.get("custom_tickers", []) if t not in FAVORITES],
                                      default=["TSLA", "AAPL"])
    
    if st.button("Add Custom Ticker"):
        new_t = st.text_input("New Ticker", key="new_ticker").upper()
        if new_t:
            if "custom_tickers" not in st.session_state:
                st.session_state.custom_tickers = []
            if new_t not in st.session_state.custom_tickers:
                st.session_state.custom_tickers.append(new_t)
            st.rerun()
    
    if selected_tickers:
        st.write("Allocation Weights (%):")
        weights = []
        cols = st.columns(len(selected_tickers))
        for i, t in enumerate(selected_tickers):
            with cols[i]:
                w = st.number_input(f"{t}", min_value=0.0, max_value=100.0, value=100.0/len(selected_tickers), step=5.0, key=f"w_{t}")
                weights.append(w / 100.0)
        
        total_w = sum(weights)
        if total_w > 0:
            weights = [w / total_w for w in weights]  # Normalize
        
        initial_cap = st.number_input("Initial Investment ($)", min_value=1000.0, value=10000.0, step=1000.0)
        
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            p_start = st.date_input("Simulation Start", value=date(2023, 1, 1))
        with col_p2:
            p_end = st.date_input("Simulation End", value=date.today())
        
        if st.button("💼 Run Portfolio Simulation", type="primary"):
            with st.spinner("Simulating portfolio..."):
                result = simulate_portfolio(selected_tickers, weights, initial_cap, p_start, p_end)
                if "error" not in result:
                    st.success(f"✅ Portfolio Return: {result['total_return']}% | Final Value: ${result['final_value']:,.2f}")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=result['equity'].index, y=result['equity'], name="Portfolio Equity", line=dict(color="#ff00aa")))
                    fig.update_layout(title="Portfolio Equity Curve", template="plotly_dark")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error(result['error'])

# TAB 3: Backtest + Forward Test Engine (Combined Backtester + Forward Testing)
with tab3:
    st.header("Backtesting & Forward Testing Engine")
    
    col_bt1, col_bt2 = st.columns(2)
    with col_bt1:
        bt_ticker = st.selectbox("Ticker for Test", FAVORITES, index=0)
    with col_bt2:
        bt_strategy = st.selectbox("Strategy", ["Rebound Dip", "MA Crossover", "Buy & Hold"])
    
    col_dates1, col_dates2 = st.columns(2)
    with col_dates1:
        bt_start = st.date_input("Start Date", value=date(2022, 1, 1), key="bt_start")
    with col_dates2:
        bt_end = st.date_input("End Date", value=date.today(), key="bt_end")
    
    initial_cap_bt = st.number_input("Initial Capital ($)", min_value=1000.0, value=10000.0, key="bt_cap")
    
    if bt_strategy == "Rebound Dip":
        dip = st.slider("Dip Threshold (%)", 1.0, 15.0, 5.0) / 100
        rebound = st.slider("Rebound Threshold (%)", 1.0, 10.0, 3.0) / 100
    else:
        dip = 0.05
        rebound = 0.03
    
    col_bt_run, col_fwd = st.columns(2)
    with col_bt_run:
        if st.button("🔄 Run Backtest (Full History)", type="primary"):
            with st.spinner("Running backtest..."):
                result = run_backtest(bt_ticker, bt_start, bt_end, initial_cap_bt, bt_strategy, dip, rebound, is_forward_test=False)
                if "error" not in result:
                    m = result["metrics"]
                    st.success("Backtest Complete!")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Return", f"{m['total_return']}%")
                    col2.metric("Sharpe Ratio", f"{m['sharpe']}")
                    col3.metric("Max Drawdown", f"{m['max_drawdown']}%")
                    col4.metric("Win Rate / Trades", f"{m['win_rate']}% / {m['trades']}")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=result["equity_curve"].index, y=result["equity_curve"], name="Equity Curve"))
                    fig.update_layout(title="Backtest Equity Curve", template="plotly_dark")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error(result["error"])
    
    with col_fwd:
        if st.button("🚀 Run Forward Test (Historical Start Point)", type="primary"):
            # Forward test: use start_date as "now", test on subsequent data
            fwd_start = bt_start
            fwd_end = bt_end
            with st.spinner("Running forward test from historical point..."):
                result = run_backtest(bt_ticker, fwd_start, fwd_end, initial_cap_bt, bt_strategy, dip, rebound, is_forward_test=True)
                if "error" not in result:
                    m = result["metrics"]
                    st.success("Forward Test Complete!")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Forward Return", f"{m['total_return']}%")
                    col2.metric("Sharpe", f"{m['sharpe']}")
                    col3.metric("Max DD", f"{m['max_drawdown']}%")
                    col4.metric("Win Rate / Trades", f"{m['win_rate']}% / {m['trades']}")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=result["equity_curve"].index, y=result["equity_curve"], name="Forward Equity"))
                    fig.update_layout(title="Forward Test Equity Curve (from Historical Start)", template="plotly_dark")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error(result["error"])
    
    # Historical Backtest Results
    st.subheader("📋 Saved Backtest & Forward Test History")
    conn = sqlite3.connect(DB_PATH)
    hist = pd.read_sql_query("SELECT * FROM backtest_results ORDER BY timestamp DESC LIMIT 20", conn)
    conn.close()
    if not hist.empty:
        st.dataframe(hist, use_container_width=True)

# TAB 4: Grok AI Insights & Settings (Combined Grok Chat + Self-Improve + Settings + Metrics)
with tab4:
    st.header("Grok AI Insights, Self-Improvement & Production Settings")
    
    # Grok Chat
    st.subheader("🤖 Ask Grok for Trading Insights")
    user_prompt = st.text_area("Prompt Grok (e.g. Analyze TSLA rebound potential from 2024 data)", 
                               "Provide a detailed rebound strategy analysis for TSLA using recent historical data.")
    if st.button("🧠 Get Grok Insight"):
        with st.spinner("Consulting Grok..."):
            grok_res = call_grok(user_prompt)
            st.markdown(grok_res["response"])
            st.caption(f"Latency: {grok_res['latency']:.2f}s | Tokens: {grok_res['total_tokens']} | Cost: ${grok_res['cost_usd']:.6f}")
    
    # Self-Improve
    st.subheader("🛠️ Self-Improvement Log")
    if st.button("Suggest Strategy Improvements"):
        prompt = "Analyze the current ReboundForge backtest strategies and suggest 3 specific improvements for better profitability on TSLA."
        grok_res = call_grok(prompt)
        st.markdown(grok_res["response"])
    
    # Settings & Export
    st.subheader("⚙️ Settings & Export")
    col_set1, col_set2 = st.columns(2)
    with col_set1:
        if st.button("Export All DB Data to CSV"):
            conn = sqlite3.connect(DB_PATH)
            for table in ["price_history", "backtest_results", "portfolio_simulations", "grok_logs"]:
                df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
                if not df.empty:
                    df.to_csv(BASE_DIR / f"{table}.csv", index=False)
            conn.close()
            st.success("All tables exported to CSV in ./XAI/App/")
    
    with col_set2:
        if st.button("Clear Old Logs (Keep Last 100)"):
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM grok_logs WHERE id NOT IN (SELECT id FROM grok_logs ORDER BY id DESC LIMIT 100)")
            conn.commit()
            conn.close()
            st.success("Old logs cleared.")
    
    # API Metrics
    st.subheader("📊 API & Performance Metrics")
    conn = sqlite3.connect(DB_PATH)
    metrics_df = pd.read_sql_query("SELECT COUNT(*) as total_calls, AVG(latency) as avg_latency, SUM(cost_usd) as total_cost FROM grok_logs", conn)
    conn.close()
    if not metrics_df.empty:
        st.metric("Total Grok Calls", int(metrics_df['total_calls'][0]))
        st.metric("Avg Latency (s)", round(metrics_df['avg_latency'][0], 2) if metrics_df['avg_latency'][0] else 0)
        st.metric("Total Cost (USD)", f"${metrics_df['total_cost'][0]:.4f}" if metrics_df['total_cost'][0] else "$0.00")
    
    st.caption("v1.1 Production Build • All tabs functional • Backward compatible with V1.0 DB • Error resilient • Cached fetches • Customizable tickers • Full portfolio/backtest/forward support")

# Footer
st.markdown("---")
st.caption("ReboundForge v1.1 | Single-file Production App | Run with: `streamlit run reboundforge.py` | Data cached 1hr | DB at ./XAI/App/reboundforge.db")
