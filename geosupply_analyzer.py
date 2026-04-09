```python
#!/usr/bin/env python3
"""
🌍 GeoSupply Short-Term Profit Predictor v2.5
Improved by Grok: Changes and Enhancements
- **Signal Calculation Sophistication**: Enhanced RSI with 14-period standard, added MACD signal, Bollinger Band width for volatility, and a composite score using weighted factors. Normalized signals with z-score and added trend detection.
- **UI Improvements**: Added sector-specific color coding in leaderboard, interactive filters for signals, improved chart interactivity with annotations, responsive layout with columns.
- **New Features**: Added "Save Evolutions" to store previous script versions in session state and download as TXT. Added export options for data and charts. Integrated news fetch for top tickers in Thesis tab.
- **Robustness**: Improved error handling in data fetch and signals, added input validation, increased cache TTL, handled empty data gracefully, added logging for improvements.
- **Other**: Updated to v2.5, refined prompts for Grok, added auto-refresh toggle.
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
import io  # For TXT download

st.set_page_config(page_title="GeoSupply v2.5", page_icon="🌍", layout="wide")

# ====================== CONFIG ======================
SECTORS = {
    "Mining": ["BHP.AX","RIO.AX","FMG.AX","FCX","NEM","VALE","SCCO"],
    "Shipping": ["ZIM","MATX","SBLK","QUB.AX","DAC"],
    "Energy": ["XOM","CVX","STO.AX","WHC.AX","CCJ","COP"],
    "Renewable": ["NEE","FSLR","ENPH","IGO.AX"],
    "Tech": ["NVDA","TSLA","WTC.AX","XRO.AX","AMD"]
}
ALL_TICKERS = list(dict.fromkeys(sum(SECTORS.values(), [])))
SECTOR_COLORS = {
    "Mining": "#FF5733", "Shipping": "#33FF57", "Energy": "#3357FF",
    "Renewable": "#FF33A1", "Tech": "#A133FF", "Other": "#808080"
}

logging.basicConfig(filename="geosupply.log", level=logging.INFO)

# ====================== DATA ======================
@st.cache_data(ttl=300)  # Increased TTL for robustness
def fetch_data(tickers):
    try:
        data = yf.Tickers(tickers).download(period="3mo", group_by="ticker", auto_adjust=True, threads=True)  # Extended period for better signals
        return {ticker: data[ticker].dropna(how="all") for ticker in tickers if not data[ticker].empty}
    except Exception as e:
        logging.error(f"Fetch error: {e}")
        st.error(f"Data fetch error: {e}. Retrying with single thread.")
        try:  # Fallback to single thread
            return {t: yf.download(t, period="3mo", auto_adjust=True).dropna(how="all") for t in tickers}
        except Exception as e2:
            logging.error(f"Fallback fetch error: {e2}")
            st.error(f"Fallback failed: {e2}")
            return {}

# ====================== SIGNALS ======================
@st.cache_data(ttl=300)
def compute_signals(raw_data, horizon="5d", selected_sectors=None, min_signal=0.0):
    lookback = {"5d":5, "10d":10, "1mo":20}.get(horizon, 5)
    records = []
    for ticker, df in raw_data.items():
        if len(df) < lookback + 14 or "Close" not in df.columns: continue  # Ensure enough data for indicators
        try:
            close = df["Close"].dropna()
            ret = close.pct_change().dropna()
            
            # Price Change
            price_change = (close.iloc[-1] / close.iloc[-(lookback+1)] - 1) * 100
            
            # Volume Spike
            vol_spike = df["Volume"].iloc[-1] / df["Volume"].rolling(lookback).mean().iloc[-1] if df["Volume"].mean() > 0 else 1.0
            
            # Enhanced RSI (14-period)
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            
            # MACD
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            signal_line = macd.ewm(span=9, adjust=False).mean()
            macd_hist = (macd - signal_line).iloc[-1]
            
            # Bollinger Band Width for volatility
            sma20 = close.rolling(20).mean()
            std20 = close.rolling(20).std()
            bb_width = (std20 / sma20 * 100).iloc[-1]
            
            # Composite Score: Weighted (price 40%, vol 20%, rsi 15%, macd 15%, bb 10%)
            score = (price_change * 0.4)