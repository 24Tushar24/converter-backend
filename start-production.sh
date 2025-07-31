#!/bin/bash

echo "🚀 Starting PSD Converter Backend in Production Mode..."

# Set production environment
export PRODUCTION=true

# Start the server with production settings
python3 main.py
