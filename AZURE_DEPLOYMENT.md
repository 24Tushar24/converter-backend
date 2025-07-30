# Azure Deployment Guide for PSD Converter Backend

## Overview

This guide will help you deploy the PSD Converter Backend to Azure App Service successfully.

## Prerequisites

- Azure subscription
- Azure App Service created
- Repository pushed to GitHub

## Step 1: Update Azure App Service Configuration

### General Settings

1. Go to your Azure App Service in the portal
2. Navigate to **Settings** → **Configuration**
3. Update the following settings:

**Stack Settings:**

- Stack: `Python`
- Major version: `Python 3`
- Minor version: `Python 3.12`

**Startup Command:**

```bash
python startup.py
```

### Application Settings (Environment Variables)

Add the following environment variables in **Configuration** → **Application Settings**:

```bash
# Cloudinary Configuration
CLOUDINARY_CLOUD_NAME=dg1dpoysz
CLOUDINARY_API_KEY=643713745468581
CLOUDINARY_API_SECRET=BK1pqUHdR0cwjmReAB_h18LAjIs

# MongoDB Configuration
MONGODB_CONNECTION_STRING=mongodb+srv://harshkardile10:BSkyKgUyeGrjtBnX@cluster0.ltbingj.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
MONGODB_DATABASE=psd_converter
MONGODB_COLLECTION=product_images

# Application Configuration
MAX_UPLOAD_SIZE_MB=500
CLEANUP_HOURS=24
MAX_WORKERS=4
CONCURRENCY_MODE=threading
TASK_TIMEOUT=300
QUEUE_SIZE=100
BATCH_SIZE=5
ENABLE_MONITORING=true

# Build Configuration (Important for Azure)
SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

## Step 2: Deployment Options

### Option A: GitHub Actions (Recommended)

The existing GitHub Actions workflow should work with the updated configuration.

### Option B: Manual Deployment

1. Zip your project files
2. Use Azure CLI or portal to deploy

### Option C: VS Code Extension

Use the Azure App Service extension in VS Code for direct deployment.

## Step 3: File Structure Verification

Ensure these files are in your repository:

```
├── main.py                 # Main FastAPI application
├── startup.py              # Azure startup script
├── requirements.txt        # Python dependencies
├── runtime.txt            # Python version specification
├── Procfile               # Process definition
├── startup.sh             # Alternative startup script
├── .env                   # Environment variables (for local)
├── converter.py           # PSD conversion logic
├── image_storage.py       # Cloudinary & MongoDB integration
├── utils.py               # Utility functions
└── storage/               # Local storage directory
```

## Step 4: Testing Deployment

### Check Application Logs

1. Go to **Monitoring** → **Log stream** in Azure portal
2. Look for successful startup messages:
   ```
   PSD Converter Backend starting up...
   Image storage service (Cloudinary + MongoDB) initialized
   Application startup complete.
   ```

### Test Endpoints

Once deployed, test these endpoints:

- `GET /` - Health check
- `GET /docs` - Swagger documentation
- `GET /product-types` - Available product types

## Step 5: Common Issues and Solutions

### Issue 1: ModuleNotFoundError

**Solution:** Ensure `requirements.txt` includes all dependencies and `SCM_DO_BUILD_DURING_DEPLOYMENT=true` is set.

### Issue 2: Environment Variables Not Found

**Solution:** Verify all required environment variables are set in Azure App Service Configuration.

### Issue 3: MongoDB Connection Timeout

**Solution:**

- Check MongoDB connection string format
- Ensure MongoDB Atlas allows connections from Azure IP ranges
- Verify database credentials

### Issue 4: Cloudinary Upload Errors

**Solution:**

- Verify Cloudinary credentials
- Check upload folder permissions
- Ensure API limits aren't exceeded

### Issue 5: Application Keeps Restarting

**Symptoms:** Continuous startup/shutdown cycles in logs
**Solutions:**

- Check for unhandled exceptions in startup code
- Verify all required environment variables
- Check file permissions and disk space

## Step 6: Monitoring and Maintenance

### Enable Application Insights

1. Go to **Settings** → **Application Insights**
2. Enable insights for detailed monitoring

### Set Up Alerts

Configure alerts for:

- Application downtime
- High error rates
- Resource usage

### Log Management

- Use Azure Log Analytics for advanced log querying
- Set log retention policies

## Step 7: Performance Optimization

### Scale Settings

- Configure auto-scaling based on CPU/memory usage
- Set minimum and maximum instance counts

### CDN Integration

- Consider Azure CDN for static assets
- Use Cloudinary's CDN capabilities

## Troubleshooting Commands

### Check Application Status

```bash
# Check if the app is running
curl https://your-app-name.azurewebsites.net/

# Check health endpoint
curl https://your-app-name.azurewebsites.net/health
```

### Azure CLI Commands

```bash
# Stream logs
az webapp log tail --name your-app-name --resource-group your-resource-group

# Restart app
az webapp restart --name your-app-name --resource-group your-resource-group

# Check app settings
az webapp config appsettings list --name your-app-name --resource-group your-resource-group
```

## Security Considerations

1. **Environment Variables**: Never commit sensitive credentials to the repository
2. **CORS**: Configure CORS properly for production
3. **HTTPS**: Ensure SSL/TLS is enabled
4. **API Keys**: Rotate API keys regularly
5. **Database Security**: Use strong passwords and connection encryption

## Success Indicators

Your deployment is successful when you see:

1. No errors in the Application logs
2. Health endpoint responds with 200 OK
3. Swagger documentation loads at `/docs`
4. File upload functionality works
5. MongoDB and Cloudinary integrations function properly
