#!/bin/bash
# SetupApp.sh - Fixed single-click installer for ShipTrack Live + GeoSupply Rebound Oracle
# Creates folder structure, fixes requirements, and securely stores API keys

set -e  # Exit immediately if any command fails

echo "🚢🌍 Setting up ShipTrack Live AIS + GeoSupply Rebound Oracle"
echo "=================================================================="

# Ask for installation directory
read -p "Enter installation directory (default: ~/ShipTrack-XAi): " INSTALL_DIR
INSTALL_DIR=${INSTALL_DIR:-~/ShipTrack-XAi}

echo "📁 Creating folder structure in $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

mkdir -p Basecode GeoSupply .streamlit logs Export

# Create placeholder for Basecode
cat > Basecode/Basecode.V1.txt << 'EOF'
# Paste the full Basecode.V1 content here (the original Python script you provided)
# This file will be executed directly by the run script
EOF

cat > GeoSupply/README.md << 'EOF'
# GeoSupply Rebound Oracle
Place analyserV4.py (or your main Streamlit file) in this folder and name it analyserV4.py
EOF

# Fixed requirements.txt (removed sqlite3)
cat > requirements.txt << EOF
streamlit
pandas
numpy
yfinance
plotly
requests
python-dotenv
folium
streamlit-folium
geopy
EOF

echo ""
echo "🔑 Secure API Key Storage"
echo "Enter your keys (they will be stored securely in .streamlit/secrets.toml)"

read -sp "Enter your xAI / Grok API key (starts with xai- or leave empty): " GROK_KEY
echo ""

read -sp "Enter your Alpha Vantage API key (optional): " ALPHA_KEY
echo ""

# Create secrets.toml with secure permissions
mkdir -p .streamlit

cat > .streamlit/secrets.toml << EOF
[grok]
key = "${GROK_KEY:-}"

[alpha_vantage]
key = "${ALPHA_KEY:-CXJGLOIMINTIXQLE}"

[general]
app_name = "ShipTrack + GeoSupply Hybrid"
version = "V2.0"
EOF

chmod 600 .streamlit/secrets.toml

# Install dependencies
echo ""
echo "📦 Installing Python dependencies (this may take a minute)..."
pip install --upgrade pip
pip install -r requirements.txt

# Create launcher script
cat > run.sh << 'EOF'
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
EOF

chmod +x run.sh

echo ""
echo "✅ Setup completed successfully!"
echo ""
echo "📂 Location: $INSTALL_DIR"
echo ""
echo "Next steps:"
echo "   1. Paste the full content of your original Basecode.V1 into Basecode/Basecode.V1.txt"
echo "   2. Copy your analyserV4.py (or main Streamlit file) into the GeoSupply/ folder"
echo "   3. Run the apps with:   ./run.sh"
echo ""
echo "Your API keys are safely stored (readable only by you)."
echo "Enjoy your hybrid maritime + supply chain intelligence platform! 🚢📈"