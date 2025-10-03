#!/bin/bash

# Push to GitHub Repository
# This script helps push your AI assistant to GitHub

echo "🚀 Pushing AI Assistant to GitHub..."
echo "Repository: https://github.com/markmishaev76/ai-daily-content-collector"
echo ""

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "❌ Not in a git repository. Please run this from the project directory."
    exit 1
fi

# Check if remote is set
if ! git remote get-url origin > /dev/null 2>&1; then
    echo "❌ No remote repository configured."
    exit 1
fi

echo "📋 Current status:"
git status --short

echo ""
echo "📦 Adding all files..."
git add .

echo "💾 Committing changes..."
git commit -m "Add AI-powered daily brief assistant

- RSS feed aggregation from 40+ professional sources
- AI-powered content summarization with Claude
- Beautiful HTML email generation
- Automated daily scheduling
- Research integration for academic papers
- Comprehensive configuration system
- Docker support included"

echo "🚀 Pushing to GitHub..."
echo ""
echo "⚠️  You may be prompted for GitHub credentials:"
echo "   - Username: your GitHub username"
echo "   - Password: use a Personal Access Token (not your GitHub password)"
echo "   - Get token from: https://github.com/settings/tokens"
echo ""

git push -u origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Successfully pushed to GitHub!"
    echo "🌐 Repository: https://github.com/markmishaev76/ai-daily-content-collector"
    echo ""
    echo "📖 Next steps:"
    echo "1. Visit your repository on GitHub"
    echo "2. Add a README description"
    echo "3. Set up GitHub Pages if desired"
    echo "4. Share with others!"
else
    echo ""
    echo "❌ Push failed. Please check your authentication:"
    echo "1. Make sure you have a Personal Access Token"
    echo "2. Use the token as your password when prompted"
    echo "3. Ensure you have write access to the repository"
fi
