"""
Personal AI Assistant - Main Application
Aggregates, summarizes, and emails your personalized daily brief
"""

import os
import yaml
import logging
from datetime import datetime
from dotenv import load_dotenv

from src.content_aggregator import ContentAggregator
from src.ai_summarizer import AISummarizer
from src.email_sender import EmailSender

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def generate_brief():
    """Main function to generate and send the daily brief"""
    try:
        # Load environment variables
        load_dotenv()
        
        # Load configuration
        config = load_config()
        
        logger.info("Starting daily brief generation...")
        
        # Initialize components
        aggregator = ContentAggregator(hours_back=48)  # Extended to 48 hours for more content
        summarizer = AISummarizer(
            provider=os.getenv("AI_PROVIDER", "openai"),
            model=config['summarization']['model']
        )
        email_sender = EmailSender()
        
        # Step 1: Aggregate content from all sources
        logger.info("Step 1: Aggregating content from sources...")
        articles_by_topic = aggregator.aggregate_content(config['topics'])
        
        # Step 2: Filter and limit articles per topic
        max_articles = config['summarization']['max_articles_per_topic']
        for topic, articles in articles_by_topic.items():
            articles_by_topic[topic] = articles[:max_articles]
        
        # Step 3: Generate AI summaries for all articles
        logger.info("Step 2: Generating AI summaries...")
        summary_length = config['summarization']['summary_length']
        
        for topic, articles in articles_by_topic.items():
            if articles:
                logger.info(f"Summarizing {len(articles)} articles for topic: {topic}")
                articles_by_topic[topic] = summarizer.generate_batch_summaries(
                    articles, 
                    length=summary_length
                )
                # Add tags and categories
                articles_by_topic[topic] = summarizer.categorize_and_tag(
                    articles_by_topic[topic], 
                    topic
                )
        
        # Step 4: Generate content recommendations for each topic
        logger.info("Step 3: Generating content recommendations...")
        recommendations_by_topic = {}
        enhanced_recommendations_by_topic = {}
        blogger_posts_by_topic = {}
        conference_recommendations_by_topic = {}
        
        for topic, articles in articles_by_topic.items():
            if articles:
                logger.info(f"Generating recommendations for topic: {topic}")
                # Generate basic recommendations
                basic_recommendations = summarizer.generate_content_recommendations(
                    topic,
                    articles
                )
                recommendations_by_topic[topic] = basic_recommendations
                
                # Fetch actual content from recommended sources
                logger.info(f"Fetching content from recommended sources for topic: {topic}")
                enhanced_content = summarizer.fetch_recommended_content(
                    basic_recommendations,
                    topic
                )
                enhanced_recommendations_by_topic[topic] = enhanced_content
                
                # Get blogger recommendations and fetch their recent posts
                logger.info(f"Getting blogger recommendations for topic: {topic}")
                bloggers = summarizer.get_blogger_recommendations(topic, articles)
                if bloggers:
                    logger.info(f"Fetching recent posts from {len(bloggers)} bloggers for topic: {topic}")
                    blogger_posts = summarizer.fetch_blogger_posts(bloggers, topic)
                    blogger_posts_by_topic[topic] = blogger_posts

                # Get conference and CFP recommendations
                logger.info(f"Getting conference recommendations for topic: {topic}")
                conferences = summarizer.get_conference_recommendations(topic, articles)
                if conferences:
                    logger.info(f"Found {len(conferences)} conference opportunities for topic: {topic}")
                    conference_recommendations_by_topic[topic] = conferences
        
        # Step 5: Generate overview
        logger.info("Step 4: Generating overview...")
        overview = summarizer.generate_overview(articles_by_topic)
        
        # Step 6: Create HTML email
        logger.info("Step 5: Creating email...")
        html_content = email_sender.create_html_email(
            articles_by_topic=articles_by_topic,
            overview=overview,
            user_name=config.get('user_name', 'there'),
            assistant_name=config.get('assistant_name', 'Your AI Assistant'),
            recommendations_by_topic=recommendations_by_topic,
            enhanced_recommendations_by_topic=enhanced_recommendations_by_topic,
            blogger_posts_by_topic=blogger_posts_by_topic,
            conference_recommendations_by_topic=conference_recommendations_by_topic
        )
        
        # Step 7: Send email
        logger.info("Step 6: Sending email...")
        subject = config['email']['subject'].format(
            date=datetime.now().strftime("%B %d, %Y")
        )
        
        success = email_sender.send_email(subject, html_content)
        
        if success:
            total_articles = sum(len(articles) for articles in articles_by_topic.values())
            logger.info(f"✅ Successfully sent daily brief with {total_articles} articles!")
        else:
            logger.error("❌ Failed to send daily brief")
        
        return success
        
    except Exception as e:
        logger.error(f"Error generating brief: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    generate_brief()

