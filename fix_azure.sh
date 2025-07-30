#!/bin/bash
# Quick Azure deployment fix script

echo "🚀 Azure Deployment Quick Fix"
echo "=============================="

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: main.py not found. Run this script from your project root."
    exit 1
fi

echo "✅ Found main.py - we're in the right directory"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1)
echo "✅ Python version: $PYTHON_VERSION"

# Test imports
echo "🔍 Testing critical imports..."
python3 -c "
import sys
try:
    import fastapi, uvicorn, cloudinary, pymongo, psd_tools
    print('✅ All critical modules available')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
" || exit 1

# Test app creation
echo "🔍 Testing app creation..."
python3 -c "
import os
os.environ['CLOUDINARY_CLOUD_NAME'] = 'test'
os.environ['CLOUDINARY_API_KEY'] = 'test'  
os.environ['CLOUDINARY_API_SECRET'] = 'test'
os.environ['MONGODB_CONNECTION_STRING'] = 'test'
try:
    from main import app
    print('✅ App creation successful')
except Exception as e:
    print(f'❌ App creation failed: {e}')
    import traceback
    traceback.print_exc()
    exit(1)
" || exit 1

echo ""
echo "🎉 Local tests passed! Now for Azure deployment:"
echo ""
echo "📋 Azure Configuration Checklist:"
echo "=================================="
echo "1. Set Startup Command to: python startup.py"
echo "2. Set these Environment Variables in Azure App Service:"
echo "   - CLOUDINARY_CLOUD_NAME=dg1dpoysz"
echo "   - CLOUDINARY_API_KEY=643713745468581"
echo "   - CLOUDINARY_API_SECRET=BK1pqUHdR0cwjmReAB_h18LAjIs"
echo "   - MONGODB_CONNECTION_STRING=your_connection_string"
echo "   - SCM_DO_BUILD_DURING_DEPLOYMENT=true"
echo ""
echo "3. Deploy your code to Azure"
echo "4. Check Azure logs for startup messages"
echo "5. Test the /health endpoint"
echo ""
echo "🔧 If you get 500 errors, check Azure logs and verify:"
echo "   - All environment variables are set"
echo "   - MongoDB connection string is accessible"
echo "   - Cloudinary credentials are valid"
echo ""
echo "📚 See AZURE_DEPLOYMENT.md for detailed instructions"
