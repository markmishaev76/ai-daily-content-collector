"""
Email Sender Module
Handles email formatting and delivery
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List
import os
import logging
from jinja2 import Template

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmailSender:
    def __init__(self):
        """Initialize the email sender with credentials from environment"""
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.email_from = os.getenv("EMAIL_FROM")
        self.email_to = os.getenv("EMAIL_TO")
        self.email_password = os.getenv("EMAIL_PASSWORD")
        
        if not all([self.email_from, self.email_to, self.email_password]):
            raise ValueError("Email configuration incomplete. Check EMAIL_FROM, EMAIL_TO, and EMAIL_PASSWORD environment variables.")
    
    def create_html_email(self, 
                         articles_by_topic: Dict[str, List[Dict]], 
                         overview: str,
                         user_name: str = "there",
                         assistant_name: str = "Your AI Assistant",
                         recommendations_by_topic: Dict[str, Dict] = None,
                         enhanced_recommendations_by_topic: Dict[str, Dict] = None,
                         blogger_posts_by_topic: Dict[str, List[Dict]] = None,
                         conference_recommendations_by_topic: Dict[str, List[Dict]] = None) -> str:
        """
        Create beautiful HTML email from articles
        
        Args:
            articles_by_topic: Dictionary mapping topics to articles
            overview: Brief overview/introduction
            user_name: User's name for personalization
            assistant_name: Assistant's name
            
        Returns:
            HTML string
        """
        template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            border-bottom: 3px solid #4A90E2;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #2C3E50;
            margin: 0 0 10px 0;
            font-size: 28px;
        }
        .date {
            color: #7F8C8D;
            font-size: 14px;
        }
        .greeting {
            font-size: 16px;
            color: #34495E;
            margin-bottom: 20px;
        }
        .overview {
            background-color: #EBF5FB;
            border-left: 4px solid #4A90E2;
            padding: 15px;
            margin-bottom: 30px;
            border-radius: 5px;
        }
        .topic-section {
            margin-bottom: 40px;
        }
        .topic-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .topic-header h2 {
            margin: 0;
            font-size: 20px;
        }
        .article {
            margin-bottom: 25px;
            padding-bottom: 25px;
            border-bottom: 1px solid #E0E0E0;
        }
        .article:last-child {
            border-bottom: none;
        }
        .article-title {
            color: #2C3E50;
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 8px;
        }
        .article-title a {
            color: #2C3E50;
            text-decoration: none;
        }
        .article-title a:hover {
            color: #4A90E2;
        }
        .article-meta {
            font-size: 12px;
            color: #95A5A6;
            margin-bottom: 10px;
        }
        .article-summary {
            color: #555;
            line-height: 1.6;
            margin-bottom: 10px;
        }
        .article-link {
            display: inline-block;
            color: #4A90E2;
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
        }
        .article-link:hover {
            text-decoration: underline;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #E0E0E0;
            text-align: center;
            color: #7F8C8D;
            font-size: 14px;
        }
        .tag {
            display: inline-block;
            background-color: #E8F4F8;
            color: #2980B9;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            margin-right: 5px;
            margin-bottom: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ assistant_name }}</h1>
            <div class="date">{{ current_date }}</div>
        </div>
        
        <div class="greeting">
            Good morning, {{ user_name }}! ☀️
        </div>
        
        <div class="overview">
            {{ overview }}
        </div>
        
        {% for topic_name, articles in articles_by_topic.items() %}
        {% if articles %}
        <div class="topic-section">
            <div class="topic-header">
                <h2>{{ topic_name }}</h2>
            </div>
            
            {% for article in articles %}
            <div class="article">
                <div class="article-title">
                    <a href="{{ article.link }}" target="_blank">{{ article.title }}</a>
                </div>
                <div class="article-meta">
                    {% if article.source %}{{ article.source }} • {% endif %}
                    {% if article.published %}{{ article.published.strftime('%B %d, %Y') }}{% endif %}
                </div>
                <div class="article-summary">
                    {{ article.ai_summary or article.summary }}
                </div>
                {% if article.tags %}
                <div class="tags">
                    {% for tag in article.tags %}
                    <span class="tag">{{ tag }}</span>
                    {% endfor %}
                </div>
                {% endif %}
                <a href="{{ article.link }}" class="article-link" target="_blank">Read more →</a>
            </div>
            {% endfor %}
            
            {% if recommendations_by_topic and recommendations_by_topic.get(topic_name) %}
            {% set recs = recommendations_by_topic[topic_name] %}
            {% if recs.research_papers %}
            <div class="recommendations-section">
                <h3 style="color: #4A90E2; margin-top: 30px; margin-bottom: 15px;">🔍 AI Recommendations for {{ topic_name }}</h3>
                
                {% if recs.research_papers %}
                <div class="recommendation-category">
                    <h4 style="color: #2C3E50; margin-bottom: 8px;">📚 Research Papers</h4>
                    <ul style="margin: 0; padding-left: 20px;">
                        {% for paper in recs.research_papers %}
                        <li style="margin-bottom: 5px;">{{ paper }}</li>
                        {% endfor %}
                    </ul>
                </div>
                {% endif %}
            </div>
            {% endif %}
            {% endif %}
            
            {% if enhanced_recommendations_by_topic and enhanced_recommendations_by_topic.get(topic_name) %}
            <div class="enhanced-recommendations-section">
                <h3 style="color: #E74C3C; margin-top: 30px; margin-bottom: 15px;">📚 AI-Recommended Reading List</h3>
                {% set enhanced = enhanced_recommendations_by_topic[topic_name] %}
                
                {% if enhanced.recommended_articles %}
                <div class="enhanced-recommendation-category">
                    <h4 style="color: #2C3E50; margin-bottom: 8px;">📰 Articles from Recommended Sources</h4>
                    {% for article in enhanced.recommended_articles %}
                    <div style="margin-bottom: 15px; padding: 10px; background-color: #F8F9FA; border-left: 3px solid #E74C3C; border-radius: 3px;">
                        <div style="font-weight: 600; color: #2C3E50; margin-bottom: 5px;">{{ article.title }}</div>
                        <div style="color: #7F8C8D; font-size: 14px; margin-bottom: 5px;">{{ article.summary }}</div>
                        <div style="color: #95A5A6; font-size: 12px; margin-bottom: 5px;">Source: {{ article.recommended_by }}</div>
                        {% if article.link %}
                        <a href="{{ article.link }}" style="color: #E74C3C; text-decoration: none; font-size: 14px;">Read article →</a>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
                
                {% if enhanced.recommended_tweets %}
                <div class="enhanced-recommendation-category">
                    <h4 style="color: #2C3E50; margin-bottom: 8px;">📖 Expert-Recommended Reading</h4>
                    {% for reading in enhanced.recommended_tweets %}
                    <div style="margin-bottom: 15px; padding: 10px; background-color: #F8F9FA; border-left: 3px solid #3498DB; border-radius: 3px;">
                        <div style="font-weight: 600; color: #2C3E50; margin-bottom: 5px;">{{ reading.title }}</div>
                        <div style="color: #7F8C8D; font-size: 14px; margin-bottom: 5px;">{{ reading.summary }}</div>
                        <div style="color: #95A5A6; font-size: 12px; margin-bottom: 5px;">{{ reading.recommended_by }}</div>
                        {% if reading.has_valid_link and reading.link %}
                        <a href="{{ reading.link }}" style="color: #3498DB; text-decoration: none; font-size: 14px;">Read now →</a>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
                
                {% if enhanced.recommended_papers %}
                <div class="enhanced-recommendation-category">
                    <h4 style="color: #2C3E50; margin-bottom: 8px;">🔬 Research Papers to Read</h4>
                    {% for paper in enhanced.recommended_papers %}
                    <div style="margin-bottom: 15px; padding: 10px; background-color: #F8F9FA; border-left: 3px solid #9B59B6; border-radius: 3px;">
                        <div style="font-weight: 600; color: #2C3E50; margin-bottom: 5px;">{{ paper.title }}</div>
                        <div style="color: #7F8C8D; font-size: 14px; margin-bottom: 5px;">{{ paper.summary }}</div>
                        <div style="color: #95A5A6; font-size: 12px; margin-bottom: 5px;">{{ paper.recommended_by }}</div>
                        {% if paper.has_valid_link and paper.link %}
                        <a href="{{ paper.link }}" style="color: #9B59B6; text-decoration: none; font-size: 14px;">Read paper →</a>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
            </div>
            {% endif %}
            
            {% if blogger_posts_by_topic and blogger_posts_by_topic.get(topic_name) %}
            <div class="blogger-posts-section">
                <h3 style="color: #27AE60; margin-top: 30px; margin-bottom: 15px;">📝 Featured Blogger Posts</h3>
                {% set blogger_posts = blogger_posts_by_topic[topic_name] %}
                
                {% for post in blogger_posts %}
                <div style="margin-bottom: 20px; padding: 15px; background-color: #F8F9FA; border-left: 4px solid #27AE60; border-radius: 5px;">
                    <div style="font-weight: 600; color: #2C3E50; margin-bottom: 8px; font-size: 16px;">
                        <a href="{{ post.link }}" style="color: #2C3E50; text-decoration: none;">{{ post.title }}</a>
                    </div>
                    <div style="color: #7F8C8D; font-size: 14px; margin-bottom: 8px;">
                        <strong>By {{ post.blogger_name }}</strong>
                        {% if post.blogger_expertise %} • {{ post.blogger_expertise }}{% endif %}
                    </div>
                    {% if post.blogger_recent_focus %}
                    <div style="color: #95A5A6; font-size: 12px; margin-bottom: 8px; font-style: italic;">
                        Recent focus: {{ post.blogger_recent_focus }}
                    </div>
                    {% endif %}
                    <div style="color: #555; line-height: 1.5; margin-bottom: 10px;">
                        {{ post.summary or post.ai_summary or 'No summary available' }}
                    </div>
                    <div style="color: #95A5A6; font-size: 12px; margin-bottom: 8px;">
                        {% if post.published %}{{ post.published.strftime('%B %d, %Y') }}{% endif %}
                    </div>
                    <a href="{{ post.link }}" style="color: #27AE60; text-decoration: none; font-size: 14px; font-weight: 500;">Read full post →</a>
                </div>
                {% endfor %}
            </div>
            {% endif %}

            {% if conference_recommendations_by_topic and conference_recommendations_by_topic.get(topic_name) %}
            <div class="conference-recommendations-section">
                <h3 style="color: #8E44AD; margin-top: 30px; margin-bottom: 15px;">🎤 Conference & Speaking Opportunities</h3>
                {% set conferences = conference_recommendations_by_topic[topic_name] %}

                {% for conf in conferences %}
                <div style="margin-bottom: 20px; padding: 15px; background-color: #F8F9FA; border-left: 4px solid #8E44AD; border-radius: 5px;">
                    <div style="font-weight: 600; color: #2C3E50; margin-bottom: 8px; font-size: 16px;">
                        {% if conf.url %}
                        <a href="{{ conf.url }}" style="color: #2C3E50; text-decoration: none;">{{ conf.name }}</a>
                        {% else %}
                        {{ conf.name }}
                        {% endif %}
                    </div>
                    <div style="color: #7F8C8D; font-size: 14px; margin-bottom: 8px;">
                        <strong>{{ conf.type|title }}</strong>
                        {% if conf.deadline %} • Deadline: {{ conf.deadline }}{% endif %}
                    </div>
                    <div style="color: #555; line-height: 1.5; margin-bottom: 10px;">
                        {{ conf.description }}
                    </div>
                    {% if conf.url %}
                    <a href="{{ conf.url }}" style="color: #8E44AD; text-decoration: none; font-size: 14px; font-weight: 500;">Learn more →</a>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
            {% endif %}
        </div>
        {% endif %}
        {% endfor %}
        
        <div class="footer">
            <p>That's all for today! Have a productive day ahead. 🚀</p>
            <p style="font-size: 12px; margin-top: 10px;">
                Generated by {{ assistant_name }} with ❤️
            </p>
        </div>
    </div>
</body>
</html>
        """
        
        # Enable auto-escaping to prevent XSS attacks from malicious article content
        t = Template(template, autoescape=True)
        html = t.render(
            articles_by_topic=articles_by_topic,
            overview=overview,
            user_name=user_name,
            assistant_name=assistant_name,
            recommendations_by_topic=recommendations_by_topic or {},
            enhanced_recommendations_by_topic=enhanced_recommendations_by_topic or {},
            blogger_posts_by_topic=blogger_posts_by_topic or {},
            conference_recommendations_by_topic=conference_recommendations_by_topic or {},
            current_date=datetime.now().strftime("%A, %B %d, %Y")
        )
        
        return html
    
    def send_email(self, subject: str, html_content: str) -> bool:
        """
        Send the email
        
        Args:
            subject: Email subject
            html_content: HTML content of the email
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            
            # Attach HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email with timeout protection
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                server.starttls()
                server.login(self.email_from, self.email_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {self.email_to}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False



