# Azure Deployment Troubleshooting Guide

## Current Issue: Package deployment using ZIP Deploy failed

### Problem Analysis:

The deployment is failing during the pip install phase in Azure. This is common with Python packages that have native dependencies.

### Solutions to Try:

## Solution 1: Fix GitHub Actions Workflow (RECOMMENDED)

The updated `.github/workflows/main_converter.yml` now includes:

- Proper virtual environment activation across steps
- Upgraded pip and build tools
- Package verification
- Better error handling

## Solution 2: Test with Minimal Requirements

If the deployment continues to fail, temporarily use `requirements-minimal.txt`:

```bash
# In your GitHub Actions workflow, change:
pip install -r requirements.txt
# To:
pip install -r requirements-minimal.txt
```

This will help identify if specific packages are causing the issue.

## Solution 3: Alternative Deployment Method

### Option A: Manual Deployment via Azure CLI

```bash
# From your local machine
az login
az webapp deployment source config-zip --resource-group your-resource-group --name converter --src deployment.zip
```

### Option B: Deploy from VS Code

1. Install Azure App Service extension
2. Right-click your project folder
3. Select "Deploy to Web App"

## Solution 4: Check Azure App Service Configuration

1. **Ensure correct Python version:**

   - Go to Azure Portal → Your App Service → Configuration → General Settings
   - Set Python version to 3.12

2. **Check startup command:**

   - Startup Command: `python startup.py`

3. **Verify environment variables are set**

## Solution 5: Debug Package Installation

If specific packages fail, check their requirements:

### PSD Tools Issue:

- Requires system libraries that might not be available in Azure
- Solution: Use alternative or build wheels

### Pillow Issues:

- Common on Linux systems
- Solution: Ensure correct Pillow version

### Cloudinary/PyMongo:

- Usually work fine but check network connectivity

## Quick Fix Steps:

1. **Commit the updated GitHub Actions workflow**
2. **Push to trigger deployment**
3. **If it fails, try minimal requirements**
4. **Check Azure deployment logs for specific error**

## Monitoring Deployment:

### GitHub Actions:

- Go to your repo → Actions tab
- Click on latest workflow run
- Check each step for errors

### Azure Logs:

- Azure Portal → Your App Service → Deployment Center
- Check deployment logs
- Look for specific pip install errors

## Expected Success Messages:

### In GitHub Actions:

```
✅ Core packages installed
✅ Service packages installed
✅ PSD tools installed
✅ App creation successful
```

### In Azure Logs:

```
Successfully installed fastapi-0.104.1 uvicorn-0.24.0 ...
Deployment successful
```

## If All Else Fails:

1. **Simplify the application** - Remove complex dependencies temporarily
2. **Use Docker deployment** instead of ZIP deploy
3. **Contact Azure support** with specific error logs

## Next Steps:

1. Push the updated code to trigger new deployment
2. Monitor GitHub Actions for the enhanced build process
3. Check if packages install successfully
4. Verify Azure startup logs show proper initialization
