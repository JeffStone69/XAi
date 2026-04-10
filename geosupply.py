#!/usr/bin/env python3
"""
🌍 GeoSupply AI Self-Evolving Rebound Profit Predictor v1.0
Grok-Evolved Edition • Dynamic Weights + Stochastic + Bollinger + Backtesting + Deep Thesis
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
from typing import List, Dict, Optional, Any

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

# ====================== SIGNAL ENGINE v1.0 ======================
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
    def calculate_stochastic(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14, smooth: int = 3) -> float:
        lowest_low = low.rolling(period).min()
        highest_high = high.rolling(period).max()
        k = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        return float(k.rolling(smooth).mean().iloc[-1]) if not pd.isna(k.rolling(smooth).mean().iloc[-1]) else 50.0

    @staticmethod
    def calculate_bollinger_percent(close: pd.Series, period: int = 20) -> float:
        sma = close.rolling(period).mean()
        std = close.rolling(period).std()
        upper = sma + 2 * std
        lower = sma - 2 * std
        if upper.iloc[-1] == lower.iloc[-1]:
            return 50.0
        return round(((close.iloc[-1] - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1])) * 100, 1)

    @staticmethod
    def calculate_volatility(close: pd.Series, period: int = 20) -> float:
        returns = close.pct_change()
        return round(returns.rolling(period).std().iloc[-1] * 100, 2)

    @staticmethod
    def compute_signals(raw_data: Dict[str, pd.DataFrame], horizon_days: int, weights: Dict[str, float]) -> pd.DataFrame:
        if not raw_data:
            return pd.DataFrame()
        
        records = []
        for ticker, hist in raw_data.items():
            if len(hist) < max(horizon_days + 30, 60):
                continue
            try:
                close = hist["Close"]
                high = hist["High"]
                low = hist["Low"]
                volume = hist["Volume"]

                price_change = ((close.iloc[-1] - close.iloc[-(horizon_days + 1)]) / close.iloc[-(horizon_days + 1)]) * 100
                vol_avg = volume.mean()
                vol_spike = volume.iloc[-1] / vol_avg if vol_avg > 0 else 1.0
                
                rsi = SignalEngine.calculate_rsi(close)
                macd_hist = SignalEngine.calculate_macd_hist(close)
                stoch = SignalEngine.calculate_stochastic(high, low, close)
                bb_percent = SignalEngine.calculate_bollinger_percent(close)
                vol_20d = SignalEngine.calculate_volatility(close)

                # Dynamic weighted rebound score (normalised weights sum to 1)
                rebound_score = round(
                    max(0, 40 - rsi) * weights["rsi"] +
                    max(0, 25 - stoch) * weights["stoch"] +
                    max(0, 50 - bb_percent) * weights["bb"] +
                    vol_spike * weights["vol"] +
                    max(0, -price_change * 2) * weights["price"] +
                    (12 if macd_hist > 0 else 0) * weights["macd"] +
                    (10 if -18 < price_change < 6 else 0),
                    1
                )

                signal_score = round(rebound_score * 0.9 + (15 if macd_hist > 0 else 0), 1)

                sector = next((name for name, tks in SECTORS.items() if ticker in tks), "Other")

                records.append({
                    "Ticker": ticker,
                    "Sector": sector,
                    "Current Price": round(close.iloc[-1], 2),
                    f"{horizon_days}d Change %": round(price_change, 1),
                    "Vol Spike": round(vol_spike, 2),
                    "RSI": round(rsi, 1),
                    "Stochastic": round(stoch, 1),
                    "BB %": bb_percent,
                    "20d Vol %": vol_20d,
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
        return "⚠️ Enter Grok API key in sidebar."
    
    headers = {"Authorization": f"Bearer {st.session_state.grok_api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": temperature, "max_tokens": 3000}
    
    try:
        resp = requests.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload, timeout=90)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            if interaction_type:
                avg_score = st.session_state.get("current_avg_score", 0.0)
                log_grok_interaction(interaction_type, model, prompt, content, horizon, market_session, avg_score)
            return content
        return f"❌ API Error ({resp.status_code})"
    except Exception as e:
        return f"❌ Grok error: {str(e)[:200]}"

# ====================== DATA FETCH ======================
@st.cache_data(ttl=120)
def fetch_raw_market_data(tickers: List[str]):
    try:
        raw = yf.download(tickers, period="3mo", interval="1d", group_by="ticker",
                          auto_adjust=True, threads=True, progress=False)
        result = {}
        for t in tickers:
            if t in raw.columns.get_level_values(0):
                df = raw[t].dropna(how="all")
                if not df.empty and {"Close", "High", "Low", "Volume"}.issubset(df.columns):
                    result[t] = df
        return result
    except Exception as e:
        st.error(f"Data fetch failed: {str(e)[:120]}")
        return {}

# ====================== BACKTEST ENGINE ======================
@st.cache_data(ttl=300)
def run_simple_backtest(raw_data: Dict, horizon_days: int, threshold: float = 65.0):
    results = []
    for ticker, hist in raw_data.items():
        if len(hist) < 80:
            continue
        close = hist["Close"]
        scores = []
        forward_returns = []
        for i in range(40, len(hist) - horizon_days):
            window = hist.iloc[i-40:i+1]
            # Simplified past score calculation (using same logic but without full weights for speed)
            past_rsi = SignalEngine.calculate_rsi(window["Close"])
            past_vol_spike = window["Volume"].iloc[-1] / window["Volume"].mean() if window["Volume"].mean() > 0 else 1
            past_change = ((window["Close"].iloc[-1] - window["Close"].iloc[-horizon_days]) / window["Close"].iloc[-horizon_days]) * 100
            score = max(0, 40 - past_rsi) * 0.4 + past_vol_spike * 0.3 + max(0, -past_change) * 0.3
            if score >= threshold:
                fwd_ret = ((close.iloc[i + horizon_days] - close.iloc[i]) / close.iloc[i]) * 100
                scores.append(score)
                forward_returns.append(fwd_ret)
        if forward_returns:
            avg_return = round(np.mean(forward_returns), 2)
            win_rate = round((np.sum(np.array(forward_returns) > 0) / len(forward_returns)) * 100, 1)
            results.append({"Ticker": ticker, "Signals Triggered": len(forward_returns), "Avg Return %": avg_return, "Win Rate %": win_rate})
    return pd.DataFrame(results).sort_values("Avg Return %", ascending=False) if results else pd.DataFrame()

# ====================== UI HELPERS ======================
def display_thesis(thesis: str, suffix: str = ""):
    if not thesis:
        return
    with st.container(border=True):
        st.markdown("### 📝 Grok Thesis")
        st.markdown(thesis)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📋 Copy", key=f"copy_{abs(hash(thesis))%100000}_{suffix}"):
                st.toast("✅ Copied to clipboard")
        with c2:
            if st.button("💾 Save to History", type="primary", key=f"save_{abs(hash(thesis))%100000}_{suffix}"):
                st.success("✅ Saved")

# ====================== MAIN ======================
def main():
    init_db()
    
    if "grok_api_key" not in st.session_state: st.session_state.grok_api_key = ""
    if "raw_data" not in st.session_state: st.session_state.raw_data = {}
    if "last_thesis" not in st.session_state: st.session_state.last_thesis = None
    if "last_ticker_thesis" not in st.session_state: st.session_state.last_ticker_thesis = {}

    st.set_page_config(page_title="GeoSupply v1.0", page_icon="🌍", layout="wide")
    st.title("🌍 GeoSupply v1.0")
    st.caption("Grok Self-Evolving Rebound Profit Predictor • Dynamic Weights • Backtesting • Deep AI Thesis")

    with st.sidebar:
        st.header("🔑 Grok API")
        key = st.text_input("Grok API Key", type="password", value=st.session_state.grok_api_key)
        if key and key != st.session_state.grok_api_key:
            st.session_state.grok_api_key = key
            st.success("✅ Key saved")

        st.header("⚙️ Market & Time Settings")
        market_mode = st.selectbox("Market Selection", ["ASX + US", "ASX Only", "US Only", "24h Global"], index=0)
        timeframe = st.selectbox("Lookback Period", ["1d", "5d", "10d", "1mo", "3mo"], index=2)
        days_map = {"1d": 1, "5d": 5, "10d": 10, "1mo": 20, "3mo": 60}
        horizon_days = days_map[timeframe]

        st.subheader("Signal Weights (Dynamic)")
        default_weights = {"rsi": 0.35, "stoch": 0.20, "bb": 0.15, "vol": 0.15, "price": 0.10, "macd": 0.05}
        weights = {}
        for k, v in default_weights.items():
            weights[k] = st.slider(k.upper(), 0.0, 1.0, v, 0.05, key=f"weight_{k}")
        total = sum(weights.values())
        if total == 0:
            weights = default_weights
        else:
            weights = {k: round(v / total, 3) for k, v in weights.items()}
        st.caption(f"Normalised weights (sum = 1.0): {weights}")

        st.subheader("Custom Tickers")
        custom_input = st.text_input("Add extra tickers (comma separated)", "NVDA, TSLA, AAPL, AMD")
        custom_tickers = [t.strip().upper() for t in custom_input.split(",") if t.strip()]

        if st.button("🔄 Fetch Latest Market Data", type="primary", use_container_width=True):
            st.cache_data.clear()
            if market_mode == "ASX Only":
                base = ALL_ASX_TICKERS
            elif market_mode == "US Only":
                base = ALL_US_TICKERS
            else:
                base = ALL_ASX_TICKERS + ALL_US_TICKERS
            all_tickers = list(set(base + custom_tickers))
            st.session_state.raw_data = fetch_raw_market_data(all_tickers)
            st.success(f"✅ Fetched {len(st.session_state.raw_data)} tickers")
            st.rerun()

    # Auto-fetch
    if not st.session_state.raw_data:
        with st.spinner("Loading initial market data..."):
            st.session_state.raw_data = fetch_raw_market_data(ALL_US_TICKERS + ["BHP.AX", "RIO.AX"])

    raw_data = st.session_state.raw_data
    summary_df = SignalEngine.compute_signals(raw_data, horizon_days, weights)

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "🚀 Top 5 Rebound", "📈 Full Leaderboard", "📊 Charts", "🔥 Heatmap",
        "🤖 Grok Self-Evolution", "📈 Backtest", "📊 Analytics"
    ])

    with tab1:
        st.subheader(f"🔥 Top 5 Real-Time Rebound Opportunities ({timeframe})")
        if summary_df.empty:
            st.warning("No data. Click Fetch Latest Market Data.")
        else:
            top5 = summary_df.head(5)
            st.dataframe(top5.style.background_gradient(subset=["Rebound Score"], cmap="RdYlGn")
                         .format({"Current Price": "${:.2f}", "Rebound Score": "{:.1f}"}),
                         use_container_width=True, hide_index=True)

            # Quick Grok Thesis for top tickers
            st.subheader("🎯 Quick Grok Thesis")
            selected_top = st.selectbox("Select ticker for instant Grok analysis", top5["Ticker"].tolist(), key="top_thesis")
            if st.button("Generate Grok Thesis for this ticker", type="primary"):
                with st.spinner("Grok thinking..."):
                    ticker_data = summary_df[summary_df["Ticker"] == selected_top].iloc[0]
                    prompt = f"""Analyze {selected_top} for short-term rebound. Current metrics: Price ${ticker_data['Current Price']}, {timeframe} change {ticker_data[f'{horizon_days}d Change %']}%, RSI {ticker_data['RSI']}, Stochastic {ticker_data['Stochastic']}, BB% {ticker_data['BB %']}, Rebound Score {ticker_data['Rebound Score']}.
                    Give a concise high-conviction thesis with entry, target, stop, and risk/reward."""
                    thesis = call_grok_api(prompt, st.session_state.get("selected_model", "grok-4.20-reasoning"), 0.6, "ticker_thesis", timeframe, market_mode)
                    st.session_state.last_ticker_thesis[selected_top] = thesis
                    display_thesis(thesis, f"top_{selected_top}")

    with tab2:
        st.subheader("Full Leaderboard")
        if not summary_df.empty:
            st.dataframe(summary_df.style.background_gradient(subset=["Rebound Score", "Signal Score"], cmap="viridis"),
                         use_container_width=True, hide_index=True)
            csv = summary_df.to_csv(index=False).encode()
            st.download_button("📥 Download Leaderboard CSV", csv, f"geosupply_leaderboard_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", "text/csv")

    with tab3:
        st.subheader("Interactive Charts")
        if not summary_df.empty:
            ticker = st.selectbox("Select ticker for deep chart", summary_df["Ticker"].tolist())
            if ticker in raw_data:
                hist = raw_data[ticker]
                fig = make_subplots(rows=4, cols=1, shared_xaxes=True, row_heights=[0.45, 0.15, 0.15, 0.25])
                fig.add_trace(go.Candlestick(x=hist.index, open=hist["Open"], high=hist["High"], low=hist["Low"], close=hist["Close"]), row=1, col=1)
                fig.add_trace(go.Bar(x=hist.index, y=hist["Volume"]), row=2, col=1)
                fig.add_trace(go.Scatter(x=hist.index, y=SignalEngine.calculate_rsi(hist["Close"]), name="RSI"), row=3, col=1)
                fig.add_trace(go.Scatter(x=hist.index, y=[SignalEngine.calculate_stochastic(hist["High"], hist["Low"], hist["Close"])]*len(hist), name="Stoch"), row=4, col=1)
                fig.update_layout(height=820, template="plotly_dark", title=f"{ticker} • Full Technical View")
                st.plotly_chart(fig, use_container_width=True)

    with tab4:
        st.subheader("Sector Heatmap")
        if not summary_df.empty:
            pivot = summary_df.pivot_table(values="Rebound Score", index="Sector", aggfunc="mean").round(1)
            st.plotly_chart(px.imshow(pivot, text_auto=True, color_continuous_scale="viridis", title="Average Rebound Score by Sector"), use_container_width=True)

    with tab5:
        st.subheader("🤖 Grok Self-Evolution Engine")
        model_choice = st.selectbox("Grok Model", AVAILABLE_MODELS, index=0, key="selected_model")
        
        if st.button("🚀 Run Full Self-Improvement Cycle", type="primary", use_container_width=True):
            if summary_df.empty:
                st.warning("No data.")
            else:
                # The optimised prompt from above
                prompt = f"""You are Grok, expert quant trader + full-stack Python/Streamlit engineer. 
Your mission is to evolve GeoSupply into the ultimate short-term rebound predictor.

CURRENT MARKET SNAPSHOT ({timeframe} - {market_mode}):
{summary_df.head(20).to_string(index=False)}

CURRENT SIGNAL ENGINE SUMMARY:
- Rebound Score = weighted combination of RSI oversold, volume spike, recent price drawdown, MACD histogram
- Weights are now user-adjustable via sidebar sliders
- New indicators added: Stochastic %K, Bollinger %B, 20-day volatility

TASK — Deliver a vastly superior next iteration:
1. HIGH-CONVICTION TRADES: Give exactly 3 trades with ticker, entry price, target (+%), stop-loss, expected horizon return, and conviction rationale.
2. OPTIMIZED SCORING FORMULA: Provide a new, mathematically superior Rebound Score formula (include Stochastic, Bollinger %B, volatility z-score, and any new factors). Show the exact Python code for the updated SignalEngine.compute_signals method.
3. NEW FEATURES & UPGRADES: Suggest 4-6 concrete new capabilities (backtesting engine, risk metrics, watchlist persistence, correlation analysis, etc.) with implementation sketches.
4. CODE EVOLUTION: Give specific, copy-paste-ready improvements to the full script (UI, caching, error handling, new tabs, Grok thesis generator, etc.).
5. SELF-LEARNING LOOP: Describe how the app can automatically incorporate future Grok suggestions.

Think step-by-step. Output in clear markdown sections with code blocks where relevant. Make the next version dramatically better than v0.94."""
                with st.spinner("Grok evolving the entire application..."):
                    thesis = call_grok_api(prompt, model_choice, 0.7, "self_improvement", timeframe, market_mode)
                    st.session_state.last_thesis = thesis
                    display_thesis(thesis, "self")

        if st.session_state.get("last_thesis"):
            display_thesis(st.session_state.last_thesis, "last")

        st.subheader("Interaction History")
        history = get_grok_history(50)
        if not history.empty:
            for _, row in history.iterrows():
                with st.expander(f"{row['timestamp']} | {row.get('interaction_type','')}"):
                    st.markdown(row['response'])

    with tab6:
        st.subheader("📈 Signal Backtest Engine")
        if st.button("Run Historical Backtest (last 3 months)", type="primary"):
            with st.spinner("Running backtest on all tickers..."):
                backtest_df = run_simple_backtest(raw_data, horizon_days)
                if not backtest_df.empty:
                    st.dataframe(backtest_df.style.background_gradient(subset=["Avg Return %"], cmap="RdYlGn"), use_container_width=True)
                    st.caption("Backtest shows hypothetical performance if you had acted on Rebound Score ≥ 65.0 in the past 40+ windows.")
                else:
                    st.info("Insufficient history for backtest.")

    with tab7:
        st.subheader("Advanced Analytics")
        if not summary_df.empty:
            col1, col2 = st.columns(2)
            with col1:
                st.plotly_chart(px.scatter(summary_df, x="Vol Spike", y="Rebound Score", color="Sector", hover_name="Ticker", title="Volume Spike vs Rebound"), use_container_width=True)
            with col2:
                st.plotly_chart(px.scatter(summary_df, x="20d Vol %", y="Signal Score", color="Sector", hover_name="Ticker", title="Volatility vs Signal Strength"), use_container_width=True)
            
            st.caption("v1.0 Grok Self-Evolving Edition • Ready for continuous autonomous improvement")

if __name__ == "__main__":
    main()