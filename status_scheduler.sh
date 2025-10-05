#!/bin/bash

# Check status of Mark's AI Assistant Scheduler

echo "📊 Mark's AI Assistant Scheduler Status"
echo "======================================="

# Check if PID file exists
if [ -f "scheduler.pid" ]; then
    PID=$(cat scheduler.pid)
    
    # Check if process is running
    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ Scheduler is RUNNING"
        echo "📊 Process ID: $PID"
        echo "⏰ Started: $(ps -o lstart= -p $PID)"
        echo "💾 Memory: $(ps -o rss= -p $PID | awk '{print $1/1024 " MB"}')"
        
        # Show recent logs
        if [ -f "logs/scheduler.log" ]; then
            echo ""
            echo "📝 Recent logs (last 10 lines):"
            echo "--------------------------------"
            tail -10 logs/scheduler.log
        fi
    else
        echo "❌ Scheduler is NOT RUNNING (PID file exists but process not found)"
        echo "🧹 Cleaning up PID file..."
        rm scheduler.pid
    fi
else
    echo "❌ Scheduler is NOT RUNNING (no PID file)"
    
    # Check for any running scheduler processes
    PIDS=$(pgrep -f "python scheduler.py")
    if [ ! -z "$PIDS" ]; then
        echo "⚠️  Found orphaned scheduler processes: $PIDS"
        echo "🛑 Run ./stop_scheduler.sh to clean them up"
    fi
fi

echo ""
echo "📧 Email configuration:"
if [ -f ".env" ]; then
    echo "   To: $(grep EMAIL_TO .env | cut -d'=' -f2 | head -1)"
    echo "   Schedule: $(grep SCHEDULE_TIME .env | cut -d'=' -f2 | head -1)"
    echo "   AI Provider: $(grep AI_PROVIDER .env | cut -d'=' -f2 | head -1)"
else
    echo "   ❌ .env file not found"
fi


