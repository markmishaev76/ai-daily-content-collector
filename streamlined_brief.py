#!/usr/bin/env python3
"""
Streamlined Daily Brief Generator - Optimized for reliability
Skips time-consuming recommendation generation to ensure delivery
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

def generate_streamlined_brief():
    """Generate a streamlined daily brief with core content only"""
    
    logger.info("🚀 Starting streamlined daily brief generation...")
    
    # Load configuration
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize components
    aggregator = ContentAggregator()
    ai_summarizer = AISummarizer()
    email_sender = EmailSender()
    
    # Core topics only (skip time-consuming ones)
    core_topics = [
        "AI Technologies & Research",
        "Cybersecurity News", 
        "Tech News & Trends"
    ]
    
    all_summaries = {}
    
    logger.info("📰 Step 1: Aggregating core content...")
    
    for topic in core_topics:
        logger.info(f"Processing topic: {topic}")
        
        # Get articles for this topic
        articles = aggregator.get_articles_for_topic(topic, max_articles=5)
        
        if not articles:
            logger.warning(f"No articles found for {topic}")
            continue
            
        logger.info(f"Found {len(articles)} articles for {topic}")
        
        # Summarize articles
        summaries = []
        for i, article in enumerate(articles[:3]):  # Limit to 3 articles per topic
            try:
                summary = ai_summarizer.summarize_article(article, f"for a Senior Engineering Manager in software supply chain security")
                summaries.append({
                    'title': article.get('title', 'No Title'),
                    'url': article.get('link', '#'),
                    'summary': summary
                })
                logger.info(f"Summarized article {i+1}/{min(3, len(articles))} for {topic}")
            except Exception as e:
                logger.error(f"Error summarizing article: {e}")
                continue
        
        if summaries:
            all_summaries[topic] = summaries
            logger.info(f"✅ Completed {topic} with {len(summaries)} summaries")
    
    if not all_summaries:
        logger.error("No summaries generated!")
        return False
    
    logger.info("📧 Step 2: Creating and sending email...")
    
    # Create email with core content only
    try:
        email_sender.create_html_email(
            all_summaries, 
            blogger_posts_by_topic={},  # Skip blogger posts
            conference_recommendations_by_topic={}  # Skip conference recommendations
        )
        logger.info("✅ Email sent successfully!")
        return True
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False

if __name__ == "__main__":
    success = generate_streamlined_brief()
    if success:
        print("🎉 Streamlined brief generated and sent successfully!")
    else:
        print("❌ Failed to generate brief")
        sys.exit(1)
