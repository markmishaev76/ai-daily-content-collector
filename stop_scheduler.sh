#!/bin/bash

# Stop Mark's AI Assistant Scheduler

echo "🛑 Stopping Mark's AI Assistant Scheduler..."

# Check if PID file exists
if [ -f "scheduler.pid" ]; then
    PID=$(cat scheduler.pid)
    
    # Check if process is running
    if ps -p $PID > /dev/null 2>&1; then
        echo "🛑 Stopping process $PID..."
        kill $PID
        
        # Wait a moment for graceful shutdown
        sleep 2
        
        # Force kill if still running
        if ps -p $PID > /dev/null 2>&1; then
            echo "⚠️  Force stopping process $PID..."
            kill -9 $PID
        fi
        
        echo "✅ Scheduler stopped successfully!"
    else
        echo "⚠️  Process $PID is not running"
    fi
    
    # Remove PID file
    rm scheduler.pid
else
    echo "⚠️  No PID file found. Scheduler may not be running."
    
    # Try to find and kill any running scheduler processes
    PIDS=$(pgrep -f "python scheduler.py")
    if [ ! -z "$PIDS" ]; then
        echo "🛑 Found running scheduler processes: $PIDS"
        kill $PIDS
        echo "✅ Scheduler processes stopped!"
    else
        echo "ℹ️  No scheduler processes found"
    fi
fi





