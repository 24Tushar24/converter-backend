# PSD to JPEG Converter Backend

A FastAPI-based backend service that converts PSD files to JPEG format with support for batch processing, deduplication, and cloud storage integration.

## 📋 Prerequisites

Before running this project, make sure you have the following installed:

### For Windows Users:

- **Python 3.8+** - [Download from python.org](https://www.python.org/downloads/)
- **Git** - [Download Git for Windows](https://git-scm.windows.com/)
- **Git Bash** (comes with Git) or **Windows Subsystem for Linux (WSL)**

### For Linux/Mac Users:

- **Python 3.8+**
- **Git**
- **pip** (usually comes with Python)

## 🚀 Quick Start

### Option 1: Using the Setup Script (Recommended for Windows)

1. **Clone the repository:**

   ```bash
   git clone https://github.com/harshk49/converter-backend.git
   cd converter-backend
   ```

2. **Run the setup script:**

   ```bash
   # On Windows (using Git Bash or WSL):
   bash setup.sh

   # On Linux/Mac:
   ./setup.sh
   ```

3. **The script will automatically:**
   - Create a virtual environment
   - Install all dependencies
   - Set up environment variables
   - Start the server

### Option 2: Manual Setup

1. **Clone and navigate to the project:**

   ```bash
   git clone https://github.com/harshk49/converter-backend.git
   cd converter-backend
   ```

2. **Create a virtual environment:**

   ```bash
   # Windows (Command Prompt):
   python -m venv .venv
   .venv\Scripts\activate

   # Windows (Git Bash/PowerShell):
   python -m venv .venv
   source .venv/Scripts/activate

   # Linux/Mac:
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**

   ```bash
   # Copy the example environment file
   cp .env.example .env

   # Edit .env file with your configurations (optional for basic usage)
   ```

5. **Run the server:**

   ```bash
   # Development mode (with auto-reload):
   python main.py

   # Or using uvicorn directly:
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

## 🔧 Configuration

The application uses environment variables for configuration. Copy `.env.example` to `.env` and modify as needed:

### Basic Configuration:

```bash
# Server Configuration
PORT=8000                        # Port to run the server on
PRODUCTION=false                 # Set to true for production mode

# File Processing
MAX_UPLOAD_SIZE_MB=1024         # Maximum file size in MB
MAX_WORKERS=4                   # Number of worker threads
TASK_TIMEOUT=300                # Task timeout in seconds
```

### Optional Cloud Storage (Cloudinary):

```bash
# Cloudinary Configuration (optional)
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

### Optional Database (MongoDB):

```bash
# MongoDB Configuration (optional)
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=converter_db
```

## 📁 Project Structure

```
converter-backend/
├── main.py                 # FastAPI application entry point
├── converter.py            # PSD conversion logic
├── image_storage.py        # File storage management
├── deduplication.py        # Duplicate detection logic
├── utils.py               # Utility functions
├── requirements.txt       # Python dependencies
├── runtime.txt           # Python version specification
├── .env.example          # Environment variables template
├── setup.sh              # Automated setup script
├── storage/              # Local file storage
│   ├── downloads/        # Converted files
│   ├── jobs/            # Job metadata
│   └── metadata/        # File metadata
└── README.md            # This file
```

## 🌐 API Usage

Once the server is running, you can access:

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **API Info**: http://localhost:8000/

### Key Endpoints:

1. **Upload PSD Files:**

   ```
   POST /product/upload
   ```

   - Supports single and multiple file uploads
   - Accepts PSD files up to configured size limit
   - Returns job ID for tracking conversion progress

2. **Check Job Status:**

   ```
   GET /product/job/{job_id}/status
   ```

3. **Download Converted Files:**
   ```
   GET /product/job/{job_id}/download
   ```

## 🧪 Testing

Test the API using the included test file:

```bash
# Make sure the server is running, then:
python simple_test.py
```

Or test using curl:

```bash
# Health check
curl http://localhost:8000/health

# Upload a PSD file
curl -X POST "http://localhost:8000/product/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@your_file.psd"
```

## 🐛 Troubleshooting

### Common Issues:

1. **Port already in use:**

   ```bash
   # Change port in .env file or run with different port:
   PORT=8001 python main.py
   ```

2. **Python version issues:**

   ```bash
   # Make sure you're using Python 3.8+:
   python --version
   ```

3. **Virtual environment issues on Windows:**

   ```bash
   # If activation fails, try:
   .venv\Scripts\activate.bat  # Command Prompt
   .venv\Scripts\Activate.ps1  # PowerShell
   ```

4. **Permission issues (Linux/Mac):**
   ```bash
   # Make setup script executable:
   chmod +x setup.sh
   ```

### Windows-Specific Notes:

- **Use Git Bash** for the best compatibility with shell scripts
- **Antivirus software** might interfere with virtual environment creation
- **Long path issues**: Enable long path support in Windows 10/11
- **PowerShell execution policy**: You might need to run:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```

## 📝 Development

### Adding New Features:

1. **Fork the repository**
2. **Create a feature branch**
3. **Make your changes**
4. **Test thoroughly**
5. **Submit a pull request**

### Code Style:

- Follow PEP 8 guidelines
- Use type hints where possible
- Add docstrings for functions and classes
- Keep functions focused and small

## 🔒 Security Notes

- The application includes file type validation
- File size limits are enforced
- CORS is configured for web client integration
- Environment variables should never be committed to version control

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Support

If you encounter any issues:

1. Check the troubleshooting section above
2. Review the server logs for error messages
3. Ensure all dependencies are properly installed
4. Contact the development team

## 🚀 Deployment

### Local Development:

```bash
python main.py  # Runs with auto-reload on localhost:8000
```

### Production:

```bash
PRODUCTION=true python main.py  # Optimized production settings
```

### Docker (if available):

```bash
# Build and run with Docker
docker build -t psd-converter .
docker run -p 8000:8000 psd-converter
```

---

**Happy Converting! 🎨➡️📸**
