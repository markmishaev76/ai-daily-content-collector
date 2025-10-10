#!/usr/bin/env python3
"""
Quick Daily Brief - Minimal working version
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.content_aggregator import ContentAggregator
from src.ai_summarizer import AISummarizer
from src.email_sender import EmailSender
import yaml
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_quick_brief():
    """Generate a quick daily brief with minimal processing"""
    
    logger.info("🚀 Starting quick daily brief generation...")
    
    # Load configuration
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize components
    aggregator = ContentAggregator()
    ai_summarizer = AISummarizer()
    email_sender = EmailSender()
    
    # Just 2 core topics for speed
    topics = ["AI Technologies & Research", "Cybersecurity News"]
    
    all_summaries = {}
    
    for topic in topics:
        logger.info(f"Processing {topic}...")
        
        # Get articles
        articles = aggregator.get_articles_for_topic(topic, max_articles=3)
        
        if not articles:
            logger.warning(f"No articles for {topic}")
            continue
            
        # Summarize just 2 articles per topic
        summaries = []
        for i, article in enumerate(articles[:2]):
            try:
                summary = ai_summarizer.summarize_article(article, "for a Senior Engineering Manager")
                summaries.append({
                    'title': article.get('title', 'No Title'),
                    'url': article.get('link', '#'),
                    'summary': summary
                })
                logger.info(f"✅ Summarized article {i+1} for {topic}")
            except Exception as e:
                logger.error(f"Error: {e}")
                continue
        
        if summaries:
            all_summaries[topic] = summaries
    
    if not all_summaries:
        logger.error("No summaries generated!")
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
    success = generate_quick_brief()
    if success:
        print("🎉 Quick brief sent!")
    else:
        print("❌ Failed")
        sys.exit(1)
