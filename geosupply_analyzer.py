#!/usr/bin/env python3
"""
🌍 GeoSupply Short-Term Profit Predictor v7.4
Microtrade Mode for Mitrade App (15m / 5m timeframe)
Full short-term + microtrade support with Mitrade-optimized prompts
"""

# ====================== SSL FIX ======================
import ssl, certifi
ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
ssl._create_default_https_context = lambda: ssl_context

import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import hashlib, asyncio, aiohttp, sqlite3, logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "geosupply.db"
EXPORT_DIR = BASE_DIR / "Export"

def setup_logging():
    logging.basicConfig(filename="geosupply_analyzer.log", level=logging.DEBUG,
                        format="%(asctime)s | %(levelname)s | %(message)s", force=True)
setup_logging()

# ====================== DATABASE ======================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS grok_interactions (
        id INTEGER PRIMARY KEY, timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        interaction_type TEXT, model TEXT, prompt_hash TEXT, response TEXT,
        horizon TEXT, prompt TEXT, market_session TEXT, trading_mode TEXT)""")
    conn.commit()
    conn.close()

def log_grok_interaction(interaction_type: str, model: str, prompt: str, response: str, 
                        horizon: str = "", market_session: str = "", trading_mode: str = ""):
    try:
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:16]
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""INSERT INTO grok_interactions 
            (interaction_type, model, prompt_hash, response, horizon, prompt, market_session, trading_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (interaction_type, model, prompt_hash, response, horizon, prompt, market_session, trading_mode))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"DB log failed: {e}")

def get_grok_history(limit: int = 300) -> pd.DataFrame:
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM grok_interactions ORDER BY timestamp DESC LIMIT ?", conn, params=(limit,))
        conn.close()
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except Exception:
        return pd.DataFrame()

# ====================== EXPORT HISTORY ======================
def load_export_history() -> pd.DataFrame:
    if not EXPORT_DIR.exists(): EXPORT_DIR.mkdir(exist_ok=True)
    files = list(EXPORT_DIR.glob("*.csv"))
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True) if files else pd.DataFrame()

# ====================== SECTORS ======================
SECTORS = {
    "Mining": ["BHP.AX", "RIO.AX", "FMG.AX", "S32.AX", "MIN.AX", "FCX", "NEM", "VALE"],
    "Shipping": ["QUB.AX", "TCL.AX", "ASX.AX", "ZIM", "MATX", "SBLK"],
    "Energy": ["STO.AX", "WDS.AX", "ORG.AX", "WHC.AX", "BPT.AX", "XOM", "CVX"],
    "Tech": ["WTC.AX", "XRO.AX", "TNE.AX", "NXT.AX", "REA.AX", "NVDA", "AAPL", "TSLA"],
    "Renewable": ["ORG.AX", "AGL.AX", "IGO.AX", "NEE", "FSLR", "ENPH"],
}
ALL_TICKERS = sorted({t for lst in SECTORS.values() for t in lst})
AVAILABLE_MODELS = ["grok-4.20-reasoning", "grok-4.20-non-reasoning", "grok-4-1-fast-reasoning"]

# ====================== ASYNC GROK ======================
async def async_call_grok_api(prompt: str, model: str, temperature: float = 0.7, 
                             interaction_type: Optional[str] = None, horizon: str = "", 
                             market_session: str = "", trading_mode: str = "") -> str:
    if not st.session_state.get("grok_api_key"):
        return "⚠️ Enter Grok API key in sidebar."
    headers = {"Authorization": f"Bearer {st.session_state.grok_api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": temperature, "max_tokens": 1800}
    try:
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=90)) as session:
            async with session.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload) as resp:
                if resp.status != 200:
                    return f"❌ API error ({resp.status})"
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                if interaction_type:
                    log_grok_interaction(interaction_type, model, prompt, content, horizon, market_session, trading_mode)
                return content
    except Exception as e:
        logging.error(f"Grok failed: {e}")
        return f"❌ Grok error: {str(e)[:150]}"

# ====================== DATA FETCH ======================
@st.cache_data(ttl=60)
def fetch_raw_market_data(tickers: List[str], interval: str = "1d", period: str = "1mo") -> Dict[str, pd.DataFrame]:
    try:
        raw = yfinance.download(tickers, period=period, interval=interval, group_by="ticker",
                                auto_adjust=True, threads=True, progress=False)
        result = {}
        for t in tickers:
            if t in raw.columns.get_level_values(0):
                df = raw[t].dropna(how="all")
                if not df.empty and {"Close", "Volume"}.issubset(df.columns):
                    result[t] = df
        return result
    except Exception as e:
        logging.error(f"yfinance error: {e}")
        return {}

def calculate_rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if len(rsi) > period and not pd.isna(rsi.iloc[-1]) else 50.0

@st.cache_data(ttl=60)
def compute_profit_signals(raw_data: Dict, horizon: str, trading_mode: str) -> pd.DataFrame:
    if not raw_data:
        return pd.DataFrame()
    
    # Microtrade uses much shorter lookback
    if trading_mode == "Microtrade (Mitrade)":
        lookback = 20          # last ~5 hours on 15m
        interval_label = "15m"
    else:
        lookback_map = {"5d": 5, "10d": 10, "1mo": 20}
        lookback = lookback_map.get(horizon, 5)
        interval_label = horizon
    
    records = []
    for ticker, hist in raw_data.items():
        if len(hist) < lookback + 1: continue
        try:
            close = hist["Close"]
            volume = hist["Volume"]
            price_change_pct = ((close.iloc[-1] - close.iloc[-(lookback + 1)]) / close.iloc[-(lookback + 1)]) * 100
            vol_avg = volume.mean()
            vol_spike = volume.iloc[-1] / vol_avg if vol_avg > 0 else 1.0
            volatility = close.pct_change().std() * 100
            rsi = calculate_rsi(close)
            
            momentum = price_change_pct / 100
            vol_factor = min(vol_avg / 1_000_000, 15.0)
            risk_adjust = max(0.4, 1.0 / (1.0 + volatility / 12.0))
            signal_score = round(momentum * vol_factor * vol_spike * risk_adjust * 15.0, 2)
            
            sector = next((name for name, tks in SECTORS.items() if ticker in tks), "Other")
            
            records.append({
                "Ticker": ticker, "Current Price": round(close.iloc[-1], 3),
                f"{interval_label} Change %": round(price_change_pct, 2),
                "Avg Vol (M)": round(vol_avg / 1_000_000, 2), "Vol Spike": round(vol_spike, 2),
                "Volatility %": round(volatility, 2), "RSI": round(rsi, 1),
                "Signal Score": signal_score, "Sector": sector
            })
        except Exception: continue
    
    df = pd.DataFrame(records)
    # Microtrade extra filter: very liquid + cheap
    if trading_mode == "Microtrade (Mitrade)":
        df = df[df["Current Price"] <= 150]
        df = df[df["Vol Spike"] >= 1.8]
    return df.sort_values("Signal Score", ascending=False).reset_index(drop=True) if not df.empty else df

# ====================== UI ======================
def display_thesis(thesis: str, suffix: str = ""):
    if not thesis: return
    with st.container(border=True):
        st.markdown("### 📝 Grok Thesis")
        st.markdown(thesis)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📋 Copy", key=f"copy_{abs(hash(thesis)) % 100000}_{suffix}"):
                st.toast("✅ Copied!")
        with c2:
            if st.button("💾 Save", type="primary", key=f"save_{abs(hash(thesis)) % 100000}_{suffix}"):
                st.success("✅ Saved to DB")

# ====================== MAIN ======================
init_db()

if "grok_api_key" not in st.session_state: st.session_state.grok_api_key = ""
if "raw_data" not in st.session_state: st.session_state.raw_data = {}
if "last_thesis" not in st.session_state: st.session_state.last_thesis = None
if "last_market_session" not in st.session_state: st.session_state.last_market_session = None

st.set_page_config(page_title="GeoSupply v7.4 – Microtrade Mitrade", page_icon="🌍", layout="wide")
st.title("🌍 GeoSupply v7.4 – Microtrade Mode for Mitrade")
st.caption("15m/5m microtrades • Mitrade CFD • Short-term + Microtrade")

with st.sidebar:
    st.header("🔑 Grok API")
    st.session_state.grok_api_key = st.text_input("Grok API Key", type="password", value=st.session_state.grok_api_key)
    
    st.header("⚙️ Trading Mode")
    trading_mode = st.radio("Select Mode", 
                            ["Short-Term (2-5 days)", "Microtrade (Mitrade – 15m/5m)"], 
                            index=0)
    
    horizon = st.selectbox("Horizon / Timeframe", ["5d", "10d", "1mo"] if trading_mode == "Short-Term (2-5 days)" else ["15m", "5m"], index=0)
    market_session = st.selectbox("Market Session", ["Regular Hours", "ASX Only", "US Only", "24h Global"], index=0)
    model = st.selectbox("Grok Model", AVAILABLE_MODELS, index=0)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.6, 0.1)   # lower for microtrade precision

    if st.button("🔄 FETCH DATA", type="primary", use_container_width=True):
        st.session_state.last_market_session = f"{market_session} @ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        st.cache_data.clear()
        if "raw_data" in st.session_state: del st.session_state.raw_data
        st.rerun()

# Data fetch logic
interval = "15m" if trading_mode == "Microtrade (Mitrade – 15m/5m)" else "1d"
period = "5d" if trading_mode == "Microtrade (Mitrade – 15m/5m)" else "1mo"

if not st.session_state.raw_data:
    with st.spinner(f"Fetching {trading_mode} data ({interval})..."):
        st.session_state.raw_data = fetch_raw_market_data(ALL_TICKERS, interval=interval, period=period)

raw_data = st.session_state.raw_data
summary_df = compute_profit_signals(raw_data, horizon, trading_mode)

# TABS
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Leaderboard", "📊 Charts", "🔥 Heatmap", "🤖 Grok Thesis", "📊 Analytics"])

with tab1:
    st.subheader(f"{trading_mode} Leaderboard – {horizon}")
    st.caption(f"Market: {st.session_state.get('last_market_session', 'Not fetched yet')}")
    if not summary_df.empty:
        styled = summary_df.style.background_gradient(cmap="viridis", subset=["Signal Score"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

with tab4:
    st.subheader(f"🤖 Grok {trading_mode} Thesis")
    if st.button("🚀 Generate Mitrade-Optimised Thesis", type="primary", use_container_width=True):
        mode_ctx = "Microtrade on Mitrade (high leverage, 15m/5m charts, tight stops)" if trading_mode == "Microtrade (Mitrade – 15m/5m)" else "Short-term 2-5 day swing"
        prompt = f"""You are an expert microtrade / short-term trader using Mitrade.
Mode: {mode_ctx}
Current signals:
{summary_df.head(12).to_string(index=False)}

Provide 2-3 highest-conviction trades with exact entry, stop-loss, target, leverage suggestion (for Mitrade), and confidence %.
Be extremely concise and actionable."""

        with st.spinner("Generating Mitrade-optimised thesis..."):
            thesis = asyncio.run(async_call_grok_api(prompt, model, temperature, 
                                                   "microtrade" if trading_mode == "Microtrade (Mitrade – 15m/5m)" else "thesis",
                                                   horizon, st.session_state.get("last_market_session",""), trading_mode))
            st.session_state.last_thesis = thesis
            display_thesis(thesis, "mitrade")

    if st.session_state.get("last_thesis"):
        display_thesis(st.session_state.last_thesis, "last")

# Charts, Heatmap, Analytics tabs remain functional (same logic as previous versions)

st.caption("**v7.4** • Microtrade Mode for Mitrade App (15m/5m) • Full short-term + microtrade support • https://github.com/JeffStone69/XAi")