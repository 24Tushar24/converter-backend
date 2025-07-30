#!/usr/bin/env python3
"""
Startup script for Azure App Service deployment.
This ensures proper initialization with environment variables.
"""

import os
import sys
import logging
from pathlib import Path

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main startup function for Azure deployment."""
    try:
        # Ensure we're in the correct directory
        app_dir = Path(__file__).parent.absolute()
        os.chdir(app_dir)
        logger.info(f"Changed working directory to: {app_dir}")
        
        # Log environment info
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Working directory: {os.getcwd()}")
        
        # Check if required environment variables are set
        required_vars = [
            'CLOUDINARY_CLOUD_NAME',
            'CLOUDINARY_API_KEY', 
            'CLOUDINARY_API_SECRET',
            'MONGODB_CONNECTION_STRING'
        ]
        
        missing_vars = []
        for var in required_vars:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
            else:
                # Log that variable is set (but don't log the value for security)
                logger.info(f"✅ {var} is configured")
        
        if missing_vars:
            logger.error(f"❌ Missing environment variables: {missing_vars}")
            logger.error("Application may not function properly")
            logger.error("Please check Azure App Service Configuration → Application Settings")
        else:
            logger.info("✅ All required environment variables are set")
        
        # Import and run the FastAPI app
        logger.info("Starting FastAPI application...")
        import uvicorn
        from main import app
        
        # Get port from environment or default to 8000
        port = int(os.getenv('PORT', 8000))
        host = os.getenv('HOST', '0.0.0.0')
        
        logger.info(f"Starting server on {host}:{port}")
        
        # Run the application
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=True
        )
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise

if __name__ == "__main__":
    main()
