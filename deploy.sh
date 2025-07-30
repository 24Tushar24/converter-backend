#!/bin/bash
# Azure deployment script for better dependency management

echo "🚀 Starting Azure deployment process..."

# Update pip and basic tools
echo "📦 Updating pip and basic tools..."
python -m pip install --upgrade pip setuptools wheel

# Install dependencies with more verbose output
echo "📦 Installing application dependencies..."
pip install --no-cache-dir --verbose -r requirements.txt

# Verify critical imports
echo "🔍 Verifying critical packages..."
python -c "
try:
    import fastapi
    print('✅ FastAPI imported successfully')
except ImportError as e:
    print(f'❌ FastAPI import failed: {e}')
    exit(1)

try:
    import uvicorn
    print('✅ Uvicorn imported successfully')
except ImportError as e:
    print(f'❌ Uvicorn import failed: {e}')
    exit(1)

try:
    import cloudinary
    print('✅ Cloudinary imported successfully')
except ImportError as e:
    print(f'❌ Cloudinary import failed: {e}')
    exit(1)

try:
    import pymongo
    print('✅ PyMongo imported successfully')
except ImportError as e:
    print(f'❌ PyMongo import failed: {e}')
    exit(1)

try:
    from psd_tools import PSDImage
    print('✅ PSD Tools imported successfully')
except ImportError as e:
    print(f'❌ PSD Tools import failed: {e}')
    exit(1)

print('🎉 All critical packages verified!')
"

if [ $? -eq 0 ]; then
    echo "✅ Deployment preparation completed successfully"
else
    echo "❌ Deployment preparation failed"
    exit 1
fi
