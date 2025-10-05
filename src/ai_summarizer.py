"""
AI Summarizer Module
Uses OpenAI or Perplexity to generate summaries and categorize content
"""

import os
from typing import List, Dict, Optional
import logging
from datetime import datetime
import requests
from urllib.parse import urlparse
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
    
    def generate_content_recommendations(self, topic_name: str, articles: List[Dict]) -> Dict[str, List[str]]:
        """
        Generate content recommendations and references for a specific topic

        Args:
            topic_name: The topic/category name
            articles: List of articles from this topic

        Returns:
            Dictionary with recommendations including:
            - additional_sources: RSS feeds and websites to follow
            - key_people: Influential people to follow
            - research_papers: Academic papers to read
            - tools_resources: Tools and resources to explore
        """
        # Create a summary of current articles for context
        article_titles = [article['title'] for article in articles[:5]]  # Top 5 articles
        current_trends = ", ".join(article_titles)

        prompt = f"""Based on the current trends in {topic_name} (recent articles: {current_trends}), provide specific recommendations for staying informed in this domain.

        Please provide recommendations in this exact format:

        ADDITIONAL_SOURCES:
        - [RSS feed or website name]: [URL]
        - [RSS feed or website name]: [URL]

        KEY_PEOPLE:
        - [Person name]: [Twitter/LinkedIn handle or description]
        - [Person name]: [Twitter/LinkedIn handle or description]

        RESEARCH_PAPERS:
        - [Paper title]: [arXiv link or description]
        - [Paper title]: [arXiv link or description]

        TOOLS_RESOURCES:
        - [Tool/Resource name]: [URL or description]
        - [Tool/Resource name]: [URL or description]

        Focus on high-quality, authoritative sources that would be valuable for someone working in {topic_name}.
        
        IMPORTANT: Only include sources, people, papers, and tools that you are confident about and can provide specific, actionable information for. If you cannot provide specific recommendations for any category, omit that category entirely rather than including generic or uncertain suggestions."""

        try:
            if self.provider == "claude":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=800,
                    temperature=0.7,
                    system="You are an expert research assistant that provides high-quality recommendations for staying informed in technology domains. Only provide specific, actionable recommendations that you are confident about.",
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                recommendations_text = response.content[0].text.strip()
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert research assistant that provides high-quality recommendations for staying informed in technology domains. Only provide specific, actionable recommendations that you are confident about."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=800
                )
                recommendations_text = response.choices[0].message.content.strip()

            # Parse the recommendations
            recommendations = self._parse_recommendations(recommendations_text)
            
            # Filter out empty or low-quality recommendations
            filtered_recommendations = self._filter_recommendations(recommendations)
            return filtered_recommendations

        except Exception as e:
            logger.error(f"Error generating recommendations for {topic_name}: {str(e)}")
            return {
                "additional_sources": [],
                "key_people": [],
                "research_papers": [],
                "tools_resources": []
            }
    
    def _parse_recommendations(self, text: str) -> Dict[str, List[str]]:
        """
        Parse the AI-generated recommendations into structured format
        
        Args:
            text: Raw recommendations text from AI
            
        Returns:
            Dictionary with parsed recommendations
        """
        recommendations = {
            "additional_sources": [],
            "key_people": [],
            "research_papers": [],
            "tools_resources": []
        }
        
        current_section = None
        
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('ADDITIONAL_SOURCES:'):
                current_section = 'additional_sources'
            elif line.startswith('KEY_PEOPLE:'):
                current_section = 'key_people'
            elif line.startswith('RESEARCH_PAPERS:'):
                current_section = 'research_papers'
            elif line.startswith('TOOLS_RESOURCES:'):
                current_section = 'tools_resources'
            elif line.startswith('- ') and current_section:
                # Remove the bullet point and add to current section
                item = line[2:].strip()
                if item:
                    recommendations[current_section].append(item)
        
        return recommendations
    
    def _filter_recommendations(self, recommendations: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """
        Filter out low-quality or empty recommendations
        
        Args:
            recommendations: Raw recommendations from AI
            
        Returns:
            Filtered recommendations with only high-quality content
        """
        filtered = {}
        
        for category, items in recommendations.items():
            if not items:
                continue
                
            filtered_items = []
            for item in items:
                # Skip items that are too short, generic, or unclear
                if (len(item.strip()) < 10 or 
                    item.lower().strip() in ['n/a', 'none', 'not available', 'tbd', 'to be determined'] or
                    'i cannot' in item.lower() or
                    'i don\'t know' in item.lower() or
                    'i\'m not sure' in item.lower() or
                    'unable to' in item.lower() or
                    'cannot provide' in item.lower()):
                    continue
                    
                # Skip items that look like errors or placeholders
                if (item.strip().startswith('[') and item.strip().endswith(']') and 
                    'url' in item.lower() or 'description' in item.lower()):
                    continue
                    
                filtered_items.append(item.strip())
            
            # Only include category if it has valid items
            if filtered_items:
                filtered[category] = filtered_items
        
        return filtered

    def validate_link(self, url: str) -> bool:
        """
        Validate if a URL is accessible and working
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is accessible, False otherwise
        """
        try:
            # Parse the URL to check if it's valid
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Skip validation for search URLs and generic links
            if any(domain in url.lower() for domain in ['google.com/search', 'bing.com/search', 'duckduckgo.com']):
                return True
            
            # Make a HEAD request to check if the URL is accessible
            response = requests.head(url, timeout=5, allow_redirects=True)
            return response.status_code < 400
            
        except Exception as e:
            logger.debug(f"Link validation failed for {url}: {e}")
            return False

    def fetch_recommended_content(self, recommendations: Dict[str, List[str]], topic_name: str) -> Dict[str, List[Dict]]:
        """
        Fetch actual content from recommended sources and generate AI-powered reading recommendations
        
        Args:
            recommendations: AI-generated recommendations
            topic_name: The topic/category name
            
        Returns:
            Dictionary with actual content from recommended sources
        """
        from .content_aggregator import ContentAggregator
        
        fetched_content = {
            "recommended_articles": [],
            "recommended_tweets": [],
            "recommended_papers": [],
            "recommended_tools": []
        }
        
        # Fetch actual content from recommended sources
        if recommendations.get('additional_sources'):
            aggregator = ContentAggregator(hours_back=168)  # Last week
            
            for source in recommendations['additional_sources'][:3]:  # Limit to top 3
                try:
                    # Extract URL from source description
                    if ':' in source and 'http' in source:
                        url = source.split(': ')[-1].strip()
                        if url.startswith('http'):
                            # Create a mock topic for fetching
                            mock_topic = {
                                'name': f"Recommended {topic_name}",
                                'sources': [{'type': 'rss', 'url': url}]
                            }
                            
                            articles = aggregator.aggregate_content([mock_topic])
                            if articles and f"Recommended {topic_name}" in articles:
                                for article in articles[f"Recommended {topic_name}"][:2]:  # Top 2 articles
                                    article['source_type'] = 'recommended_source'
                                    article['recommended_by'] = source
                                    fetched_content['recommended_articles'].append(article)
                except Exception as e:
                    logger.warning(f"Could not fetch from recommended source {source}: {e}")
                    continue
        
        # Generate AI-powered reading recommendations for people
        if recommendations.get('key_people'):
            for person in recommendations['key_people'][:3]:  # Limit to top 3
                try:
                    # Use AI to generate specific reading recommendations
                    person_name = person.split(':')[0].strip()
                    reading_prompt = f"""Based on {person_name}'s expertise in {topic_name}, recommend 1-2 specific articles, papers, or resources they would likely recommend reading. 

                    Person: {person}
                    Topic: {topic_name}
                    
                    Provide specific, actionable reading recommendations with:
                    - Article/paper title
                    - Brief summary (2-3 sentences)
                    - Why this person would recommend it
                    - Link to the content
                    
                    Format as:
                    TITLE: [specific title]
                    SUMMARY: [brief summary]
                    REASON: [why this person would recommend it]
                    LINK: [URL]"""

                    if self.provider == "claude":
                        response = self.client.messages.create(
                            model=self.model,
                            max_tokens=400,
                            temperature=0.7,
                            system="You are an expert research assistant that provides specific reading recommendations based on expert knowledge.",
                            messages=[
                                {"role": "user", "content": reading_prompt}
                            ]
                        )
                        reading_text = response.content[0].text.strip()
                    else:
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": "You are an expert research assistant that provides specific reading recommendations based on expert knowledge."},
                                {"role": "user", "content": reading_prompt}
                            ],
                            temperature=0.7,
                            max_tokens=400
                        )
                        reading_text = response.choices[0].message.content.strip()
                    
                    # Parse the AI response
                    lines = reading_text.split('\n')
                    title = ""
                    summary = ""
                    reason = ""
                    link = ""
                    
                    for line in lines:
                        if line.startswith('TITLE:'):
                            title = line.replace('TITLE:', '').strip()
                        elif line.startswith('SUMMARY:'):
                            summary = line.replace('SUMMARY:', '').strip()
                        elif line.startswith('REASON:'):
                            reason = line.replace('REASON:', '').strip()
                        elif line.startswith('LINK:'):
                            link = line.replace('LINK:', '').strip()
                    
                    if title and summary:
                        # Use provided link or generate search link
                        final_link = link or f"https://google.com/search?q={title.replace(' ', '+')}"
                        
                        # Validate the link
                        if self.validate_link(final_link):
                            person_content = {
                                'title': title,
                                'link': final_link,
                                'summary': f"{summary} {reason}".strip(),
                                'published': datetime.now().strftime('%Y-%m-%d'),
                                'source_type': 'recommended_reading',
                                'recommended_by': f"Recommended by {person_name}",
                                'has_valid_link': True
                            }
                            fetched_content['recommended_tweets'].append(person_content)
                        else:
                            # Include without link if validation fails
                            person_content = {
                                'title': title,
                                'link': '',
                                'summary': f"{summary} {reason}".strip(),
                                'published': datetime.now().strftime('%Y-%m-%d'),
                                'source_type': 'recommended_reading',
                                'recommended_by': f"Recommended by {person_name}",
                                'has_valid_link': False
                            }
                            fetched_content['recommended_tweets'].append(person_content)
                        
                except Exception as e:
                    logger.warning(f"Could not generate reading recommendations for {person}: {e}")
                    continue
        
        # Generate AI-powered reading recommendations for papers
        if recommendations.get('research_papers'):
            for paper in recommendations['research_papers'][:3]:  # Limit to top 3
                try:
                    # Use AI to generate specific paper recommendations
                    paper_prompt = f"""For the research paper "{paper}" in {topic_name}, provide:
                    
                    1. A specific, recent paper title that builds on or relates to this work
                    2. Brief summary of why this paper is important
                    3. Direct link to the paper (arXiv, conference, journal)
                    
                    Format as:
                    TITLE: [specific paper title]
                    SUMMARY: [why this paper is important for {topic_name}]
                    LINK: [direct URL to paper]"""

                    if self.provider == "claude":
                        response = self.client.messages.create(
                            model=self.model,
                            max_tokens=300,
                            temperature=0.7,
                            system="You are an expert research assistant that provides specific academic paper recommendations.",
                            messages=[
                                {"role": "user", "content": paper_prompt}
                            ]
                        )
                        paper_text = response.content[0].text.strip()
                    else:
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": "You are an expert research assistant that provides specific academic paper recommendations."},
                                {"role": "user", "content": paper_prompt}
                            ],
                            temperature=0.7,
                            max_tokens=300
                        )
                        paper_text = response.choices[0].message.content.strip()
                    
                    # Parse the AI response
                    lines = paper_text.split('\n')
                    title = ""
                    summary = ""
                    link = ""
                    
                    for line in lines:
                        if line.startswith('TITLE:'):
                            title = line.replace('TITLE:', '').strip()
                        elif line.startswith('SUMMARY:'):
                            summary = line.replace('SUMMARY:', '').strip()
                        elif line.startswith('LINK:'):
                            link = line.replace('LINK:', '').strip()
                    
                    if title and summary:
                        # Use provided link or generate search link
                        final_link = link or f"https://arxiv.org/search/?query={title.replace(' ', '+')}"
                        
                        # Validate the link
                        if self.validate_link(final_link):
                            paper_content = {
                                'title': title,
                                'link': final_link,
                                'summary': summary,
                                'published': datetime.now().strftime('%Y-%m-%d'),
                                'source_type': 'recommended_paper',
                                'recommended_by': f"Related to: {paper}",
                                'has_valid_link': True
                            }
                            fetched_content['recommended_papers'].append(paper_content)
                        else:
                            # Include without link if validation fails
                            paper_content = {
                                'title': title,
                                'link': '',
                                'summary': summary,
                                'published': datetime.now().strftime('%Y-%m-%d'),
                                'source_type': 'recommended_paper',
                                'recommended_by': f"Related to: {paper}",
                                'has_valid_link': False
                            }
                            fetched_content['recommended_papers'].append(paper_content)
                        
                except Exception as e:
                    logger.warning(f"Could not generate paper recommendations for {paper}: {e}")
                    continue
        
        # Generate AI-powered reading recommendations for tools
        if recommendations.get('tools_resources'):
            for tool in recommendations['tools_resources'][:3]:  # Limit to top 3
                try:
                    # Use AI to generate specific tool recommendations
                    tool_prompt = f"""For the tool/resource "{tool}" in {topic_name}, recommend:
                    
                    1. A specific tutorial, guide, or documentation to read
                    2. Brief summary of what you'll learn
                    3. Direct link to the resource
                    
                    Format as:
                    TITLE: [specific resource title]
                    SUMMARY: [what you'll learn from this resource]
                    LINK: [direct URL to resource]"""

                    if self.provider == "claude":
                        response = self.client.messages.create(
                            model=self.model,
                            max_tokens=300,
                            temperature=0.7,
                            system="You are an expert research assistant that provides specific learning resource recommendations.",
                            messages=[
                                {"role": "user", "content": tool_prompt}
                            ]
                        )
                        tool_text = response.content[0].text.strip()
                    else:
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": "You are an expert research assistant that provides specific learning resource recommendations."},
                                {"role": "user", "content": tool_prompt}
                            ],
                            temperature=0.7,
                            max_tokens=300
                        )
                        tool_text = response.choices[0].message.content.strip()
                    
                    # Parse the AI response
                    lines = tool_text.split('\n')
                    title = ""
                    summary = ""
                    link = ""
                    
                    for line in lines:
                        if line.startswith('TITLE:'):
                            title = line.replace('TITLE:', '').strip()
                        elif line.startswith('SUMMARY:'):
                            summary = line.replace('SUMMARY:', '').strip()
                        elif line.startswith('LINK:'):
                            link = line.replace('LINK:', '').strip()
                    
                    if title and summary:
                        # Use provided link or generate search link
                        final_link = link or f"https://google.com/search?q={title.replace(' ', '+')}"
                        
                        # Validate the link
                        if self.validate_link(final_link):
                            tool_content = {
                                'title': title,
                                'link': final_link,
                                'summary': summary,
                                'published': datetime.now().strftime('%Y-%m-%d'),
                                'source_type': 'recommended_tool',
                                'recommended_by': f"Learning resource for: {tool}",
                                'has_valid_link': True
                            }
                            fetched_content['recommended_tools'].append(tool_content)
                        else:
                            # Include without link if validation fails
                            tool_content = {
                                'title': title,
                                'link': '',
                                'summary': summary,
                                'published': datetime.now().strftime('%Y-%m-%d'),
                                'source_type': 'recommended_tool',
                                'recommended_by': f"Learning resource for: {tool}",
                                'has_valid_link': False
                            }
                            fetched_content['recommended_tools'].append(tool_content)
                        
                except Exception as e:
                    logger.warning(f"Could not generate tool recommendations for {tool}: {e}")
                    continue
        
        return fetched_content

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

