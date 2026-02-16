#!/bin/bash

# Installation script for Azure Avatar RAG

echo "=========================================="
echo "📦 Installing Azure Avatar RAG"
echo "=========================================="
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | grep -oP '3\.\d+')
required_version="3.11"

if [ -z "$python_version" ]; then
    echo "❌ Python 3 not found!"
    exit 1
fi

echo "✅ Python version: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p uploads
mkdir -p logs

# Copy .env.example if .env doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env from template..."
    cp .env.example .env
    echo "⚠️  Don't forget to fill in your Azure credentials in .env!"
fi

echo ""
echo "=========================================="
echo "✅ Installation Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env with your Azure credentials"
echo "2. Run: ./start.sh"
echo ""
