#!/bin/bash
cd /Users/markmishaev/ai-eba
source venv/bin/activate
python main.py >> logs/brief.log 2>&1
