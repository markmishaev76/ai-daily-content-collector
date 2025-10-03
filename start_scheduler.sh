#!/bin/bash

# Start Mark's AI Assistant Scheduler
# This script starts the daily brief scheduler in the background

echo "🤖 Starting Mark's AI Assistant Scheduler..."
echo "============================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run setup first:"
    echo "   python -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Please configure your settings first."
    exit 1
fi

# Create logs directory
mkdir -p logs

# Start scheduler in background
echo "🚀 Starting scheduler..."
nohup python scheduler.py > logs/scheduler.log 2>&1 &

# Get the process ID
PID=$!
echo $PID > scheduler.pid

echo "✅ Scheduler started successfully!"
echo "📊 Process ID: $PID"
echo "📝 Logs: logs/scheduler.log"
echo "🛑 To stop: ./stop_scheduler.sh"
echo ""
echo "📧 Your daily brief will be sent at $(grep SCHEDULE_TIME .env | cut -d'=' -f2 | head -1)"
echo "📧 Email: $(grep EMAIL_TO .env | cut -d'=' -f2 | head -1)"

