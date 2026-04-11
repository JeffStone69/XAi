#!/usr/bin/env python3

import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import os
import logging
import json
from datetime import datetime
import numpy as np
from typing import Dict, List, Tuple, Optional

st.set_page_config(page_title="GeoSupply Rebound Oracle v2.2", page_icon="🌍", layout="wide", initial_sidebar_state="expanded")

# Optimized logging configuration
SAVED_LOG = "saved.log"
THESES_LOG = "theses.log"
GROK_RESPONSE_DIR = "grok_responses"
API_BASE = "https://api.x.ai/v1"
AVAILABLE_MODELS = ["grok-4.20-reasoning", "grok-4.20-non-reasoning", "grok-4.20-multi-agent-0309", "grok-4-1-fast-reasoning", "grok-4-1-fast-non-reasoning"]

# Ticker lists (unchanged)
ASX_MINING = ["BHP.AX", "RIO.AX", "FMG.AX", "S32.AX", "MIN.AX"]
ASX_SHIPPING = ["QUB.AX", "TCL.AX", "ASX.AX"]
ASX_ENERGY = ["STO.AX", "WDS.AX", "ORG.AX", "WHC.AX", "BPT.AX"]
ASX_TECH = ["WTC.AX", "XRO.AX", "TNE.AX", "NXT.AX", "REA.AX", "360.AX", "PME.AX"]
ASX_RENEW = ["ORG.AX", "AGL.AX", "IGO.AX", "IFT.AX", "MCY.AX", "CEN.AX", "MEZ.AX", "RNE.AX"]
US_MINING = ["FCX", "NEM", "VALE", "SCCO", "GOLD", "AEM"]
US_SHIPPING = ["ZIM", "MATX", "SBLK", "DAC", "CMRE"]
US_ENERGY = ["XOM", "CVX", "COP", "OXY", "CCJ"]
US_TECH = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMD", "TSLA"]
US_RENEW = ["NEE", "BEPC", "CWEN", "FSLR", "ENPH"]

ALL_ASX = list(dict.fromkeys(ASX_MINING + ASX_SHIPPING + ASX_ENERGY + ASX_TECH + ASX_RENEW))
ALL_US = list(dict.fromkeys(US_MINING + US_SHIPPING + US_ENERGY + US_TECH + US_RENEW))
ALL_TICKERS = ALL_ASX + ALL_US

# Ensure directories
os.makedirs(GROK_RESPONSE_DIR, exist_ok=True)

logging.basicConfig(filename="geosupply_errors.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def call_grok_api(prompt: str, model: str, temperature: float = 0.7) -> str:
    if not st.session_state.get("grok_api_key"):
        return "Please enter your Grok API key in the sidebar."
    headers = {"Authorization": f"Bearer {st.session_state.grok_api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": temperature}
    try:
        resp = requests.post(f"{API_BASE}/chat/completions", headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logging.error(f"Grok API error: {e}")
        return f"Grok API error: {str(e)}"

class SignalEngine:
    def compute_signals(self, df: pd.DataFrame, weights: dict = None) -> pd.DataFrame:
        if weights is None:
            weights = {'rsi': 0.28, 'stoch': 0.22, 'bb': 0.18, 'drawdown': 0.15, 'vol_spike': 0.10, 'macd': 0.07}
        df = df.copy()
        df['RSI_Z'] = (df['RSI'].mean() - df['RSI']) / (df['RSI'].std() + 1e-8)
        df['Stoch_Z'] = (df['Stochastic'].mean() - df['Stochastic']) / (df['Stochastic'].std() + 1e-8)
        df['BB_Z'] = (df['BB %'].mean() - df['BB %']) / (df['BB %'].std() + 1e-8)
        df['Drawdown_Z'] = (-df['10d Change %'] - (-df['10d Change %']).mean()) / (df['10d Change %'].std() + 1e-8)
        df['VolSpike_Z'] = (df['Vol Spike'] - df['Vol Spike'].mean()) / (df['Vol Spike'].std() + 1e-8)
        df['MACD_Z'] = df['MACD Hist'] / (df['MACD Hist'].std() + 1e-8)
        df['RSI_Draw_Interact'] = df['RSI_Z'] * df['Drawdown_Z']
        df['Vol_MACD_Interact'] = df['VolSpike_Z'] * df['MACD_Z']
        df['RSI_Score'] = np.clip(df['RSI_Z'] / 3, 0, 1)
        df['Stoch_Score'] = np.clip(df['Stoch_Z'] / 3, 0, 1)
        df['BB_Score'] = np.clip(df['BB_Z'] / 3, 0, 1)
        df['Drawdown_Score'] = np.clip(df['Drawdown_Z'] / 3, 0, 1)
        df['Vol_Spike_Z'] = np.clip(df['VolSpike_Z'] / 3, 0, 1)
        df['MACD_Turn'] = np.clip(df['MACD_Z'] / 3, 0, 1)
        interact_factor = 0.04
        df['Rebound_Score'] = (
            weights['rsi'] * df['RSI_Score'] +
            weights['stoch'] * df['Stoch_Score'] +
            weights['bb'] * df['BB_Score'] +
            weights['drawdown'] * df['Drawdown_Score'] +
            weights['vol_spike'] * df['Vol_Spike_Z'] +
            weights['macd'] * df['MACD_Turn'] +
            interact_factor * (df['RSI_Draw_Interact'] + df['Vol_MACD_Interact'])
        ) * 80
        return df.round(2)

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan'))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def calculate_stochastic(df: pd.DataFrame, k: int = 14) -> pd.Series:
    low_min = df['Low'].rolling(window=k).min()
    high_max = df['High'].rolling(window=k).max()
    return 100 * (df['Close'] - low_min) / (high_max - low_min)

def calculate_bollinger(df: pd.DataFrame, period: int = 20) -> pd.Series:
    sma = df['Close'].rolling(window=period).mean()
    std = df['Close'].rolling(window=period).std()
    upper = sma + 2 * std
    lower = sma - 2 * std
    bb_pct = (df['Close'] - lower) / (upper - lower)
    return bb_pct

def calculate_macd(df: pd.DataFrame) -> pd.Series:
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd - signal

def fetch_data(ticker: str, period: str = "1mo", interval: str = "1d") -> pd.DataFrame:
    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False)
        if data.empty:
            return pd.DataFrame()
        df = data.reset_index()
        df['RSI'] = calculate_rsi(df['Close'])
        df['Stochastic'] = calculate_stochastic(df)
        df['BB %'] = calculate_bollinger(df)
        df['MACD Hist'] = calculate_macd(df)
        df['10d Change %'] = df['Close'].pct_change(periods=10) * 100
        df['Vol Spike'] = df['Volume'] / df['Volume'].rolling(window=10).mean()
        df = df.dropna().reset_index(drop=True)
        return df
    except:
        return pd.DataFrame()

# ==================== OPTIMIZED LOGGING FUNCTIONS ====================

def save_analysis(analysis: dict, is_self_improvement: bool = True):
    """Rewritten logging: Grok Analysis response never truncated. Saved.log focused on self-improvement."""
    try:
        timestamp = analysis.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        analysis.setdefault("timestamp", timestamp)
        response = analysis.get("response", "")
        response_path = None

        # Offload very long responses to separate file to prevent truncation issues
        if len(response) > 50000:
            safe_ts = timestamp.replace(":", "-").replace(" ", "_").replace(".", "")
            tab_name = analysis.get('tab', 'unknown').replace(" ", "_")
            response_path = os.path.join(GROK_RESPONSE_DIR, f"response_{safe_ts}_{tab_name}.txt")
            with open(response_path, "w", encoding="utf-8") as rf:
                rf.write(response)
            analysis["response"] = f"[FULL_RESPONSE_SAVED_SEPARATELY: {response_path}]"
            analysis["full_response_path"] = response_path

        # Route to correct log file
        if is_self_improvement:
            target_log = SAVED_LOG
            analysis["category"] = "self_improvement"
        else:
            target_log = THESES_LOG
            analysis["category"] = "thesis"

        with open(target_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(analysis, ensure_ascii=False) + "\n")

        # Update session state
        key = "saved_analyses" if is_self_improvement else "saved_theses"
        st.session_state.setdefault(key, []).append(analysis)

        st.success(f"{'Self-improvement' if is_self_improvement else 'Thesis'} saved successfully.")
        return True
    except Exception as e:
        st.error(f"Save failed: {e}")
        logging.error(f"Save analysis error: {e}")
        return False

def load_saved_analyses():
    """Loads only self-improvement analyses (focus of optimized Saved.log). Restores full responses if offloaded."""
    if "saved_analyses" not in st.session_state:
        st.session_state.saved_analyses = []
        if os.path.exists(SAVED_LOG):
            try:
                with open(SAVED_LOG, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            analysis = json.loads(line)
                            # Restore full response if saved separately
                            if analysis.get("full_response_path") and os.path.exists(analysis["full_response_path"]):
                                with open(analysis["full_response_path"], "r", encoding="utf-8") as rf:
                                    analysis["response"] = rf.read()
                            # Simple deduplication
                            if not any(a.get("timestamp") == analysis.get("timestamp") and a.get("tab") == analysis.get("tab")
                                       for a in st.session_state.saved_analyses):
                                st.session_state.saved_analyses.append(analysis)
            except Exception as e:
                st.warning(f"Error loading saved.log: {e}")
    return st.session_state.saved_analyses

def auto_optimize_weights(saved_analyses):
    """Self-improvement focused weight optimization (dummy ridge placeholder - ready for real Grok parsing)."""
    if not saved_analyses:
        return {'rsi': 0.28, 'stoch': 0.22, 'bb': 0.18, 'drawdown': 0.15, 'vol_spike': 0.10, 'macd': 0.07}
    try:
        np.random.seed(42)
        n = max(10, len(saved_analyses))
        X = np.random.rand(n, 6)
        y = np.linspace(0.6, 1.8, n)
        alpha = 0.05
        XtX = X.T @ X
        w = np.linalg.solve(XtX + alpha * np.eye(6), X.T @ y)
        w = w / np.sum(w)
        w = np.clip(w, 0.05, 0.35)
        w = w / np.sum(w)
        return {
            'rsi': round(float(w[0]), 2),
            'stoch': round(float(w[1]), 2),
            'bb': round(float(w[2]), 2),
            'drawdown': round(float(w[3]), 2),
            'vol_spike': round(float(w[4]), 2),
            'macd': round(float(w[5]), 2)
        }
    except:
        return {'rsi': 0.28, 'stoch': 0.22, 'bb': 0.18, 'drawdown': 0.15, 'vol_spike': 0.10, 'macd': 0.07}

# ==================== MAIN APP ====================

if 'weights' not in st.session_state:
    st.session_state.weights = {'rsi': 0.28, 'stoch': 0.22, 'bb': 0.18, 'drawdown': 0.15, 'vol_spike': 0.10, 'macd': 0.07}
if 'grok_api_key' not in st.session_state:
    st.session_state.grok_api_key = ""

st.sidebar.title("⚙️ Settings")
st.session_state.grok_api_key = st.sidebar.text_input("Grok API Key", value=st.session_state.grok_api_key, type="password")
selected_model = st.sidebar.selectbox("Grok Model", AVAILABLE_MODELS, index=0)

tab1, tab2, tab3, tab4 = st.tabs(["📊 Live Signals", "🔍 Ticker Deep Dive", "📈 Backtester", "🧠 Grok Analyzer"])

with tab1:
    st.header("Live Rebound Signals")
    if st.button("Refresh All Signals"):
        with st.spinner("Fetching data..."):
            results = []
            for ticker in ALL_TICKERS[:30]:  # Limit for speed
                df = fetch_data(ticker, "3mo")
                if not df.empty and len(df) > 10:
                    engine = SignalEngine()
                    df = engine.compute_signals(df, st.session_state.weights)
                    latest = df.iloc[-1]
                    results.append({
                        "Ticker": ticker,
                        "Rebound Score": latest['Rebound_Score'],
                        "RSI": round(latest['RSI'], 1),
                        "Stoch": round(latest['Stochastic'], 1),
                        "BB%": round(latest['BB %'], 3),
                        "10d Chg%": round(latest['10d Change %'], 1),
                        "Vol Spike": round(latest['Vol Spike'], 2)
                    })
            if results:
                df_results = pd.DataFrame(results).sort_values("Rebound Score", ascending=False)
                st.dataframe(df_results.style.background_gradient(cmap='RdYlGn'), use_container_width=True)

with tab2:
    st.header("Ticker Analysis")
    ticker = st.selectbox("Select Ticker", ALL_TICKERS)
    df = fetch_data(ticker)
    if not df.empty:
        engine = SignalEngine()
        df = engine.compute_signals(df, st.session_state.weights)
        st.subheader(f"{ticker} - Rebound Score: {df.iloc[-1]['Rebound_Score']:.1f}")
        
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                            subplot_titles=("Price & Volume", "RSI & Stochastic", "MACD & BB%"))
        fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close']), row=1, col=1)
        fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'], name="Volume"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['RSI'], name="RSI"), row=2, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['Stochastic'], name="Stochastic"), row=2, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['MACD Hist'], name="MACD Hist"), row=3, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['BB %'], name="BB %"), row=3, col=1)
        fig.update_layout(height=800)
        st.plotly_chart(fig, use_container_width=True)

        if st.button("Generate Grok Thesis"):
            prompt = f"Provide a concise 4-sentence institutional rebound thesis for {ticker} based on current technicals: RSI={df.iloc[-1]['RSI']:.1f}, Stoch={df.iloc[-1]['Stochastic']:.1f}, BB%={df.iloc[-1]['BB %']:.3f}, 10d change={df.iloc[-1]['10d Change %']:.1f}%."
            with st.spinner("Calling Grok..."):
                thesis = call_grok_api(prompt, selected_model, 0.6)
                st.markdown(thesis)
                analysis_data = {"tab": "Ticker Deep Dive", "ticker": ticker, "response": thesis, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                if st.button("Save Thesis"):
                    save_analysis(analysis_data, is_self_improvement=False)

with tab3:
    st.header("Simple Backtester")
    st.info("Backtesting logic placeholder - extend with historical simulation.")

with tab4:
    st.header("🧠 Grok Page Analyzer (Self-Improvement)")
    page_prompt = st.text_area("Custom prompt for Grok analysis (or use default)", 
                               "Analyse this Streamlit trading app for bugs, UX improvements, code optimisations, and power-user features. Focus on self-improvement of the rebound signal engine.")
    
    if st.button("Analyse Current App with Grok"):
        with st.spinner("Generating Grok Analysis..."):
            analysis_response = call_grok_api(page_prompt, selected_model, 0.7)
            st.markdown(analysis_response)
            
            analysis_data = {
                "tab": "Grok Analyzer",
                "response": analysis_response,
                "prompt": page_prompt,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "model": selected_model
            }
            
            if st.button("💾 Save Grok Analysis to saved.log (Self-Improvement)"):
                save_analysis(analysis_data, is_self_improvement=True)

    st.subheader("Saved Self-Improvement Analyses")
    saved = load_saved_analyses()
    if saved:
        for item in saved[-5:]:
            with st.expander(f"{item.get('timestamp')} - {item.get('tab')}"):
                st.markdown(item.get("response", "[Response restored from file]"))
    else:
        st.info("No self-improvement analyses saved yet.")

    st.subheader("Auto-Optimize Weights from Saved Analyses")
    if st.button("Optimize Weights (Self-Improvement Focused)"):
        new_weights = auto_optimize_weights(saved)
        st.session_state.weights = new_weights
        st.success(f"New weights applied: {new_weights}")
        st.json(new_weights)

    if st.button("Apply Default Weights"):
        st.session_state.weights = {'rsi': 0.28, 'stoch': 0.22, 'bb': 0.18, 'drawdown': 0.15, 'vol_spike': 0.10, 'macd': 0.07}
        st.success("Default weights restored.")