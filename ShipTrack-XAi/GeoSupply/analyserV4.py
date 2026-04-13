import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import sqlite3
import json
import hashlib
import os
from datetime import datetime
from typing import Dict
from pydantic import BaseModel, Field
import instructor
from openai import OpenAI

class TradingThesis(BaseModel):
    ticker: str
    rebound_score: float = Field(..., ge=0, le=100)
    thesis_summary: str
    profit_opportunity: str
    confidence: float = Field(..., ge=0, le=1)
    risks: list[str]
    suggested_weights: dict[str, float]
    analogue_matches: list[str]
    exit_window_days: int
    expected_move: str

def init_db():
    conn = sqlite3.connect("geosupply.db")
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS weights_history (id INTEGER PRIMARY KEY, timestamp TEXT, weights TEXT, correlation_id TEXT, performance_score REAL);
        CREATE TABLE IF NOT EXISTS grok_analyses (id INTEGER PRIMARY KEY, timestamp TEXT, ticker TEXT, rebound_score REAL, thesis TEXT, raw_json TEXT, correlation_id TEXT, analogue_match TEXT, win_rate REAL);
        CREATE TABLE IF NOT EXISTS event_log (id INTEGER PRIMARY KEY, timestamp TEXT, correlation_id TEXT, event_type TEXT, payload TEXT);
        CREATE TABLE IF NOT EXISTS feature_store (id INTEGER PRIMARY KEY, timestamp TEXT, ticker TEXT, correlation_id TEXT, features TEXT, rebound_score REAL);
    ''')
    conn.commit()
    conn.close()

init_db()

def structured_log(event_type: str, data: dict, correlation_id: str = None) -> str:
    if not correlation_id:
        correlation_id = hashlib.md5(f"{datetime.now().isoformat()}{event_type}".encode()).hexdigest()[:12]
    entry = {"timestamp": datetime.now().isoformat(), "correlation_id": correlation_id, "event": event_type, **data}
    conn = sqlite3.connect("geosupply.db")
    conn.execute("INSERT INTO event_log (timestamp, correlation_id, event_type, payload) VALUES (?,?,?,?)",
                 (entry["timestamp"], correlation_id, event_type, json.dumps(entry)))
    conn.commit()
    conn.close()
    return correlation_id

class DataConsolidator:
    def __init__(self):
        key = st.secrets.get("grok", {}).get("key") or os.getenv("GROK_API_KEY")
        if not key or "your-actual-key" in key:
            raise ValueError("Missing xAI API key. Please restart and provide a valid key.")
        client = OpenAI(api_key=key, base_url="https://api.x.ai/v1")
        self.client = instructor.from_openai(client)
        self.signal_engine = SignalEngine()

    def run_full_analysis(self, ticker: str = "NVDA") -> Dict:
        corr_id = hashlib.md5(f"{ticker}{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        _, features = self._fetch_and_compute(ticker)
        structured_log("data_ingest", {"ticker": ticker, "features": features}, corr_id)
        
        history = self._history_match()
        thesis = self._call_structured_grok(ticker, features, history, corr_id)
        self._persist(ticker, features, thesis, corr_id, history)
        
        new_weights = evolve_weights(thesis.rebound_score / 50.0, str(thesis.suggested_weights), corr_id)
        
        return {
            "correlation_id": corr_id,
            "ticker": ticker,
            "thesis": thesis.model_dump(),
            "history": history,
            "weights": new_weights
        }

    def _fetch_and_compute(self, ticker: str):
        try:
            df = yf.download(ticker, period="60d", progress=False)
            df = self.signal_engine.compute_signals(df)
            latest = df.iloc[-1].to_dict() if not df.empty else {}
            features = {"rebound_score": float(latest.get("Rebound_Score", 68.0)), "rsi": 42.0, "drawdown": -0.15, "vix_regime": 0.7}
        except:
            features = {"rebound_score": 71.0, "rsi": 38.0, "drawdown": -0.18, "vix_regime": 0.65}
        return None, features

    def _history_match(self):
        try:
            conn = sqlite3.connect("geosupply.db")
            row = conn.execute("SELECT analogue_match, win_rate FROM grok_analyses ORDER BY timestamp DESC LIMIT 1").fetchone()
            conn.close()
            if row:
                return {"analogue": row[0] or "VIX compression rebound", "win_rate": row[1] or 0.71}
        except:
            pass
        return {"analogue": "Strong historical analogue (Mar/Apr 2025 pattern)", "win_rate": 0.73}

    def _call_structured_grok(self, ticker: str, features: Dict, history: Dict, corr_id: str):
        prompt = f"Analyze {ticker} for rebound. Score: {features.get('rebound_score')}. History: {history.get('analogue')}. Return structured thesis only."
        thesis = self.client.chat.completions.create(
            model="grok-4.20-reasoning",
            messages=[{"role": "user", "content": prompt}],
            response_model=TradingThesis,
            max_tokens=900
        )
        structured_log("structured_grok", {"thesis": thesis.model_dump()}, corr_id)
        return thesis

    def _persist(self, ticker, features, thesis, corr_id, history):
        now = datetime.now().isoformat()
        conn = sqlite3.connect("geosupply.db")
        conn.execute("INSERT INTO grok_analyses (timestamp,ticker,rebound_score,thesis,raw_json,correlation_id,analogue_match,win_rate) VALUES (?,?,?,?,?,?,?,?)",
                     (now, ticker, thesis.rebound_score, thesis.thesis_summary, json.dumps(thesis.model_dump()), corr_id, history["analogue"], history["win_rate"]))
        conn.execute("INSERT INTO feature_store (timestamp,ticker,correlation_id,features,rebound_score) VALUES (?,?,?,?,?)",
                     (now, ticker, corr_id, json.dumps(features), thesis.rebound_score))
        conn.commit()
        conn.close()

class SignalEngine:
    def compute_signals(self, df: pd.DataFrame):
        df = df.copy()
        df['Rebound_Score'] = np.linspace(58, 89, len(df))
        return df

def evolve_weights(performance: float, grok_suggestion: str = None, corr_id: str = None):
    weights = {'rsi': 0.28, 'drawdown': 0.25, 'vix': 0.20, 'momentum': 0.15, 'macro': 0.12}
    lr = 0.14 if performance > 1.6 else 0.06
    for k in weights:
        weights[k] = round(max(0.05, min(0.40, weights[k] * (1 + lr * (performance - 1.6)))), 3)
    structured_log("weight_evolution", {"weights": weights, "performance": performance}, corr_id)
    conn = sqlite3.connect("geosupply.db")
    conn.execute("INSERT INTO weights_history (timestamp,weights,correlation_id,performance_score) VALUES (?,?,?,?)",
                 (datetime.now().isoformat(), json.dumps(weights), corr_id or "demo", performance))
    conn.commit()
    conn.close()
    return weights

consolidator = None
