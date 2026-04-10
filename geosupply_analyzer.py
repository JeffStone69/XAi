#!/usr/bin/env python3
"""
🌍 GeoSupply Short-Term Profit Predictor v9.3
Rebound Profit Edition + Full Grok Self-Improvement & History
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import hashlib
import sqlite3
import logging
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# ====================== CONFIG ======================
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "geosupply.db"
EXPORT_DIR = BASE_DIR / "Export"
EXPORT_DIR.mkdir(exist_ok=True)

AVAILABLE_MODELS = ["grok-4.20-reasoning", "grok-4.20-non-reasoning", "grok-4-1-fast-reasoning"]

SECTORS = {
    "Mining": ["BHP.AX", "RIO.AX", "FMG.AX", "S32.AX", "MIN.AX"],
    "Energy": ["STO.AX", "WDS.AX", "ORG.AX", "XOM", "CVX"],
    "Tech": ["NVDA", "AAPL", "TSLA", "AMD", "MSFT", "WTC.AX"],
    "Shipping": ["ZIM", "MATX", "SBLK"],
    "Renewable": ["NEE", "FSLR", "ENPH"],
}

ALL_TICKERS = sorted({t for lst in SECTORS.values() for t in lst})

# ====================== LOGGING & DB ======================
logging.basicConfig(filename="geosupply_analyzer.log", level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s", force=True)
logger = logging.getLogger("GeoSupply")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS grok_interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        interaction_type TEXT,
        model TEXT,
        prompt_hash TEXT,
        response TEXT,
        horizon TEXT,
        prompt TEXT,
        market_session TEXT,
        signal_score_avg REAL)""")
    conn.commit()
    conn.close()

def log_grok_interaction(interaction_type: str, model: str, prompt: str, response: str,
                         horizon: str = "", market_session: str = "", avg_score: float = 0.0):
    try:
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:16]
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""INSERT INTO grok_interactions 
            (interaction_type, model, prompt_hash, response, horizon, prompt, market_session, signal_score_avg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (interaction_type, model, prompt_hash, response, horizon, prompt, market_session, avg_score))
        conn.commit()
        conn.close()
        logger.info(f"Logged {interaction_type} interaction")
    except Exception as e:
        logger.error(f"DB log failed: {e}")

def get_grok_history(limit: int = 100) -> pd.DataFrame:
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM grok_interactions ORDER BY timestamp DESC LIMIT ?", conn, params=(limit,))
        conn.close()
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except Exception:
        return pd.DataFrame()

# ====================== SIGNAL ENGINE ======================
class SignalEngine:
    @staticmethod
    def calculate_rsi(close: pd.Series, period: int = 14) -> float:
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = -delta.clip(upper=0).rolling(period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1]) if len(rsi) > period else 50.0

    @staticmethod
    def calculate_macd_hist(close: pd.Series):
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        return float(macd.iloc[-1] - signal.iloc[-1])

    @staticmethod
    def compute_signals(raw_data: Dict[str, pd.DataFrame], horizon: str) -> pd.DataFrame:
        if not raw_data:
            return pd.DataFrame()
        
        lookback = {"5d": 5, "10d": 10, "1mo": 20}.get(horizon, 5)
        records = []
        
        for ticker, hist in raw_data.items():
            if len(hist) < lookback + 10: continue
            try:
                close = hist["Close"]
                volume = hist["Volume"]
                
                price_change = ((close.iloc[-1] - close.iloc[-(lookback + 1)]) / close.iloc[-(lookback + 1)]) * 100
                vol_avg = volume.mean()
                vol_spike = volume.iloc[-1] / vol_avg if vol_avg > 0 else 1.0
                rsi = SignalEngine.calculate_rsi(close)
                macd_hist = SignalEngine.calculate_macd_hist(close)

                rebound_score = round(
                    max(0, 40 - rsi) * 0.45 +
                    vol_spike * 0.30 +
                    max(0, -price_change) * 0.15 +
                    (15 if -10 < price_change < 3 else 0), 1
                )

                signal_score = round(rebound_score * 0.85 + (12 if macd_hist > 0 else 0), 1)

                sector = next((name for name, tks in SECTORS.items() if ticker in tks), "Other")

                records.append({
                    "Ticker": ticker,
                    "Sector": sector,
                    "Current Price": round(close.iloc[-1], 2),
                    f"{horizon} Change %": round(price_change, 1),
                    "Vol Spike": round(vol_spike, 2),
                    "RSI": round(rsi, 1),
                    "MACD Hist": round(macd_hist, 2),
                    "Rebound Score": rebound_score,
                    "Signal Score": signal_score,
                    "Last Updated": datetime.now().strftime("%H:%M:%S")
                })
            except Exception:
                continue
                
        df = pd.DataFrame(records)
        return df.sort_values("Rebound Score", ascending=False).reset_index(drop=True) if not df.empty else df

# ====================== GROK API ======================
def call_grok_api(prompt: str, model: str, temperature: float = 0.7,
                  interaction_type: Optional[str] = None, horizon: str = "", market_session: str = "") -> str:
    if not st.session_state.get("grok_api_key"):
        return "⚠️ Please enter your Grok API key in the sidebar to enable AI features."
    
    headers = {"Authorization": f"Bearer {st.session_state.grok_api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 2000
    }
    
    try:
        resp = requests.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            if interaction_type:
                avg_score = st.session_state.get("current_avg_score", 0.0)
                log_grok_interaction(interaction_type, model, prompt, content, horizon, market_session, avg_score)
            return content
        else:
            return f"❌ API Error ({resp.status_code})"
    except Exception as e:
        logger.error(f"Grok API failed: {e}")
        return f"❌ Grok connection error: {str(e)[:120]}"

# ====================== DATA FETCH ======================
@st.cache_data(ttl=90, show_spinner=False)
def fetch_raw_market_data(tickers: List[str]):
    try:
        raw = yf.download(tickers, period="1mo", interval="1d", group_by="ticker",
                          auto_adjust=True, threads=True, progress=False)
        result = {}
        for t in tickers:
            if t in raw.columns.get_level_values(0):
                df = raw[t].dropna(how="all")
                if not df.empty and {"Close", "Volume"}.issubset(df.columns):
                    result[t] = df
        return result
    except Exception as e:
        logger.error(f"yfinance failed: {e}")
        return {}

# ====================== UI HELPERS ======================
def display_thesis(thesis: str, suffix: str = ""):
    if not thesis: return
    with st.container(border=True):
        st.markdown("### 📝 Grok Thesis")
        st.markdown(thesis)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📋 Copy", key=f"copy_{abs(hash(thesis))%100000}_{suffix}"):
                st.toast("✅ Copied to clipboard")
        with c2:
            if st.button("💾 Save to History", type="primary", key=f"save_{abs(hash(thesis))%100000}_{suffix}"):
                st.success("✅ Saved to Grok History")

# ====================== MAIN APP ======================
def main():
    init_db()
    
    if "grok_api_key" not in st.session_state:
        st.session_state.grok_api_key = ""
    if "raw_data" not in st.session_state:
        st.session_state.raw_data = {}
    if "last_thesis" not in st.session_state:
        st.session_state.last_thesis = None
    if "last_market_session" not in st.session_state:
        st.session_state.last_market_session = None

    st.set_page_config(page_title="GeoSupply v9.3", page_icon="🌍", layout="wide")
    st.title("🌍 GeoSupply v9.3")
    st.caption("**Rebound Profit Predictor** • Full Grok Self-Improvement + History")

    with st.sidebar:
        st.header("🔑 Grok API")
        key = st.text_input("Grok API Key", type="password", value=st.session_state.grok_api_key)
        if key and key != st.session_state.grok_api_key:
            st.session_state.grok_api_key = key
            st.success("✅ API Key saved")

        st.header("⚙️ Settings")
        horizon = st.selectbox("Signal Horizon", ["5d", "10d", "1mo"], index=0)
        market_session = st.selectbox("Market Session", 
            ["Regular Hours (ASX+US)", "ASX Only", "US Only", "24h Global"], index=0)
        model = st.selectbox("Grok Model", AVAILABLE_MODELS, index=0)
        temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.1)

        st.subheader("Custom Tickers")
        custom = st.text_input("Add tickers (comma separated)", "NVDA, TSLA, AAPL, AMD")
        custom_tickers = [t.strip().upper() for t in custom.split(",") if t.strip()]

        if st.button("🔄 Fetch Latest Market Data", type="primary", use_container_width=True):
            st.session_state.last_market_session = f"{market_session} @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            st.cache_data.clear()
            all_t = list(set(ALL_TICKERS + custom_tickers))
            st.session_state.raw_data = fetch_raw_market_data(all_t)
            st.success("✅ Market data updated")
            st.rerun()

    # Auto-fetch reliable tickers on first load
    if not st.session_state.raw_data:
        with st.spinner("Loading initial market data..."):
            st.session_state.raw_data = fetch_raw_market_data(ALL_TICKERS + ["NVDA", "TSLA", "AAPL", "AMD"])

    raw_data = st.session_state.raw_data
    summary_df = SignalEngine.compute_signals(raw_data, horizon)

    # ====================== TABS ======================
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🚀 Top 5 Rebound", "📈 Full Leaderboard", "📊 Charts",
        "🔥 Heatmap", "🤖 Grok Self-Improvement", "📊 Analytics"
    ])

    with tab1:
        st.subheader(f"🔥 Top 5 Real-Time Rebound Profit Opportunities ({horizon})")
        st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S AEST')}")
        if summary_df.empty:
            st.warning("No data available. Click 'Fetch Latest Market Data'.")
        else:
            top5 = summary_df.head(5).copy()
            st.dataframe(
                top5.style.background_gradient(subset=["Rebound Score"], cmap="RdYlGn")
                    .format({"Current Price": "${:.2f}", "Rebound Score": "{:.1f}"}),
                use_container_width=True, hide_index=True
            )

    with tab2:
        st.subheader("Full Leaderboard")
        if not summary_df.empty:
            st.dataframe(summary_df.style.background_gradient(subset=["Rebound Score", "Signal Score"], cmap="viridis"),
                         use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("Interactive Charts")
        if not summary_df.empty:
            ticker = st.selectbox("Select ticker", summary_df["Ticker"].tolist())
            if ticker in raw_data:
                hist = raw_data[ticker]
                fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.55, 0.2, 0.25])
                fig.add_trace(go.Candlestick(x=hist.index, open=hist.get("Open"), high=hist.get("High"),
                                             low=hist.get("Low"), close=hist["Close"]), row=1, col=1)
                fig.add_trace(go.Bar(x=hist.index, y=hist["Volume"]), row=2, col=1)
                fig.update_layout(height=700, template="plotly_dark", title=f"{ticker} Technical Analysis")
                st.plotly_chart(fig, use_container_width=True)

    with tab4:
        st.subheader("Sector Heatmap")
        if not summary_df.empty:
            pivot = summary_df.pivot_table(values="Rebound Score", index="Sector", aggfunc="mean").round(1)
            st.plotly_chart(px.imshow(pivot, text_auto=True, color_continuous_scale="viridis"), use_container_width=True)

    with tab5:
        st.subheader("🤖 Grok Self-Improvement & History")
        
        if st.button("🚀 Run Self-Improvement Cycle", type="primary", use_container_width=True):
            if summary_df.empty:
                st.warning("No data to analyze yet.")
            else:
                ctx = f"Current top signals:\n{summary_df.head(12).to_string(index=False)}\n\n"
                prompt = ctx + """Analyze the current rebound opportunities.
                1. Suggest 2-3 high-conviction trades.
                2. Provide self-improvement suggestions for the signal engine (weights, new indicators, etc.).
                3. Rate overall system performance."""
                
                with st.spinner("Grok is analyzing and improving the system..."):
                    thesis = call_grok_api(prompt, model, temperature, "self_improvement", horizon, st.session_state.last_market_session)
                    st.session_state.last_thesis = thesis
                    display_thesis(thesis, "self_improve")

        if st.session_state.get("last_thesis"):
            display_thesis(st.session_state.last_thesis, "last")

        st.subheader("📖 Grok Interaction History")
        history_df = get_grok_history(50)
        if not history_df.empty:
            for _, row in history_df.iterrows():
                with st.expander(f"{row['timestamp']} | {row.get('interaction_type', '—')}"):
                    st.markdown(row['response'])
        else:
            st.info("No Grok interactions yet. Run a Self-Improvement Cycle to begin.")

    with tab6:
        st.subheader("Advanced Analytics")
        if not summary_df.empty:
            st.plotly_chart(px.scatter(summary_df, x="Vol Spike", y="Rebound Score", color="Sector",
                                       hover_name="Ticker", title="Volume Spike vs Rebound Potential"), use_container_width=True)

    st.caption("v9.3 • Rebound Profit + Full Grok Self-Improvement & History • Production Ready")

if __name__ == "__main__":
    main()