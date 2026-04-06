#!/usr/bin/env bash
# Foodie Agent — Setup script
# Creates virtual environment and installs dependencies

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

echo "======================================"
echo "  🍜 Foodie Agent — Setup"
echo "======================================"

# 1. Create .env from example if it doesn't exist
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "[1/4] Creating .env from .env.example ..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "      ✅ .env created — please edit it and fill in your API keys!"
else
    echo "[1/4] .env already exists, skipping."
fi

# 2. Create virtual environment
if [ -d "$VENV_DIR" ]; then
    echo "[2/4] Virtual environment already exists at .venv/, skipping."
else
    echo "[2/4] Creating virtual environment ..."
    python -m venv "$VENV_DIR"
    echo "      ✅ .venv created."
fi

# 3. Activate venv (show instructions for manual activation)
echo ""
echo "[3/4] Activate the virtual environment:"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    echo "      source .venv/Scripts/activate"
else
    echo "      source .venv/bin/activate"
fi

# 4. Install dependencies
echo "[4/4] Installing dependencies ..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    "$VENV_DIR/Scripts/pip" install -r "$PROJECT_DIR/requirements.txt"
else
    "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
fi
echo "      ✅ Dependencies installed."

echo ""
echo "======================================"
echo "  ✅ Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Edit .env and fill in your API keys"
echo "  2. Activate: source .venv/bin/activate  (Linux/macOS)"
echo "              .venv\\Scripts\\activate     (Windows Git Bash)"
echo "  3. Run:     py main.py"
echo "======================================"
