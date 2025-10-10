#!/usr/bin/env python3
"""
Simple Daily Brief - No AI, just latest articles
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.content_aggregator import ContentAggregator
from src.email_sender import EmailSender
import yaml
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_simple_brief():
    """Generate a simple daily brief with latest articles (no AI processing)"""
    
    logger.info("🚀 Starting simple daily brief generation...")
    
    # Load configuration
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize components
    aggregator = ContentAggregator()
    email_sender = EmailSender()
    
    # Core topics - need to match config structure
    topics_config = [
        {"name": "AI Technologies & Research", "sources": []},
        {"name": "Cybersecurity News", "sources": []},
        {"name": "Tech News & Trends", "sources": []}
    ]
    
    # Get articles for all topics
    logger.info("Fetching articles for all topics...")
    articles_by_topic = aggregator.aggregate_content(topics_config)
    
    all_summaries = {}
    
    for topic_name, articles in articles_by_topic.items():
        logger.info(f"Processing {topic_name}...")
        
        if not articles:
            logger.warning(f"No articles for {topic_name}")
            continue
        
        if not articles:
            logger.warning(f"No articles for {topic}")
            continue
            
        # Create simple summaries (just use article titles and snippets)
        summaries = []
        for i, article in enumerate(articles[:3]):
            title = article.get('title', 'No Title')
            url = article.get('link', '#')
            summary = article.get('summary', '')[:200] + "..." if article.get('summary') else "No summary available"
            
            summaries.append({
                'title': title,
                'url': url,
                'summary': summary
            })
            logger.info(f"✅ Added article {i+1} for {topic}: {title[:50]}...")
        
        if summaries:
            all_summaries[topic] = summaries
    
    if not all_summaries:
        logger.error("No articles found!")
        return False
    
    logger.info("📧 Sending email...")
    
    try:
        email_sender.create_html_email(all_summaries, {}, {})
        logger.info("✅ Email sent successfully!")
        return True
    except Exception as e:
        logger.error(f"Email error: {e}")
        return False

if __name__ == "__main__":
    success = generate_simple_brief()
    if success:
        print("🎉 Simple brief sent!")
    else:
        print("❌ Failed")
        sys.exit(1)
