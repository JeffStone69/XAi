#!/usr/bin/env python3
"""
🌍 GeoSupply Short-Term Profit Predictor v2.1
Optimized & Fixed by Grok (xAI)
"""

import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import logging
import numpy as np                     # ← FIXED: Added this import
from typing import List, Dict
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="GeoSupply Short-Term Profit Predictor v2.1",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ====================== SECTOR DEFINITIONS ======================
ASX_MINING = ["BHP.AX", "RIO.AX", "FMG.AX", "S32.AX", "MIN.AX"]
ASX_SHIPPING = ["QUB.AX", "TCL.AX", "ASX.AX"]
ASX_ENERGY = ["STO.AX", "WDS.AX", "ORG.AX", "WHC.AX", "BPT.AX"]
ASX_TECH = ["WTC.AX", "XRO.AX", "TNE.AX", "NXT.AX", "REA.AX", "360.AX", "PME.AX"]
ASX_RENEW = ["ORG.AX", "AGL.AX", "IGO.AX", "IFT.AX", "MCY.AX", "CEN.AX", "MEZ.AX", "JNS.AX"]

US_MINING = ["FCX", "NEM", "VALE", "SCCO", "GOLD", "AEM"]
US_SHIPPING = ["ZIM", "MATX", "SBLK", "DAC", "CMRE"]
US_ENERGY = ["XOM", "CVX", "COP", "OXY", "CCJ"]
US_TECH = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMD", "TSLA"]
US_RENEW = ["NEE", "BEPC", "CWEN", "FSLR", "ENPH"]

SECTORS: Dict[str, List[str]] = {
    "Mining": ASX_MINING + US_MINING,
    "Shipping": ASX_SHIPPING + US_SHIPPING,
    "Energy": ASX_ENERGY + US_ENERGY,
    "Tech": ASX_TECH + US_TECH,
    "Renewable": ASX_RENEW + US_RENEW,
}

ALL_TICKERS = list(dict.fromkeys(
    ASX_MINING + ASX_SHIPPING + ASX_ENERGY + ASX_TECH + ASX_RENEW +
    US_MINING + US_SHIPPING + US_ENERGY + US_TECH + US_RENEW
))

API_BASE = "https://api.x.ai/v1"
AVAILABLE_MODELS = [
    "grok-4.20-reasoning",
    "grok-4.20-non-reasoning",
    "grok-4.20-multi-agent-0309",
    "grok-4-1-fast-reasoning",
    "grok-4-1-fast-non-reasoning"
]

logging.basicConfig(
    filename="geosupply_analyzer.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# ====================== GROK API ======================
def call_grok_api(prompt: str, model: str, temperature: float = 0.6) -> str:
    if not st.session_state.get("grok_api_key"):
        return "⚠️ Please enter your Grok API key in the sidebar."
    headers = {"Authorization": f"Bearer {st.session_state.grok_api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": temperature, "max_tokens": 1200}
    try:
        resp = requests.post(f"{API_BASE}/chat/completions", headers=headers, json=payload, timeout=75)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logging.error(f"Grok API error: {e}")
        return f"❌ Grok API error: {str(e)[:150]}"

# ====================== BATCH DATA FETCH ======================
@st.cache_data(ttl=180, show_spinner=False)
def fetch_raw_market_data(tickers: List[str]) -> Dict[str, pd.DataFrame]:
    try:
        raw = yf.download(tickers=tickers, period="1mo", interval="1d", group_by="ticker",
                          auto_adjust=True, threads=True, progress=False)
        if raw.empty:
            return {}

        ticker_data = {}
        if len(tickers) == 1:
            ticker_data[tickers[0]] = raw.dropna(how="all")
        else:
            for ticker in tickers:
                if ticker in raw.columns.get_level_values(0):
                    df = raw[ticker].dropna(how="all")
                    if not df.empty and "Close" in df.columns:
                        ticker_data[ticker] = df
        return ticker_data
    except Exception as e:
        logging.error(f"Batch download failed: {e}")
        return {}

# ====================== SIGNAL CALCULATION (FIXED) ======================
@st.cache_data(ttl=180, show_spinner=False)
def compute_profit_signals(raw_data: Dict[str, pd.DataFrame], horizon: str) -> pd.DataFrame:
    if not raw_data:
        return pd.DataFrame()

    lookback_map = {"5d": 5, "10d": 10, "1mo": 20}
    lookback = lookback_map.get(horizon, 5)

    records = []
    for ticker, hist in raw_data.items():
        if hist.empty or len(hist) < lookback + 1 or "Close" not in hist.columns:
            continue

        try:
            current_price = float(hist["Close"].iloc[-1])
            past_price = float(hist["Close"].iloc[-(lookback + 1)])
            price_change_pct = ((current_price - past_price) / past_price) * 100

            volume_avg = float(hist["Volume"].mean())
            recent_vol = float(hist["Volume"].iloc[-1])
            vol_spike = recent_vol / volume_avg if volume_avg > 0 else 1.0

            daily_returns = hist["Close"].pct_change().dropna()
            volatility_pct = float(daily_returns.std() * 100) if not daily_returns.empty else 0.0

            # Enhanced risk-adjusted signal (no extra np usage that caused crash)
            momentum = price_change_pct / 100
            vol_factor = min(volume_avg / 1_000_000, 12.0)
            risk_adjust = 1.0 / (1.0 + volatility_pct / 8.0) if volatility_pct > 0 else 1.0
            signal_score = round(momentum * vol_factor * vol_spike * risk_adjust * 12.0, 3)

            sector = next((name for name, tks in SECTORS.items() if ticker in tks), "Other")

            records.append({
                "Ticker": ticker,
                "Current Price": round(current_price, 2),
                f"{horizon} Change %": round(price_change_pct, 1),
                "Avg Vol (M)": round(volume_avg / 1_000_000, 1),
                "Vol Spike": round(vol_spike, 2),
                "Volatility %": round(volatility_pct, 1),
                "Signal Score": signal_score,
                "Sector": sector
            })
        except Exception as e:
            logging.warning(f"Error processing {ticker}: {e}")
            continue

    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values("Signal Score", ascending=False).reset_index(drop=True)
    return df

# ====================== IBKR EXPORT ======================
def create_ibkr_watchlist_csv(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    top10 = df.head(10).copy()
    top10["Action"] = "BUY"
    top10["Quantity"] = ""
    top10["Exchange"] = top10["Ticker"].apply(lambda x: "ASX" if x.endswith(".AX") else "SMART")
    ibkr_df = top10[["Ticker", "Exchange", "Action", "Current Price"]].rename(
        columns={"Ticker": "Symbol", "Current Price": "Last Price"}
    )
    return ibkr_df.to_csv(index=False)

# ====================== MAIN APP ======================
if "grok_api_key" not in st.session_state:
    st.session_state.grok_api_key = ""

st.title("🌍 GeoSupply Short-Term Profit Predictor **v2.1**")
st.caption("**Fixed • Batch-optimized • Risk-adjusted signals** | 2-5 Day Geo-Supply Chain Alpha")

with st.sidebar:
    st.header("🔑 Grok API")
    api_key = st.text_input("Grok API Key (x.ai)", type="password", value=st.session_state.grok_api_key)
    if api_key:
        st.session_state.grok_api_key = api_key
        st.success("✅ API key saved")

    st.header("⚙️ Settings")
    horizon = st.selectbox("Signal Horizon", ["5d", "10d", "1mo"], index=0)
    model = st.selectbox("Grok Model", AVAILABLE_MODELS, index=0)

    st.divider()
    if st.button("🔄 Refresh All Data & Signals", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption("**Not financial advice.**")

# Tabs
tab1, tab2, tab3 = st.tabs(["📈 Leaderboard", "📊 Charts", "🤖 Grok Thesis"])

if "raw_data" not in st.session_state:
    with st.spinner("Fetching market data..."):
        st.session_state.raw_data = fetch_raw_market_data(ALL_TICKERS)

raw_data = st.session_state.raw_data

with tab1:
    st.subheader(f"🔥 Profit Signal Leaderboard ({horizon})")
    summary_df = compute_profit_signals(raw_data, horizon)

    if not summary_df.empty:
        st.dataframe(
            summary_df.style.background_gradient(cmap="RdYlGn", subset=["Signal Score"]),
            use_container_width=True,
            hide_index=True
        )

        col1, col2 = st.columns(2)
        with col1:
            st.download_button("📥 Full Watchlist CSV", data=summary_df.to_csv(index=False),
                               file_name=f"geosupply_{horizon}.csv", mime="text/csv")
        with col2:
            ibkr_csv = create_ibkr_watchlist_csv(summary_df)
            st.download_button("🚀 IBKR Top-10 Export", data=ibkr_csv,
                               file_name=f"IBKR_GeoSupply_Top10_{horizon}.csv", mime="text/csv")

        st.subheader("🚀 Top 5 Trades")
        cols = st.columns(5)
        for i, row in summary_df.head(5).iterrows():
            with cols[i]:
                st.metric(label=row['Ticker'], value=f"${row['Current Price']}",
                          delta=f"{row[f'{horizon} Change %']}%")
                st.caption(f"Signal: {row['Signal Score']} | {row['Sector']}")
    else:
        st.error("No data. Try refreshing.")

with tab2:
    st.subheader("Price & Volume Charts")
    if not summary_df.empty:
        for ticker in summary_df.head(5)["Ticker"]:
            hist = raw_data.get(ticker)
            if hist is not None and not hist.empty:
                fig = make_subplots(specs=[[{"secondary_y": True}]])
                fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], name="Price", line=dict(color="#00ff9d")), secondary_y=False)
                fig.add_trace(go.Bar(x=hist.index, y=hist["Volume"], name="Volume", opacity=0.4, marker_color="#00ff9d"), secondary_y=True)
                fig.update_layout(title=f"{ticker} — {horizon} View", height=340, template="plotly_dark")
                st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("🤖 Grok 2-5 Day Thesis")
    if st.button("Generate Thesis", type="primary"):
        if not st.session_state.get("grok_api_key"):
            st.error("Enter Grok API key first.")
        else:
            with st.spinner("Analyzing..."):
                prompt = f"""Current leaderboard:\n{summary_df.head(12).to_string(index=False)}\n\nGive a concise 3-bullet 2-5 day thesis."""
                response = call_grok_api(prompt, model)
                st.markdown(response)

st.divider()
st.caption("GeoSupply Analyzer v2.1 • Fixed numpy import • Self-improving ready")