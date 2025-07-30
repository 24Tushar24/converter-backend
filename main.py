"""
Simplified FastAPI application for PSD to JPEG converter backend.
Only includes essential product management endpoints.
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import time
from typing import Optional
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from converter import PSDConverter
from image_storage import ImageStorageService
from utils import setup_logging, generate_job_id, get_env_var, format_file_size

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize services
converter = PSDConverter()
image_storage = ImageStorageService()

# Configuration
MAX_FILE_SIZE = get_env_var("MAX_UPLOAD_SIZE_MB", 500, int) * 1024 * 1024  # Convert MB to bytes
ALLOWED_EXTENSIONS = ['psd']

# Base product types - always available
BASE_PRODUCT_TYPES = ['metal_cards', 'nfc_cards', 'standees']
DEFAULT_PRODUCT_TYPE = 'metal_cards'

# Dynamic product types storage - loaded from file/database
DYNAMIC_PRODUCT_TYPES = []
PRODUCT_TYPES_FILE = "product_types.json"

# Global job tracking for product uploads
product_jobs = {}


def load_dynamic_product_types():
    """Load dynamic product types from file."""
    global DYNAMIC_PRODUCT_TYPES
    try:
        if os.path.exists(PRODUCT_TYPES_FILE):
            import json
            with open(PRODUCT_TYPES_FILE, 'r') as f:
                data = json.load(f)
                DYNAMIC_PRODUCT_TYPES = data.get('dynamic_types', [])
                logger.info(f"Loaded {len(DYNAMIC_PRODUCT_TYPES)} dynamic product types")
        else:
            DYNAMIC_PRODUCT_TYPES = []
            logger.info("No dynamic product types file found, starting with base types only")
    except Exception as e:
        logger.error(f"Error loading dynamic product types: {e}")
        DYNAMIC_PRODUCT_TYPES = []


def save_dynamic_product_types():
    """Save dynamic product types to file."""
    try:
        import json
        data = {
            'dynamic_types': DYNAMIC_PRODUCT_TYPES,
            'last_updated': time.time()
        }
        with open(PRODUCT_TYPES_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved {len(DYNAMIC_PRODUCT_TYPES)} dynamic product types")
    except Exception as e:
        logger.error(f"Error saving dynamic product types: {e}")


def get_all_product_types():
    """Get all available product types (base + dynamic)."""
    return BASE_PRODUCT_TYPES + DYNAMIC_PRODUCT_TYPES


def normalize_product_type(name):
    """Normalize product type name to lowercase with underscores."""
    import re
    # Convert to lowercase and replace spaces/special chars with underscores
    normalized = re.sub(r'[^a-zA-Z0-9]+', '_', name.lower().strip())
    # Remove leading/trailing underscores and multiple consecutive underscores
    normalized = re.sub(r'^_+|_+$', '', normalized)
    normalized = re.sub(r'_+', '_', normalized)
    return normalized


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    logger.info("PSD Converter Backend starting up...")
    
    # Load dynamic product types
    load_dynamic_product_types()
    logger.info(f"Total product types available: {len(get_all_product_types())} (Base: {len(BASE_PRODUCT_TYPES)}, Dynamic: {len(DYNAMIC_PRODUCT_TYPES)})")
    
    # Initialize image storage service
    try:
        await image_storage.initialize()
        logger.info("Image storage service (Cloudinary + MongoDB) initialized")
    except Exception as e:
        logger.warning(f"Image storage service initialization failed: {e}")
        logger.warning("Product upload features may not work properly")
    
    yield
    
    # Shutdown
    logger.info("PSD Converter Backend shutting down...")
    await image_storage.shutdown()
    logger.info("All services shutdown complete")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="PSD Converter Backend - Simplified",
    description="Convert PSD files to JPEG and store in Cloudinary + MongoDB",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "PSD Converter Backend is running",
        "supported_products": get_all_product_types(),
        "default_product": DEFAULT_PRODUCT_TYPE,
        "workflow": "PSD → JPEG → Cloudinary → MongoDB"
    }


@app.get("/health")
async def health_check():
    """Detailed health check endpoint"""
    try:
        # Check environment variables
        env_status = {
            "cloudinary_configured": bool(os.getenv("CLOUDINARY_CLOUD_NAME")),
            "mongodb_configured": bool(os.getenv("MONGODB_CONNECTION_STRING")),
        }
        
        # Check services
        services_status = {
            "image_storage_initialized": hasattr(image_storage, 'cloudinary_service'),
            "converter_initialized": hasattr(converter, 'storage_optimizer'),
        }
        
        return {
            "status": "healthy",
            "environment": env_status,
            "services": services_status,
            "product_types": get_all_product_types(),
            "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
            "allowed_extensions": ALLOWED_EXTENSIONS
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@app.get("/product-types")
async def get_product_types():
    """Get list of supported product types"""
    return {
        "product_types": get_all_product_types(),
        "base_types": BASE_PRODUCT_TYPES,
        "dynamic_types": DYNAMIC_PRODUCT_TYPES,
        "default": DEFAULT_PRODUCT_TYPE,
        "descriptions": {
            "metal_cards": "Premium metal business cards with custom designs",
            "nfc_cards": "NFC-enabled smart cards with digital connectivity",
            "standees": "Custom printed standees for events and displays"
        }
    }


# ============================================================================
# Dynamic Product Type Management API
# ============================================================================

@app.post("/folders")
async def create_product_folder(folder_data: dict):
    """
    Create a new product type folder.
    
    Args:
        folder_data: JSON with 'name' and optional 'description'
        
    Example:
        {"name": "Stickers", "description": "Custom printed stickers"}
        
    Returns:
        Created product type information
    """
    try:
        folder_name = folder_data.get('name', '').strip()
        description = folder_data.get('description', '').strip()
        
        if not folder_name:
            raise HTTPException(status_code=400, detail="Folder name is required")
        
        # Normalize the folder name to create product type
        normalized_type = normalize_product_type(folder_name)
        
        if not normalized_type:
            raise HTTPException(status_code=400, detail="Invalid folder name. Must contain alphanumeric characters")
        
        # Check if it already exists (base types or dynamic types)
        all_types = get_all_product_types()
        if normalized_type in all_types:
            raise HTTPException(status_code=400, detail=f"Product type '{normalized_type}' already exists")
        
        # Add to dynamic product types
        DYNAMIC_PRODUCT_TYPES.append(normalized_type)
        save_dynamic_product_types()
        
        logger.info(f"Created new product type: {normalized_type} (from folder: {folder_name})")
        
        return {
            "message": "Product folder created successfully",
            "folder_name": folder_name,
            "product_type": normalized_type,
            "description": description or f"Custom {folder_name.lower()}",
            "total_types": len(get_all_product_types())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating product folder: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/folders")
async def list_product_folders():
    """
    List all product type folders (base + dynamic).
    
    Returns:
        List of all available product types with their sources
    """
    try:
        return {
            "folders": [
                {
                    "name": ptype.replace('_', ' ').title(),
                    "product_type": ptype,
                    "source": "base" if ptype in BASE_PRODUCT_TYPES else "dynamic",
                    "can_delete": ptype not in BASE_PRODUCT_TYPES
                }
                for ptype in get_all_product_types()
            ],
            "total": len(get_all_product_types()),
            "base_count": len(BASE_PRODUCT_TYPES),
            "dynamic_count": len(DYNAMIC_PRODUCT_TYPES)
        }
        
    except Exception as e:
        logger.error(f"Error listing folders: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/folders/{product_type}")
async def delete_product_folder(product_type: str):
    """
    Delete a dynamic product type folder.
    
    Args:
        product_type: The product type to delete
        
    Returns:
        Deletion result
        
    Note: Base product types (metal_cards, nfc_cards, standees) cannot be deleted
    """
    try:
        if product_type in BASE_PRODUCT_TYPES:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete base product type: {product_type}"
            )
        
        if product_type not in DYNAMIC_PRODUCT_TYPES:
            raise HTTPException(
                status_code=404, 
                detail=f"Dynamic product type not found: {product_type}"
            )
        
        # Remove from dynamic types
        DYNAMIC_PRODUCT_TYPES.remove(product_type)
        save_dynamic_product_types()
        
        logger.info(f"Deleted dynamic product type: {product_type}")
        
        return {
            "message": "Product folder deleted successfully",
            "deleted_type": product_type,
            "remaining_types": get_all_product_types()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting product folder: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Product Management API - Updated for Dynamic Types
# ============================================================================

@app.post("/product/upload")
async def upload_product_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    product_type: str = DEFAULT_PRODUCT_TYPE,
    quality: Optional[int] = 75,
    format: Optional[str] = "jpeg"
):
    """
    Upload PSD file, convert to JPEG, upload to Cloudinary, and save metadata to MongoDB.
    
    Simple Workflow:
    1. Upload PSD file
    2. Convert to optimized JPEG
    3. Upload JPEG to Cloudinary
    4. Save metadata to MongoDB
    
    Args:
        file: PSD file to upload
        product_type: Type of product - "metal_cards", "nfc_cards", or "standees" (default: "metal_cards")
        quality: JPEG quality (1-100, default: 75)
        format: Output format (jpeg recommended for Cloudinary)
    
    Returns:
        Job ID and product information
    """
    try:
        # Validate file presence
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Validate file type
        file_extension = file.filename.lower().split('.')[-1]
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"Only PSD files allowed for product uploads. Got: .{file_extension}"
            )
        
        # Validate file size
        content = await file.read()
        file_size = len(content)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large: {format_file_size(file_size)}. Maximum allowed: {format_file_size(MAX_FILE_SIZE)}"
            )
        
        # Validate parameters
        if not (1 <= quality <= 100):
            raise HTTPException(status_code=400, detail="Quality must be between 1 and 100")
        
        if not product_type or len(product_type.strip()) == 0:
            raise HTTPException(status_code=400, detail="Product type is required")
        
        # Validate product type against allowed types
        all_product_types = get_all_product_types()
        if product_type not in all_product_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid product type. Allowed types: {', '.join(all_product_types)}"
            )
        
        # No need to clean product type since it's validated against allowed list
        
        # Generate job ID
        job_id = generate_job_id("product")
        
        logger.info(f"Starting product upload job {job_id} for {product_type}: {file.filename}")
        
        # Start background processing
        background_tasks.add_task(
            process_product_upload,
            job_id=job_id,
            file_content=content,
            filename=file.filename,
            product_type=product_type,
            quality=quality,
            output_format=format
        )
        
        return JSONResponse(
            status_code=202,
            content={
                "job_id": job_id,
                "message": "Product image upload started",
                "product_type": product_type,
                "filename": file.filename,
                "status": "processing",
                "workflow": "PSD → JPEG → Cloudinary → MongoDB"
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (they have proper status codes)
        raise
    except Exception as e:
        logger.error(f"Error in product upload endpoint: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error details: {repr(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/products")
async def get_products(product_type: Optional[str] = None):
    """
    Get all product images or filter by product type.
    
    Args:
        product_type: Optional filter by product type
        
    Returns:
        List of product images with metadata
    """
    try:
        products = await image_storage.get_products(product_type)
        
        return {
            "products": products,
            "count": len(products),
            "filter": product_type or "all"
        }
        
    except Exception as e:
        logger.error(f"Error getting products: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/products/{document_id}")
async def delete_product(document_id: str):
    """
    Delete a product image from both Cloudinary and MongoDB.
    
    Args:
        document_id: MongoDB document ID
        
    Returns:
        Deletion result
    """
    try:
        result = await image_storage.delete_product(document_id)
        
        if result.get("success"):
            return {
                "message": "Product deleted successfully",
                "document_id": document_id
            }
        else:
            raise HTTPException(
                status_code=404, 
                detail=result.get("error", "Product not found")
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting product: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Background Task for Product Processing
# ============================================================================

async def process_product_upload(
    job_id: str,
    file_content: bytes,
    filename: str,
    product_type: str,
    quality: int,
    output_format: str
):
    """
    Background task for processing product uploads.
    
    Workflow:
    1. Save uploaded PSD file
    2. Convert PSD to optimized JPEG
    3. Upload JPEG to Cloudinary
    4. Save metadata to MongoDB
    5. Clean up temporary files
    """
    # Initialize job status
    product_jobs[job_id] = {
        "status": "processing",
        "progress": 0.0,
        "message": "Converting PSD to JPEG...",
        "error": None,
        "result": None,
        "created_at": time.time()
    }
    
    try:
        logger.info(f"Processing product upload job {job_id}")
        
        # Update job status
        product_jobs[job_id].update({
            "status": "processing",
            "progress": 10.0,
            "message": "Converting PSD to JPEG..."
        })
        
        # Step 1: Save uploaded file temporarily
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.psd', delete=False) as temp_psd:
            temp_psd.write(file_content)
            temp_psd_path = temp_psd.name
        
        try:
            # Step 2: Convert PSD to JPEG with optimization
            logger.info(f"Converting PSD for product {product_type}")
            
            product_jobs[job_id].update({
                "progress": 30.0,
                "message": "Processing PSD conversion..."
            })
            
            output_filename = f"{os.path.splitext(filename)[0]}.{output_format}"
            temp_output_path = os.path.join(tempfile.gettempdir(), f"product_{job_id}_{output_filename}")
            
            # Use converter with storage optimization for products
            conversion_result = converter.convert_psd_to_image_optimized(
                psd_path=temp_psd_path,
                output_path=temp_output_path,
                quality=quality,
                output_format=output_format,
                quality_profile="web_optimized",  # Best for Cloudinary
                strip_metadata=True,
                generate_thumbnails=False,  # Not needed for Cloudinary
                use_case="web"
            )
            
            if not conversion_result.get('success'):
                raise Exception(f"PSD conversion failed: {conversion_result.get('error')}")
            
            # Step 3: Upload to Cloudinary and save to MongoDB
            product_jobs[job_id].update({
                "progress": 70.0,
                "message": "Uploading to Cloudinary..."
            })
            
            storage_result = await image_storage.store_product_image(
                image_path=temp_output_path,
                product_type=product_type,
                original_filename=filename
            )
            
            if not storage_result.get("success"):
                raise Exception(f"Storage failed: {storage_result.get('error')}")
            
            # Step 4: Update job with final results
            final_result = {
                "job_id": job_id,
                "status": "completed",
                "product_type": product_type,
                "original_filename": filename,
                "image_url": storage_result["image_url"],
                "document_id": storage_result["document_id"],
                "uploaded_at": storage_result["uploaded_at"],
                "conversion_info": {
                    "original_size": len(file_content),
                    "optimized_size": conversion_result.get("output_size"),
                    "compression_ratio": conversion_result.get("compression_ratio"),
                    "format": output_format,
                    "quality": quality
                }
            }
            
            product_jobs[job_id].update({
                "status": "completed",
                "progress": 100.0,
                "message": "Product image uploaded successfully",
                "result": final_result
            })
            
            logger.info(f"Product upload job {job_id} completed: {storage_result['image_url']}")
            
        finally:
            # Clean up temporary files
            try:
                os.unlink(temp_psd_path)
                if os.path.exists(temp_output_path):
                    os.unlink(temp_output_path)
            except Exception as cleanup_error:
                logger.warning(f"Could not clean up temporary files: {cleanup_error}")
        
    except Exception as e:
        logger.error(f"Product upload job {job_id} failed: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error details: {repr(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        product_jobs[job_id].update({
            "status": "failed",
            "progress": 0.0,
            "message": f"Error: {str(e)}",
            "error": str(e)
        })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
