#!/usr/bin/env python3
"""
🌍 GeoSupply Short-Term Profit Predictor v7.2
Consolidated Grok Self-Improvement + History • Open Market Selection with Timestamps
"""

# ====================== STRONG SSL FIX ======================
import ssl
import certifi
ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
ssl._create_default_https_context = lambda: ssl_context

# ====================== IMPORTS ======================
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import hashlib
import asyncio
import aiohttp
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# ====================== CONFIG ======================
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "geosupply.db"
EXPORT_DIR = BASE_DIR / "Export"

def setup_logging():
    logging.basicConfig(filename="geosupply_analyzer.log", level=logging.DEBUG,
                        format="%(asctime)s | %(levelname)s | %(message)s", force=True)

setup_logging()
logging.info("=== GeoSupply v7.2 started with Open Market ===")

# ====================== DATABASE ======================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS grok_interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        interaction_type TEXT, model TEXT, prompt_hash TEXT, response TEXT,
        horizon TEXT, prompt TEXT, market_session TEXT)""")
    conn.commit()
    conn.close()

def log_grok_interaction(interaction_type: str, model: str, prompt: str, response: str, horizon: str = "", market_session: str = ""):
    try:
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:16]
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""INSERT INTO grok_interactions 
            (interaction_type, model, prompt_hash, response, horizon, prompt, market_session)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (interaction_type, model, prompt_hash, response, horizon, prompt, market_session))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"DB log failed: {e}")

def get_grok_history(limit: int = 200) -> pd.DataFrame:
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM grok_interactions ORDER BY timestamp DESC LIMIT ?", conn, params=(limit,))
        conn.close()
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()

# ====================== EXPORT HISTORY & PROFITABILITY ======================
def load_export_history() -> pd.DataFrame:
    if not EXPORT_DIR.exists():
        EXPORT_DIR.mkdir(exist_ok=True)
        return pd.DataFrame()
    files = list(EXPORT_DIR.glob("*.csv"))
    if not files:
        return pd.DataFrame()
    dfs = [pd.read_csv(f) for f in files]
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def compute_profitability_improvement() -> dict:
    exports = load_export_history()
    return {
        "total_exports": len(exports),
        "avg_signal_score": exports.get("Signal Score", pd.Series([0])).mean(),
        "top_sectors": exports.groupby("Sector")["Signal Score"].mean().nlargest(5).to_dict() if not exports.empty else {}
    }

# ====================== SECTORS ======================
SECTORS: Dict[str, List[str]] = {
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
                             interaction_type: Optional[str] = None, horizon: str = "", market_session: str = "") -> str:
    if not st.session_state.get("grok_api_key"):
        return "⚠️ Enter Grok API key."
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
                    log_grok_interaction(interaction_type, model, prompt, content, horizon, market_session)
                return content
    except Exception as e:
        logging.error(f"Grok failed: {e}")
        return f"❌ Grok error: {str(e)[:150]}"

# ====================== DATA ======================
@st.cache_data(ttl=300)
def fetch_raw_market_data(tickers: List[str]) -> Dict[str, pd.DataFrame]:
    try:
        raw = yf.download(tickers, period="1mo", interval="1d", group_by="ticker", auto_adjust=True, threads=True, progress=False)
        result = {}
        for t in tickers:
            if t in raw.columns.get_level_values(0):
                df = raw[t].dropna(how="all")
                if not df.empty and {"Close", "Volume"}.issubset(df.columns):
                    result[t] = df
        return result
    except Exception as e:
        logging.error(f"yfinance: {e}")
        return {}

def calculate_rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if len(rsi) > period and not pd.isna(rsi.iloc[-1]) else 50.0

@st.cache_data(ttl=300)
def compute_profit_signals(raw_data: Dict[str, pd.DataFrame], horizon: str) -> pd.DataFrame:
    if not raw_data:
        return pd.DataFrame()
    lookback = {"5d":5,"10d":10,"1mo":20}.get(horizon,5)
    records = []
    for ticker, hist in raw_data.items():
        if len(hist) < lookback + 1: continue
        try:
            close = hist["Close"]
            volume = hist["Volume"]
            price_change_pct = ((close.iloc[-1] - close.iloc[-(lookback+1)]) / close.iloc[-(lookback+1)]) * 100
            vol_avg = volume.mean()
            vol_spike = volume.iloc[-1] / vol_avg if vol_avg > 0 else 1.0
            volatility = close.pct_change().std() * 100
            rsi = calculate_rsi(close)
            momentum = price_change_pct / 100
            vol_factor = min(vol_avg / 1_000_000, 15.0)
            risk_adjust = max(0.4, 1.0 / (1.0 + volatility / 12.0))
            signal_score = round(momentum * vol_factor * vol_spike * risk_adjust * 15.0, 2)
            sector = next((name for name, tks in SECTORS.items() if ticker in tks), "Other")
            records.append({"Ticker":ticker,"Current Price":round(close.iloc[-1],2),
                           f"{horizon} Change %":round(price_change_pct,1),"Avg Vol (M)":round(vol_avg/1_000_000,1),
                           "Vol Spike":round(vol_spike,2),"Volatility %":round(volatility,1),"RSI":round(rsi,1),
                           "Signal Score":signal_score,"Sector":sector})
        except Exception: continue
    df = pd.DataFrame(records)
    return df.sort_values("Signal Score", ascending=False).reset_index(drop=True) if not df.empty else df

# ====================== UI ======================
def display_thesis(thesis: str, suffix: str = ""):
    if not thesis: return
    with st.container(border=True):
        st.markdown("### 📝 Grok Thesis")
        st.markdown(thesis)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📋 Copy", key=f"copy_{abs(hash(thesis))%100000}_{suffix}"):
                st.toast("✅ Copied")
        with c2:
            if st.button("💾 Save", type="primary", key=f"save_{abs(hash(thesis))%100000}_{suffix}"):
                st.success("✅ Saved")

# ====================== MAIN ======================
init_db()

if "grok_api_key" not in st.session_state: st.session_state.grok_api_key = ""
if "raw_data" not in st.session_state: st.session_state.raw_data = {}
if "last_thesis" not in st.session_state: st.session_state.last_thesis = None
if "last_market_session" not in st.session_state: st.session_state.last_market_session = None

st.set_page_config(page_title="GeoSupply v7.2", page_icon="🌍", layout="wide")
st.title("🌍 GeoSupply Short-Term Profit Predictor **v7.2**")
st.caption("Open Market Selection + Timestamps • Consolidated Self-Improvement")

with st.sidebar:
    st.header("🔑 Grok API")
    key = st.text_input("Grok API Key", type="password", value=st.session_state.grok_api_key)
    if key and key != st.session_state.grok_api_key:
        st.session_state.grok_api_key = key
        st.success("✅ Saved")

    st.header("⚙️ Settings")
    horizon = st.selectbox("Signal Horizon", ["5d", "10d", "1mo"], index=0)
    market_session = st.selectbox("Open Market Session", 
                                  ["Regular Hours (ASX+US)", "ASX Only", "US Only", "Pre-Market", "Post-Market", "24h Global"], 
                                  index=0)
    model = st.selectbox("Grok Model", AVAILABLE_MODELS, index=0)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.1)

    fetch_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if st.button("🔄 Fetch Data for Selected Market", type="primary", use_container_width=True):
        st.session_state.last_market_session = f"{market_session} @ {fetch_ts}"
        st.cache_data.clear()
        if "raw_data" in st.session_state: del st.session_state.raw_data
        st.rerun()

# Fetch data
if not st.session_state.raw_data:
    with st.spinner(f"Fetching for {market_session}..."):
        st.session_state.raw_data = fetch_raw_market_data(ALL_TICKERS)
raw_data = st.session_state.raw_data
summary_df = compute_profit_signals(raw_data, horizon)

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Leaderboard", "📊 Charts", "🔥 Heatmap", "🤖 Grok Self-Improvement & History", "📊 Analytics"])

with tab1:
    st.subheader(f"Leaderboard ({horizon}) - {st.session_state.get('last_market_session','No market selected')}")
    if not summary_df.empty:
        st.dataframe(summary_df.style.background_gradient(cmap="viridis", subset=["Signal Score"]), use_container_width=True, hide_index=True)
        c1,c2 = st.columns(2)
        with c1: st.download_button("📥 CSV", summary_df.to_csv(index=False), f"geosupply_{horizon}.csv")
        with c2: 
            top10 = summary_df.head(10).copy()
            top10["Action"] = "BUY"
            top10["Exchange"] = top10["Ticker"].apply(lambda x: "ASX" if x.endswith(".AX") else "SMART")
            st.download_button("🚀 IBKR", top10[["Ticker","Exchange","Action"]].to_csv(index=False), "IBKR_top10.csv")

with tab4:
    st.subheader("🤖 Grok Self-Improvement & History")
    stats = compute_profitability_improvement()
    c1,c2,c3 = st.columns(3)
    with c1: st.metric("Past Exports", stats["total_exports"])
    with c2: st.metric("Avg Score", f"{stats['avg_signal_score']:.2f}")
    with c3: st.metric("Top Sectors", len(stats["top_sectors"]))

    if st.button("🚀 Generate Self-Improved Thesis", type="primary", use_container_width=True):
        ctx = f"Historical context: {stats}\nMarket session: {st.session_state.get('last_market_session','N/A')}"
        prompt = f"""Current signals ({horizon}):
{summary_df.head(12).to_string(index=False)}

{ctx}

Provide 2-3 refined trades + self-improvement suggestion."""
        with st.spinner("Generating..."):
            thesis = asyncio.run(async_call_grok_api(prompt, model, temperature, "self_improvement", horizon, st.session_state.get("last_market_session","")))
            st.session_state.last_thesis = thesis
            display_thesis(thesis, "improve")

    if st.session_state.get("last_thesis"):
        display_thesis(st.session_state.last_thesis, "last")

    st.subheader("📖 History")
    history_df = get_grok_history(30)
    if not history_df.empty:
        for _, row in history_df.iterrows():
            with st.expander(f"{row['timestamp']} | {row.get('market_session','N/A')} | {row.get('interaction_type')}"):
                st.markdown(row['response'])

st.caption("v7.2 • Open Market + Timestamps • https://github.com/JeffStone69/XAi")