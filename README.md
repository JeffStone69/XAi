GeoSupply v1.0 - Grok Self-Evolving Rebound Profit Predictor
Readme.txt
What is GeoSupply?
GeoSupply is a simple, powerful, single-file stock market dashboard built with Streamlit. It scans real-time data from the ASX and US markets (Mining, Energy, Tech, Shipping, and Renewable sectors) and highlights short-term "rebound" opportunities — stocks that look ready to bounce back in the next 1–30 days.
It uses technical indicators (RSI, Stochastic, Bollinger Bands, MACD, volume spikes, etc.) to calculate a Rebound Score and Signal Score.
It also connects to Grok (xAI) so you can instantly get smart AI-written trading theses, entry/exit ideas, and even let Grok suggest improvements to the app itself.
Perfect for beginners who want to learn while seeing live market signals — no complicated setup required!
Who is this for?

Complete beginners who have never used Python before
Anyone who wants to understand stock rebounds without staring at 10 charts
People who want to experiment with AI (Grok) helping them trade smarter

IMPORTANT DISCLAIMER
This app is for education and research only.
It is NOT financial advice.
Past performance does not predict future results.
Trade at your own risk. Always do your own research.

How to Install and Run (Step-by-Step for Beginners)

Install Python
Go to https://www.python.org/downloads/
Download and install Python 3.10 or higher (make sure to tick “Add Python to PATH” during installation).

Download the App
Save the file you received as geosupply_analyzer.py (or copy the entire code into a new file with that name).

Install Required Packages
Open your computer’s Command Prompt (Windows) or Terminal (Mac/Linux) and run these commands one by one:Bashpip install streamlit pandas numpy yfinance plotly requests pathlib
Get Your Free Grok API Key (Optional but Recommended)
Go to https://console.x.ai/
Sign up / log in with your X (Twitter) account
Create a new API key
Copy the key (it looks like gsk_xxxxxxxxxxxxxxxx)

Run the App
In the same Command Prompt / Terminal, navigate to the folder where you saved geosupply_analyzer.py and type:Bashstreamlit run geosupply_analyzer.pyYour web browser should automatically open the dashboard.


First-Time Setup Inside the App

On the left sidebar you will see “Grok API”
Paste your Grok API key and press Enter.
Click the big blue button “🔄 Fetch Latest Market Data” (this downloads the latest prices).

You are now ready to use all features!

Quick Guide to the Tabs













































TabWhat You SeeBest For Beginners🚀 Top 5 ReboundThe 5 hottest rebound opportunities right nowStart here every day📈 Full LeaderboardAll stocks ranked by Rebound ScoreSee the full picture📊 ChartsBeautiful interactive price + volume + RSI chartClick any ticker to understand why it scored high🔥 HeatmapAverage score by sector (Mining, Energy, etc.)Spot which sector is strongest🤖 Grok Self-EvolutionLet Grok rewrite/improve the entire appAdvanced — watch Grok make the app smarter📈 BacktestHistorical test: “Would this strategy have made money?”See if the signals actually worked in the past📊 AnalyticsScatter plots of volume vs scoreFun way to explore relationships
Pro Tip for Beginners:
Start every session by going to Top 5 Rebound → pick a ticker → click “Generate Grok Thesis for this ticker”. Grok will give you a simple 3–4 sentence trading idea with entry, target, and stop-loss.

How the Magic Works (Simple Explanation)

The app downloads the last 3 months of price data.
It calculates:
How oversold the stock is (RSI + Stochastic)
Volume spike (big buyers coming in)
Recent price drop (the “rebound” setup)
MACD and Bollinger Band position

These are combined into a Rebound Score (higher = better opportunity).
You can move the sliders in the sidebar to change how important each factor is.
Grok AI then writes human-readable explanations.


Common Questions
Q: Do I need to pay for anything?
A: No. Grok API is free for reasonable personal use (check x.ai for current limits).
Q: Why is the data not updating?
A: Click “🔄 Fetch Latest Market Data” again. It refreshes every time you press it.
Q: Can I add my own stocks?
A: Yes! In the sidebar under “Custom Tickers” type any ticker symbols separated by commas (e.g. BHP.AX, AAPL, TSLA).
Q: The app feels slow the first time.
A: That’s normal — it is downloading market data. After the first run everything is cached and becomes very fast.

Advanced Feature: Grok Self-Evolution
In the tab “🤖 Grok Self-Evolution” click the big button “🚀 Run Full Self-Improvement Cycle”.
Grok will analyse the current market and then give you:

3 high-conviction trades
A better scoring formula
New code improvements you can copy-paste

This is the “self-evolving” part — the app literally gets smarter every time you run it!

Files Created by the App

geosupply.db → saves your Grok conversations
geosupply_analyzer.log → debugging log
Export/ folder → any CSV files you download

You can safely delete these if you want to start fresh.

Need Help?

Check the log file geosupply_analyzer.log
Make sure your Grok API key is correct
Re-run pip install commands if you see import errors

Enjoy learning and trading smarter!
Built with ❤️ and Grok (xAI) — April 2026
Version: 1.0 (Basecode)
License: Free for personal use (see LICENSE file if present)
You now have everything you need to start using GeoSupply today! 🚀
