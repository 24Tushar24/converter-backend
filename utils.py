"""
Utility functions for the PSD converter backend.
Includes logging, file operations, hashing, and helper functions.
"""

import os
import shutil
import hashlib
import uuid
import tempfile
import logging
from pathlib import Path
from typing import Optional, Any
import aiofiles
from datetime import datetime


def setup_logging(level: str = "INFO") -> None:
    """
    Setup logging configuration for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    import os
    
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Check if production mode
    is_production = os.getenv("PRODUCTION", "false").lower() == "true"
    
    # In production, use WARNING level and no file logging to reduce noise
    if is_production:
        logging.basicConfig(
            level=logging.WARNING,
            format=log_format,
            handlers=[logging.StreamHandler()]
        )
    else:
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format=log_format,
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler("psd_converter.log")
            ]
        )
    
    # Reduce verbosity of third-party loggers
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def generate_job_id(prefix: str = "job") -> str:
    """
    Generate a unique job ID.
    
    Args:
        prefix: Optional prefix for the job ID (default: "job")
    
    Returns:
        Unique job identifier string
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return f"{prefix}_{timestamp}_{unique_id}"


def get_file_hash(file_path: str, algorithm: str = "sha256") -> str:
    """
    Calculate hash of a file.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm (md5, sha1, sha256)
        
    Returns:
        Hexadecimal hash string
    """
    hash_func = hashlib.new(algorithm)
    
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        
        return hash_func.hexdigest()
    except Exception as e:
        logging.error(f"Error calculating hash for {file_path}: {str(e)}")
        return ""


def ensure_directory(directory_path: str) -> None:
    """
    Ensure a directory exists, create if it doesn't.
    
    Args:
        directory_path: Path to the directory
    """
    try:
        Path(directory_path).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logging.error(f"Error creating directory {directory_path}: {str(e)}")
        raise


def cleanup_directory(directory_path: str) -> bool:
    """
    Remove a directory and all its contents.
    
    Args:
        directory_path: Path to directory to remove
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if os.path.exists(directory_path):
            shutil.rmtree(directory_path)
            logging.debug(f"Cleaned up directory: {directory_path}")
            return True
        return True
    except Exception as e:
        logging.error(f"Error cleaning up directory {directory_path}: {str(e)}")
        return False


async def save_file_from_upload(upload_file, destination_path: Optional[str] = None) -> str:
    """
    Save an uploaded file to disk asynchronously.
    
    Args:
        upload_file: FastAPI UploadFile object
        destination_path: Optional path to save file to
        
    Returns:
        Path to saved file
    """
    if destination_path is None:
        # Create temporary file
        suffix = f".{upload_file.filename.split('.')[-1]}"
        fd, destination_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
    
    try:
        # Ensure destination directory exists
        ensure_directory(os.path.dirname(destination_path))
        
        # Save file content
        async with aiofiles.open(destination_path, 'wb') as f:
            # Reset file pointer to beginning
            await upload_file.seek(0)
            content = await upload_file.read()
            await f.write(content)
        
        logging.debug(f"Saved uploaded file to: {destination_path}")
        return destination_path
        
    except Exception as e:
        logging.error(f"Error saving uploaded file: {str(e)}")
        # Clean up partial file
        if os.path.exists(destination_path):
            os.unlink(destination_path)
        raise


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"


def validate_file_extension(filename: str, allowed_extensions: list) -> bool:
    """
    Validate if file has an allowed extension.
    
    Args:
        filename: Name of the file
        allowed_extensions: List of allowed extensions (without dots)
        
    Returns:
        True if extension is allowed, False otherwise
    """
    if not filename:
        return False
    
    file_extension = filename.lower().split('.')[-1]
    return file_extension in [ext.lower() for ext in allowed_extensions]


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing/replacing invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove leading/trailing spaces and dots
    filename = filename.strip(' .')
    
    # Ensure filename is not empty
    if not filename:
        filename = "untitled"
    
    return filename


def get_temp_directory(prefix: str = "psd_converter_") -> str:
    """
    Create a temporary directory.
    
    Args:
        prefix: Prefix for the temporary directory name
        
    Returns:
        Path to created temporary directory
    """
    return tempfile.mkdtemp(prefix=prefix)


def is_safe_path(base_path: str, target_path: str) -> bool:
    """
    Check if target_path is safely within base_path (prevent directory traversal).
    
    Args:
        base_path: Base directory path
        target_path: Target file/directory path
        
    Returns:
        True if path is safe, False otherwise
    """
    try:
        base_path = os.path.abspath(base_path)
        target_path = os.path.abspath(target_path)
        
        # Check if target_path starts with base_path
        return target_path.startswith(base_path + os.sep) or target_path == base_path
    except Exception:
        return False


def get_available_disk_space(path: str) -> int:
    """
    Get available disk space for a given path.
    
    Args:
        path: Path to check
        
    Returns:
        Available space in bytes
    """
    try:
        statvfs = os.statvfs(path)
        return statvfs.f_frsize * statvfs.f_availav
    except Exception as e:
        logging.error(f"Error getting disk space for {path}: {str(e)}")
        return 0


def create_error_response(error_message: str, status_code: int = 500) -> dict:
    """
    Create a standardized error response.
    
    Args:
        error_message: Error message
        status_code: HTTP status code
        
    Returns:
        Error response dictionary
    """
    return {
        "error": True,
        "message": error_message,
        "status_code": status_code,
        "timestamp": datetime.now().isoformat()
    }


def create_success_response(data: Any, message: str = "Success") -> dict:
    """
    Create a standardized success response.
    
    Args:
        data: Response data
        message: Success message
        
    Returns:
        Success response dictionary
    """
    return {
        "success": True,
        "message": message,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }


class ProgressTracker:
    """Simple progress tracking utility."""
    
    def __init__(self, total: int):
        self.total = total
        self.current = 0
        self.start_time = datetime.now()
    
    def update(self, increment: int = 1) -> dict:
        """Update progress and return current status."""
        self.current = min(self.current + increment, self.total)
        
        progress_percent = (self.current / self.total) * 100 if self.total > 0 else 0
        elapsed_time = (datetime.now() - self.start_time).total_seconds()
        
        if progress_percent > 0:
            estimated_total_time = elapsed_time / (progress_percent / 100)
            remaining_time = estimated_total_time - elapsed_time
        else:
            remaining_time = 0
        
        return {
            "current": self.current,
            "total": self.total,
            "percentage": round(progress_percent, 2),
            "elapsed_seconds": round(elapsed_time, 2),
            "remaining_seconds": round(remaining_time, 2)
        }
    
    def is_complete(self) -> bool:
        """Check if progress is complete."""
        return self.current >= self.total


def log_performance(func_name: str, start_time: datetime, end_time: datetime = None) -> None:
    """
    Log performance metrics for a function.
    
    Args:
        func_name: Name of the function
        start_time: Function start time
        end_time: Function end time (defaults to now)
    """
    if end_time is None:
        end_time = datetime.now()
    
    duration = (end_time - start_time).total_seconds()
    logging.info(f"Performance: {func_name} took {duration:.3f} seconds")


# Environment variable helpers
def get_env_var(var_name: str, default_value: Any = None, var_type: type = str) -> Any:
    """
    Get environment variable with type conversion and default value.
    
    Args:
        var_name: Environment variable name
        default_value: Default value if not found
        var_type: Type to convert to (str, int, float, bool)
        
    Returns:
        Environment variable value or default
    """
    value = os.getenv(var_name)
    
    if value is None:
        return default_value
    
    try:
        if var_type == bool:
            return value.lower() in ('true', '1', 'yes', 'on')
        elif var_type == int:
            return int(value)
        elif var_type == float:
            return float(value)
        else:
            return str(value)
    except (ValueError, TypeError):
        logging.warning(f"Could not convert env var {var_name}={value} to {var_type}, using default")
        return default_value
