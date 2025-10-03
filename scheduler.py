"""
Scheduler for Daily Brief
Runs the brief generation at a specified time each day
"""

import os
import schedule
import time
import logging
import signal
import sys
from datetime import datetime
from dotenv import load_dotenv
from main import generate_brief

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def job():
    """Wrapper function for the scheduled job"""
    logger.info("=" * 60)
    logger.info(f"Running scheduled brief generation at {datetime.now()}")
    logger.info("=" * 60)
    generate_brief()


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    logger.info("\n🛑 Shutdown signal received. Stopping scheduler...")
    sys.exit(0)

def main():
    """Main scheduler function"""
    # Load environment variables
    load_dotenv()
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Get schedule time from environment (default: 06:00)
    schedule_time = os.getenv("SCHEDULE_TIME", "06:00")
    
    logger.info("=" * 60)
    logger.info("🤖 Mark's AI Assistant - Daily Brief Scheduler")
    logger.info("=" * 60)
    logger.info(f"📅 Scheduled time: {schedule_time} daily")
    logger.info(f"📧 Email: {os.getenv('EMAIL_TO', 'Not configured')}")
    logger.info(f"🤖 AI Provider: {os.getenv('AI_PROVIDER', 'claude')}")
    logger.info("=" * 60)
    logger.info("Press Ctrl+C to stop the scheduler")
    logger.info("=" * 60)
    
    # Schedule the job
    schedule.every().day.at(schedule_time).do(job)
    
    # Optional: Run once immediately for testing
    if os.getenv("RUN_IMMEDIATELY", "false").lower() == "true":
        logger.info("🧪 Running immediate test generation...")
        job()
    
    # Keep the script running
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("🛑 Scheduler stopped by user")
    except Exception as e:
        logger.error(f"❌ Scheduler error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

