#!/bin/bash
# Startup script for Azure Web App

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Starting Gunicorn..."
gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 4 app:app
