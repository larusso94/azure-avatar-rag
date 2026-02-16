#!/bin/bash

# Avatar RAG Startup Script

echo "=========================================="
echo "🚀 Starting Azure Avatar RAG System"
echo "=========================================="
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "💡 Run: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "💡 Copy .env.example to .env and fill in your Azure credentials"
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Create uploads directory
mkdir -p uploads

# Start backend in background
echo "📡 Starting Backend API (port 5000)..."
python app.py &
BACKEND_PID=$!

# Wait for backend to initialize
sleep 3

# Start frontend server
echo "🌐 Starting Frontend Server (port 9090)..."
python server.py &
FRONTEND_PID=$!

echo ""
echo "=========================================="
echo "✅ Services Started!"
echo "=========================================="
echo "📡 Backend API:  http://localhost:5000"
echo "🌐 Frontend UI:  http://localhost:9090/index.html"
echo ""
echo "💡 Press Ctrl+C to stop all services"
echo "=========================================="

# Handle Ctrl+C
trap "echo ''; echo '🛑 Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo '✅ All services stopped'; exit 0" INT

# Wait for processes
wait
