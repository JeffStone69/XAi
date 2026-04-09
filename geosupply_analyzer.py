#!/usr/bin/env python3
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import logging
import json
from typing import List
import warnings

warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="GeoSupply Short-Term Profit Predictor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ====================== SECTOR TICKERS ======================
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

ALL_ASX = list(dict.fromkeys(ASX_MINING + ASX_SHIPPING + ASX_ENERGY + ASX_TECH + ASX_RENEW))
ALL_US = list(dict.fromkeys(US_MINING + US_SHIPPING + US_ENERGY + US_TECH + US_RENEW))
ALL_TICKERS = ALL_ASX + ALL_US

API_BASE = "https://api.x.ai/v1"
AVAILABLE_MODELS = [
    "grok-4.20-reasoning",
    "grok-4.20-non-reasoning",
    "grok-4.20-multi-agent-0309",
    "grok-4-1-fast-reasoning",
    "grok-4-1-fast-non-reasoning"
]

logging.basicConfig(
    filename="geosupply_errors.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ====================== GROK API ======================
def call_grok_api(prompt: str, model: str, temperature: float = 0.65) -> str:
    if not st.session_state.get("grok_api_key"):
        return "Please enter your Grok API key in the sidebar."
    headers = {"Authorization": f"Bearer {st.session_state.grok_api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": temperature}
    try:
        resp = requests.post(f"{API_BASE}/chat/completions", headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logging.error(f"Grok API error: {e}")
        return f"Grok API error: {str(e)}"

# ====================== SHORT-TERM PROFIT SIGNALS ======================
@st.cache_data(ttl=300)
def fetch_profit_signals(tickers: List[str], period: str = "5d") -> pd.DataFrame:
    data = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period if period != "5d" else "1mo")
            if hist.empty or len(hist) < 3:
                continue
            current_price = hist['Close'].iloc[-1]
            
            # 5-day momentum
            if len(hist) >= 5:
                five_d_ago = hist['Close'].iloc[-6] if len(hist) > 5 else hist['Close'].iloc[0]
                price_change = ((current_price - five_d_ago) / five_d_ago) * 100
            else:
                price_change = ((current_price - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100

            volume_avg = hist['Volume'].mean()
            signal_score = (price_change / 100) * (volume_avg / 1_000_000) * 8.5
            
            data.append({
                "Ticker": ticker,
                "Current Price": round(current_price, 2),
                "5d Change %": round(price_change, 1),
                "Avg Daily Vol (M)": round(volume_avg / 1e6, 1),
                "Signal Score": round(signal_score, 3),
                "Sector": next((s for s, t in [
                    ("Mining", ASX_MINING + US_MINING),
                    ("Shipping", ASX_SHIPPING + US_SHIPPING),
                    ("Energy", ASX_ENERGY + US_ENERGY),
                    ("Tech", ASX_TECH + US_TECH),
                    ("Renewable", ASX_RENEW + US_RENEW)
                ] if ticker in t), "Other")
            })
        except Exception as e:
            logging.error(f"Error fetching {ticker}: {e}")
            continue
    
    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values("Signal Score", ascending=False).reset_index(drop=True)
    return df

# ====================== IBKR WATCHLIST EXPORT ======================
def create_ibkr_watchlist_csv(df: pd.DataFrame) -> str:
    """Creates IBKR-compatible CSV for top signals (highest probability trades)"""
    top10 = df.head(10).copy()
    top10["Action"] = "BUY"
    top10["Quantity"] = ""  # user can fill in TWS
    top10["Exchange"] = top10["Ticker"].apply(lambda x: "ASX" if x.endswith(".AX") else "SMART")
    
    ibkr_df = top10[["Ticker", "Exchange", "Action", "Current Price"]].rename(columns={
        "Ticker": "Symbol",
        "Current Price": "Last Price"
    })
    return ibkr_df.to_csv(index=False)

# ====================== MAIN APP ======================
if "grok_api_key" not in st.session_state:
    st.session_state.grok_api_key = ""

st.title("🌍 GeoSupply Short-Term Profit Predictor")
st.caption("**2-5 Day Momentum + Volume Signals** | Highest Probability Geo-Supply Chain Trades | Live yFinance + Grok-4")

with st.sidebar:
    st.header("🔑 Grok API")
    api_key = st.text_input("Grok API Key (x.ai)", type="password", value=st.session_state.grok_api_key)
    if api_key:
        st.session_state.grok_api_key = api_key
        st.success("✅ API key saved")

    st.header("⚙️ Trading Settings")
    period = st.selectbox("Signal Lookback", ["5d", "10d", "1mo"], index=0, 
                         help="5d = strongest 2-5 day signals")
    model = st.selectbox("Grok Model", AVAILABLE_MODELS, index=0)
    
    st.divider()
    if st.button("🔄 Refresh All Data & Signals", type="primary"):
        st.cache_data.clear()
        st.rerun()

    st.caption("**Disclaimer**: Not financial advice. For informational purposes only.")

# ====================== TABS ======================
tab1, tab2, tab3 = st.tabs(["📈 Profit Signal Leaderboard", "📊 Charts", "🤖 Grok 2-5 Day Thesis"])

with tab1:
    st.subheader("🔥 Short-Term Profit Signal Leaderboard (2-5 Day Horizon)")
    summary_df = fetch_profit_signals(ALL_TICKERS, period)
    
    if not summary_df.empty:
        st.dataframe(
            summary_df.style.background_gradient(cmap="RdYlGn", subset=["Signal Score"])
            .format({"Current Price": "${:.2f}", "Signal Score": "{:.3f}"}),
            use_container_width=True,
            hide_index=True
        )
        
        # Export buttons
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="📥 Download Full Watchlist (CSV)",
                data=summary_df.to_csv(index=False),
                file_name=f"geosupply_watchlist_{period}.csv",
                mime="text/csv"
            )
        with col2:
            ibkr_csv = create_ibkr_watchlist_csv(summary_df)
            st.download_button(
                label="🚀 IBKR Ready Export (Top 10 Highest Probability)",
                data=ibkr_csv,
                file_name=f"IBKR_GeoSupply_Top10_{period}.csv",
                mime="text/csv",
                help="Import directly into Interactive Brokers TWS → Watchlist"
            )
        
        # Top 5 live cards
        st.subheader("Top 5 Highest Probability Trades")
        cols = st.columns(5)
        for i, row in summary_df.head(5).iterrows():
            with cols[i]:
                st.metric(
                    label=f"**{row['Ticker']}**",
                    value=f"${row['Current Price']}",
                    delta=f"{row['5d Change %']}%"
                )
                st.caption(f"**Signal: {row['Signal Score']}** | {row['Sector']}")
    else:
        st.error("No data fetched. Check internet connection.")

with tab2:
    st.subheader("Price & Volume Charts (Top Signals)")
    if 'summary_df' in locals() and not summary_df.empty:
        top5 = summary_df.head(5)["Ticker"].tolist()
        for ticker in top5:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)
            if not hist.empty:
                fig = make_subplots(specs=[[{"secondary_y": True}]])
                fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name="Price", line=dict(color="#00ff9d")), secondary_y=False)
                fig.add_trace(go.Bar(x=hist.index, y=hist['Volume'], name="Volume", opacity=0.4, marker_color="#00ff9d"), secondary_y=True)
                fig.update_layout(title=f"{ticker} — 2-5 Day Momentum", height=320, template="plotly_dark")
                st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("🤖 Grok 2-5 Day Strategic Thesis")
    if st.button("Generate 2-5 Day Profit Thesis (Grok-4)", type="primary"):
        if not st.session_state.get("grok_api_key"):
            st.error("Enter Grok API key first.")
        else:
            with st.spinner("Calling Grok-4 for real-time 2-5 day analysis..."):
                prompt = f"""You are an elite short-term geopolitical trading analyst.
Focus EXCLUSIVELY on the next 2-5 trading days.

Current short-term profit signal leaderboard:
{summary_df.to_string(index=False)}

Deliver a concise 3-bullet thesis:
1. Top 3-5 tickers most likely to be profitable in the next 2-5 days + expected edge
2. Key catalysts driving the moves
3. Risk factors and exact stop-loss levels for these trades

Use current prices and technical levels where possible. Be specific and actionable."""
                response = call_grok_api(prompt, model)
                st.markdown(response)

# Footer
st.divider()
st.caption("GeoSupply Short-Term Profit Predictor v1.5 • Pure Momentum + Volume • IBKR Export Ready • 2-5 Day Geo-Supply Chain Alpha")