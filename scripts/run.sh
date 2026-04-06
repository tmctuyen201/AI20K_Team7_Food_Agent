#!/usr/bin/env bash
# Foodie Agent — Run script
# Must be run with the virtual environment activated

set -e

# Activate venv if not already activated
if [ -z "$VIRTUAL_ENV" ]; then
    PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    VENV_DIR="$PROJECT_DIR/.venv"

    if [ ! -d "$VENV_DIR" ]; then
        echo "❌ Virtual environment not found. Run setup.sh first."
        exit 1
    fi

    echo "🔧 Activating virtual environment ..."
    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate"
fi

echo "🚀 Starting Foodie Agent ..."
echo ""

cd "$(dirname "${BASH_SOURCE[0]}")"
py main.py
