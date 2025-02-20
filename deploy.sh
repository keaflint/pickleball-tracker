#!/bin/bash

echo "Starting deployment..."

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Run database migrations
flask db upgrade

# Clear cache if any
if [ -d "flask_cache" ]; then
    rm -rf flask_cache/*
fi

# Restart Gunicorn (adjust the path as needed)
sudo systemctl restart pickleball

echo "Deployment completed!" 