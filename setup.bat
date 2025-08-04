@echo off
REM PSD Converter Backend Setup Script for Windows
REM This batch file provides an alternative to the bash script for pure Windows environments

echo ======================================
echo   PSD Converter Backend Setup
echo ======================================
echo.

REM Check if Python is installed
echo [INFO] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo [ERROR] Please install Python 3.8+ from https://python.org/downloads/
    pause
    exit /b 1
)

REM Get Python version
for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo [SUCCESS] Python %PYTHON_VERSION% found

REM Create virtual environment
echo [INFO] Creating virtual environment...
if exist ".venv" (
    echo [WARNING] Virtual environment already exists. Removing old one...
    rmdir /s /q .venv
)

python -m venv .venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment
    pause
    exit /b 1
)
echo [SUCCESS] Virtual environment created successfully

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)
echo [SUCCESS] Virtual environment activated

REM Upgrade pip
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo [WARNING] Failed to upgrade pip, continuing anyway...
) else (
    echo [SUCCESS] Pip upgraded successfully
)

REM Install dependencies
echo [INFO] Installing Python dependencies...
if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found!
    pause
    exit /b 1
)

pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo [SUCCESS] Dependencies installed successfully

REM Setup environment variables
echo [INFO] Setting up environment variables...
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo [SUCCESS] Created .env file from .env.example
        echo [WARNING] Please review and update .env file with your configurations
    ) else (
        echo [WARNING] .env.example not found, creating basic .env file
        (
            echo # Basic Configuration
            echo PORT=8000
            echo PRODUCTION=false
            echo MAX_UPLOAD_SIZE_MB=1024
            echo MAX_WORKERS=4
            echo TASK_TIMEOUT=300
            echo.
            echo # Optional: Add your Cloudinary credentials here
            echo # CLOUDINARY_CLOUD_NAME=your_cloud_name
            echo # CLOUDINARY_API_KEY=your_api_key
            echo # CLOUDINARY_API_SECRET=your_api_secret
            echo.
            echo # Optional: Add your MongoDB connection here
            echo # MONGODB_URL=mongodb://localhost:27017
            echo # MONGODB_DATABASE=converter_db
        ) > .env
        echo [SUCCESS] Created basic .env file
    )
) else (
    echo [SUCCESS] .env file already exists
)

REM Create storage directories
echo [INFO] Creating storage directories...
if not exist "storage" mkdir storage
if not exist "storage\downloads" mkdir storage\downloads
if not exist "storage\jobs" mkdir storage\jobs
if not exist "storage\metadata" mkdir storage\metadata

REM Create .gitkeep files
echo. > storage\downloads\.gitkeep
echo. > storage\jobs\.gitkeep
echo. > storage\metadata\.gitkeep

echo [SUCCESS] Storage directories created

echo [SUCCESS] Setup completed successfully!
echo.

REM Check if user wants to start the server
set /p START_SERVER="Do you want to start the development server now? (y/n): "
if /i "%START_SERVER%"=="y" (
    echo [INFO] Starting the development server...
    echo [INFO] Server will be available at: http://localhost:8000
    echo [INFO] API documentation will be at: http://localhost:8000/docs
    echo.
    echo [WARNING] Press Ctrl+C to stop the server
    echo.
    timeout /t 2 /nobreak >nul
    python main.py
) else (
    echo [INFO] Setup complete. To start the server manually, run:
    echo.
    echo   .venv\Scripts\activate.bat
    echo   python main.py
    echo.
    echo Or simply run: setup.bat
)

pause
