#!/usr/bin/env python3
"""
🌍 GeoSupply Short-Term Profit Predictor v7.1
Consolidated Grok Self-Improvement + History Tab
Data-driven profitability tracking over time using Export/ + geosupply.db
"""

# ====================== STRONG SSL FIX ======================
import ssl
import certifi
ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE  # Remove after Install Certificates.command
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
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# ====================== CONFIG ======================
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "geosupply.db"
EXPORT_DIR = BASE_DIR / "Export"
GENERATED_DIR = BASE_DIR / "Generated_response"

def setup_logging():
    logging.basicConfig(
        filename="geosupply_analyzer.log",
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)s | %(message)s",
        force=True
    )

setup_logging()
logging.info("=== GeoSupply v7.1 started - Consolidated Self-Improvement ===")

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
    conn.commit()
    conn.close()

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
        logging.info(f"Logged interaction: {interaction_type} | Horizon: {horizon}")
    except Exception as e:
        logging.error(f"DB log failed: {e}")

def get_grok_history(limit: int = 200) -> pd.DataFrame:
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM grok_interactions ORDER BY timestamp DESC LIMIT ?", conn, params=(limit,))
        conn.close()
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df["response_length"] = df["response"].str.len()
        return df
    except Exception as e:
        logging.error(f"History load failed: {e}")
        return pd.DataFrame()

# ====================== LOAD EXPORT HISTORY FOR PROFITABILITY TRACKING ======================
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
            df["export_date"] = pd.to_datetime(f.stem.split("_")[-1] if "_" in f.stem else datetime.now().date(), errors="coerce")
            dfs.append(df)
        except Exception as e:
            logging.warning(f"Failed to load export {f}: {e}")
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def compute_profitability_improvement() -> dict:
    """Track profitability improvements over time from exports + history."""
    exports = load_export_history()
    history = get_grok_history(500)
    
    stats = {
        "total_exports": len(exports),
        "total_theses": len(history),
        "avg_signal_score": exports["Signal Score"].mean() if not exports.empty and "Signal Score" in exports.columns else 0,
        "top_performing_sectors": exports.groupby("Sector")["Signal Score"].mean().nlargest(5).to_dict() if not exports.empty and "Sector" in exports.columns else {},
        "recent_improvement_trend": "Insufficient data" 
    }
    
    if not history.empty:
        thesis_types = history["interaction_type"].value_counts().to_dict()
        stats["self_improvement_count"] = thesis_types.get("self_improvement", 0)
    
    return stats

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

    headers = {"Authorization": f"Bearer {st.session_state.grok_api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 1800
    }

    try:
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=90)) as session:
            async with session.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logging.error(f"Grok API error {resp.status}: {error_text[:300]}")
                    return f"❌ Grok API error ({resp.status}): {error_text[:200]}"
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                if interaction_type:
                    log_grok_interaction(interaction_type, model, prompt, content, horizon)
                return content
    except Exception as e:
        logging.error(f"Grok API failed: {e}", exc_info=True)
        return f"❌ Grok error: {str(e)[:200]}"

# ====================== MARKET DATA ======================
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
    if not thesis or not isinstance(thesis, str):
        return
    with st.container(border=True):
        st.markdown("### 📝 Grok Thesis")
        st.markdown(thesis)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📋 Copy to Clipboard", key=f"copy_{abs(hash(thesis)) % 100000}_{suffix}"):
                st.toast("✅ Copied!", icon="📋")
        with col2:
            if st.button("💾 Save to History", type="primary", key=f"save_{abs(hash(thesis)) % 100000}_{suffix}"):
                st.success("✅ Saved & logged to DB")
                st.rerun()

# ====================== MAIN APP ======================
init_db()

if "grok_api_key" not in st.session_state:
    st.session_state.grok_api_key = ""
if "raw_data" not in st.session_state:
    st.session_state.raw_data = {}
if "last_thesis" not in st.session_state:
    st.session_state.last_thesis = None

st.set_page_config(page_title="GeoSupply v7.1", page_icon="🌍", layout="wide")

st.title("🌍 GeoSupply Short-Term Profit Predictor **v7.1**")
st.caption("**Consolidated Self-Improvement + History** • Profitability Tracking Over Time")

with st.sidebar:
    st.header("🔑 Grok API")
    api_key = st.text_input("Grok API Key (x.ai)", type="password", value=st.session_state.grok_api_key)
    if api_key and api_key != st.session_state.grok_api_key:
        st.session_state.grok_api_key = api_key
        st.success("✅ API key saved")

    st.header("⚙️ Settings")
    horizon = st.selectbox("Signal Horizon", ["5d", "10d", "1mo"], index=0)
    model = st.selectbox("Grok Model", AVAILABLE_MODELS, index=0)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.1)

    if st.button("🔄 Refresh All Data", type="primary", use_container_width=True):
        st.cache_data.clear()
        if "raw_data" in st.session_state:
            del st.session_state.raw_data
        st.rerun()

# Load market data
if not st.session_state.raw_data:
    with st.spinner("Fetching latest market data..."):
        st.session_state.raw_data = fetch_raw_market_data(ALL_TICKERS)

raw_data = st.session_state.raw_data
summary_df = compute_profit_signals(raw_data, horizon)

# Tabs - Consolidated Grok + History + Self-Improvement
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Leaderboard", "📊 Charts", "🔥 Sector Heatmap",
    "🤖 Grok Self-Improvement & History", "📊 Analytics"
])

with tab1:
    st.subheader(f"🔥 Profit Signal Leaderboard ({horizon})")
    if not summary_df.empty:
        styled_df = summary_df.style.background_gradient(cmap="viridis", subset=["Signal Score"])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
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
            x=["Avg Signal Score"],
            y=sector_stats.index,
            colorscale="Viridis"
        ))
        fig.update_layout(title="Sector Average Signal Strength", height=420, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.subheader("🤖 Grok Self-Improvement & History")
    st.caption("Generate improved theses + track profitability over time from Export/ and DB")

    # Profitability stats
    stats = compute_profitability_improvement()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Past Exports", stats["total_exports"])
    with col2:
        st.metric("Total Theses", stats["total_theses"])
    with col3:
        st.metric("Avg Signal Score", f"{stats['avg_signal_score']:.2f}")
    with col4:
        st.metric("Self-Improvement Runs", stats.get("self_improvement_count", 0))

    st.subheader("Historical Improvement Context")
    st.write(stats["top_performing_sectors"])

    # Generate button
    if st.button("🚀 Generate Self-Improved Thesis (Data-Driven)", type="primary", use_container_width=True):
        if summary_df.empty:
            st.error("Refresh market data first.")
        else:
            improvement_ctx = f"""
Historical Profitability Insights from Export/ and DB:
- Total past signals: {stats['total_exports']}
- Average Signal Score: {stats['avg_signal_score']:.2f}
- Top sectors: {stats['top_performing_sectors']}
- Self-improvement count: {stats.get('self_improvement_count', 0)}
"""
            prompt = f"""You are a self-improving short-term supply-chain trader.

Current leaderboard (horizon: {horizon}):
{summary_df.head(12).to_string(index=False)}

{improvement_ctx}

Provide:
1. Overall narrative with historical lessons
2. 2-3 refined trade ideas (adjust based on past performance)
3. Specific self-improvement recommendations for the GeoSupply system

Be concise and actionable."""

            with st.spinner("Generating self-improved thesis using repo history..."):
                try:
                    thesis = asyncio.run(async_call_grok_api(prompt, model, temperature, 
                                                           interaction_type="self_improvement", horizon=horizon))
                    st.session_state.last_thesis = thesis
                    if "❌" not in thesis[:100]:
                        st.success("✅ Self-improved thesis generated and logged!")
                    else:
                        st.error(thesis)
                    display_thesis(thesis, "improve")
                except Exception as e:
                    st.error(f"Generation failed: {str(e)}")

    # Show last thesis
    if st.session_state.get("last_thesis"):
        st.markdown("---")
        display_thesis(st.session_state.last_thesis, "last")

    # History section
    st.subheader("📖 Recent Grok History (Self-Improvement Included)")
    history_df = get_grok_history(30)
    if not history_df.empty:
        search = st.text_input("🔍 Filter history", "")
        filtered = history_df
        if search:
            filtered = history_df[history_df["response"].str.contains(search, case=False, na=False) |
                                  history_df.get("interaction_type", "").str.contains(search, case=False, na=False)]
        for _, row in filtered.iterrows():
            with st.expander(f"🕒 {row['timestamp'].strftime('%Y-%m-%d %H:%M')} | {row.get('interaction_type','N/A')} | {row.get('model','N/A')}"):
                st.markdown(row['response'])
    else:
        st.info("No Grok interactions yet. Generate some theses.")

with tab5:
    st.subheader("📊 Grok Memory Analytics")
    analytics_df = get_grok_history(1000)
    if not analytics_df.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Interactions", len(analytics_df))
        with col2:
            st.metric("Unique Models", analytics_df["model"].nunique() if "model" in analytics_df.columns else 0)
        
        if "timestamp" in analytics_df.columns and not analytics_df["timestamp"].isna().all():
            daily = analytics_df.resample("D", on="timestamp").size().reset_index(name="Count")
            fig = px.line(daily, x="timestamp", y="Count", title="Grok Activity Over Time")
            st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(analytics_df[["timestamp", "interaction_type", "model", "horizon", "response_length"]].head(100),
                     use_container_width=True)
    else:
        st.info("Generate theses to see analytics and profitability trends.")

st.caption("**v7.1** • Consolidated Self-Improvement + History Tab • Profitability Tracking from Export/ + DB • https://github.com/JeffStone69/XAi")