# PSD Converter Backend

A FastAPI-based service for converting PSD files to compressed images.

## 🚀 Quick Start

### 1. One-Command Setup & Run

```bash
# Setup everything (first time only)
./setup.sh

# Run the server locally
./run.sh

# Deploy to Azure (optional)
./deploy-azure.sh
```

### 2. Manual Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python main.py
```

### 3. Access API

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/

## 🔧 Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn main:app --reload --port 8000
```

### Production

```bash
# Run production server
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 📋 API Endpoints

### Upload PSD File

```
POST /product/upload
```

- Upload PSD file with product type and quality settings
- Returns job ID for tracking conversion progress

### Get Products

```
GET /products
```

- List all converted products with pagination

### Get Folders

```
GET /folders
```

- List all product type folders

### Delete Product

```
DELETE /products/{id}
```

- Remove a specific product

## ☁️ Azure Deployment

### Quick Azure Deploy

```bash
# 1. Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# 2. Login to Azure
az login

# 3. Create Web App (replace with your unique name)
az webapp up --name your-converter-app --location westus2 --runtime "PYTHON:3.11"
```

### Environment Variables in Azure

Set these in Azure Portal → App Services → Configuration:

```bash
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
MONGODB_CONNECTION_STRING=your_mongodb_connection
```

### Azure Startup Command

In Azure Portal → Configuration → General Settings → Startup Command:

```bash
python main.py
```

Your API will be available at: `https://your-converter-app.azurewebsites.net/docs`

## 🔧 Environment Setup

Create a `.env` file with:

```bash
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
MONGODB_CONNECTION_STRING=your_mongodb_connection
```

## 📁 Project Structure

```
converter backend/
├── main.py              # FastAPI application
├── converter.py         # PSD conversion logic
├── image_storage.py     # Image storage service
├── deduplication.py     # Duplicate detection
├── utils.py            # Helper functions
├── storage.py          # File management
├── zip_handler.py      # ZIP file processing
├── requirements.txt    # Dependencies
├── setup.sh           # One-command setup
├── run.sh             # One-command run
└── README.md          # This file
```

That's it! Simple and clean. 🚀
