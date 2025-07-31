#!/bin/bash

echo "☁️ Deploying PSD Converter to Azure..."

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI not found. Installing..."
    curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
fi

# Check if logged in to Azure
if ! az account show &> /dev/null; then
    echo "🔐 Please login to Azure..."
    az login
fi

# Get app name from user
read -p "Enter your app name (must be unique): " APP_NAME

if [ -z "$APP_NAME" ]; then
    echo "❌ App name cannot be empty"
    exit 1
fi

echo "🚀 Deploying to Azure..."

# Create and deploy web app
az webapp up \
    --name "$APP_NAME" \
    --location westus2 \
    --runtime "PYTHON:3.11" \
    --sku B1

if [ $? -eq 0 ]; then
    echo "✅ Deployment successful!"
    echo ""
    echo "🌐 Your API is available at:"
    echo "   https://$APP_NAME.azurewebsites.net"
    echo "   https://$APP_NAME.azurewebsites.net/docs"
    echo ""
    echo "⚙️ Next steps:"
    echo "1. Go to Azure Portal → App Services → $APP_NAME → Configuration"
    echo "2. Add your environment variables:"
    echo "   - CLOUDINARY_CLOUD_NAME"
    echo "   - CLOUDINARY_API_KEY" 
    echo "   - CLOUDINARY_API_SECRET"
    echo "   - MONGODB_CONNECTION_STRING"
    echo "3. Set Startup Command to: python main.py"
    echo "4. Restart the app"
else
    echo "❌ Deployment failed. Please check the error above."
fi
