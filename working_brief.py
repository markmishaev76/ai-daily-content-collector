#!/usr/bin/env python3
"""
Working Daily Brief - Uses actual config structure
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.content_aggregator import ContentAggregator
from src.email_sender import EmailSender
import yaml
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_working_brief():
    """Generate a working daily brief using the actual config"""
    
    logger.info("🚀 Starting working daily brief generation...")
    
    # Load configuration
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize components
    aggregator = ContentAggregator()
    email_sender = EmailSender()
    
    # Get just 3 core topics from config
    core_topics = config['topics'][:3]  # First 3 topics
    
    logger.info("📰 Fetching articles...")
    
    # Get articles for core topics
    articles_by_topic = aggregator.aggregate_content(core_topics)
    
    all_summaries = {}
    
    for topic_name, articles in articles_by_topic.items():
        logger.info(f"Processing {topic_name} with {len(articles)} articles...")
        
        if not articles:
            logger.warning(f"No articles for {topic_name}")
            continue
            
        # Create simple summaries (just use article titles and snippets)
        summaries = []
        for i, article in enumerate(articles[:3]):  # Limit to 3 articles per topic
            title = article.get('title', 'No Title')
            url = article.get('link', '#')
            summary = article.get('summary', '')[:200] + "..." if article.get('summary') else "No summary available"
            
            summaries.append({
                'title': title,
                'url': url,
                'summary': summary
            })
            logger.info(f"✅ Added article {i+1} for {topic_name}: {title[:50]}...")
        
        if summaries:
            all_summaries[topic_name] = summaries
    
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
    success = generate_working_brief()
    if success:
        print("🎉 Working brief sent!")
    else:
        print("❌ Failed")
        sys.exit(1)
