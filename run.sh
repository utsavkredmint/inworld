#!/bin/bash

# AI Voice Agent Project - Single Run Script
# This script starts both the backend and the frontend.

# Function to stop background processes when the script is terminated
cleanup() {
    echo ""
    echo "Stopping servers..."
    kill $BACKEND_PID 2>/dev/null
    exit
}

# Trap Ctrl+C (SIGINT) and call the cleanup function
trap cleanup SIGINT

# 1. Start Backend
echo "Starting Backend (FastAPI)..."
cd bot
source venv/bin/activate
# Start backend in the background
python app.py &
BACKEND_PID=$!
cd ..

# 2. Wait a moment for background to initialize
sleep 2

# 3. Start Frontend
echo "Starting Frontend (Vite)..."
cd DSGROUPDASHBOARD
# Load nvm
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Start frontend in the foreground
npm run dev
