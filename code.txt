#!/usr/bin/env python3
"""
🌍 GeoSupply Short-Term Profit Predictor v5.3
Grok Memory Analytics Edition • Persistent DB Insights
Clean, Production-Ready, and Fully Functional
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

# ====================== CONFIG ======================
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "geosupply.db"

def setup_logging():
    logging.basicConfig(
        filename="geosupply_analyzer.log",
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

setup_logging()

# ====================== DATABASE ======================
def init_db():
    """Initialize or migrate the Grok interactions table."""
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
    # Safe migrations for missing columns
    for col in ["horizon", "model"]:
        try:
            conn.execute(f"ALTER TABLE grok_interactions ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
    conn.commit()
    conn.close()
    logging.info("Grok memory DB initialized/migrated")

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

def get_grok_history(limit: int = 100) -> pd.DataFrame:
    """Load Grok interactions from the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("""
            SELECT id, timestamp, interaction_type, model, horizon, response
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
        return pd.DataFrame(columns=["id", "timestamp", "interaction_type", "model", "horizon", "response"])

# ====================== GROK MEMORY ANALYTICS ======================
def get_grok_analytics() -> dict:
    df = get_grok_history(limit=1000)
    if df.empty:
        return {"total_interactions": 0, "df": pd.DataFrame()}

    return {
        "total_interactions": len(df),
        "unique_models": df["model"].nunique() if "model" in df.columns else 0,
        "time_span": f"{df['timestamp'].min().date()} → {df['timestamp'].max().date()}" if not df["timestamp"].isna().all() else "N/A",
        "most_common_type": df["interaction_type"].mode()[0] if not df["interaction_type"].empty else "N/A",
        "avg_response_length": int(df["response_length"].mean()) if "response_length" in df.columns else 0,
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

# ====================== MAIN APP ======================
init_db()

if "grok_api_key" not in st.session_state:
    st.session_state.grok_api_key = ""

st.set_page_config(page_title="GeoSupply v5.3", page_icon="🌍", layout="wide")

st.title("🌍 GeoSupply Short-Term Profit Predictor **v5.3**")
st.caption("**Grok Memory Analytics** • Persistent Self-Improvement • Clean & Fixed")

with st.sidebar:
    st.header("🔑 Grok API")
    api_key = st.text_input("Grok API Key (x.ai)", type="password", value=st.session_state.grok_api_key)
    if api_key:
        st.session_state.grok_api_key = api_key
        st.success("✅ API key saved")

    st.header("⚙️ Settings")
    horizon = st.selectbox("Signal Horizon", ["5d", "10d", "1mo"], index=0)
    model = st.selectbox("Grok Model", AVAILABLE_MODELS, index=0)

    if st.button("🔄 Refresh All Data", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption("Not financial advice.")

# Load data
if "raw_data" not in st.session_state:
    with st.spinner("Fetching market data..."):
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
        st.dataframe(
            summary_df.style.background_gradient(cmap="Viridis", subset=["Signal Score"]),
            use_container_width=True,
            hide_index=True
        )
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("📥 Full CSV", summary_df.to_csv(index=False), f"geosupply_{horizon}.csv", "text/csv")
        with col2:
            top10 = summary_df.head(10).copy()
            top10["Action"] = "BUY"
            top10["Exchange"] = top10["Ticker"].apply(lambda x: "ASX" if x.endswith(".AX") else "SMART")
            st.download_button("🚀 IBKR Top-10", top10[["Ticker", "Exchange", "Action"]].to_csv(index=False), "IBKR_top10.csv", "text/csv")
    else:
        st.warning("No data available. Refresh.")

with tab2:
    st.subheader("Price & Volume Charts (Top 8)")
    if not summary_df.empty:
        for ticker in summary_df.head(8)["Ticker"]:
            hist = raw_data.get(ticker)
            if hist is not None and not hist.empty:
                fig = make_subplots(specs=[[{"secondary_y": True}]])
                fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], name="Price", line=dict(color="#00ff9d")), secondary_y=False)
                fig.add_trace(go.Bar(x=hist.index, y=hist["Volume"], name="Volume", opacity=0.4), secondary_y=True)
                fig.update_layout(title=ticker, template="plotly_dark", height=340)
                st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("🔥 Sector Momentum Heatmap")
    if not summary_df.empty:
        sector_stats = summary_df.groupby("Sector")["Signal Score"].mean().round(2)
        fig = go.Figure(data=go.Heatmap(
            z=sector_stats.values.reshape(-1, 1),
            x=["Avg Signal"],
            y=sector_stats.index,
            colorscale="Viridis"
        ))
        fig.update_layout(title="Sector Heatmap", height=400, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.subheader("🤖 Grok 2-5 Day Thesis")
    if st.button("Generate Thesis + Self-Improvement Suggestions", type="primary"):
        if summary_df.empty:
            st.error("No signals available. Refresh data first.")
        else:
            with st.spinner("Generating thesis..."):
                prompt = f"""Analyze this GeoSupply leaderboard for short-term (2-5 day) opportunities (horizon: {horizon}):
{summary_df.head(12).to_string(index=False)}

Provide a concise thesis with 2-3 specific trade ideas."""
                thesis = call_grok_api(prompt, model, interaction_type="thesis", horizon=horizon)
                st.markdown(thesis)

with tab5:
    st.subheader("📖 Raw Grok Interaction History")
    history_df = get_grok_history(30)
    if not history_df.empty:
        for _, row in history_df.iterrows():
            with st.expander(f"{row['timestamp']} | {row.get('interaction_type', 'N/A')} | {row.get('model', 'N/A')}"):
                st.markdown(row['response'])
    else:
        st.info("No history yet. Generate a thesis.")

with tab6:
    st.subheader("📊 Grok Memory Analytics")
    st.caption("Deep insights from all stored Grok interactions in geosupply.db")

    analytics = get_grok_analytics()
    df = analytics["df"]

    if analytics["total_interactions"] == 0:
        st.warning("No Grok interactions found yet. Generate some theses to populate analytics.")
    else:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Interactions", analytics["total_interactions"])
        with col2:
            st.metric("Unique Models", analytics["unique_models"])
        with col3:
            st.metric("Time Span", analytics["time_span"])
        with col4:
            st.metric("Avg Response Length", f"{analytics['avg_response_length']} chars")

        # Charts
        if not df["timestamp"].isna().all():
            st.subheader("Interactions Over Time")
            daily = df.resample("D", on="timestamp").size().reset_index(name="Count")
            fig_time = px.line(daily, x="timestamp", y="Count", title="Daily Grok Activity")
            st.plotly_chart(fig_time, use_container_width=True)

        col_a, col_b = st.columns(2)
        with col_a:
            if "model" in df.columns and not df["model"].empty:
                st.subheader("Model Usage")
                fig_model = px.pie(df["model"].value_counts().reset_index(), names="model", values="count", title="By Model")
                st.plotly_chart(fig_model, use_container_width=True)

        with col_b:
            if "interaction_type" in df.columns and not df["interaction_type"].empty:
                st.subheader("Interaction Types")
                fig_type = px.bar(df["interaction_type"].value_counts().reset_index(), x="interaction_type", y="count", title="By Type")
                st.plotly_chart(fig_type, use_container_width=True)

        # Searchable table
        st.subheader("Searchable Responses")
        search = st.text_input("Filter by keyword")
        filtered = df
        if search:
            filtered = df[df["response"].str.contains(search, case=False, na=False) |
                          df.get("interaction_type", "").str.contains(search, case=False, na=False)]

        st.dataframe(filtered[["timestamp", "interaction_type", "model", "horizon", "response_length"]].head(50),
                     use_container_width=True)

        if st.button("Export Full Analytics CSV"):
            st.download_button("Download", df.to_csv(index=False), "grok_memory_analytics.csv", "text/csv")

st.caption("v5.3 • Grok Memory Analytics • https://github.com/JeffStone69/XAi • Fixed & Ready")
