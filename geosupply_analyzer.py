#!/usr/bin/env python3
"""
🌍 GeoSupply Short-Term Profit Predictor v2.4
Added fully functional Self-Improvement tab.
"""

import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import logging
from datetime import datetime
import numpy as np
import inspect

st.set_page_config(page_title="GeoSupply v2.4", page_icon="🌍", layout="wide")

# ====================== CONFIG ======================
SECTORS = {
    "Mining": ["BHP.AX","RIO.AX","FMG.AX","FCX","NEM","VALE","SCCO"],
    "Shipping": ["ZIM","MATX","SBLK","QUB.AX","DAC"],
    "Energy": ["XOM","CVX","STO.AX","WHC.AX","CCJ","COP"],
    "Renewable": ["NEE","FSLR","ENPH","IGO.AX"],
    "Tech": ["NVDA","TSLA","WTC.AX","XRO.AX","AMD"]
}
ALL_TICKERS = list(dict.fromkeys(sum(SECTORS.values(), [])))

logging.basicConfig(filename="geosupply.log", level=logging.INFO)

# ====================== DATA ======================
@st.cache_data(ttl=180)
def fetch_data(tickers):
    try:
        data = yf.Tickers(tickers).download(period="1mo", group_by="ticker", auto_adjust=True, threads=True)
        return {ticker: data[ticker].dropna(how="all") for ticker in tickers if not data[ticker].empty}
    except Exception as e:
        st.error(f"Fetch error: {e}")
        return {}

# ====================== SIGNALS ======================
@st.cache_data(ttl=180)
def compute_signals(raw_data, horizon="5d", selected_sectors=None):
    lookback = {"5d":5, "10d":10, "1mo":20}.get(horizon, 5)
    records = []
    for ticker, df in raw_data.items():
        if len(df) < lookback + 5 or "Close" not in df.columns: continue
        try:
            close = df["Close"]
            ret = close.pct_change().dropna()
            price_change = (close.iloc[-1] / close.iloc[-(lookback+1)] - 1) * 100
            vol_spike = df["Volume"].iloc[-1] / df["Volume"].mean() if df["Volume"].mean() > 0 else 1.0
            rsi = 100 - (100 / (1 + (ret[ret>0].mean() / -ret[ret<0].mean()))) if len(ret)>0 else 50
            vol = ret.std() * 100

            score = round(price_change * min(vol_spike, 3.0) * (rsi/50) / (1 + vol/15), 2)
            sector = next((s for s,tks in SECTORS.items() if ticker in tks), "Other")

            if selected_sectors and sector not in selected_sectors: continue

            records.append({
                "Ticker": ticker, "Price": round(close.iloc[-1],2),
                f"{horizon}%": round(price_change,1), "Vol Spike": round(vol_spike,2),
                "RSI": round(rsi,1), "Signal": score, "Sector": sector
            })
        except: continue

    df = pd.DataFrame(records)
    if not df.empty:
        df["Signal"] = round((df["Signal"] - df["Signal"].mean()) / df["Signal"].std(), 3)
        df = df.sort_values("Signal", ascending=False).reset_index(drop=True)
    return df

# ====================== GROK ======================
def call_grok(prompt, model="grok-4"):
    if not st.session_state.get("api_key"):
        return "Please enter your xAI Grok API key in the sidebar."
    try:
        r = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {st.session_state.api_key}"},
            json={"model": model, "messages": [{"role":"user","content":prompt}], "temperature":0.7, "max_tokens":1200},
            timeout=45
        )
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"API Error: {str(e)[:100]}"

# ====================== UI ======================
if "api_key" not in st.session_state: st.session_state.api_key = ""

st.title("GeoSupply Short-Term Profit Predictor **v2.4**")
st.caption("Self-Improving • RSI + Z-Score Signals • Real Geo-Supply Edge")

with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input("xAI Grok API Key", type="password", value=st.session_state.api_key)
    if api_key: st.session_state.api_key = api_key

    horizon = st.selectbox("Horizon", ["5d","10d","1mo"], index=0)
    selected_sectors = st.multiselect("Sectors", options=SECTORS.keys(), default=list(SECTORS.keys()))
    model = st.selectbox("Grok Model", ["grok-4","grok-beta"], index=0)

    if st.button("Refresh Data", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

raw_data = fetch_data(ALL_TICKERS)
df = compute_signals(raw_data, horizon, selected_sectors)

tab1, tab2, tab3, tab4 = st.tabs(["Leaderboard", "Charts", "Grok Thesis", "Self Improvement"])

with tab1:
    st.subheader(f"Leaderboard — {horizon} | {datetime.now().strftime('%H:%M')}")
    if not df.empty:
        st.dataframe(df.style.background_gradient(subset=["Signal"], cmap="RdYlGn"), use_container_width=True, hide_index=True)
        st.download_button("Export CSV", df.to_csv(index=False), f"geosupply_{horizon}.csv", use_container_width=True)
    else:
        st.error("No data available.")

with tab2:
    st.subheader("Top 5 Charts")
    for ticker in df.head(5)["Ticker"].values if not df.empty else []:
        hist = raw_data.get(ticker)
        if hist is not None and not hist.empty:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], name="Price", line=dict(color="#00ff9d")))
            fig.add_trace(go.Bar(x=hist.index, y=hist["Volume"], name="Volume", opacity=0.35), secondary_y=True)
            fig.update_layout(title=ticker, template="plotly_dark", height=320)
            st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("Grok 2-5 Day Thesis")
    if st.button("Generate Thesis", type="primary"):
        with st.spinner("Calling Grok..."):
            prompt = f"""Analyze this geo-supply leaderboard for 2-5 day edge.\n{df.head(12).to_string(index=False)}\nReturn exactly 3 high-signal bullets focusing on supply tension and catalysts."""
            response = call_grok(prompt, model)
            st.markdown(response)

with tab4:
    st.subheader("Self Improvement")
    st.caption("Let Grok review and improve this entire script")
    
    with st.expander("Current Script Source", expanded=False):
        with open(__file__, "r", encoding="utf-8") as f:
            current_code = f.read()
        st.code(current_code, language="python")
    
    improvement_request = st.text_area("Your improvement instructions (optional)", 
                                       "Make the signal calculation more sophisticated, improve UI, add new features, and increase robustness.", height=100)
    
    if st.button("Ask Grok to Improve This Script", type="primary"):
        with st.spinner("Sending full script to Grok for self-improvement analysis..."):
            prompt = f"""You are an expert Python/Streamlit quant developer.
Here is the complete current script:

```python
{current_code}
Please analyze it and provide a significantly improved version (v2.5) with your changes clearly explained at the top. Focus on: {improvement_request} Return ONLY the full improved Python script wrapped in a single ```python code block."""
        response = call_grok(prompt, model)
        st.subheader("Grok's Improved Version")
        st.code(response, language="python")
        st.success("Copy the code above to create the next version. This script is now truly self-improving.")
st.caption("v2.4 • Added real Self-Improvement tab • Merged best logic from v2.1 • Ready for continuous evolution")
1