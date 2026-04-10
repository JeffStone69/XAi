#!/usr/bin/env python3
"""
🌍 GeoSupply Short-Term Profit Predictor v7.0 RESTORED
Grok Memory Analytics + Data-Driven Self-Improvement
Uses Export/, Generated_response/, and DB for real feedback loop
"""

# ====================== STRONG SSL FIX (macOS) ======================
import ssl
import certifi
ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE  # Remove after running Install Certificates.command
ssl._create_default_https_context = lambda: ssl_context

# ====================== IMPORTS ======================
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import hashlib
import asyncio
import aiohttp
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# ====================== CONFIG ======================
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "geosupply.db"
EXPORT_DIR = BASE_DIR / "Export"
GENERATED_DIR = BASE_DIR / "Generated_response"

def setup_logging():
    logging.basicConfig(filename="geosupply_analyzer.log", level=logging.DEBUG,
                        format="%(asctime)s | %(levelname)s | %(message)s", force=True)

setup_logging()
logging.info("=== GeoSupply v7.0 RESTORED started ===")

# ====================== DATABASE ======================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS grok_interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        interaction_type TEXT, model TEXT, prompt_hash TEXT, response TEXT,
        horizon TEXT, prompt TEXT)""")
    conn.commit()
    conn.close()

def log_grok_interaction(interaction_type: str, model: str, prompt: str, response: str, horizon: str = ""):
    try:
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:16]
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO grok_interactions (interaction_type, model, prompt_hash, response, horizon, prompt) VALUES (?, ?, ?, ?, ?, ?)",
                     (interaction_type, model, prompt_hash, response, horizon, prompt))
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
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()

# ====================== LOAD REPO HISTORY FOR SELF-IMPROVEMENT ======================
def load_export_history() -> pd.DataFrame:
    if not EXPORT_DIR.exists():
        EXPORT_DIR.mkdir(exist_ok=True)
        return pd.DataFrame()
    files = list(EXPORT_DIR.glob("*.csv"))
    if not files:
        return pd.DataFrame()
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f)
            df["export_file"] = f.name
            dfs.append(df)
        except Exception as e:
            logging.warning(f"Failed loading {f}: {e}")
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def get_self_improvement_context() -> str:
    history = load_export_history()
    if history.empty:
        return "No historical export data yet. Export leaderboards to enable data-driven improvement."
    return f"""Historical Performance from Export/ folder:
- Total past signals: {len(history)}
- Unique tickers: {history.get('Ticker', pd.Series()).nunique()}
- Avg Signal Score: {history.get('Signal Score', pd.Series([0])).mean():.2f}
- Top sectors: {history.groupby('Sector')['Signal Score'].mean().nlargest(3).to_dict() if 'Sector' in history.columns else 'N/A'}
Use this to refine confidence and avoid past weak patterns."""

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

# ====================== ASYNC GROK ======================
async def async_call_grok_api(prompt: str, model: str, temperature: float = 0.7, interaction_type: Optional[str] = None, horizon: str = "") -> str:
    if not st.session_state.get("grok_api_key"):
        return "⚠️ Enter Grok API key in sidebar."
    headers = {"Authorization": f"Bearer {st.session_state.grok_api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": temperature, "max_tokens": 1800}
    try:
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=90)) as session:
            async with session.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    return f"❌ API error ({resp.status}): {err[:200]}"
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                if interaction_type:
                    log_grok_interaction(interaction_type, model, prompt, content, horizon)
                return content
    except Exception as e:
        logging.error(f"Grok call failed: {e}", exc_info=True)
        return f"❌ Grok error: {str(e)[:150]}"

# ====================== DATA & SIGNALS ======================
@st.cache_data(ttl=300)
def fetch_raw_market_data(tickers: List[str]) -> Dict[str, pd.DataFrame]:
    try:
        raw = yf.download(tickers, period="1mo", interval="1d", group_by="ticker", auto_adjust=True, threads=True, progress=False)
        result = {}
        for t in tickers:
            if t in raw.columns.get_level_values(0):
                df = raw[t].dropna(how="all")
                if not df.empty and {"Close", "Volume"}.issubset(df.columns):
                    result[t] = df
        return result
    except Exception as e:
        logging.error(f"yfinance error: {e}")
        return {}

def calculate_rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if len(rsi) > period and not pd.isna(rsi.iloc[-1]) else 50.0

@st.cache_data(ttl=300)
def compute_profit_signals(raw_data: Dict[str, pd.DataFrame], horizon: str) -> pd.DataFrame:
    if not raw_data:
        return pd.DataFrame()
    lookback = {"5d": 5, "10d": 10, "1mo": 20}.get(horizon, 5)
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
def display_thesis(thesis: str, suffix: str = ""):
    if not thesis:
        return
    with st.container(border=True):
        st.markdown("### 📝 Grok Thesis")
        st.markdown(thesis)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📋 Copy", key=f"copy_{abs(hash(thesis)) % 100000}_{suffix}"):
                st.toast("✅ Copied to clipboard")
        with c2:
            if st.button("💾 Save", type="primary", key=f"save_{abs(hash(thesis)) % 100000}_{suffix}"):
                st.success("✅ Saved to DB")

# ====================== MAIN ======================
init_db()

if "grok_api_key" not in st.session_state:
    st.session_state.grok_api_key = ""
if "raw_data" not in st.session_state:
    st.session_state.raw_data = {}
if "last_thesis" not in st.session_state:
    st.session_state.last_thesis = None

st.set_page_config(page_title="GeoSupply v7.0", page_icon="🌍", layout="wide")
st.title("🌍 GeoSupply Short-Term Profit Predictor **v7.0 RESTORED**")
st.caption("Data from Export/ + DB • Self-Improving Grok Thesis")

with st.sidebar:
    st.header("🔑 Grok API")
    key = st.text_input("Grok API Key (x.ai)", type="password", value=st.session_state.grok_api_key)
    if key and key != st.session_state.grok_api_key:
        st.session_state.grok_api_key = key
        st.success("✅ Saved")
    st.header("⚙️ Settings")
    horizon = st.selectbox("Horizon", ["5d", "10d", "1mo"], index=0)
    model = st.selectbox("Model", AVAILABLE_MODELS, index=0)
    temp = st.slider("Temperature", 0.0, 1.0, 0.7, 0.1)
    if st.button("🔄 Refresh All", type="primary", use_container_width=True):
        st.cache_data.clear()
        if "raw_data" in st.session_state:
            del st.session_state.raw_data
        st.rerun()

# Load data safely
if not st.session_state.raw_data:
    with st.spinner("Loading market data..."):
        st.session_state.raw_data = fetch_raw_market_data(ALL_TICKERS)
raw_data = st.session_state.raw_data
summary_df = compute_profit_signals(raw_data, horizon)

tabs = st.tabs(["📈 Leaderboard", "📊 Charts", "🔥 Heatmap", "🤖 Grok Thesis", "📖 History", "📊 Analytics", "🧠 Self-Improvement"])

with tabs[0]:
    st.subheader(f"Profit Signal Leaderboard ({horizon})")
    if not summary_df.empty:
        styled = summary_df.style.background_gradient(cmap="viridis", subset=["Signal Score"])
        st.dataframe(styled, use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("📥 CSV", summary_df.to_csv(index=False), f"geosupply_{horizon}.csv")
        with c2:
            top10 = summary_df.head(10).copy()
            top10["Action"] = "BUY"
            top10["Exchange"] = top10["Ticker"].apply(lambda x: "ASX" if x.endswith(".AX") else "SMART")
            st.download_button("🚀 IBKR Top-10", top10[["Ticker","Exchange","Action"]].to_csv(index=False), "IBKR_top10.csv")
    else:
        st.warning("No data – refresh or check connection.")

with tabs[1]:
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

with tabs[2]:
    st.subheader("Sector Heatmap")
    if not summary_df.empty:
        sector_avg = summary_df.groupby("Sector")["Signal Score"].mean().round(2)
        fig = go.Figure(data=go.Heatmap(z=sector_avg.values.reshape(-1,1), x=["Avg Score"], y=sector_avg.index, colorscale="Viridis"))
        fig.update_layout(title="Sector Momentum", template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

with tabs[3]:
    st.subheader("🤖 Grok Thesis")
    if st.button("🚀 Generate Thesis + Self-Improvement", type="primary", use_container_width=True):
        if summary_df.empty:
            st.error("Refresh data first")
        else:
            ctx = get_self_improvement_context()
            prompt = f"""Analyze this GeoSupply leaderboard (horizon: {horizon}):
{summary_df.head(12).to_string(index=False)}

{ctx}

Provide concise 2-3 trade ideas with rationale and one self-improvement suggestion for the model."""
            with st.spinner("Generating..."):
                thesis = asyncio.run(async_call_grok_api(prompt, model, temp, "thesis", horizon))
                st.session_state.last_thesis = thesis
                if "❌" not in thesis:
                    st.success("✅ Generated (data-driven)")
                else:
                    st.error(thesis)
                display_thesis(thesis, "thesis")

    if st.session_state.get("last_thesis"):
        display_thesis(st.session_state.last_thesis, "last")

with tabs[4]:
    st.subheader("📖 Grok History")
    hist_df = get_grok_history(30)
    if not hist_df.empty:
        for _, row in hist_df.iterrows():
            with st.expander(f"{row['timestamp']} | {row.get('interaction_type')}"):
                st.markdown(row['response'])
    else:
        st.info("No history yet")

with tabs[5]:
    st.subheader("📊 Grok Analytics")
    df = get_grok_history(1000)
    if not df.empty:
        col1, col2 = st.columns(2)
        with col1: st.metric("Total Interactions", len(df))
        with col2: st.metric("Unique Models", df["model"].nunique() if "model" in df.columns else 0)
        st.dataframe(df[["timestamp", "interaction_type", "model", "response"]].head(50), use_container_width=True)
    else:
        st.info("Generate theses to populate analytics")

with tabs[6]:
    st.subheader("🧠 Self-Improvement")
    st.caption("Learns from Export/ folder + past theses")
    ctx = get_self_improvement_context()
    st.write(ctx)
    if st.button("Generate Improved Thesis Using Repo Data", type="primary"):
        if summary_df.empty:
            st.error("No current signals")
        else:
            prompt = f"""You are a self-improving trader. Current signals:
{summary_df.head(12).to_string(index=False)}

{ctx}

Refine trade ideas using historical lessons and suggest model improvements."""
            with st.spinner("Improving with repo data..."):
                thesis = asyncio.run(async_call_grok_api(prompt, model, temp, "self_improvement", horizon))
                st.session_state.last_thesis = thesis
                display_thesis(thesis, "improve")

st.caption("v7.0 RESTORED • Self-Improvement from Export/ + DB • https://github.com/JeffStone69/XAi")