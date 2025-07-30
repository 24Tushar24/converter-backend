# PSD Converter API Endpoints

## Quick Start

### 1. Activate Virtual Environment

```bash
# Activ**"JobInfo.__init__() got an unexpected keyword argument" error**:

- This was a code issue that has been fixed
- Restart the server if you see this error: `python main.py`

**"No files to store" error with duplicates**:

- This happens when deduplication detects files identical to previously processed ones
- Files are now kept for each job even if duplicates are detected
- Check the response for `deduplication_info` to see duplicate statusthe existing virtual environment
source .venv/bin/activate

# You should see (.venv) in your terminal prompt
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Setup Environment

```bash
cp .env.enhanced .env
# Edit .env with your configuration values
```

### 4. Start the Server

```bash
# Method 1: Direct Python execution (recommended for development)
python main.py

# Method 2: Using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Method 3: Production mode (no auto-reload)
uvicorn main:app --host 0.0.0.0 --port 8000
```

The server will start on `http://127.0.0.1:8000` with auto-reload enabled in development mode.

### 5. Verify Server is Running

```bash
# Check health endpoint
curl http://127.0.0.1:8000/health

# Or open in browser
# http://127.0.0.1:8000/docs (Swagger UI)
# http://127.0.0.1:8000/redoc (ReDoc)
```

## Troubleshooting

### Common Issues

#### "ModuleNotFoundError: No module named 'fastapi'"

Make sure you have activated the virtual environment:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

#### Virtual Environment Not Found

If `.venv` doesn't exist, create it:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Port Already in Use

If port 8000 is busy, use a different port:

```bash
python main.py  # Uses port 8000 by default
# or
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

#### Upload Errors

**"Field required" error for file field**:

- Ensure the form field is named exactly `file` (not `psd`, `upload`, etc.)
- In Postman: Use `form-data` body type and set field type to "File"
- In cURL: Use `-F "file=@yourfile.psd"`

**422 Unprocessable Entity**:

- Check that the uploaded file is a valid PSD file
- Verify file size is under the limit (500MB default)
- Ensure file is not corrupted

**"JobInfo.**init**() got an unexpected keyword argument" error**:

- This was a code issue that has been fixed
- Restart the server if you see this error: `python main.py`

## Base URL

```
http://127.0.0.1:8000
```

## Product Management API

### Get Supported Product Types

```
GET /product-types
```

Returns the list of supported product types and their descriptions.

## Dynamic Folder Management

### Create Product Folder

```
POST /folders
Content-Type: application/json

Body:
{
  "name": "Stickers",
  "description": "Custom printed stickers" (optional)
}
```

Creates a new product type folder. The folder name "Stickers" will create product type "stickers".

### List All Folders

```
GET /folders
```

Lists all product type folders (base + dynamic) with their sources and deletion permissions.

### Delete Product Folder

```
DELETE /folders/{product_type}
```

Deletes a dynamic product type folder. Base types (metal_cards, nfc_cards, standees) cannot be deleted.

### Upload PSD File and Convert to Product

```
POST /product/upload
Content-Type: multipart/form-data

Form Data:
- file: PSD file (required) - Must be named exactly "file"
- product_type: Product type - any available type from /folders or /product-types (optional, default: "metal_cards")
- quality: Image quality 1-100 (optional, default: 75)
- format: Output format - "jpeg" (optional, default: "jpeg")
```

**Simple Workflow**: PSD → JPEG conversion → Cloudinary upload → MongoDB storage

### List All Products

```
GET /products
```

Lists all stored products from MongoDB.

### Delete Product

```
DELETE /products/{document_id}
```

Deletes a product from both Cloudinary and MongoDB using the document ID.

## Testing Examples

### Postman Testing Guide

#### Get Product Types

1. **Set Request Type**: GET
2. **URL**: `http://127.0.0.1:8000/product-types`
3. **No body needed**

#### Create Product Folder

1. **Set Request Type**: POST
2. **URL**: `http://127.0.0.1:8000/folders`
3. **Headers**: `Content-Type: application/json`
4. **Body**: Select `raw` and `JSON`
5. **Add JSON Body**:

```json
{
  "name": "Stickers",
  "description": "Custom printed stickers"
}
```

#### List All Folders

1. **Set Request Type**: GET
2. **URL**: `http://127.0.0.1:8000/folders`
3. **No body needed**

#### Delete Product Folder

1. **Set Request Type**: DELETE
2. **URL**: `http://127.0.0.1:8000/folders/stickers`
3. **No body needed**

#### Upload PSD File

1. **Set Request Type**: POST
2. **URL**: `http://127.0.0.1:8000/product/upload`
3. **Headers**: Remove `Content-Type` header (Postman sets it automatically for form-data)
4. **Body**: Select `form-data`
5. **Add Form Fields**:
   - **Key**: `file` (Type: File) - **REQUIRED**
   - **Key**: `product_type` (Type: Text) - Value: `stickers` or `metal_cards` or `nfc_cards` or `standees` (optional)
   - **Key**: `quality` (Type: Text) - Value: `90` (optional)

#### List Products

1. **Set Request Type**: GET
2. **URL**: `http://127.0.0.1:8000/products`
3. **No body needed**

#### Delete Product

1. **Set Request Type**: DELETE
2. **URL**: `http://127.0.0.1:8000/products/{document_id}`
3. Replace `{document_id}` with actual MongoDB document ID
4. **No body needed**

### cURL Testing Examples

#### Get Product Types

```bash
curl "http://127.0.0.1:8000/product-types"
```

#### Create Product Folder

```bash
curl -X POST "http://127.0.0.1:8000/folders" \
  -H "Content-Type: application/json" \
  -d '{"name": "Stickers", "description": "Custom printed stickers"}'
```

#### List All Folders

```bash
curl "http://127.0.0.1:8000/folders"
```

#### Delete Product Folder

```bash
curl -X DELETE "http://127.0.0.1:8000/folders/stickers"
```

#### Upload PSD

```bash
curl -X POST "http://127.0.0.1:8000/product/upload" \
  -F "file=@your_file.psd" \
  -F "product_type=stickers" \
  -F "quality=90"
```

#### List Products

```bash
curl "http://127.0.0.1:8000/products"
```

#### Delete Product

```bash
curl -X DELETE "http://127.0.0.1:8000/products/64f1a2b3c4d5e6f7g8h9i0j1"
```

## Response Formats

### Product Types Response

```json
{
  "product_types": ["metal_cards", "nfc_cards", "standees", "stickers"],
  "base_types": ["metal_cards", "nfc_cards", "standees"],
  "dynamic_types": ["stickers"],
  "default": "metal_cards",
  "descriptions": {
    "metal_cards": "Premium metal business cards with custom designs",
    "nfc_cards": "NFC-enabled smart cards with digital connectivity",
    "standees": "Custom printed standees for events and displays"
  }
}
```

### Create Folder Response

```json
{
  "message": "Product folder created successfully",
  "folder_name": "Stickers",
  "product_type": "stickers",
  "description": "Custom printed stickers",
  "total_types": 4
}
```

### List Folders Response

```json
{
  "folders": [
    {
      "name": "Metal Cards",
      "product_type": "metal_cards",
      "source": "base",
      "can_delete": false
    },
    {
      "name": "Stickers",
      "product_type": "stickers",
      "source": "dynamic",
      "can_delete": true
    }
  ],
  "total": 4,
  "base_count": 3,
  "dynamic_count": 1
}
```

### Delete Folder Response

```json
{
  "message": "Product folder deleted successfully",
  "deleted_type": "stickers",
  "remaining_types": ["metal_cards", "nfc_cards", "standees"]
}
```

### Upload Response

```json
{
  "document_id": "64f1a2b3c4d5e6f7g8h9i0j1",
  "cloudinary_url": "https://res.cloudinary.com/your_cloud/image/upload/v123456789/product_image.jpg",
  "product_type": "metal_cards",
  "message": "File converted and uploaded successfully"
}
```

### List Products Response

```json
{
  "products": [
    {
      "_id": "64f1a2b3c4d5e6f7g8h9i0j1",
      "filename": "business_card_design.psd",
      "product_type": "metal_cards",
      "cloudinary_url": "https://res.cloudinary.com/...",
      "upload_timestamp": "2025-07-30T16:17:58Z"
    }
  ],
  "total": 1
}
```

### Delete Response

```json
{
  "message": "Product deleted successfully",
  "document_id": "64f1a2b3c4d5e6f7g8h9i0j1"
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
