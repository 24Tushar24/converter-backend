#!/bin/bash

echo "🚀 Starting PSD Converter Backend..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Run ./setup.sh first!"
    exit 1
fi

# Check if dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "❌ Dependencies not installed. Run ./setup.sh first!"
    exit 1
fi

# Start the server
echo "🌟 Server starting at http://localhost:8000"
echo "📚 API docs available at http://localhost:8000/docs"
echo "Press Ctrl+C to stop"
echo ""

python main.py
