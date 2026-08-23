#!/usr/bin/env bash
# exit on error
set -o errexit

echo "========================================="
echo "🔧 ChaiTea Backend Build Script"
echo "========================================="

# Force Python 3.10
echo "==> Checking Python version..."
python3.10 --version || {
    echo "❌ Python 3.10 not found! Trying python3..."
    python3 --version
}

# Install Python dependencies using Python 3.10
echo "==> Upgrading pip..."
python3.10 -m pip install --upgrade pip setuptools wheel || python3 -m pip install --upgrade pip setuptools wheel

echo "==> Installing dependencies..."
python3.10 -m pip install -r requirements.txt || python3 -m pip install -r requirements.txt

echo "========================================="
echo "✅ Build completed successfully!"
echo "========================================="
