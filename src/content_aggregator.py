"""
Content Aggregator Module
Collects content from various sources (RSS feeds, web pages, APIs)
"""

import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import logging
from urllib.parse import urlparse
import ipaddress

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ContentAggregator:
    # Global limits to prevent resource exhaustion
    MAX_ARTICLES_PER_FEED = 50  # Maximum articles to process per RSS feed
    MAX_TOTAL_ARTICLES = 500  # Maximum total articles across all feeds
    
    def __init__(self, hours_back: int = 24):
        """
        Initialize the content aggregator
        
        Args:
            hours_back: How many hours back to fetch content (default: 24)
        """
        self.hours_back = hours_back
        # Use timezone-aware datetime for proper comparison with RSS feed dates
        self.cutoff_date = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        self.total_articles_fetched = 0  # Track total articles for resource limiting
    
    def _validate_url(self, url: str) -> bool:
        """
        Validate URL to prevent SSRF attacks
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is safe, False otherwise
        """
        try:
            parsed = urlparse(url)
            
            # Only allow http and https schemes
            if parsed.scheme not in ['http', 'https']:
                logger.warning(f"Invalid URL scheme: {parsed.scheme}")
                return False
            
            # Ensure hostname exists
            if not parsed.netloc:
                logger.warning(f"URL missing hostname: {url}")
                return False
            
            # Extract hostname (remove port if present)
            hostname = parsed.netloc.split(':')[0]
            
            # Try to resolve hostname to IP
            try:
                import socket
                ip = socket.gethostbyname(hostname)
                ip_obj = ipaddress.ip_address(ip)
                
                # Block private, loopback, and reserved IP ranges (SSRF protection)
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved:
                    logger.warning(f"Blocked private/internal IP: {ip} for {hostname}")
                    return False
                    
            except (socket.gaierror, ValueError) as e:
                logger.warning(f"Could not resolve hostname {hostname}: {e}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"URL validation error for {url}: {e}")
            return False
    
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
        
        # Validate URL to prevent SSRF
        if not self._validate_url(url):
            logger.error(f"URL validation failed for: {url}")
            return articles
        
        try:
            # Check global resource limit
            if self.total_articles_fetched >= self.MAX_TOTAL_ARTICLES:
                logger.warning(f"Reached maximum total articles limit ({self.MAX_TOTAL_ARTICLES}), skipping {url}")
                return articles
            
            feed = feedparser.parse(url)
            
            # Enforce per-feed limit
            feed_limit = min(max_items, self.MAX_ARTICLES_PER_FEED)
            
            for entry in feed.entries[:feed_limit]:
                # Parse published date (timezone-aware)
                published_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    try:
                        published_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    except (TypeError, ValueError):
                        pass
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    try:
                        published_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                    except (TypeError, ValueError):
                        pass
                
                # Skip old articles (only if we have a valid date)
                if published_date is not None:
                    try:
                        if published_date < self.cutoff_date:
                            continue
                    except TypeError:
                        # Handle timezone comparison issues gracefully
                        logger.debug(f"Could not compare dates for article: {entry.get('title', 'Unknown')}")
                        pass
                
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
                self.total_articles_fetched += 1
                
                # Check if we've hit the global limit
                if self.total_articles_fetched >= self.MAX_TOTAL_ARTICLES:
                    logger.warning(f"Reached maximum total articles limit ({self.MAX_TOTAL_ARTICLES})")
                    break
            
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
        # Validate URL to prevent SSRF
        if not self._validate_url(url):
            logger.error(f"URL validation failed for: {url}")
            return None
            
        try:
            response = requests.get(url, timeout=10, verify=True)
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
                'published': datetime.now(timezone.utc),
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

