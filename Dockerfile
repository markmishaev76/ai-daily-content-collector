# Dockerfile for Personal AI Assistant
# Build: docker build -t personal-ai-assistant .
# Run: docker run -d --env-file .env personal-ai-assistant

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create volume for config
VOLUME ["/app/config"]

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the scheduler
CMD ["python", "scheduler.py"]






