"""
Email Scanner Module
Scans email for tech blogs, newsletters, and updates to extract content
"""

import imaplib
import email
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
from bs4 import BeautifulSoup
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmailScanner:
    def __init__(self):
        """Initialize email scanner with IMAP credentials"""
        self.imap_server = os.getenv("IMAP_SERVER", "imap.gmail.com")
        self.imap_port = int(os.getenv("IMAP_PORT", "993"))
        self.email_user = os.getenv("EMAIL_FROM")
        self.email_password = os.getenv("EMAIL_PASSWORD")
        
        if not all([self.email_user, self.email_password]):
            raise ValueError("Email credentials not found in environment variables")
    
    def connect_to_email(self):
        """Connect to email server using IMAP"""
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.email_user, self.email_password)
            return mail
        except Exception as e:
            logger.error(f"Error connecting to email: {str(e)}")
            return None
    
    def search_tech_emails(self, mail, days_back: int = 7) -> List[str]:
        """
        Search for tech-related emails in the last N days
        
        Args:
            mail: IMAP connection
            days_back: Number of days to look back
            
        Returns:
            List of email IDs
        """
        try:
            # Select inbox
            mail.select('INBOX')
            
            # Calculate date range
            since_date = (datetime.now() - timedelta(days=days_back)).strftime('%d-%b-%Y')
            
            # Search for emails from tech sources
            tech_sources = [
                'github', 'gitlab', 'aws', 'google', 'microsoft', 'docker', 'kubernetes',
                'hackernews', 'techcrunch', 'arstechnica', 'wired', 'verge',
                'stackoverflow', 'dev.to', 'medium', 'substack', 'hashnode',
                'newsletter', 'blog', 'engineering', 'security', 'devops'
            ]
            
            # Build search query
            search_queries = []
            for source in tech_sources:
                search_queries.append(f'(FROM "{source}" SINCE "{since_date}")')
                search_queries.append(f'(SUBJECT "{source}" SINCE "{since_date}")')
            
            # Combine queries with OR
            search_query = f'({" OR ".join(search_queries)})'
            
            # Search for emails
            status, messages = mail.search(None, search_query)
            
            if status == 'OK':
                email_ids = messages[0].split()
                logger.info(f"Found {len(email_ids)} potential tech emails")
                return email_ids
            else:
                logger.warning("No tech emails found")
                return []
                
        except Exception as e:
            logger.error(f"Error searching emails: {str(e)}")
            return []
    
    def extract_email_content(self, mail, email_id: str) -> Optional[Dict]:
        """
        Extract content from a specific email
        
        Args:
            mail: IMAP connection
            email_id: Email ID to extract
            
        Returns:
            Dictionary with email content or None
        """
        try:
            # Fetch email
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            
            if status != 'OK':
                return None
            
            # Parse email
            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            # Extract basic info
            subject = email_message.get('Subject', '')
            from_addr = email_message.get('From', '')
            date_str = email_message.get('Date', '')
            
            # Extract body content
            body = self._extract_email_body(email_message)
            
            if not body:
                return None
            
            # Check if it's a tech-related email
            if not self._is_tech_related(subject, from_addr, body):
                return None
            
            return {
                'subject': subject,
                'from': from_addr,
                'date': date_str,
                'body': body,
                'source': 'email_scan'
            }
            
        except Exception as e:
            logger.error(f"Error extracting email content: {str(e)}")
            return None
    
    def _extract_email_body(self, email_message) -> str:
        """Extract text content from email body"""
        body = ""
        
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                elif content_type == "text/html" and "attachment" not in content_disposition:
                    html_content = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    # Convert HTML to text
                    soup = BeautifulSoup(html_content, 'html.parser')
                    body += soup.get_text()
        else:
            body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
        
        return body.strip()
    
    def _is_tech_related(self, subject: str, from_addr: str, body: str) -> bool:
        """Check if email is tech-related"""
        tech_keywords = [
            'software', 'engineering', 'development', 'programming', 'code',
            'technology', 'tech', 'cloud', 'aws', 'azure', 'gcp', 'docker',
            'kubernetes', 'devops', 'security', 'cybersecurity', 'ai', 'ml',
            'data', 'database', 'api', 'web', 'mobile', 'frontend', 'backend',
            'javascript', 'python', 'java', 'go', 'rust', 'react', 'vue',
            'angular', 'node', 'spring', 'django', 'flask', 'rails',
            'github', 'gitlab', 'bitbucket', 'jenkins', 'ci/cd', 'deployment',
            'monitoring', 'logging', 'testing', 'qa', 'agile', 'scrum'
        ]
        
        text_to_check = f"{subject} {from_addr} {body}".lower()
        
        # Check for tech keywords
        tech_score = sum(1 for keyword in tech_keywords if keyword in text_to_check)
        
        # Check for newsletter indicators
        newsletter_indicators = ['newsletter', 'digest', 'weekly', 'daily', 'update', 'brief']
        newsletter_score = sum(1 for indicator in newsletter_indicators if indicator in text_to_check)
        
        # Consider it tech-related if it has tech keywords or newsletter indicators
        return tech_score >= 2 or newsletter_score >= 1
    
    def extract_articles_from_email(self, email_content: Dict) -> List[Dict]:
        """
        Extract individual articles/links from email content
        
        Args:
            email_content: Email content dictionary
            
        Returns:
            List of article dictionaries
        """
        articles = []
        
        try:
            body = email_content['body']
            subject = email_content['subject']
            
            # Extract URLs from email body
            url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            urls = re.findall(url_pattern, body)
            
            # Extract article titles and descriptions
            # Look for common newsletter patterns
            lines = body.split('\n')
            current_article = {}
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if line contains a URL
                line_urls = re.findall(url_pattern, line)
                if line_urls:
                    # This might be an article
                    article = {
                        'title': self._extract_title_from_line(line),
                        'link': line_urls[0],
                        'summary': self._extract_summary_from_line(line),
                        'published': datetime.now(),
                        'source': email_content['from'],
                        'email_subject': subject
                    }
                    
                    if article['title'] and article['link']:
                        articles.append(article)
            
            # If no articles found with pattern matching, create one from the email itself
            if not articles and email_content['body']:
                articles.append({
                    'title': subject,
                    'link': '',  # No specific link
                    'summary': body[:500] + '...' if len(body) > 500 else body,
                    'published': datetime.now(),
                    'source': email_content['from'],
                    'email_subject': subject
                })
            
            logger.info(f"Extracted {len(articles)} articles from email: {subject}")
            
        except Exception as e:
            logger.error(f"Error extracting articles from email: {str(e)}")
        
        return articles
    
    def _extract_title_from_line(self, line: str) -> str:
        """Extract article title from a line of text"""
        # Remove URLs and clean up
        line = re.sub(r'http[s]?://\S+', '', line)
        line = line.strip()
        
        # Take first 100 characters as title
        return line[:100] if line else "No Title"
    
    def _extract_summary_from_line(self, line: str) -> str:
        """Extract summary from a line of text"""
        # Remove URLs and clean up
        line = re.sub(r'http[s]?://\S+', '', line)
        line = line.strip()
        
        # Take first 200 characters as summary
        return line[:200] if line else ""
    
    def scan_emails_for_content(self, days_back: int = 7) -> List[Dict]:
        """
        Main method to scan emails and extract tech content
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            List of article dictionaries
        """
        articles = []
        
        try:
            # Connect to email
            mail = self.connect_to_email()
            if not mail:
                return articles
            
            # Search for tech emails
            email_ids = self.search_tech_emails(mail, days_back)
            
            # Process each email
            for email_id in email_ids[:20]:  # Limit to 20 emails
                email_content = self.extract_email_content(mail, email_id)
                if email_content:
                    email_articles = self.extract_articles_from_email(email_content)
                    articles.extend(email_articles)
            
            # Close connection
            mail.close()
            mail.logout()
            
            logger.info(f"Scanned emails and found {len(articles)} articles")
            
        except Exception as e:
            logger.error(f"Error scanning emails: {str(e)}")
        
        return articles


# Example usage
def scan_mark_emails():
    """Scan Mark's emails for tech content"""
    scanner = EmailScanner()
    articles = scanner.scan_emails_for_content(days_back=7)
    
    print(f"Found {len(articles)} articles from email scanning:")
    for article in articles[:5]:  # Show first 5
        print(f"- {article['title']}")
        print(f"  From: {article['source']}")
        print(f"  Link: {article['link']}")
        print()
    
    return articles


if __name__ == "__main__":
    scan_mark_emails()

