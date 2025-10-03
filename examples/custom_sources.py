"""
Example: Adding Custom Content Sources

This example shows how to extend the ContentAggregator
to support custom sources like APIs, databases, or web scraping.
"""

from src.content_aggregator import ContentAggregator
import requests
from typing import List, Dict


class CustomContentAggregator(ContentAggregator):
    """Extended aggregator with custom source support"""
    
    def fetch_hacker_news_top_stories(self, max_items: int = 5) -> List[Dict]:
        """
        Fetch top stories from Hacker News API
        
        Returns:
            List of article dictionaries
        """
        articles = []
        
        try:
            # Get top story IDs
            response = requests.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json",
                timeout=10
            )
            story_ids = response.json()[:max_items]
            
            # Fetch each story
            for story_id in story_ids:
                story_response = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                    timeout=10
                )
                story = story_response.json()
                
                if story.get('type') == 'story':
                    article = {
                        'title': story.get('title', 'No Title'),
                        'link': story.get('url', f"https://news.ycombinator.com/item?id={story_id}"),
                        'summary': story.get('text', 'No summary available'),
                        'published': None,
                        'source': 'Hacker News'
                    }
                    articles.append(article)
            
            return articles
            
        except Exception as e:
            print(f"Error fetching Hacker News: {e}")
            return []
    
    def fetch_reddit_posts(self, subreddit: str, max_items: int = 5) -> List[Dict]:
        """
        Fetch top posts from a subreddit
        
        Args:
            subreddit: Subreddit name (without r/)
            max_items: Maximum number of posts
            
        Returns:
            List of article dictionaries
        """
        articles = []
        
        try:
            headers = {'User-Agent': 'Personal AI Assistant'}
            response = requests.get(
                f"https://www.reddit.com/r/{subreddit}/hot.json?limit={max_items}",
                headers=headers,
                timeout=10
            )
            data = response.json()
            
            for post in data['data']['children']:
                post_data = post['data']
                
                article = {
                    'title': post_data.get('title', 'No Title'),
                    'link': f"https://reddit.com{post_data.get('permalink', '')}",
                    'summary': post_data.get('selftext', 'No summary available')[:500],
                    'published': None,
                    'source': f"r/{subreddit}"
                }
                articles.append(article)
            
            return articles
            
        except Exception as e:
            print(f"Error fetching Reddit posts: {e}")
            return []


# Example usage
if __name__ == "__main__":
    aggregator = CustomContentAggregator()
    
    # Fetch from Hacker News
    hn_articles = aggregator.fetch_hacker_news_top_stories(max_items=3)
    print(f"Fetched {len(hn_articles)} articles from Hacker News")
    
    # Fetch from Reddit
    reddit_articles = aggregator.fetch_reddit_posts('technology', max_items=3)
    print(f"Fetched {len(reddit_articles)} articles from Reddit")
    
    for article in hn_articles + reddit_articles:
        print(f"\n- {article['title']}")
        print(f"  {article['link']}")


