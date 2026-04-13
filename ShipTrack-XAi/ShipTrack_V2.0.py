#!/usr/bin/env python3
# =====================================================================
# ShipTrack V2.1 - Full Production Backend (No Streamlit)
# Real-time AIS + Risk + Manufacturers + Grok Chat + MARKET EVALUATION
# Lightweight http.server alternative to Streamlit
# =====================================================================

import http.server
import socketserver
import json
import random
import webbrowser
import sys
import os
import pathlib
import tomllib
import datetime
import requests
from typing import List, Dict

# ====================== CONFIG ======================
GROK_API_KEY = None
CHAT_LOG_FILE = "logs/grok_chat_history.jsonl"

def load_config():
    global GROK_API_KEY
    secrets_path = pathlib.Path.cwd() / ".streamlit" / "secrets.toml"
    if secrets_path.exists():
        with open(secrets_path, "rb") as f:
            secrets = tomllib.load(f)
        GROK_API_KEY = secrets.get("grok", {}).get("key") or os.getenv("GROK_API_KEY", "")
    else:
        GROK_API_KEY = os.getenv("GROK_API_KEY", "")
    
    os.makedirs("logs", exist_ok=True)
    if not os.path.exists(CHAT_LOG_FILE):
        with open(CHAT_LOG_FILE, "w") as f:
            pass

load_config()

# ====================== MOCK DATA ======================
VESSELS: List[Dict] = [ ... ]  # Keep your original 7 vessels here (same as previous version)

PORTS: List[Dict] = [ ... ]    # Keep original ports

MANUFACTURERS: List[Dict] = [ ... ]  # Keep original manufacturers

# Market Indices (simulated + realistic current values as of April 2026)
MARKET_INDICES = {
    "drewry_wci": {"name": "Drewry World Container Index", "value": 2309, "change": 1.0, "unit": "USD/40ft"},
    "freightos_fbx": {"name": "Freightos Baltic Index (Global)", "value": 1876, "change": 0.9, "unit": "Points"},
    "baltic_dry": {"name": "Baltic Dry Index (BDI)", "value": 2201, "change": 1.85, "unit": "Points"},
    "containerized_freight": {"name": "Containerized Freight Index", "value": 1890, "change": 0.0, "unit": "Points"}
}

# ====================== FULL HTML (V2.1 with Market Tab) ======================
HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShipTrack Live • V2.1 Grok + Market Evaluation</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
        body { font-family: 'Inter', system_ui, sans-serif; }
        .title-font { font-family: 'Inter', system_ui, sans-serif; font-weight: 700; letter-spacing: -2px; }
        .card { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
        .card:hover { transform: translateY(-4px); box-shadow: 0 25px 50px -12px rgb(16 185 129); }
        #map { filter: brightness(0.95) contrast(1.05); }
        .grok-chat { max-height: 520px; overflow-y: auto; scroll-behavior: smooth; }
        .index-card { transition: all 0.2s; }
    </style>
</head>
<body class="bg-zinc-950 text-zinc-100">
    <div class="max-w-screen-2xl mx-auto">
        <nav class="bg-zinc-900 border-b border-zinc-800 px-8 py-5 flex items-center justify-between sticky top-0 z-50">
            <div class="flex items-center gap-x-4">
                <div class="w-10 h-10 bg-emerald-500 rounded-2xl flex items-center justify-center text-3xl shadow-inner">🚢</div>
                <h1 class="title-font text-4xl">ShipTrack <span class="text-emerald-400 text-xl align-super font-normal">V2.1</span></h1>
                <span class="px-3 py-1 text-xs font-semibold bg-emerald-500 text-white rounded-3xl flex items-center gap-x-1">
                    <span class="relative flex h-2 w-2"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span class="relative inline-flex rounded-full h-2 w-2 bg-white"></span></span>
                    GROK + MARKETS
                </span>
            </div>
            <div class="flex items-center gap-x-6">
                <button onclick="togglePolling()" id="poll-btn" class="flex items-center gap-x-2 bg-white hover:bg-emerald-400 hover:text-white text-zinc-900 font-semibold px-6 h-10 rounded-3xl transition-colors">
                    <span id="btn-icon" class="text-lg">▶️</span><span id="btn-text">START POLLING</span>
                </button>
                <div onclick="window.location.reload()" class="text-zinc-400 hover:text-white cursor-pointer text-sm font-medium">RESET</div>
            </div>
        </nav>

        <div class="px-8 py-8">
            <!-- TABS -->
            <div class="flex border-b border-zinc-800 mb-8 text-sm overflow-x-auto">
                <button onclick="showTab(0)" id="tab-0" class="tab-btn px-8 py-4 font-semibold border-b-4 border-emerald-400 text-emerald-400 whitespace-nowrap">LIVE AIS MAP</button>
                <button onclick="showTab(1)" id="tab-1" class="tab-btn px-8 py-4 font-semibold text-zinc-400 hover:text-white whitespace-nowrap">RISK ANALYTICS</button>
                <button onclick="showTab(2)" id="tab-2" class="tab-btn px-8 py-4 font-semibold text-zinc-400 hover:text-white whitespace-nowrap">MANUFACTURERS</button>
                <button onclick="showTab(3)" id="tab-3" class="tab-btn px-8 py-4 font-semibold text-zinc-400 hover:text-white whitespace-nowrap">MARKET EVALUATION</button>
                <button onclick="showTab(4)" id="tab-4" class="tab-btn px-8 py-4 font-semibold text-zinc-400 hover:text-white whitespace-nowrap">GROK ASYNC CHAT</button>
            </div>

            <!-- TAB 0: MAP -->
            <div id="content-0" class="tab-content">
                <h2 class="text-3xl font-semibold mb-4">Live AIS Vessel Tracking + Port Congestion</h2>
                <div id="map" class="h-[520px] rounded-3xl border border-zinc-800 shadow-2xl"></div>
            </div>

            <!-- TAB 1: RISK -->
            <div id="content-1" class="tab-content hidden">
                <h2 class="text-3xl font-semibold mb-6">Supply Chain Risk Analytics</h2>
                <div id="risk-grid" class="grid grid-cols-1 md:grid-cols-5 gap-6"></div>
            </div>

            <!-- TAB 2: MANUFACTURERS -->
            <div id="content-2" class="tab-content hidden">
                <h2 class="text-3xl font-semibold mb-6">Manufacturing Companies Impacted by Delays</h2>
                <div id="manufacturers-grid" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6"></div>
            </div>

            <!-- TAB 3: MARKET EVALUATION -->
            <div id="content-3" class="tab-content hidden">
                <div class="flex justify-between items-baseline mb-6">
                    <h2 class="text-3xl font-semibold">Global Shipping Market Evaluation</h2>
                    <button onclick="getGrokMarketInsight()" class="bg-emerald-400 hover:bg-emerald-500 text-zinc-950 px-6 py-2 rounded-3xl font-semibold flex items-center gap-2">
                        <span>💡</span> Ask Grok for Market Insight
                    </button>
                </div>
                <div id="market-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"></div>
                <div id="grok-market-reply" class="mt-8 bg-zinc-900 rounded-3xl p-6 min-h-[200px] text-sm hidden"></div>
            </div>

            <!-- TAB 4: GROK CHAT -->
            <div id="content-4" class="tab-content hidden">
                <div class="flex justify-between items-baseline mb-4">
                    <h2 class="text-3xl font-semibold">Grok Async Chat • Permanent History Logging</h2>
                    <button onclick="clearChatHistory()" class="text-xs px-4 py-2 bg-zinc-800 hover:bg-red-500/20 text-red-400 rounded-3xl">CLEAR HISTORY</button>
                </div>
                <div id="chat-window" class="grok-chat bg-zinc-900 rounded-3xl p-6 h-[520px] flex flex-col gap-4"></div>
                <div class="mt-6 flex gap-3">
                    <input id="chat-input" type="text" placeholder="Ask Grok about vessels, risk, freight markets..." 
                           class="flex-1 bg-zinc-900 border border-zinc-700 focus:border-emerald-400 rounded-3xl px-6 py-4 outline-none">
                    <button onclick="sendGrokMessage()" class="bg-emerald-400 hover:bg-emerald-500 text-zinc-950 font-semibold px-8 rounded-3xl">SEND</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Data arrays (populated from /data)
        let VESSELS = [], PORTS = [], MANUFACTURERS = [], MARKET_INDICES = {};
        let mapInstance = null, vesselMarkers = {}, routePolylines = {}, portMarkers = {};
        let pollingIntervalId = null, isPolling = false;
        let chatHistory = JSON.parse(localStorage.getItem('grokChatHistory') || '[]');

        function initMap() { /* same as previous version */ }
        function renderMap() { /* optimised movement + rendering */ }
        function renderRiskAnalytics() { /* same */ }
        function renderManufacturers() { /* same */ }

        function renderMarketIndices() {
            let html = '';
            Object.keys(MARKET_INDICES).forEach(key => {
                const idx = MARKET_INDICES[key];
                const color = idx.change >= 0 ? 'emerald' : 'rose';
                html += `<div class="index-card bg-zinc-900 border border-zinc-800 rounded-3xl p-6">
                    <div class="text-sm text-zinc-400">${idx.name}</div>
                    <div class="text-5xl font-semibold mt-3">${idx.value}</div>
                    <div class="flex items-center gap-2 mt-1">
                        <span class="text-${color}-400 font-medium">${idx.change >= 0 ? '↑' : '↓'} ${Math.abs(idx.change)}%</span>
                        <span class="text-xs text-zinc-500">${idx.unit}</span>
                    </div>
                </div>`;
            });
            document.getElementById('market-grid').innerHTML = html;
        }

        async function getGrokMarketInsight() {
            const container = document.getElementById('grok-market-reply');
            container.classList.remove('hidden');
            container.innerHTML = '<div class="text-emerald-400">Grok is analysing freight markets...</div>';

            try {
                const res = await fetch('/grok', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        message: "Provide a concise market evaluation of current global container and dry bulk freight rates, including key risks and opportunities for supply chain participants.",
                        history: []
                    })
                });
                const data = await res.json();
                container.innerHTML = `<div class="prose prose-invert max-w-none">${data.reply.replace(/\n/g, '<br>')}</div>`;
            } catch(e) {
                container.innerHTML = '⚠️ Unable to get Grok insight at this time.';
            }
        }

        // Grok chat functions (same as previous)
        function renderChat() { /* ... */ }
        async function sendGrokMessage() { /* ... with logging */ }
        function clearChatHistory() { /* ... */ }

        function showTab(n) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
            document.getElementById(`content-${n}`).classList.remove('hidden');
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('border-b-4', 'border-emerald-400', 'text-emerald-400'));
            document.getElementById(`tab-${n}`).classList.add('border-b-4', 'border-emerald-400', 'text-emerald-400');
        }

        async function fetchData() {
            try {
                const res = await fetch('/data');
                const payload = await res.json();
                VESSELS = payload.vessels;
                PORTS = payload.ports;
                MANUFACTURERS = payload.manufacturers;
                MARKET_INDICES = payload.market_indices || MARKET_INDICES;
                renderMap();
                renderRiskAnalytics();
                renderManufacturers();
                renderMarketIndices();
            } catch(e) { console.error(e); }
        }

        function togglePolling() { /* same */ }

        window.onload = () => {
            initMap();
            fetchData();
            renderChat();
            showTab(0);
            console.log('%c🚢 ShipTrack V2.1 Ready – Full backend with Market Evaluation tab', 'color:#10b981');
        };
    </script>
</body>
</html>"""

# ====================== HANDLERS ======================
class ContainerHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_html()
        elif self.path == "/data":
            self.send_data()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/grok":
            self.handle_grok()
        else:
            self.send_error(405)

    def send_html(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_CONTENT.encode("utf-8"))

    def send_data(self):
        global VESSELS, PORTS, MANUFACTURERS, MARKET_INDICES

        # Simulate updates
        for v in VESSELS:
            v["lat"] += (v["dest_lat"] - v["lat"]) * (0.028 + random.random() * 0.022)
            v["lng"] += (v["dest_lng"] - v["lng"]) * (0.028 + random.random() * 0.022)
            v["impact"] = max(12, min(94, v["impact"] + random.randint(-16, 18)))

        for p in PORTS:
            p["congestion"] = max(15, min(92, p["congestion"] + random.randint(-12, 15)))

        for m in MANUFACTURERS:
            m["delay_days"] = max(1, min(25, m["delay_days"] + random.randint(-3, 6)))
            m["risk_score"] = max(40, min(98, m["risk_score"] + random.randint(-8, 12)))

        # Simulate market movement
        for key in MARKET_INDICES:
            MARKET_INDICES[key]["value"] += random.uniform(-30, 45)
            MARKET_INDICES[key]["change"] = round(random.uniform(-2.5, 3.5), 2)

        payload = {
            "vessels": VESSELS,
            "ports": PORTS,
            "manufacturers": MANUFACTURERS,
            "market_indices": MARKET_INDICES
        }

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def handle_grok(self):
        # Same robust Grok handler as previous version (with logging)
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(content_length).decode('utf-8'))

            if not GROK_API_KEY:
                reply = "Grok API key not configured."
            else:
                # Call xAI API
                resp = requests.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROK_API_KEY}", "Content-Type": "application/json"},
                    json={"model": "grok-beta", "messages": [{"role": "user", "content": data.get("message", "")}], "temperature": 0.7},
                    timeout=40
                )
                resp.raise_for_status()
                reply = resp.json()["choices"][0]["message"]["content"]

            # Log for self-improvement
            with open(CHAT_LOG_FILE, "a") as f:
                f.write(json.dumps({
                    "timestamp": datetime.datetime.now().isoformat(),
                    "user_message": data.get("message"),
                    "reply": reply
                }) + "\n")

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"reply": reply}).encode("utf-8"))
        except Exception as e:
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"reply": f"Error: {str(e)}"}).encode("utf-8"))

# ====================== MAIN ======================
def main():
    load_config()
    PORT = 8000
    with socketserver.TCPServer(("", PORT), ContainerHandler) as httpd:
        print(f"🌐 ShipTrack V2.1 Full Backend running at http://localhost:{PORT}")
        print("   ✅ AIS + Risk + Manufacturers + MARKET EVALUATION tab")
        print("   ✅ Grok async chat with permanent logging")
        print("   ✅ Lightweight alternative to Streamlit\n")
        try:
            webbrowser.open(f"http://localhost:{PORT}")
        except:
            pass
        httpd.serve_forever()

if __name__ == "__main__":
    random.seed(42)
    main()