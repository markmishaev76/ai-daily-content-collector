"""
Personal AI Assistant - Main Application
Aggregates, ranks, and emails your personalized daily brief
"""

import yaml
import logging
from datetime import datetime
from dotenv import load_dotenv

from src.content_aggregator import ContentAggregator
from src.email_sender import EmailSender
from src.hn import hn_counts, is_hn_item, min_points

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


AX_THEME_KEYWORDS = {
    # Agent Experience & agentic design
    "agent experience": 5, " ax ": 4, "agentic": 3, "mcp": 4, "model context protocol": 5,
    # Identity & authorization for agents
    "cedar": 4, "opa": 3, "policy-as-code": 4, "policy as code": 4, "zero trust": 3,
    "service account": 2, "composite identity": 5, "workload identity": 4,
    "spiffe": 4, "spire": 4, "oauth scope": 3, "fine-grained": 2,
    "agent identity": 5, "non-human identity": 5, "workload authorization grant": 5,
    "id-jag": 5, "identity assertion": 4, "wimse": 5, "token exchange": 4,
    "rfc 8693": 4, "rfc 7523": 4, "dpop": 4, "on-behalf-of": 3, "delegated access": 3,
    "scim": 3, "cross-app access": 4, "agent sso": 4, "entra agent id": 5,
    "agentcore identity": 5,
    # Audit & trust
    "audit trail": 3, "structured audit": 4, "provenance": 3, "slsa": 4, "sigstore": 3,
    "attestation": 3, "sbom": 3,
    # Secrets for agents
    "openbao": 5, "vault": 2, "secrets management": 3, "short-lived credential": 4,
    "credential rotation": 3,
    # AI agents & platforms
    "ai agent": 4, "autonomous agent": 4, "agent security": 5, "prompt injection": 4,
    "red team": 2, "jailbreak": 2, "ai safety": 3,
    # CI/CD software factories
    "software factory": 5, "ci/cd": 2, "pipeline security": 4, "dependency firewall": 5,
    "supply chain": 3, "dependency confusion": 4, "malicious package": 4,
    # Reliability and multi-tenancy
    "rate limit": 3, "noisy neighbor": 4, "multi-tenant": 2, "postmortem": 2,
    # Reproducible builds
    "reproducible build": 4, "hermetic": 3,
    # MCP and agent tool security
    "mcp server": 3, "tool poisoning": 4,
    # AI adoption
    "ai adoption": 3, "developer productivity": 2,
    # AI coding assistants
    "copilot": 2, "devin": 3, "claude code": 3, "codex": 2,
}


def _score_article(article: dict) -> float:
    """Rank articles by relevance to AX/Trust/agent-security themes.

    Returns higher scores for articles matching keywords. Articles with no
    matches fall back to a neutral 0.0 and keep their existing publish-date
    ordering (stable sort preserves it).
    """
    title = (article.get("title") or "").lower()
    body = (article.get("summary") or "").lower()
    score = 0.0
    for keyword, weight in AX_THEME_KEYWORDS.items():
        if keyword in title:
            score += weight * 2
        if keyword in body:
            score += weight
    return score


def rank_articles_by_theme(articles: list) -> list:
    """Stable sort: theme-matching articles first, ties preserve original order."""
    indexed = list(enumerate(articles))
    indexed.sort(key=lambda pair: (-_score_article(pair[1]), pair[0]))
    return [article for _, article in indexed]


def select_articles(articles_by_topic: dict, max_articles: int, min_hn_points: int = 0) -> dict:
    """Rank each topic and keep its top N, skipping links already shown in an earlier topic
    and Hacker News items with fewer than min_hn_points points.

    Used by both the email and the site so they pick the same articles.
    """
    shown = set()
    selected = {}
    for topic, articles in articles_by_topic.items():
        picked = []
        for article in rank_articles_by_theme(articles):
            if len(picked) == max_articles:
                break
            link = article.get('link')
            if link and link in shown:
                continue
            if is_hn_item(article) and hn_counts(article.get('summary'))[0] < min_hn_points:
                continue
            picked.append(article)
        shown.update(a.get('link') for a in picked if a.get('link'))
        selected[topic] = picked
    return selected


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
        email_sender = EmailSender()
        
        # Step 1: Aggregate content from all sources
        logger.info("Step 1: Aggregating content from sources...")
        articles_by_topic = aggregator.aggregate_content(config['topics'])
        
        # Step 2: Rank by theme relevance and keep the top N per topic, without repeats
        articles_by_topic = select_articles(articles_by_topic, config['brief']['max_articles_per_topic'],
                                            min_points(config, 'section_min_hn_points'))
        
        # Step 3: Create HTML email
        logger.info("Step 2: Creating email...")
        html_content = email_sender.create_html_email(
            articles_by_topic=articles_by_topic,
            user_name=config.get('user_name', 'there'),
            assistant_name=config.get('assistant_name', 'Your AI Assistant'),
        )
        
        # Step 4: Send email
        logger.info("Step 3: Sending email...")
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

