#!/bin/bash

# Local Development Setup Script
# Sets up the environment for testing without committing temp files

echo "🚀 Setting up AI Assistant for local development..."

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp env.example .env
    echo "⚠️  Please edit .env file with your actual API keys and email credentials"
else
    echo "✅ .env file already exists"
fi

# Create logs directory
mkdir -p logs

echo ""
echo "✅ Setup complete!"
echo ""
echo "🔧 Next steps:"
echo "1. Edit .env file with your actual credentials:"
echo "   - ANTHROPIC_API_KEY=your_claude_api_key"
echo "   - EMAIL_FROM=your_email@gmail.com"
echo "   - EMAIL_TO=your_email@gmail.com"
echo "   - EMAIL_PASSWORD=your_app_password"
echo ""
echo "2. Test the setup:"
echo "   source venv/bin/activate"
echo "   python test_brief.py"
echo ""
echo "3. Start the scheduler:"
echo "   ./start_scheduler.sh"
echo ""
echo "🎉 Happy coding!"
