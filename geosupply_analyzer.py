#!/usr/bin/env python3
"""
🌍 GeoSupply Short-Term Profit Predictor v5.1
Clean • Fast • Fixed • Self-Improving Edition
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
import sqlite3
import logging
import os
from pathlib import Path

# Optional enhanced logging
try:
    from loguru import logger
    USE_LOGURU = True
except ImportError:
    USE_LOGURU = False

# ====================== PATHS & CONFIG ======================
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "geosupply.db"

def setup_logging():
    if USE_LOGURU:
        logger.remove()
        logger.add("geosupply_analyzer.log", rotation="10 MB", level="INFO")
        logger.add(lambda msg: print(msg, end=""), level="INFO")
    else:
        logging.basicConfig(filename="geosupply_analyzer.log", level=logging.INFO)

setup_logging()

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
            horizon TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_grok_interaction(interaction_type: str, model: str, prompt: str, response: str, horizon: str = ""):
    try:
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:16]
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO grok_interactions 
            (interaction_type, model, prompt_hash, response, horizon)
            VALUES (?, ?, ?, ?, ?)
        """, (interaction_type, model, prompt_hash, response, horizon))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.warning(f"DB log failed: {e}")

def get_grok_history(limit: int = 15):
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("""
            SELECT timestamp, interaction_type, model, response, horizon
            FROM grok_interactions ORDER BY timestamp DESC LIMIT ?
        """, conn, params=(limit,))
        conn.close()
        return df
    except:
        return pd.DataFrame()

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

# ====================== GROK API ======================
def call_grok_api(prompt: str, model: str, temperature: float = 0.7, interaction_type: Optional[str] = None, horizon: str = "") -> str:
    if not st.session_state.get("grok_api_key"):
        return "⚠️ Please enter your Grok API key in the sidebar."

    headers = {"Authorization": f"Bearer {st.session_state.grok_api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 1800
    }

    try:
        resp = requests.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        if interaction_type:
            log_grok_interaction(interaction_type, model, prompt, content, horizon)
        return content
    except Exception as e:
        logging.error(f"Grok API error: {e}")
        return f"❌ Grok API error: {str(e)[:200]}"

# ====================== DATA & SIGNALS ======================
@st.cache_data(ttl=300)
def fetch_raw_market_data(tickers: List[str]):
    try:
        data = yf.download(tickers, period="1mo", interval="1d", group_by="ticker", auto_adjust=True, threads=True, progress=False)
        result = {}
        for t in tickers:
            if t in data.columns.get_level_values(0):
                df = data[t].dropna(how="all")
                if not df.empty and "Close" in df.columns and "Volume" in df.columns:
                    result[t] = df
        return result
    except Exception as e:
        logging.error(f"yfinance error: {e}")
        return {}

def calculate_rsi(close: pd.Series, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss
    return (100 - (100 / (1 + rs))).iloc[-1]

@st.cache_data(ttl=300)
def compute_profit_signals(raw_data: Dict, horizon: str):
    if not raw_data:
        return pd.DataFrame()
    
    lookback = {"5d": 5, "10d": 10, "1mo": 20}.get(horizon, 5)
    records = []
    
    for ticker, hist in raw_data.items():
        if len(hist) < lookback + 1:
            continue
        try:
            close = hist["Close"]
            vol = hist["Volume"]
            
            price_change = ((close.iloc[-1] - close.iloc[-(lookback+1)]) / close.iloc[-(lookback+1)]) * 100
            vol_avg = vol.mean()
            vol_spike = vol.iloc[-1] / vol_avg if vol_avg > 0 else 1.0
            volatility = close.pct_change().std() * 100
            rsi = calculate_rsi(close)
            
            signal = round((price_change/100) * min(vol_avg/1e6, 15) * vol_spike * max(0.4, 1 - volatility/15) * 15, 2)
            
            sector = next((s for s, tks in SECTORS.items() if ticker in tks), "Other")
            
            records.append({
                "Ticker": ticker,
                "Current Price": round(close.iloc[-1], 2),
                f"{horizon} Change %": round(price_change, 1),
                "Avg Vol (M)": round(vol_avg/1e6, 1),
                "Vol Spike": round(vol_spike, 2),
                "Volatility %": round(volatility, 1),
                "RSI": round(rsi, 1),
                "Signal Score": signal,
                "Sector": sector
            })
        except:
            continue
    
    df = pd.DataFrame(records)
    return df.sort_values("Signal Score", ascending=False).reset_index(drop=True) if not df.empty else df

# ====================== MAIN ======================
init_db()

if "grok_api_key" not in st.session_state:
    st.session_state.grok_api_key = ""

st.set_page_config(page_title="GeoSupply v5.1", page_icon="🌍", layout="wide")
st.title("🌍 GeoSupply Short-Term Profit Predictor **v5.1**")
st.caption("Fixed • Clean • Ready to Run")

with st.sidebar:
    st.header("🔑 Grok API")
    key = st.text_input("Grok API Key", type="password", value=st.session_state.grok_api_key)
    if key:
        st.session_state.grok_api_key = key
        st.success("Key saved")

    st.header("⚙️ Settings")
    horizon = st.selectbox("Horizon", ["5d", "10d", "1mo"], index=0)
    model = st.selectbox("Model", AVAILABLE_MODELS, index=0)

    if st.button("🔄 Refresh All Data", type="primary"):
        st.cache_data.clear()
        st.rerun()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Leaderboard", "📊 Charts", "🔥 Heatmap", "🤖 Grok Thesis", "📜 History"])

if "raw_data" not in st.session_state:
    with st.spinner("Fetching market data..."):
        st.session_state.raw_data = fetch_raw_market_data(ALL_TICKERS)

raw_data = st.session_state.raw_data
summary_df = compute_profit_signals(raw_data, horizon)

with tab1:
    st.subheader(f"Profit Signals ({horizon})")
    if not summary_df.empty:
        st.dataframe(summary_df.style.background_gradient(subset=["Signal Score"]), use_container_width=True, hide_index=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("Download Full CSV", summary_df.to_csv(index=False), f"geosupply_{horizon}.csv")
        with col2:
            # Simple IBKR top 10
            top10 = summary_df.head(10).copy()
            top10["Action"] = "BUY"
            top10["Exchange"] = top10["Ticker"].apply(lambda x: "ASX" if x.endswith(".AX") else "SMART")
            st.download_button("IBKR Top 10", top10[["Ticker","Exchange","Action"]].to_csv(index=False), "IBKR_top10.csv")
    else:
        st.error("No data loaded. Refresh.")

with tab2:
    st.subheader("Top Charts")
    for ticker in summary_df.head(6)["Ticker"] if not summary_df.empty else []:
        hist = raw_data.get(ticker)
        if hist is not None:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], name="Price"), secondary_y=False)
            fig.add_trace(go.Bar(x=hist.index, y=hist["Volume"], name="Volume", opacity=0.4), secondary_y=True)
            fig.update_layout(title=ticker, template="plotly_dark", height=300)
            st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("Sector Heatmap")
    if not summary_df.empty:
        sector_avg = summary_df.groupby("Sector")["Signal Score"].mean().round(2)
        fig = go.Figure(data=go.Heatmap(
            z=sector_avg.values.reshape(-1,1),
            x=["Avg Signal"],
            y=sector_avg.index,
            colorscale="Viridis"
        ))
        fig.update_layout(title="Sector Momentum", height=400, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.subheader("Grok Thesis (2-5 days)")
    if st.button("Generate Thesis + Suggestions"):
        with st.spinner("Thinking..."):
            prompt = f"Analyze this GeoSupply leaderboard for short-term opportunities (horizon {horizon}):\n{summary_df.head(12).to_string()}\nGive clear trade ideas."
            thesis = call_grok_api(prompt, model, interaction_type="thesis", horizon=horizon)
            st.markdown(thesis)

with tab5:
    st.subheader("Grok History")
    history = get_grok_history()
    if not history.empty:
        for _, row in history.iterrows():
            with st.expander(f"{row['timestamp']} | {row.get('interaction_type','')}"):
                st.markdown(row['response'])
    else:
        st.info("No history yet.")

st.caption("v5.1 Fixed & Cleaned • https://github.com/JeffStone69/XAi")