#!/bin/bash
# Azure App Service startup script

echo "Starting PSD Converter Backend on Azure..."
echo "Python version: $(python --version)"
echo "Working directory: $(pwd)"
echo "Files in directory: $(ls -la)"

# Check if requirements are installed
python -c "import fastapi; print('FastAPI is available')" || {
    echo "FastAPI not found, installing requirements..."
    pip install -r requirements.txt
}

# Set default environment variables if not provided
export PORT=${PORT:-8000}
export HOST=${HOST:-0.0.0.0}

echo "Starting application on $HOST:$PORT"

# Start the application with explicit module path
python -m uvicorn main:app --host $HOST --port $PORT --log-level info
