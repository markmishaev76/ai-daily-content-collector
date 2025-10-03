# 🤖 AI-Powered Daily Brief Assistant

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Claude](https://img.shields.io/badge/AI-Claude%203.5%20Sonnet-orange.svg)](https://anthropic.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Your personalized daily brief that saves you hours every day! Get one clean email every morning with curated updates, research papers, and AI-powered summaries across all your topics of interest.

> **Save 3+ hours daily** with automated content aggregation and AI-powered summarization from 40+ professional sources.

## ✨ What You Get

- 📰 **Daily News Brief**: Curated articles from 40+ professional sources
- 🔬 **Research Integration**: Latest research papers and academic content
- 🧠 **AI Summaries**: Claude-powered summaries of all content
- 📧 **Beautiful HTML Emails**: Professional, mobile-friendly format
- ⚙️ **Fully Automated**: Runs daily at your chosen time
- 🎯 **Domain-Specific**: Tailored to your professional interests

## 🎯 Key Features

- 📰 **Content Aggregation**: 40+ professional RSS feeds and sources
- 🔬 **Research Integration**: Academic papers, industry reports, and surveys  
- 🧠 **AI Summaries**: Claude 3.5 Sonnet for intelligent content summarization
- 📧 **Professional Emails**: Beautiful HTML format with mobile optimization
- ⚙️ **Fully Automated**: Daily scheduling with background processing
- 🎯 **Domain Expertise**: Pre-configured for tech, security, and engineering topics
- 🐳 **Docker Support**: Easy deployment with containerization
- 🔧 **Highly Configurable**: Customize sources, schedule, and AI settings

## 🛠️ Tech Stack

- **Python 3.8+**
- **Claude 3.5 Sonnet** for AI summaries
- **feedparser** for RSS feeds
- **BeautifulSoup** for web scraping
- **Jinja2** for email templates
- **schedule** for automation
- **SMTP** for email delivery

## 🚀 Quick Start

### 1. Clone and Install

```bash
# Navigate to the project directory
cd ai-eba

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the example environment file and configure it:

```bash
cp env.example .env
```

Edit `.env` with your actual values:

```bash
# AI Provider (claude, openai, or gemini)
AI_PROVIDER=claude

# Claude API Key (get from https://console.anthropic.com/)
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Email Configuration (Gmail example)
EMAIL_FROM=your.email@gmail.com
EMAIL_TO=your.email@gmail.com
EMAIL_PASSWORD=your-app-password-here
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Schedule Time (24-hour format)
SCHEDULE_TIME=06:00
```

#### 📧 Gmail Setup (Recommended)

To use Gmail, you need to create an **App Password**:

1. Go to your Google Account settings
2. Enable 2-Factor Authentication if not already enabled
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Select "Mail" and your device
5. Copy the generated 16-character password
6. Use this password in `EMAIL_PASSWORD` (not your regular Gmail password)

### 3. Customize Your Topics (Optional)

The system comes pre-configured with comprehensive topics for tech professionals. You can edit `config.yaml` to customize:

```yaml
assistant_name: "Your AI Assistant"  # Name your assistant!
user_name: "Your Name"

topics:
  - name: "AI Technologies & Research"
    category: "AI/ML"
    sources:
      - type: "rss"
        url: "https://blog.openai.com/rss/"
      - type: "rss"
        url: "https://www.anthropic.com/news/rss.xml"
  
  - name: "Cybersecurity News"
    category: "Security"
    sources:
      - type: "rss"
        url: "https://krebsonsecurity.com/feed/"
  
  # 10+ more pre-configured topics included!
```

### 4. Test Your Setup

```bash
python test_brief.py
```

This will generate and send a test email immediately. Check your inbox!

### 5. Start the Scheduler

```bash
# Start the scheduler
./start_scheduler.sh

# Check status
./status_scheduler.sh

# Stop when needed
./stop_scheduler.sh
```

The scheduler will run in the background and send your brief at the configured time every day.

## 📋 Configuration Options

### Summarization Settings

```yaml
summarization:
  model: "gpt-4o-mini"  # or "gpt-4" for better quality
  max_articles_per_topic: 5  # Limit articles per topic
  summary_length: "brief"  # brief, medium, or detailed
```

### Email Settings

```yaml
email:
  subject: "Your Morning Brief - {date}"
  include_links: true
  group_by_category: true
```

## 🔧 Advanced Usage

### Finding RSS Feeds

Most blogs and news sites have RSS feeds. Common locations:
- `/feed/`
- `/rss/`
- `/feed.xml`
- `/rss.xml`

Use browser extensions like "RSS Feed Reader" to find feeds on any site.

### Alternative Email Providers

The system works with any SMTP server. Common providers:

**Outlook/Hotmail:**
```
SMTP_SERVER=smtp-mail.outlook.com
SMTP_PORT=587
```

**Yahoo:**
```
SMTP_SERVER=smtp.mail.yahoo.com
SMTP_PORT=587
```

### Running as a Background Service

#### macOS (launchd):

Create `~/Library/LaunchAgents/com.user.ai-assistant.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.ai-assistant</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/Users/markmishaev/ai-eba/scheduler.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/markmishaev/ai-eba</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

Load the service:
```bash
launchctl load ~/Library/LaunchAgents/com.user.ai-assistant.plist
```

#### Linux (systemd):

Create `/etc/systemd/system/ai-assistant.service`:

```ini
[Unit]
Description=Personal AI Assistant
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/home/yourusername/ai-eba
ExecStart=/usr/bin/python3 /home/yourusername/ai-eba/scheduler.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable ai-assistant
sudo systemctl start ai-assistant
```

### Docker Deployment (Optional)

Coming soon! You can also containerize this application for easy deployment.

## 🎨 Customizing the Email Template

Edit `src/email_sender.py` to modify the HTML template. The template uses Jinja2, making it easy to customize:

- Change colors and styles in the `<style>` section
- Modify the layout in the HTML body
- Add your own branding or logos

## 🐛 Troubleshooting

### No articles in the brief
- Check if the RSS feeds are valid (test them in a feed reader)
- Adjust `hours_back` parameter in the ContentAggregator
- Some feeds may not publish daily content

### Email not sending
- Verify your SMTP credentials
- For Gmail, ensure you're using an App Password, not your regular password
- Check that 2FA is enabled on your Google account
- Look for error messages in the logs

### API errors
- Verify your OpenAI API key is correct
- Check your API quota/billing
- Ensure you have internet connectivity

### Rate limiting
- The system processes articles sequentially to avoid rate limits
- If you have many articles, consider increasing delays or reducing `max_articles_per_topic`

## 💡 Tips for Best Results

1. **Start small**: Begin with 2-3 topics and gradually add more
2. **Quality over quantity**: Focus on high-quality RSS feeds
3. **Test regularly**: Use `test_brief.py` when adding new sources
4. **Adjust summary length**: Experiment with "brief", "medium", or "detailed"
5. **Schedule wisely**: Choose a time when you typically check email

## 🔒 Security Notes

- Never commit your `.env` file to version control
- Keep your API keys secure
- Use app-specific passwords for email services
- Regularly rotate your API keys

## 📊 Cost Estimation

Using GPT-4o-mini (recommended):
- ~10 articles/day × 30 days = $0.50-1.00/month
- OpenAI API is pay-as-you-go

Using GPT-4:
- ~10 articles/day × 30 days = $3-5/month

RSS feeds and email are completely free!

## 🚧 Future Enhancements

- [ ] Slack/Discord/Teams integration
- [ ] Web dashboard to view past briefs
- [ ] Mobile app support
- [ ] Custom AI training on your preferences
- [ ] Sentiment analysis and trending topics
- [ ] Integration with read-it-later services (Pocket, Instapaper)

## 📝 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the issues page.

## 👨‍💻 Author

Built with ❤️ by Mark

---

**Enjoy your extra 3 hours every day! ⏰**

