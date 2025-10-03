"""
AI Summarizer Module
Uses OpenAI or Perplexity to generate summaries and categorize content
"""

import os
from typing import List, Dict, Optional
import logging
from openai import OpenAI
from anthropic import Anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AISummarizer:
    def __init__(self, provider: str = "openai", model: str = "gpt-4o-mini"):
        """
        Initialize the AI summarizer
        
        Args:
            provider: AI provider (openai, perplexity, or claude)
            model: Model name to use
        """
        self.provider = provider
        self.model = model
        
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in environment variables")
            self.client = OpenAI(api_key=api_key)
        elif provider == "perplexity":
            api_key = os.getenv("PERPLEXITY_API_KEY")
            if not api_key:
                raise ValueError("PERPLEXITY_API_KEY not found in environment variables")
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://api.perplexity.ai"
            )
        elif provider == "claude":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
            self.client = Anthropic(api_key=api_key)
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    def summarize_article(self, article: Dict, length: str = "brief") -> str:
        """
        Generate a summary for a single article
        
        Args:
            article: Article dictionary with title, summary, and link
            length: Summary length (brief, medium, or detailed)
            
        Returns:
            Summary string
        """
        length_instructions = {
            "brief": "in 1-2 sentences",
            "medium": "in 2-3 sentences",
            "detailed": "in 3-5 sentences"
        }
        
        instruction = length_instructions.get(length, "in 1-2 sentences")
        
        prompt = f"""Summarize the following article {instruction}. Focus on the key insights and why it matters.

Title: {article['title']}
Content: {article['summary'][:1000]}

Provide only the summary, without any preamble."""
        
        try:
            if self.provider == "claude":
                # Use Claude API format
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=200,
                    temperature=0.7,
                    system="You are a helpful assistant that creates concise, insightful summaries of news articles and blog posts.",
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                summary = response.content[0].text.strip()
            else:
                # Use OpenAI-compatible API format
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that creates concise, insightful summaries of news articles and blog posts."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=200
                )
                summary = response.choices[0].message.content.strip()
            
            return summary
            
        except Exception as e:
            logger.error(f"Error summarizing article '{article['title']}': {str(e)}")
            return article['summary'][:200] + "..."
    
    def categorize_and_tag(self, articles: List[Dict], topic_name: str) -> List[Dict]:
        """
        Add tags and categories to articles using AI
        
        Args:
            articles: List of articles
            topic_name: The topic/category name
            
        Returns:
            List of articles with added tags and categories
        """
        # For simplicity, we'll add basic tags based on the topic
        # You can enhance this with AI-powered tagging
        
        for article in articles:
            article['category'] = topic_name
            article['tags'] = [topic_name]
        
        return articles
    
    def generate_batch_summaries(self, articles: List[Dict], length: str = "brief") -> List[Dict]:
        """
        Generate summaries for multiple articles
        
        Args:
            articles: List of articles
            length: Summary length
            
        Returns:
            List of articles with added 'ai_summary' field
        """
        for article in articles:
            article['ai_summary'] = self.summarize_article(article, length)
        
        return articles
    
    def generate_overview(self, articles_by_topic: Dict[str, List[Dict]]) -> str:
        """
        Generate an overview/introduction for the entire brief
        
        Args:
            articles_by_topic: Dictionary mapping topics to articles
            
        Returns:
            Overview text
        """
        topics = list(articles_by_topic.keys())
        total_articles = sum(len(articles) for articles in articles_by_topic.values())
        
        prompt = f"""Generate a brief, engaging introduction (2-3 sentences) for a daily news brief that covers the following topics: {', '.join(topics)}. 
        
There are {total_articles} total articles. Make it personal and energetic, like a friend catching you up on what's happening."""
        
        try:
            if self.provider == "claude":
                # Use Claude API format
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=150,
                    temperature=0.8,
                    system="You are a friendly assistant creating personalized daily briefings.",
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                overview = response.content[0].text.strip()
            else:
                # Use OpenAI-compatible API format
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a friendly assistant creating personalized daily briefings."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.8,
                    max_tokens=150
                )
                overview = response.choices[0].message.content.strip()
            
            return overview
            
        except Exception as e:
            logger.error(f"Error generating overview: {str(e)}")
            return "Here's your personalized brief with the latest updates across your topics of interest."

