#!/bin/bash
cd "$(dirname "$0")"

echo "🚀 Launching ShipTrack Live AIS Dashboard on http://localhost:8000 ..."
python3 -c '
import sys
sys.path.insert(0, ".")
with open("Basecode/Basecode.V1.txt", "r", encoding="utf-8") as f:
    exec(f.read())
' &

echo "🌍 Launching GeoSupply Rebound Oracle on http://localhost:8501 ..."
streamlit run GeoSupply/analyserV4.py --server.port 8501 --server.headless true &

echo ""
echo "✅ Both applications are starting!"
echo "   → ShipTrack AIS Dashboard : http://localhost:8000"
echo "   → GeoSupply Oracle        : http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop both apps."
wait
