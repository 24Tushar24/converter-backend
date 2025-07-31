#!/bin/bash

echo "🚀 Setting up PSD Converter Backend..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8+ first."
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ Created .env file from .env.example"
        echo "🔧 Please edit .env with your credentials before running the server"
    else
        echo "⚠️  No .env.example found. You'll need to create .env manually"
    fi
fi

echo "✅ Setup complete!"
echo ""
echo "🎯 Next steps:"
echo "1. Edit .env with your Cloudinary and MongoDB credentials"
echo "2. Run: python main.py"
echo "3. Open: http://localhost:8000/docs"
