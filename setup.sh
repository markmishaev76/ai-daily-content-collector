#!/bin/bash

# Setup script for Personal AI Assistant

echo "=================================="
echo "Personal AI Assistant - Setup"
echo "=================================="
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "=================================="
echo "✅ Setup complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API keys and email settings"
echo "2. Customize config.yaml with your topics of interest"
echo "3. Test with: python test_brief.py"
echo "4. Start scheduler: python scheduler.py"
echo ""
echo "For Gmail setup, see README.md section on App Passwords"
echo ""



