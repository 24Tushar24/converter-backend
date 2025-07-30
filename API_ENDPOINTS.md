# PSD Converter API Endpoints

## Quick Start

### 1. Activate Virtual Environment
```bash
# Activate the existing virtual environment
source .venv/bin/activate

# You should see (.venv) in your terminal prompt
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Setup Environmentbash
cp .env.enhanced .env
# Edit .env with your configuration values
```

### 3. Start the Server

```bash
# Method 1: Direct Python execution (recommended for development)
python main.py

# Method 2: Using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Method 3: Production mode (no auto-reload)
uvicorn main:app --host 0.0.0.0 --port 8000
```

The server will start on `http://127.0.0.1:8000` with auto-reload enabled in development mode.

### 4. Verify Server is Running

```bash
# Check health endpoint
curl http://127.0.0.1:8000/health

# Or open in browser
# http://127.0.0.1:8000/docs (Swagger UI)
# http://127.0.0.1:8000/redoc (ReDoc)
```

## Base URL

```
http://127.0.0.1:8000
```

## Health Check

```
GET /health
```

Returns server status and health information.

## Upload & Convert PSD

### Upload PSD File

```
POST /upload
Content-Type: multipart/form-data

Form Data:
- file: PSD file (required)
- quality: Image quality 1-100 (optional, default: 85)
- format: Output format - jpeg/png/webp (optional, default: jpeg)
- enable_deduplication: Enable duplicate detection (optional, default: true)
```

### Get Job Status

```
GET /status/{job_id}
```

Returns the current status of a conversion job.

### List All Jobs

```
GET /jobs
```

Returns a list of all conversion jobs.

## Download Converted Files

### Download by Product ID

```
GET /download/product/{document_id}
```

Downloads the converted image using MongoDB document ID.

### Download by Job ID

```
GET /download/job/{job_id}
```

Downloads the converted image using job ID.

### Custom Download with Processing

```
POST /download/custom
Content-Type: application/json

Body:
{
    "source_type": "product" | "job",
    "source_id": "string",
    "download_options": {
        "filename": "string (optional)",
        "format": "jpeg" | "png" | "webp",
        "quality": 1-100,
        "resize": {
            "width": number,
            "height": number
        }
    }
}
```

## Storage Management

### Storage Statistics

```
GET /storage/stats
```

Returns storage usage statistics.

### Clean Old Files

```
POST /storage/cleanup
```

Cleans up old temporary files and jobs.

## Image Management (Step 11)

### Upload Image to Cloudinary

```
POST /images/upload
Content-Type: multipart/form-data

Form Data:
- file: Image file (required)
- public_id: Custom public ID (optional)
- folder: Cloudinary folder (optional)
```

### Get Image by ID

```
GET /images/{image_id}
```

Retrieves image information from MongoDB.

### List All Images

```
GET /images
```

Lists all stored images with pagination.

### Delete Image

```
DELETE /images/{image_id}
```

Deletes image from both Cloudinary and MongoDB.

## Testing Examples

### Upload and Convert PSD

```bash
curl -X POST "http://127.0.0.1:8000/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@your_file.psd" \
  -F "quality=90" \
  -F "format=jpeg"
```

### Download Converted File

```bash
curl "http://127.0.0.1:8000/download/product/6889ce60ddf14ca0aba9f7c6" \
  -o "converted_image.jpeg"
```

### Custom Download with Processing

```bash
curl -X POST "http://127.0.0.1:8000/download/custom" \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "product",
    "source_id": "6889ce60ddf14ca0aba9f7c6",
    "download_options": {
      "filename": "my-image.jpeg",
      "format": "jpeg",
      "quality": 85,
      "resize": {"width": 1920, "height": 1080}
    }
  }' \
  -o "custom_image.jpeg"
```

## Response Formats

### Success Response

```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {
    // Response data
  }
}
```

### Error Response

```json
{
  "success": false,
  "error": "Error description",
  "details": {
    // Additional error details
  }
}
```

## Environment Configuration

Copy `.env.enhanced` to `.env` and configure:

```bash
# MongoDB Configuration
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB=psd_converter

# Cloudinary Configuration
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Application Configuration
MAX_UPLOAD_SIZE_MB=500
JPEG_QUALITY=85
PNG_COMPRESSION=6
WEBP_QUALITY=85
```
