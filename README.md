# GeoSupply — Grok-Powered Rebound Scanner

**GeoSupply v1.0**  
A simple, single-file **Streamlit dashboard** for scanning short-term rebound opportunities in the physical economy.

It focuses on stocks in **Mining, Energy, Tech, Shipping, and Renewables** (ASX + US markets). The app calculates technical **Rebound Scores** and **Signal Scores** using indicators like RSI, Stochastic, Bollinger Bands, MACD, and volume spikes. It also integrates with **Grok (xAI)** to generate plain-English trading theses and even suggest improvements to the app itself.

---

## What It Actually Does

- Downloads recent price/volume data for a curated list of geo-supply-related tickers.
- Computes a **Rebound Score** based on oversold conditions, volume conviction, and momentum setups.
- Ranks stocks for potential short-term bounces (typically 1–30 days horizon).
- Provides interactive charts, sector heatmaps, and export options.
- Includes a **Grok AI** tab for generating human-readable trade ideas, entry/exit suggestions, and self-improvement feedback on the scoring logic or code.
- Stores conversation history in `geosupply.db` and logs activity.

The tool is designed to be beginner-friendly while offering advanced users the ability to tweak weights via sidebar sliders and let Grok help evolve the strategy.

---

## Repository Files

- `geosupply.py` — Main Streamlit application (core script)
- `requirements.txt` — Python dependencies
- `geosupply.db` — SQLite database for saving Grok conversations
- `geosupply_analyzer.log` — Log file for debugging
- `Export/` — Directory for exported CSV files
- `LICENSE` — Apache-2.0

**Note:** The app was previously referenced as `geosupply_analyzer.py` in some documentation, but the actual file in the repository is **`geosupply.py`**.

---

## Installation & Quick Start (Beginner-Friendly)

1. **Install Python** (3.10 or higher recommended) from [python.org](https://www.python.org/downloads/).

2. **Clone or download** the repository:
   ```bash
   git clone https://github.com/JeffStone69/XAi.git
   cd XAi

Install dependencies:Bashpip install -r requirements.txt(Or manually: streamlit pandas numpy yfinance plotly requests)
Run the app:Bashstreamlit run geosupply.py
(Optional but recommended) Add your xAI Grok API key in the sidebar to enable AI thesis generation and self-evolution features.
Get a free key at: https://console.x.ai/



Key Features

Top Rebound Leaderboard — Ranked by composite Rebound Score
Interactive Charts — Price, volume, RSI, etc.
Sector Heatmap — Quick view of which geo-supply sectors are showing strength
Grok Integration — One-click AI theses + self-improvement suggestions
Custom Tickers — Add your own symbols via the sidebar
Exports — CSV watchlists and data
Backtesting / Analytics tabs (where implemented)
Fully local — no external database required beyond the included SQLite file


How the Scoring Works (Simplified)
The app pulls ~3 months of data and evaluates:

Oversold conditions (RSI + Stochastic)
Volume spikes (sign of conviction)
Recent price action and technical pattern alignment (MACD, Bollinger Bands)
Customizable weights via sidebar sliders

Higher scores indicate cleaner rebound setups with institutional interest signals.

Grok Self-Evolution
In the dedicated tab, you can ask Grok to:

Analyze current market conditions
Suggest better scoring formulas
Propose code improvements
Generate specific trade theses

This “self-evolving” aspect is one of the more unique parts of the project.

Important Disclaimer
This tool is for educational and research purposes only.
It is NOT financial advice.
Past performance does not guarantee future results.
Always do your own due diligence and trade at your own risk.

Credits

Created by: JeffStone69
Enhanced with help from Grok (xAI)
Built with Streamlit, yfinance, Plotly, and the xAI API


Star the repo if you're exploring real-time supply-chain and commodity-related market signals.
Happy hunting — and may your rebounds be strong.
Version: 1.0 (April 2026)
License: Apache-2.0 (see LICENSE file)
