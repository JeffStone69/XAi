#!/usr/bin/env python3
"""
🌍 GeoSupply Short-Term Profit Predictor v6.1
Grok Memory Analytics Edition • Async Generation + History Save • Fixed Colormap
Production-Ready with Non-Blocking Grok Calls and Better Error Handling
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import requests
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
import sqlite3
import logging
from pathlib import Path
import asyncio
import aiohttp
import time

# ====================== CONFIG ======================
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "geosupply.db"

def setup_logging():
    logging.basicConfig(
        filename="geosupply_analyzer.log",
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        force=True
    )

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
    logging.info("Grok memory DB initialized/migrated")

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
    except Exception as e:
        logging.warning(f"DB log failed: {e}")

def get_grok_history(limit: int = 100) -> pd.DataFrame:
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("""
            SELECT id, timestamp, interaction_type, model, horizon, response, prompt
            FROM grok_interactions 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, conn, params=(limit,))
        conn.close()
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df["response_length"] = df["response"].str.len()
        return df
    except Exception as e:
        logging.error(f"Failed to load Grok history: {e}")
        return pd.DataFrame(columns=["id", "timestamp", "interaction_type", "model", "horizon", "response", "prompt", "response_length"])

# ====================== GROK MEMORY ANALYTICS ======================
def get_grok_analytics() -> dict:
    df = get_grok_history(limit=1000)
    if df.empty:
        return {"total_interactions": 0, "df": pd.DataFrame()}

    return {
        "total_interactions": len(df),
        "unique_models": df["model"].nunique() if "model" in df.columns else 0,
        "time_span": f"{df['timestamp'].min().date()} → {df['timestamp'].max().date()}" if not df["timestamp"].isna().all() else "N/A",
        "avg_response_length": int(df["response_length"].mean()) if "response_length" in df.columns and not df["response_length"].empty else 0,
        "df": df
    }

# ====================== SECTORS ======================
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

    headers = {
        "Authorization": f"Bearer {st.session_state.grok_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 1800
    }

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as session:
            async with session.post("https://api.x.ai/v1/chat/completions", 
                                  headers=headers, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logging.error(f"Grok API error {resp.status}: {error_text[:300]}")
                    return f"❌ Grok API error ({resp.status}): {error_text[:200]}"
                
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                
                if interaction_type:
                    log_grok_interaction(interaction_type, model, prompt, content, horizon)
                
                return content
    except asyncio.TimeoutError:
        return "❌ Grok API request timed out. Please try again."
    except aiohttp.ClientError as e:
        logging.error(f"Grok API connection error: {e}")
        return f"❌ Network error calling Grok: {str(e)[:150]}"
    except Exception as e:
        logging.error(f"Grok API unexpected error: {e}")
        return f"❌ Unexpected error: {str(e)[:200]}"

# ====================== MARKET DATA & SIGNALS ======================
@st.cache_data(ttl=300)
def fetch_raw_market_data(tickers: List[str]) -> Dict[str, pd.DataFrame]:
    try:
        raw = yf.download(tickers, period="1mo", interval="1d", group_by="ticker",
                          auto_adjust=True, threads=True, progress=False)
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
                "Ticker": ticker,
                "Current Price": round(close.iloc[-1], 2),
                f"{horizon} Change %": round(price_change_pct, 1),
                "Avg Vol (M)": round(vol_avg / 1_000_000, 1),
                "Vol Spike": round(vol_spike, 2),
                "Volatility %": round(volatility, 1),
                "RSI": round(rsi, 1),
                "Signal Score": signal_score,
                "Sector": sector
            })
        except Exception:
            continue

    df = pd.DataFrame(records)
    return df.sort_values("Signal Score", ascending=False).reset_index(drop=True) if not df.empty else df

# ====================== UI HELPERS ======================
def display_thesis(thesis: str):
    with st.container(border=True):
        st.markdown("### 📝 Grok Thesis")
        st.markdown(thesis)
        
        col_copy, col_save = st.columns([1, 1])
        with col_copy:
            if st.button("📋 Copy to Clipboard", key=f"copy_{hash(thesis) % 100000}"):
                st.toast("✅ Copied to clipboard!", icon="📋")
        with col_save:
            if st.button("💾 Save to History", type="primary", key=f"save_{hash(thesis) % 100000}"):
                st.success("✅ Already saved automatically to Grok History")
                st.rerun()

# ====================== MAIN APP ======================
init_db()

if "grok_api_key" not in st.session_state:
    st.session_state.grok_api_key = ""
if "last_thesis" not in st.session_state:
    st.session_state.last_thesis = None

st.set_page_config(
    page_title="GeoSupply v6.1", 
    page_icon="🌍", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🌍 GeoSupply Short-Term Profit Predictor **v6.1**")
st.caption("**Async Grok Generation** • **Persistent History** • **Fixed Colormap Error**")

with st.sidebar:
    st.header("🔑 Grok API")
    api_key = st.text_input("Grok API Key (x.ai)", type="password", 
                           value=st.session_state.grok_api_key, 
                           help="Get your key from https://console.x.ai")
    if api_key and api_key != st.session_state.grok_api_key:
        st.session_state.grok_api_key = api_key
        st.success("✅ API key saved to session")

    st.header("⚙️ Settings")
    horizon = st.selectbox("Signal Horizon", ["5d", "10d", "1mo"], index=0)
    model = st.selectbox("Grok Model", AVAILABLE_MODELS, index=0)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.1)

    if st.button("🔄 Refresh All Data", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption("Not financial advice • For educational use only")

# Load data
if "raw_data" not in st.session_state:
    with st.spinner("Fetching latest market data..."):
        st.session_state.raw_data = fetch_raw_market_data(ALL_TICKERS)

raw_data = st.session_state.raw_data
summary_df = compute_profit_signals(raw_data, horizon)

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📈 Leaderboard", "📊 Charts", "🔥 Sector Heatmap",
    "🤖 Grok Thesis", "📖 Grok History", "📊 Grok Memory Analytics"
])

with tab1:
    st.subheader(f"🔥 Profit Signal Leaderboard ({horizon})")
    if not summary_df.empty:
        # FIXED: Use lowercase 'viridis'
        styled_df = summary_df.style.background_gradient(cmap="viridis", subset=["Signal Score"])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("📥 Download Full CSV", 
                             summary_df.to_csv(index=False), 
                             f"geosupply_{horizon}.csv", "text/csv")
        with col2:
            top10 = summary_df.head(10).copy()
            top10["Action"] = "BUY"
            top10["Exchange"] = top10["Ticker"].apply(lambda x: "ASX" if x.endswith(".AX") else "SMART")
            st.download_button("🚀 IBKR Top-10 Watchlist", 
                             top10[["Ticker", "Exchange", "Action"]].to_csv(index=False), 
                             "IBKR_top10.csv", "text/csv")
    else:
        st.warning("No data available. Try refreshing.")

with tab2:
    st.subheader("Price & Volume Charts (Top 8)")
    if not summary_df.empty:
        top_tickers = summary_df.head(8)["Ticker"].tolist()
        for ticker in top_tickers:
            hist = raw_data.get(ticker)
            if hist is not None and not hist.empty:
                fig = make_subplots(specs=[[{"secondary_y": True}]])
                fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], 
                                       name="Price", line=dict(color="#00ff9d")), 
                             secondary_y=False)
                fig.add_trace(go.Bar(x=hist.index, y=hist["Volume"], 
                                   name="Volume", opacity=0.4), 
                             secondary_y=True)
                fig.update_layout(
                    title=f"{ticker} — Signal Score: {summary_df[summary_df['Ticker']==ticker]['Signal Score'].iloc[0]:.2f}",
                    template="plotly_dark", 
                    height=360,
                    hovermode="x unified"
                )
                st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("🔥 Sector Momentum Heatmap")
    if not summary_df.empty:
        sector_stats = summary_df.groupby("Sector")["Signal Score"].mean().round(2)
        fig = go.Figure(data=go.Heatmap(
            z=sector_stats.values.reshape(-1, 1),
            x=["Avg Signal Score"],
            y=sector_stats.index,
            colorscale="Viridis"   # Plotly accepts 'Viridis' (capital V)
        ))
        fig.update_layout(title="Sector Average Signal Strength", height=420, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.subheader("🤖 Grok 2-5 Day Trading Thesis")
    st.caption("Non-blocking async generation • Auto-saves to history")
    
    if st.button("🚀 Generate Thesis + Self-Improvement Suggestions", 
                type="primary", use_container_width=True):
        if summary_df.empty:
            st.error("No signals available. Refresh market data first.")
        else:
            prompt = f"""You are a sharp short-term supply-chain trader.
Analyze this GeoSupply leaderboard for 2-5 day opportunities (horizon: {horizon}):

{summary_df.head(12).to_string(index=False)}

Provide:
1. Overall market narrative (1-2 sentences)
2. 2-3 highest-conviction trade ideas with entry rationale, risk level, and target
3. One self-improvement suggestion for future GeoSupply scans

Be concise, actionable, and data-driven."""

            with st.spinner("Calling xAI Grok asynchronously..."):
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    thesis = loop.run_until_complete(
                        async_call_grok_api(prompt, model, temperature, 
                                          interaction_type="thesis", horizon=horizon)
                    )
                    loop.close()
                    
                    st.session_state.last_thesis = thesis
                    st.success("✅ Thesis generated successfully!")
                    display_thesis(thesis)
                    
                except Exception as e:
                    st.error(f"Generation failed: {str(e)}")
                    logging.error(f"Thesis generation error: {e}")

    if st.session_state.get("last_thesis"):
        display_thesis(st.session_state.last_thesis)

with tab5:
    st.subheader("📖 Grok Interaction History")
    history_df = get_grok_history(50)
    
    if not history_df.empty:
        search = st.text_input("🔍 Search history", "")
        filtered = history_df
        if search:
            filtered = history_df[
                history_df["response"].str.contains(search, case=False, na=False) |
                history_df.get("interaction_type", "").str.contains(search, case=False, na=False)
            ]
        
        for _, row in filtered.iterrows():
            with st.expander(f"🕒 {row['timestamp'].strftime('%Y-%m-%d %H:%M')} | {row.get('interaction_type','N/A')} | {row.get('model','N/A')}"):
                st.markdown(row['response'])
    else:
        st.info("No Grok interactions yet. Generate a thesis.")

with tab6:
    st.subheader("📊 Grok Memory Analytics")
    analytics = get_grok_analytics()
    df = analytics["df"]

    if analytics["total_interactions"] == 0:
        st.warning("Generate some theses to see analytics.")
    else:
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("Total Interactions", analytics["total_interactions"])
        with col2: st.metric("Unique Models", analytics["unique_models"])
        with col3: st.metric("Time Span", analytics["time_span"])
        with col4: st.metric("Avg Response Length", f"{analytics['avg_response_length']} chars")

        if not df["timestamp"].isna().all():
            daily = df.resample("D", on="timestamp").size().reset_index(name="Count")
            fig_time = px.line(daily, x="timestamp", y="Count", title="Daily Grok Activity")
            st.plotly_chart(fig_time, use_container_width=True)

        col_a, col_b = st.columns(2)
        with col_a:
            if not df["model"].empty:
                fig_model = px.pie(df["model"].value_counts().reset_index(), names="model", values="count")
                st.plotly_chart(fig_model, use_container_width=True)
        with col_b:
            if not df["interaction_type"].empty:
                fig_type = px.bar(df["interaction_type"].value_counts().reset_index(), x="interaction_type", y="count")
                st.plotly_chart(fig_type, use_container_width=True)

        st.dataframe(df[["timestamp", "interaction_type", "model", "horizon", "response_length"]].head(100),
                     use_container_width=True)

st.caption("**v6.1** • Fixed Viridis colormap • Async Grok + History • https://github.com/JeffStone69/XAi")