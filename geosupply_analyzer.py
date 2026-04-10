#!/usr/bin/env python3
"""
🌍 GeoSupply Short-Term Profit Predictor v0.94
Rebound Profit Edition • Improved Market Selection + Granular Timeframes
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

ALL_ASX_TICKERS = [t for lst in SECTORS.values() for t in lst if t.endswith(".AX")]
ALL_US_TICKERS = [t for lst in SECTORS.values() for t in lst if not t.endswith(".AX")]

# ====================== LOGGING & DB ======================
logging.basicConfig(filename="geosupply_analyzer.log", level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s", force=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS grok_interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        interaction_type TEXT, model TEXT, prompt_hash TEXT,
        response TEXT, horizon TEXT, prompt TEXT, market_session TEXT,
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
    except Exception as e:
        logging.error(f"DB log failed: {e}")

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
    def compute_signals(raw_data: Dict[str, pd.DataFrame], horizon_days: int) -> pd.DataFrame:
        if not raw_data:
            return pd.DataFrame()
        
        records = []
        for ticker, hist in raw_data.items():
            if len(hist) < horizon_days + 10: 
                continue
            try:
                close = hist["Close"]
                volume = hist["Volume"]
                
                price_change = ((close.iloc[-1] - close.iloc[-(horizon_days + 1)]) / close.iloc[-(horizon_days + 1)]) * 100
                vol_avg = volume.mean()
                vol_spike = volume.iloc[-1] / vol_avg if vol_avg > 0 else 1.0
                rsi = SignalEngine.calculate_rsi(close)
                macd_hist = SignalEngine.calculate_macd_hist(close)

                rebound_score = round(
                    max(0, 40 - rsi) * 0.45 +
                    vol_spike * 0.30 +
                    max(0, -price_change) * 0.15 +
                    (15 if -10 < price_change < 4 else 0), 1
                )

                signal_score = round(rebound_score * 0.85 + (12 if macd_hist > 0 else 0), 1)

                sector = next((name for name, tks in SECTORS.items() if ticker in tks), "Other")

                records.append({
                    "Ticker": ticker,
                    "Sector": sector,
                    "Current Price": round(close.iloc[-1], 2),
                    f"{horizon_days}d Change %": round(price_change, 1),
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
        return "⚠️ Enter Grok API key in sidebar for AI features."
    
    headers = {"Authorization": f"Bearer {st.session_state.grok_api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": temperature, "max_tokens": 2000}
    
    try:
        resp = requests.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            if interaction_type:
                avg_score = st.session_state.get("current_avg_score", 0.0)
                log_grok_interaction(interaction_type, model, prompt, content, horizon, market_session, avg_score)
            return content
        return f"❌ API Error ({resp.status_code})"
    except Exception as e:
        return f"❌ Grok error: {str(e)[:150]}"

# ====================== DATA FETCH ======================
@st.cache_data(ttl=90)
def fetch_raw_market_data(tickers: List[str]):
    try:
        raw = yf.download(tickers, period="3mo", interval="1d", group_by="ticker",
                          auto_adjust=True, threads=True, progress=False)
        result = {}
        for t in tickers:
            if t in raw.columns.get_level_values(0):
                df = raw[t].dropna(how="all")
                if not df.empty and {"Close", "Volume"}.issubset(df.columns):
                    result[t] = df
        return result
    except Exception as e:
        st.error(f"Data fetch failed: {str(e)[:100]}")
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
                st.toast("✅ Copied")
        with c2:
            if st.button("💾 Save", type="primary", key=f"save_{abs(hash(thesis))%100000}_{suffix}"):
                st.success("✅ Saved to History")

# ====================== MAIN ======================
def main():
    init_db()
    
    if "grok_api_key" not in st.session_state: st.session_state.grok_api_key = ""
    if "raw_data" not in st.session_state: st.session_state.raw_data = {}
    if "last_thesis" not in st.session_state: st.session_state.last_thesis = None

    st.set_page_config(page_title="GeoSupply v0.94", page_icon="🌍", layout="wide")
    st.title("🌍 GeoSupply v0.94")
    st.caption("Rebound Profit Predictor • Improved Market Selection & Granular Timeframes")

    with st.sidebar:
        st.header("🔑 Grok API")
        key = st.text_input("Grok API Key", type="password", value=st.session_state.grok_api_key)
        if key and key != st.session_state.grok_api_key:
            st.session_state.grok_api_key = key
            st.success("✅ Key saved")

        st.header("⚙️ Market & Time Settings")
        
        market_mode = st.selectbox(
            "Market Selection",
            ["ASX + US", "ASX Only", "US Only", "24h Global"],
            index=0
        )
        
        timeframe = st.selectbox(
            "Data Timeframe (Lookback)",
            ["1d", "5d", "10d", "1mo", "3mo"],
            index=2  # default 10d
        )
        
        # Convert to days for calculation
        days_map = {"1d": 1, "5d": 5, "10d": 10, "1mo": 20, "3mo": 60}
        horizon_days = days_map[timeframe]

        st.subheader("Custom Tickers")
        custom_input = st.text_input("Add extra tickers", "NVDA, TSLA, AAPL, AMD")
        custom_tickers = [t.strip().upper() for t in custom_input.split(",") if t.strip()]

        if st.button("🔄 Fetch Latest Market Data", type="primary", use_container_width=True):
            st.cache_data.clear()
            
            if market_mode == "ASX Only":
                base_tickers = ALL_ASX_TICKERS
            elif market_mode == "US Only":
                base_tickers = ALL_US_TICKERS
            else:
                base_tickers = ALL_ASX_TICKERS + ALL_US_TICKERS
                
            all_tickers = list(set(base_tickers + custom_tickers))
            st.session_state.raw_data = fetch_raw_market_data(all_tickers)
            st.success(f"✅ Fetched data for {len(st.session_state.raw_data)} tickers ({market_mode})")
            st.rerun()

    # Auto-fetch on first load
    if not st.session_state.raw_data:
        with st.spinner("Loading initial market data..."):
            st.session_state.raw_data = fetch_raw_market_data(ALL_US_TICKERS + ["BHP.AX", "RIO.AX"])

    raw_data = st.session_state.raw_data
    summary_df = SignalEngine.compute_signals(raw_data, horizon_days)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🚀 Top 5 Rebound", "📈 Full Leaderboard", "📊 Charts",
        "🔥 Heatmap", "🤖 Grok Self-Improvement", "📊 Analytics"
    ])

    with tab1:
        st.subheader(f"🔥 Top 5 Real-Time Rebound Opportunities ({timeframe})")
        st.caption(f"Market: {market_mode} | Last updated: {datetime.now().strftime('%H:%M:%S')}")
        if summary_df.empty:
            st.warning("No data loaded. Please click 'Fetch Latest Market Data'.")
        else:
            top5 = summary_df.head(5)
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
                st.warning("No data to analyze.")
            else:
                prompt = f"""Current top rebound opportunities ({timeframe} - {market_mode}):
{summary_df.head(12).to_string(index=False)}

Provide 2-3 high-conviction trades and suggest improvements to the rebound scoring logic."""
                with st.spinner("Grok analyzing and self-improving..."):
                    thesis = call_grok_api(prompt, "grok-4.20-reasoning", 0.7, "self_improvement", timeframe, market_mode)
                    st.session_state.last_thesis = thesis
                    display_thesis(thesis, "self")

        if st.session_state.get("last_thesis"):
            display_thesis(st.session_state.last_thesis, "last")

        st.subheader("Interaction History")
        history = get_grok_history(40)
        if not history.empty:
            for _, row in history.iterrows():
                with st.expander(f"{row['timestamp']} | {row.get('interaction_type','')}"):
                    st.markdown(row['response'])

    with tab6:
        st.subheader("Analytics")
        if not summary_df.empty:
            st.plotly_chart(px.scatter(summary_df, x="Vol Spike", y="Rebound Score", color="Sector",
                                       hover_name="Ticker", title="Volume vs Rebound Potential"), use_container_width=True)

    st.caption("v0.94 • Improved Market Selection + Granular Timeframes")

if __name__ == "__main__":
    main()