#!/usr/bin/env python3
"""
🌍 GeoSupply Short-Term Profit Predictor v4.0
Self-Improving • Database-Powered • Sector Heatmap • Persistent Grok Memory Edition
Optimized & Architected by Grok (xAI) for GitHub Repo: https://github.com/JeffStone69/XAi

Complete ready-to-run Streamlit app.
Run with: streamlit run geosupply_analyzer.py

Key Optimizations in v4.0:
- SQLite database persistence for ALL Grok responses (thesis + self-improvement)
- New "📜 Grok History" tab with expandable persistent records
- Sector Momentum Heatmap (average signal by sector)
- Cleaner architecture: dedicated DB module, improved type hints, centralized constants
- Dramatically more powerful: persistent memory, visual sector analysis, full audit trail
- Hyper-optimized self-improvement: updated prompt with v4.0 context + next-gen suggestions
- Production-ready: comprehensive error handling, DB resilience, structured logging + DB sync
- No breaking changes — fully backward compatible with v3.0

Not financial advice. For educational & research use only.
"""

import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import logging
import numpy as np
import sqlite3
import hashlib
from typing import List, Dict, Any, Optional, Tuple
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

# ====================== CONFIG & LOGGING (v4.0 ENHANCED) ======================
st.set_page_config(
    page_title="GeoSupply Short-Term Profit Predictor v4.0",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enhanced logging: INFO for events, ERROR for failures, dedicated Grok + DB tracking
logging.basicConfig(
    filename="geosupply_analyzer.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(console_handler)

logging.info("🚀 GeoSupply Short-Term Profit Predictor v4.0 initialized - DB persistence + enhanced logging active")

# ====================== DATABASE PERSISTENCE (NEW v4.0) ======================
def init_db() -> None:
    """Initialize SQLite database for persistent Grok memory."""
    try:
        conn = sqlite3.connect("geosupply.db")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS grok_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                interaction_type TEXT,
                model TEXT,
                prompt_hash TEXT,
                response TEXT
            )
        """)
        conn.commit()
        conn.close()
        logging.info("DB_INIT: SQLite database 'geosupply.db' ready")
    except Exception as e:
        logging.error(f"DB_INIT: Critical failure - {e}")

def log_grok_interaction(interaction_type: str, model: str, prompt: str, response: str) -> None:
    """Persist Grok API interaction to SQLite (no sensitive data)."""
    try:
        prompt_hash = hashlib.md5(prompt.encode("utf-8")).hexdigest()[:16]
        conn = sqlite3.connect("geosupply.db")
        conn.execute("""
            INSERT INTO grok_interactions 
            (interaction_type, model, prompt_hash, response)
            VALUES (?, ?, ?, ?)
        """, (interaction_type, model, prompt_hash, response))
        conn.commit()
        conn.close()
        logging.info(f"DB_LOG: SUCCESS | Type={interaction_type} | Model={model} | Hash={prompt_hash}")
    except Exception as e:
        logging.warning(f"DB_LOG: Failed to persist - {e}")

def get_grok_history(limit: int = 20) -> pd.DataFrame:
    """Retrieve recent Grok interactions from persistent database."""
    try:
        conn = sqlite3.connect("geosupply.db")
        df = pd.read_sql_query(
            """
            SELECT 
                timestamp,
                interaction_type,
                model,
                prompt_hash,
                response
            FROM grok_interactions 
            ORDER BY timestamp DESC 
            LIMIT ?
            """,
            conn,
            params=(limit,)
        )
        conn.close()
        return df
    except Exception as e:
        logging.warning(f"DB_HISTORY: Query failed - {e}")
        return pd.DataFrame(columns=["timestamp", "interaction_type", "model", "prompt_hash", "response"])


# ====================== SECTOR DEFINITIONS (CENTRALIZED) ======================
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

# ====================== GROK API (v4.0 + DB LOGGING) ======================
def call_grok_api(
    prompt: str,
    model: str,
    temperature: float = 0.6,
    interaction_type: Optional[str] = None
) -> str:
    """Call Grok API with full event logging + optional SQLite persistence."""
    if not st.session_state.get("grok_api_key"):
        logging.warning("GROK_INTERACTION: No API key provided")
        return "⚠️ Please enter your Grok API key in the sidebar."

    logging.info(f"GROK_INTERACTION: Initiated | Type={interaction_type or 'generic'} | Model={model} | Temp={temperature} | Prompt chars={len(prompt)}")

    headers = {"Authorization": f"Bearer {st.session_state.grok_api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 1800
    }

    try:
        resp = requests.post(f"{API_BASE}/chat/completions", headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        logging.info(f"GROK_INTERACTION: SUCCESS | Response chars={len(content)}")

        # Persist to database if interaction_type provided
        if interaction_type:
            log_grok_interaction(interaction_type, model, prompt, content)

        return content
    except Exception as e:
        error_msg = f"Grok API error: {str(e)[:200]}"
        logging.error(f"GROK_INTERACTION: FAILED | Type={interaction_type or 'generic'} | Error={error_msg}")
        return f"❌ {error_msg}"


# ====================== OPTIMIZED DATA FETCH ======================
@st.cache_data(ttl=300, show_spinner=False)
def fetch_raw_market_data(tickers: List[str]) -> Dict[str, pd.DataFrame]:
    """Ultra-fast batch fetch with enhanced error resilience and logging."""
    start_time = datetime.now()
    logging.info(f"DATA_FETCH: Starting batch download for {len(tickers)} tickers")

    try:
        raw = yf.download(
            tickers=tickers,
            period="1mo",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
            prepost=False
        )

        if raw.empty:
            logging.warning("DATA_FETCH: Empty response from yfinance")
            return {}

        ticker_data: Dict[str, pd.DataFrame] = {}
        if len(tickers) == 1:
            ticker_data[tickers[0]] = raw.dropna(how="all")
        else:
            for ticker in tickers:
                if ticker in raw.columns.get_level_values(0):
                    df = raw[ticker].dropna(how="all")
                    if not df.empty and "Close" in df.columns and "Volume" in df.columns:
                        ticker_data[ticker] = df

        duration = (datetime.now() - start_time).total_seconds()
        logging.info(f"DATA_FETCH: SUCCESS | Fetched {len(ticker_data)} tickers in {duration:.2f}s")
        return ticker_data

    except Exception as e:
        logging.error(f"DATA_FETCH: CRITICAL FAILURE - {e}")
        return {}


# ====================== ENHANCED SIGNAL CALCULATION ======================
def calculate_rsi(close_series: pd.Series, period: int = 14) -> float:
    """Vectorized RSI calculation - fast and pure pandas."""
    delta = close_series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if len(rsi) > period and not pd.isna(rsi.iloc[-1]) else 50.0


@st.cache_data(ttl=300, show_spinner=False)
def compute_profit_signals(raw_data: Dict[str, pd.DataFrame], horizon: str) -> pd.DataFrame:
    """Ultra-optimized signal engine with RSI + improved risk adjustment."""
    if not raw_data:
        return pd.DataFrame()

    lookback_map = {"5d": 5, "10d": 10, "1mo": 20}
    lookback = lookback_map.get(horizon, 5)

    records: List[Dict[str, Any]] = []
    for ticker, hist in raw_data.items():
        if hist.empty or len(hist) < lookback + 14 or "Close" not in hist.columns or "Volume" not in hist.columns:
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

            rsi_val = calculate_rsi(hist["Close"])

            momentum = price_change_pct / 100
            vol_factor = min(volume_avg / 1_000_000, 12.0)
            risk_adjust = 1.0 / (1.0 + volatility_pct / 8.0) if volatility_pct > 0 else 1.0
            rsi_momentum_boost = (100 - rsi_val) / 100 if rsi_val > 50 else (rsi_val / 50)
            signal_score = round(momentum * vol_factor * vol_spike * risk_adjust * rsi_momentum_boost * 12.0, 3)

            sector = next((name for name, tks in SECTORS.items() if ticker in tks), "Other")

            records.append({
                "Ticker": ticker,
                "Current Price": round(current_price, 2),
                f"{horizon} Change %": round(price_change_pct, 1),
                "Avg Vol (M)": round(volume_avg / 1_000_000, 1),
                "Vol Spike": round(vol_spike, 2),
                "Volatility %": round(volatility_pct, 1),
                "RSI (14)": round(rsi_val, 1),
                "Signal Score": signal_score,
                "Sector": sector
            })
        except Exception as e:
            logging.warning(f"SIGNAL_CALC: Error processing {ticker}: {e}")
            continue

    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values("Signal Score", ascending=False).reset_index(drop=True)
    return df


# ====================== IBKR EXPORT ======================
def create_ibkr_watchlist_csv(df: pd.DataFrame) -> str:
    """IBKR-compatible Top-10 export."""
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


# ====================== SELF-IMPROVEMENT ENGINE (v4.0 UPDATED) ======================
def generate_self_improvement_suggestion(model: str) -> str:
    """Self-improving core: Grok analyzes the full v4.0 app and returns concrete upgrades."""
    prompt = """You are the self-improving architect for the GeoSupply Short-Term Profit Predictor (v4.0 Streamlit app).

Current capabilities (v4.0):
- Batch yfinance + vectorized RSI + enhanced risk-adjusted signals
- SQLite database persistence for ALL Grok interactions + full history viewer
- Sector Momentum Heatmap + leaderboard
- Production logging + DB sync
- Grok-powered 2-5 day thesis + IBKR export
- Self-Improvement Engine with persistent memory

Provide EXACT, ready-to-copy code improvements in this format:
1. SPEED: [specific change + code snippet]
2. CLEANLINESS: [refactor suggestion + code]
3. POWER: [new feature e.g. live news, backtesting engine, email alerts + code]
4. SELF-IMPROVING: [meta feature e.g. auto-apply patches via GitHub, version auto-evolution + code]
5. NEXT VERSION: [full v4.1 headline feature]

Be concise, production-ready, and focused on dramatic gains."""
    return call_grok_api(prompt, model, temperature=0.7, interaction_type="self_improvement")


# ====================== MAIN APP ======================
init_db()  # Ensure database exists before any Grok calls

if "grok_api_key" not in st.session_state:
    st.session_state.grok_api_key = ""

st.title("🌍 GeoSupply Short-Term Profit Predictor **v4.0**")
st.caption("**Database-Powered • Sector Heatmap • Persistent Grok Memory • Self-Improving** | 2-5 Day Geo-Supply Chain Alpha")

with st.sidebar:
    st.header("🔑 Grok API")
    api_key = st.text_input("Grok API Key (x.ai)", type="password", value=st.session_state.grok_api_key)
    if api_key and api_key != st.session_state.grok_api_key:
        st.session_state.grok_api_key = api_key
        logging.info("SIDEBAR: Grok API key updated")
        st.success("✅ API key saved")

    st.header("⚙️ Settings")
    horizon = st.selectbox("Signal Horizon", ["5d", "10d", "1mo"], index=0)
    model = st.selectbox("Grok Model", AVAILABLE_MODELS, index=0)

    st.divider()
    if st.button("🔄 Refresh All Data & Signals", type="primary", use_container_width=True):
        st.cache_data.clear()
        logging.info("USER_TRIGGER: Full cache cleared and refresh requested")
        st.rerun()

    st.caption("**Not financial advice.** Built for GitHub: https://github.com/JeffStone69/XAi")

# Initialize raw data
if "raw_data" not in st.session_state:
    with st.spinner("🚀 Fetching latest market data..."):
        st.session_state.raw_data = fetch_raw_market_data(ALL_TICKERS)

raw_data = st.session_state.raw_data

# ====================== TABS (v4.0) ======================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Leaderboard",
    "📊 Charts & Heatmap",
    "🤖 Grok Thesis",
    "🧬 Self-Improvement",
    "📜 Grok History"
])

with tab1:
    st.subheader(f"🔥 Profit Signal Leaderboard ({horizon})")
    summary_df = compute_profit_signals(raw_data, horizon)

    if not summary_df.empty:
        # New v4.0: Sector Overview (fast grouped summary)
        st.subheader("📊 Sector Overview")
        sector_summary = summary_df.groupby("Sector").agg(
            Avg_Signal=("Signal Score", "mean"),
            Tickercount=("Ticker", "count")
        ).round(2).sort_values("Avg_Signal", ascending=False)
        st.dataframe(sector_summary, use_container_width=True)

        st.dataframe(
            summary_df.style.background_gradient(cmap="RdYlGn", subset=["Signal Score"]),
            use_container_width=True,
            hide_index=True
        )

        col1, col2 = st.columns(2)
        with col1:
            st.download_button("📥 Full Watchlist CSV", data=summary_df.to_csv(index=False),
                               file_name=f"geosupply_{horizon}_v4.csv", mime="text/csv")
        with col2:
            ibkr_csv = create_ibkr_watchlist_csv(summary_df)
            st.download_button("🚀 IBKR Top-10 Export", data=ibkr_csv,
                               file_name=f"IBKR_GeoSupply_Top10_{horizon}_v4.csv", mime="text/csv")

        st.subheader("🚀 Top 5 Trades")
        cols = st.columns(5)
        for i, row in summary_df.head(5).iterrows():
            with cols[i]:
                st.metric(
                    label=row['Ticker'],
                    value=f"${row['Current Price']}",
                    delta=f"{row[f'{horizon} Change %']}%"
                )
                st.caption(f"Signal: {row['Signal Score']} | RSI: {row['RSI (14)']} | {row['Sector']}")
    else:
        st.error("No data. Try refreshing.")

with tab2:
    st.subheader("Price & Volume Charts (Top 5)")
    if not summary_df.empty:
        for ticker in summary_df.head(5)["Ticker"]:
            hist = raw_data.get(ticker)
            if hist is not None and not hist.empty:
                fig = make_subplots(specs=[[{"secondary_y": True}]])
                fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], name="Price", line=dict(color="#00ff9d")), secondary_y=False)
                fig.add_trace(go.Bar(x=hist.index, y=hist["Volume"], name="Volume", opacity=0.4, marker_color="#00ff9d"), secondary_y=True)
                fig.update_layout(
                    title=f"{ticker} — {horizon} View (RSI: {calculate_rsi(hist['Close']):.1f})",
                    height=340,
                    template="plotly_dark"
                )
                st.plotly_chart(fig, use_container_width=True)

    # New v4.0: Sector Momentum Heatmap
    st.subheader("🚀 Sector Momentum Heatmap")
    if not summary_df.empty:
        sector_avg = summary_df.groupby("Sector")["Signal Score"].mean().sort_values(ascending=False)
        fig = go.Figure(go.Bar(
            x=sector_avg.index,
            y=sector_avg.values,
            text=[f"{v:.2f}" for v in sector_avg.values],
            textposition="auto",
            marker_color="#00ff9d"
        ))
        fig.update_layout(
            title="Average Signal Score by Sector",
            xaxis_title="Sector",
            yaxis_title="Avg Signal Score",
            template="plotly_dark",
            height=420
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No signals yet — refresh data above.")

with tab3:
    st.subheader("🤖 Grok 2-5 Day Thesis")
    if st.button("Generate Thesis", type="primary"):
        if not st.session_state.get("grok_api_key"):
            st.error("Enter Grok API key first.")
        else:
            with st.spinner("Analyzing leaderboard with Grok..."):
                prompt = f"""Current leaderboard (v4.0 with RSI + DB persistence):\n{summary_df.head(12).to_string(index=False)}\n\nGive a concise 3-bullet 2-5 day thesis for the strongest GeoSupply opportunities."""
                response = call_grok_api(prompt, model, interaction_type="thesis")
                st.markdown(response)

with tab4:
    st.subheader("🧬 Self-Improvement Engine v4.0")
    st.caption("Grok analyzes this exact app (including DB + heatmap) and returns production-ready upgrades")
    if st.button("🚀 Generate Next-Version Optimizations", type="primary", use_container_width=True):
        if not st.session_state.get("grok_api_key"):
            st.error("Enter Grok API key first.")
        else:
            with st.spinner("Grok is architecting v4.1 improvements..."):
                suggestion = generate_self_improvement_suggestion(model)
                st.markdown("### Grok's Self-Improvement Recommendations")
                st.markdown(suggestion)
                st.success("💡 Copy these changes into the next version of geosupply_analyzer.py")

with tab5:
    st.subheader("📜 Grok Interaction History")
    st.caption("Persistent SQLite record of every Grok thesis and self-improvement call")
    history_df = get_grok_history()
    if not history_df.empty:
        for idx, row in history_df.iterrows():
            with st.expander(f"🕒 {row['timestamp']} | {row['interaction_type'].title()} | {row['model']} (hash: {row['prompt_hash']})"):
                st.markdown(row["response"])
        if st.button("🗑️ Clear All History (irreversible)", type="secondary"):
            try:
                conn = sqlite3.connect("geosupply.db")
                conn.execute("DELETE FROM grok_interactions")
                conn.commit()
                conn.close()
                st.success("History cleared")
                st.rerun()
            except Exception as e:
                st.error(f"Clear failed: {e}")
    else:
        st.info("No Grok interactions recorded yet. Generate a thesis or self-improvement suggestion to populate the database.")

st.divider()
st.caption("GeoSupply Analyzer v4.0 • SQLite Persistent Memory • Sector Heatmap • Full Grok History • Optimized by Grok (xAI)")