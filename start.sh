#!/bin/bash

# dbAI Pulse - Startup Script
# Starts both backend (FastAPI) and frontend (Vite React)

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Starting dbAI Pulse..."

# Start backend
echo "Starting backend on http://localhost:8000..."
cd "$PROJECT_DIR/backend"
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt 2>/dev/null
uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start frontend
echo "Starting frontend on http://localhost:5173..."
cd "$PROJECT_DIR/frontend"
if [ ! -d "node_modules" ]; then
    echo "Installing npm dependencies..."
    npm install
fi
npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================="
echo "  dbAI Pulse is running!"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo "========================================="
echo "Press Ctrl+C to stop all services"

# Handle shutdown
trap "echo 'Shutting down...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM

# Wait for processes
wait
