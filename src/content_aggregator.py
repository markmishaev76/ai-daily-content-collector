"""
Content Aggregator Module
Collects content from various sources (RSS feeds, web pages, APIs)
"""

import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ContentAggregator:
    def __init__(self, hours_back: int = 24):
        """
        Initialize the content aggregator
        
        Args:
            hours_back: How many hours back to fetch content (default: 24)
        """
        self.hours_back = hours_back
        self.cutoff_date = datetime.now() - timedelta(hours=hours_back)
    
    def fetch_rss_feed(self, url: str, max_items: int = 10) -> List[Dict]:
        """
        Fetch articles from an RSS feed
        
        Args:
            url: RSS feed URL
            max_items: Maximum number of items to fetch
            
        Returns:
            List of article dictionaries
        """
        articles = []
        
        try:
            feed = feedparser.parse(url)
            
            for entry in feed.entries[:max_items]:
                # Parse published date
                published_date = None
                if hasattr(entry, 'published_parsed'):
                    published_date = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed'):
                    published_date = datetime(*entry.updated_parsed[:6])
                
                # Skip old articles
                if published_date and published_date < self.cutoff_date:
                    continue
                
                article = {
                    'title': entry.get('title', 'No Title'),
                    'link': entry.get('link', ''),
                    'summary': entry.get('summary', entry.get('description', '')),
                    'published': published_date,
                    'source': feed.feed.get('title', url)
                }
                
                # Clean HTML from summary
                if article['summary']:
                    soup = BeautifulSoup(article['summary'], 'html.parser')
                    article['summary'] = soup.get_text().strip()
                
                articles.append(article)
            
            logger.info(f"Fetched {len(articles)} articles from {url}")
            
        except Exception as e:
            logger.error(f"Error fetching RSS feed {url}: {str(e)}")
        
        return articles
    
    def fetch_web_page(self, url: str) -> Optional[Dict]:
        """
        Fetch and parse a web page
        
        Args:
            url: Web page URL
            
        Returns:
            Article dictionary or None
        """
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try to extract title
            title = soup.find('title')
            title = title.get_text().strip() if title else 'No Title'
            
            # Try to extract main content (this is basic, can be improved)
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            article = {
                'title': title,
                'link': url,
                'summary': text[:500] + '...' if len(text) > 500 else text,
                'published': datetime.now(),
                'source': url
            }
            
            return article
            
        except Exception as e:
            logger.error(f"Error fetching web page {url}: {str(e)}")
            return None
    
    def aggregate_content(self, topics: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Aggregate content from all sources defined in topics
        
        Args:
            topics: List of topic configurations
            
        Returns:
            Dictionary mapping topic names to lists of articles
        """
        aggregated_content = {}
        
        for topic in topics:
            topic_name = topic['name']
            articles = []
            
            logger.info(f"Fetching content for topic: {topic_name}")
            
            for source in topic.get('sources', []):
                source_type = source.get('type')
                source_url = source.get('url')
                
                if source_type == 'rss':
                    articles.extend(self.fetch_rss_feed(source_url))
                elif source_type == 'web':
                    article = self.fetch_web_page(source_url)
                    if article:
                        articles.append(article)
            
            aggregated_content[topic_name] = articles
        
        return aggregated_content

