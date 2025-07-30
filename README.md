# PSD Converter Backend

A FastAPI-based service for converting PSD files to compressed JPEG/WebP/AVIF formats.

## Features

- **Single PSD Upload**: Convert individual PSD files
- **Batch ZIP Processing**: Extract and convert multiple PSD files from ZIP archives
- **Multiple Output Formats**: JPEG, WebP, and AVIF support
- **Asynchronous Processing**: Background job handling with progress tracking
- **Optimized Compression**: Configurable quality settings for minimal file sizes
- **Duplicate Detection**: Image hashing to prevent redundant storage
- **Modular Architecture**: Clean separation of concerns

## Quick Start

1. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment** (optional):

   ```bash
   cp .env.example .env
   # Edit .env with your preferred settings
   ```

3. **Run the server**:

   ```bash
   python main.py
   ```

   Or using uvicorn directly:

   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Access the API**:
   - API docs: http://localhost:8000/docs
   - Health check: http://localhost:8000/

## API Endpoints

### Upload File

```
POST /upload
```

Upload a PSD file or ZIP archive containing PSD files.

**Parameters:**

- `file`: PSD or ZIP file
- `quality` (optional): JPEG quality 1-100 (default: 75)
- `format` (optional): Output format - jpeg, webp, avif (default: jpeg)

**Response:**

```json
{
  "job_id": "job_20241230_123456_abc12345",
  "message": "File upload accepted, conversion started",
  "filename": "example.psd",
  "status": "processing"
}
```

### Check Job Status

```
GET /status/{job_id}
```

Get the current status and progress of a conversion job.

### Download Results

```
GET /download/{job_id}
```

Download converted files or get download information.

## Project Structure

```
converter backend/
├── main.py              # FastAPI application and routes
├── converter.py         # PSD to image conversion logic
├── zip_handler.py       # ZIP extraction and batch processing
├── tasks.py            # Background job management
├── storage.py          # File storage and organization
├── utils.py            # Helper functions and utilities
├── requirements.txt    # Python dependencies
├── .env.example       # Environment configuration template
└── README.md          # This file
```

## Configuration

Copy `.env.example` to `.env` and adjust settings:

- **Storage**: Configure storage paths and limits
- **Processing**: Set worker counts and file limits
- **Compression**: Default quality and format settings
- **Server**: Host, port, and debug settings

## Storage Structure

```
storage/
├── jobs/              # Individual job results
│   └── {job_id}/     # Files for specific job
├── downloads/         # ZIP archives for download
└── metadata/         # Job metadata and information
```

## Development

The codebase is organized into modular components:

- **main.py**: FastAPI app, routing, and HTTP handling
- **converter.py**: Core PSD conversion using psd-tools and Pillow
- **zip_handler.py**: ZIP file extraction and batch processing
- **tasks.py**: Async job management and progress tracking
- **storage.py**: File storage, organization, and cleanup
- **utils.py**: Shared utilities, logging, and helpers

## Performance Optimization

- **Concurrent Processing**: Multiple files processed simultaneously
- **Optimized Compression**: Quality settings balance size vs. quality
- **Progress Tracking**: Real-time job status and completion estimates
- **Background Tasks**: Non-blocking upload and conversion
- **Storage Management**: Automatic cleanup of old jobs

## Error Handling

- Comprehensive validation of uploaded files
- Graceful handling of corrupted PSD files
- Detailed error messages and logging
- Progress tracking even for failed conversions

## Supported Formats

**Input**: PSD files (single or in ZIP archives)
**Output**: JPEG, WebP, AVIF with configurable compression

## License

[Add your license information here]
