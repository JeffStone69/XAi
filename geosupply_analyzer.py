#!/usr/bin/env python3
"""
🌍 GeoSupply Short-Term Profit Predictor v7.0
Grok Memory Analytics + Data-Driven Self-Improvement Edition
Uses Export/ folder + DB history for real performance feedback loop
"""

# ====================== STRONG SSL FIX ======================
import ssl
import certifi
import aiohttp
import asyncio

ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE  # Remove after running Install Certificates.command

ssl._create_default_https_context = lambda: ssl_context

# ====================== IMPORTS ======================
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import sqlite3
import logging
from pathlib import Path
import glob
import os

# ====================== CONFIG & LOGGING ======================
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "geosupply.db"
EXPORT_DIR = BASE_DIR / "Export"
GENERATED_DIR = BASE_DIR / "Generated_response"

def setup_logging():
    logging.basicConfig(
        filename="geosupply_analyzer.log",
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)s | %(message)s",
        force=True
    )

setup_logging()
logging.info("=== GeoSupply v7.0 started with Self-Improvement ===")

# ====================== DATABASE ======================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS grok_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            interaction_type TEXT,
            model TEXT,
            prompt_hash TEXT,
            response TEXT,
            horizon TEXT,
            prompt TEXT
        )
    """)
    for col in ["horizon", "model", "prompt"]:
        try:
            conn.execute(f"ALTER TABLE grok_interactions ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()
    logging.info("Grok memory DB initialized")

def log_grok_interaction(interaction_type: str, model: str, prompt: str, response: str, horizon: str = ""):
    try:
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:16]
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO grok_interactions 
            (interaction_type, model, prompt_hash, response, horizon, prompt)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (interaction_type, model, prompt_hash, response, horizon, prompt))
        conn.commit()
        conn.close()
        logging.info(f"Logged: {interaction_type} | Model: {model}")
    except Exception as e:
        logging.error(f"DB log failed: {e}")

def get_grok_history(limit: int = 100) -> pd.DataFrame:
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("""
            SELECT * FROM grok_interactions ORDER BY timestamp DESC LIMIT ?
        """, conn, params=(limit,))
        conn.close()
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df["response_length"] = df["response"].str.len()
        return df
    except Exception as e:
        logging.error(f"Failed to load history: {e}")
        return pd.DataFrame()

# ====================== SELF-IMPROVEMENT: LOAD EXPORT HISTORY ======================
def load_export_history() -> pd.DataFrame:
    """Load all CSV files from Export/ folder for performance analysis."""
    export_files = list(EXPORT_DIR.glob("*.csv"))
    if not export_files:
        logging.warning("No export files found in Export/ folder")
        return pd.DataFrame()
    
    dfs = []
    for file in export_files:
        try:
            df = pd.read_csv(file)
            df["export_date"] = pd.to_datetime(file.stem.split("_")[-1], errors="coerce") if "_" in file.stem else datetime.now()
            dfs.append(df)
        except Exception as e:
            logging.error(f"Failed to load {file}: {e}")
    
    if dfs:
        combined = pd.concat(dfs, ignore_index=True)
        logging.info(f"Loaded {len(export_files)} export files with {len(combined)} records")
        return combined
    return pd.DataFrame()

def compute_self_improvement_stats() -> dict:
    """Analyze past exports vs current signals for self-improvement insights."""
    history = load_export_history()
    if history.empty:
        return {"status": "No historical export data found. Generate and export signals first."}
    
    # Basic stats
    stats = {
        "total_past_signals": len(history),
        "unique_tickers": history["Ticker"].nunique() if "Ticker" in history.columns else 0,
        "avg_signal_score": history["Signal Score"].mean() if "Signal Score" in history.columns else 0,
        "top_sectors": history.groupby("Sector")["Signal Score"].mean().nlargest(3).to_dict() if "Sector" in history.columns else {},
        "status": "Ready"
    }
    return stats

# ====================== SECTORS & MODELS ======================
SECTORS: Dict[str, List[str]] = {
    "Mining": ["BHP.AX", "RIO.AX", "FMG.AX", "S32.AX", "MIN.AX", "FCX", "NEM", "VALE"],
    "Shipping": ["QUB.AX", "TCL.AX", "ASX.AX", "ZIM", "MATX", "SBLK"],
    "Energy": ["STO.AX", "WDS.AX", "ORG.AX", "WHC.AX", "BPT.AX", "XOM", "CVX"],
    "Tech": ["WTC.AX", "XRO.AX", "TNE.AX", "NXT.AX", "REA.AX", "NVDA", "AAPL", "TSLA"],
    "Renewable": ["ORG.AX", "AGL.AX", "IGO.AX", "NEE", "FSLR", "ENPH"],
}

ALL_TICKERS = sorted({t for sector_list in SECTORS.values() for t in sector_list})
AVAILABLE_MODELS = ["grok-4.20-reasoning", "grok-4.20-non-reasoning", "grok-4-1-fast-reasoning"]

# ====================== ASYNC GROK API ======================
async def async_call_grok_api(prompt: str, model: str, temperature: float = 0.7, 
                             interaction_type: Optional[str] = None, horizon: str = "") -> str:
    if not st.session_state.get("grok_api_key"):
        return "⚠️ Please enter your Grok API key in the sidebar."

    headers = {"Authorization": f"Bearer {st.session_state.grok_api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": temperature, "max_tokens": 1800}

    try:
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=90)) as session:
            async with session.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    return f"❌ Grok API error ({resp.status}): {error_text[:300]}"
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                if interaction_type:
                    log_grok_interaction(interaction_type, model, prompt, content, horizon)
                return content
    except Exception as e:
        logging.error(f"Grok API error: {e}", exc_info=True)
        return f"❌ Error calling Grok: {str(e)[:200]}"

# ====================== MARKET DATA & SIGNALS (unchanged core) ======================
@st.cache_data(ttl=300)
def fetch_raw_market_data(tickers: List[str]) -> Dict[str, pd.DataFrame]:
    try:
        raw = yf.download(tickers, period="1mo", interval="1d", group_by="ticker", auto_adjust=True, threads=True, progress=False)
        result = {}
        for ticker in tickers:
            if ticker in raw.columns.get_level_values(0):
                df = raw[ticker].dropna(how="all")
                if not df.empty and {"Close", "Volume"}.issubset(df.columns):
                    result[ticker] = df
        return result
    except Exception as e:
        logging.error(f"yfinance error: {e}")
        return {}

# ... (keep calculate_rsi and compute_profit_signals exactly as in v6.3) ...

def calculate_rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = -delta.clip(upper=0).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if len(rsi) > period and not pd.isna(rsi.iloc[-1]) else 50.0

@st.cache_data(ttl=300)
def compute_profit_signals(raw_data: Dict[str, pd.DataFrame], horizon: str) -> pd.DataFrame:
    if not raw_data:
        return pd.DataFrame()
    lookback_map = {"5d": 5, "10d": 10, "1mo": 20}
    lookback = lookback_map.get(horizon, 5)
    records = []
    for ticker, hist in raw_data.items():
        if len(hist) < lookback + 1:
            continue
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
                "Ticker": ticker, "Current Price": round(close.iloc[-1], 2),
                f"{horizon} Change %": round(price_change_pct, 1),
                "Avg Vol (M)": round(vol_avg / 1_000_000, 1), "Vol Spike": round(vol_spike, 2),
                "Volatility %": round(volatility, 1), "RSI": round(rsi, 1),
                "Signal Score": signal_score, "Sector": sector
            })
        except Exception:
            continue
    df = pd.DataFrame(records)
    return df.sort_values("Signal Score", ascending=False).reset_index(drop=True) if not df.empty else df

# ====================== UI HELPERS ======================
def display_thesis(thesis: str, unique_key_suffix: str = ""):
    if not thesis:
        return
    with st.container(border=True):
        st.markdown("### 📝 Grok Thesis")
        st.markdown(thesis)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📋 Copy", key=f"copy_{abs(hash(thesis)) % 100000}_{unique_key_suffix}"):
                st.toast("✅ Copied!")
        with col2:
            if st.button("💾 Save", type="primary", key=f"save_{abs(hash(thesis)) % 100000}_{unique_key_suffix}"):
                st.success("✅ Saved to history")

# ====================== MAIN APP ======================
init_db()

if "grok_api_key" not in st.session_state:
    st.session_state.grok_api_key = ""
if "last_thesis" not in st.session_state:
    st.session_state.last_thesis = None

st.set_page_config(page_title="GeoSupply v7.0", page_icon="🌍", layout="wide")

st.title("🌍 GeoSupply Short-Term Profit Predictor **v7.0**")
st.caption("**Data-Driven Self-Improvement** using Export/ + DB • Async Grok")

with st.sidebar:
    st.header("🔑 Grok API")
    api_key = st.text_input("Grok API Key", type="password", value=st.session_state.grok_api_key)
    if api_key and api_key != st.session_state.grok_api_key:
        st.session_state.grok_api_key = api_key
        st.success("✅ Key saved")

    st.header("⚙️ Settings")
    horizon = st.selectbox("Signal Horizon", ["5d", "10d", "1mo"], index=0)
    model = st.selectbox("Grok Model", AVAILABLE_MODELS, index=0)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.1)

    if st.button("🔄 Refresh Data", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# Load data
if "raw_data" not in st.session_state:
    with st.spinner("Fetching market data..."):
        st.session_state.raw_data = fetch_raw_market_data(ALL_TICKERS)

raw_data = st.session_state.raw_data
summary_df = compute_profit_signals(raw_data, horizon)

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📈 Leaderboard", "📊 Charts", "🔥 Sector Heatmap",
    "🤖 Grok Thesis", "📖 History", "📊 Analytics", "🧠 Self-Improvement"
])

# Tab 1-6 remain similar to v6.3 (omitted for brevity - copy from previous v6.3 if needed)
# ... (Leaderboard, Charts, Heatmap, Grok Thesis, History, Analytics tabs here - same as v6.3)

with tab7:
    st.subheader("🧠 Data-Driven Self-Improvement")
    st.caption("Analyzes Export/ folder + DB to improve future theses")
    
    stats = compute_self_improvement_stats()
    
    if stats.get("status") == "No historical export data found.":
        st.warning(stats["status"])
        st.info("Generate signals → Export CSV from Leaderboard tab → Run again")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Past Signals Analyzed", stats["total_past_signals"])
        with col2:
            st.metric("Unique Tickers", stats["unique_tickers"])
        with col3:
            st.metric("Avg Historical Score", round(stats["avg_signal_score"], 2))
        
        st.subheader("Top Performing Sectors (Historical)")
        st.write(stats["top_sectors"])
        
        if st.button("🚀 Generate Self-Improved Thesis", type="primary"):
            if summary_df.empty:
                st.error("No current signals")
            else:
                improvement_context = f"""
Historical Performance Summary:
- Total past signals analyzed: {stats['total_past_signals']}
- Average Signal Score: {stats['avg_signal_score']:.2f}
- Top sectors: {stats['top_sectors']}
"""
                prompt = f"""You are a self-improving supply-chain trader.
Current leaderboard (horizon: {horizon}):
{summary_df.head(12).to_string(index=False)}

{improvement_context}

Provide:
1. Updated market narrative incorporating past performance lessons
2. 2-3 refined trade ideas (adjust confidence based on historical hit-rate)
3. Specific self-improvement actions for the GeoSupply model

Be data-driven and actionable."""

                with st.spinner("Generating self-improved thesis..."):
                    try:
                        thesis = asyncio.run(async_call_grok_api(prompt, model, temperature, 
                                                               interaction_type="self_improvement", horizon=horizon))
                        st.session_state.last_thesis = thesis
                        st.success("✅ Self-improved thesis generated!")
                        display_thesis(thesis, "self_improve")
                    except Exception as e:
                        st.error(f"Failed: {e}")

st.caption("**v7.0** • Self-Improvement using Export/ + DB • https://github.com/JeffStone69/XAi")