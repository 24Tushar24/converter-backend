"""
Simplified FastAPI application for PSD to JPEG converter backend.
Only includes essential product management endpoints.
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import time
from typing import Optional, List, Union
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
MAX_FILE_SIZE = get_env_var("MAX_UPLOAD_SIZE_MB", 1024, int) * 1024 * 1024  # Convert MB to bytes
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
    allow_origins=[
        "https://taponnrender.vercel.app",  
        "http://localhost:3000",            
    ],
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
        "workflow": "PSD → JPEG → Cloudinary → MongoDB",
        "features": {
            "single_file_upload": True,
            "batch_upload": True,
            "dynamic_product_types": True,
            "job_tracking": True
        },
        "endpoints": {
            "upload": "/product/upload (supports single and multiple files)",
            "job_status": "/job/status/{job_id}",
            "list_jobs": "/jobs",
            "product_types": "/product-types",
            "manage_folders": "/folders"
        }
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
    files: List[UploadFile] = File(default=[]),
    product_type: Optional[str] = Form(None),
    quality: Optional[int] = Form(75),
    format: Optional[str] = Form("jpeg")
):
    """
    Upload PSD file(s), convert to JPEG, upload to Cloudinary, and save metadata to MongoDB.
    
    Supports both single file and multiple file uploads in the same endpoint.
    
    Simple Workflow:
    1. Upload PSD file(s)
    2. Convert each to optimized JPEG
    3. Upload JPEG(s) to Cloudinary
    4. Save metadata to MongoDB
    
    Args:
        files: Single PSD file or list of PSD files to upload
        product_type: Type of product - "metal_cards", "nfc_cards", or "standees" (default: "metal_cards")
        quality: JPEG quality (1-100, default: 75)
        format: Output format (jpeg recommended for Cloudinary)
    
    Returns:
        Job ID and product information (single file) or batch job information (multiple files)
        
    Usage:
        Single file: Send 'files' as a single file
        Multiple files: Send 'files' as multiple files with the same field name
    """
    try:
        # Validate that we have valid files
        if not files or len(files) == 0:
            raise HTTPException(
                status_code=400, 
                detail="No files provided. Please include 'files' field in your multipart form data."
            )
        
        # Apply fallbacks for missing parameters
        if product_type is None or product_type.strip() == "":
            product_type = DEFAULT_PRODUCT_TYPE  # Fallback to "metal_cards"
            logger.info(f"Product type not provided, using fallback: {product_type}")
        
        if quality is None:
            quality = 75
            logger.info(f"Quality not provided, using default: {quality}")
            
        if format is None or format.strip() == "":
            format = "jpeg"
            logger.info(f"Format not provided, using default: {format}")
        
        # Files is already a list
        file_list = files
        is_batch = len(file_list) > 1
        
        # Debug log to verify received parameters
        logger.info(f"Upload request received - product_type: {product_type}, file_count: {len(file_list)}, quality: {quality}, format: {format}")
        logger.info(f"Files: {[f.filename if f and f.filename else 'None' for f in file_list]}")
        
        # Validate that we have valid files
        if any(f is None for f in file_list):
            raise HTTPException(
                status_code=400, 
                detail="No valid files provided. Please include at least one file in the 'files' field."
            )
        
        # Validate each file
        total_size = 0
        for file in file_list:
            if not file.filename:
                raise HTTPException(status_code=400, detail="One or more files have no filename")
            
            # Validate file type
            file_extension = file.filename.lower().split('.')[-1]
            if file_extension not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Only PSD files allowed for product uploads. File '{file.filename}' has extension: .{file_extension}"
                )
        
        # Read all files and validate total size
        file_data = []
        for file in file_list:
            content = await file.read()
            file_size = len(content)
            total_size += file_size
            
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413, 
                    detail=f"File '{file.filename}' too large: {format_file_size(file_size)}. Maximum allowed: {format_file_size(MAX_FILE_SIZE)}"
                )
            
            file_data.append({
                'filename': file.filename,
                'content': content,
                'size': file_size
            })
        
        # Validate total batch size (optional limit for batch uploads)
        max_batch_size = MAX_FILE_SIZE * 5  # Allow up to 5x single file limit for batches
        if total_size > max_batch_size:
            raise HTTPException(
                status_code=413, 
                detail=f"Total batch size too large: {format_file_size(total_size)}. Maximum allowed: {format_file_size(max_batch_size)}"
            )
        
        # Validate parameters (fallbacks already applied above)
        if not (1 <= quality <= 100):
            raise HTTPException(status_code=400, detail="Quality must be between 1 and 100")
        
        # Validate product type against allowed types (fallback already applied)
        all_product_types = get_all_product_types()
        if product_type not in all_product_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid product type '{product_type}'. Allowed types: {', '.join(all_product_types)}"
            )
        
        if is_batch:
            # Handle multiple files - create batch job
            batch_job_id = generate_job_id("batch")
            logger.info(f"Starting batch upload job {batch_job_id} for {product_type}: {len(file_list)} files")
            
            # Start batch background processing
            background_tasks.add_task(
                process_batch_product_upload,
                batch_job_id=batch_job_id,
                file_data=file_data,
                product_type=product_type,
                quality=quality,
                output_format=format
            )
            
            return JSONResponse(
                status_code=202,
                content={
                    "batch_job_id": batch_job_id,
                    "message": f"Batch product upload started for {len(file_list)} files",
                    "product_type": product_type,
                    "file_count": len(file_list),
                    "filenames": [fd['filename'] for fd in file_data],
                    "total_size": format_file_size(total_size),
                    "status": "processing",
                    "workflow": "Multiple PSD → JPEG → Cloudinary → MongoDB",
                    "is_batch": True
                }
            )
        else:
            # Handle single file - use existing logic
            file_info = file_data[0]
            job_id = generate_job_id("product")
            
            logger.info(f"Starting single product upload job {job_id} for {product_type}: {file_info['filename']}")
            
            # Start background processing
            background_tasks.add_task(
                process_product_upload,
                job_id=job_id,
                file_content=file_info['content'],
                filename=file_info['filename'],
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
                    "filename": file_info['filename'],
                    "status": "processing",
                    "workflow": "PSD → JPEG → Cloudinary → MongoDB",
                    "is_batch": False
                }
            )
        
    except HTTPException:
        # Re-raise HTTP exceptions (they have proper status codes)
        raise
    except Exception as e:
        logger.error(f"Error in product upload endpoint: {str(e)}")
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
        product_jobs[job_id].update({
            "status": "failed",
            "progress": 0.0,
            "message": f"Error: {str(e)}",
            "error": str(e)
        })


# ============================================================================
# Batch Product Processing Function
# ============================================================================

async def process_batch_product_upload(
    batch_job_id: str,
    file_data: List[dict],
    product_type: str,
    quality: int,
    output_format: str
):
    """
    Background task for processing multiple product uploads in a batch.
    
    Workflow:
    1. Process each PSD file sequentially
    2. Convert each to optimized JPEG
    3. Upload each JPEG to Cloudinary
    4. Save metadata to MongoDB
    5. Track overall batch progress
    """
    # Initialize batch job status
    product_jobs[batch_job_id] = {
        "status": "processing",
        "progress": 0.0,
        "message": f"Processing batch of {len(file_data)} files...",
        "error": None,
        "results": [],
        "completed_files": 0,
        "failed_files": 0,
        "total_files": len(file_data),
        "created_at": time.time(),
        "is_batch": True
    }
    
    try:
        logger.info(f"Processing batch upload job {batch_job_id} with {len(file_data)} files")
        
        completed_results = []
        failed_files = []
        
        for i, file_info in enumerate(file_data):
            filename = file_info['filename']
            file_content = file_info['content']
            
            try:
                # Update batch progress
                file_progress = (i / len(file_data)) * 100
                product_jobs[batch_job_id].update({
                    "progress": file_progress,
                    "message": f"Processing file {i+1}/{len(file_data)}: {filename}",
                    "current_file": filename
                })
                
                logger.info(f"Batch {batch_job_id}: Processing file {i+1}/{len(file_data)}: {filename}")
                
                # Step 1: Save uploaded file temporarily
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.psd', delete=False) as temp_psd:
                    temp_psd.write(file_content)
                    temp_psd_path = temp_psd.name
                
                try:
                    # Step 2: Convert PSD to JPEG with optimization
                    output_filename = f"{os.path.splitext(filename)[0]}.{output_format}"
                    temp_output_path = os.path.join(tempfile.gettempdir(), f"batch_{batch_job_id}_{i}_{output_filename}")
                    
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
                    storage_result = await image_storage.store_product_image(
                        image_path=temp_output_path,
                        product_type=product_type,
                        original_filename=filename
                    )
                    
                    if not storage_result.get("success"):
                        raise Exception(f"Storage failed: {storage_result.get('error')}")
                    
                    # Step 4: Collect successful result
                    file_result = {
                        "filename": filename,
                        "status": "completed",
                        "product_type": product_type,
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
                    
                    completed_results.append(file_result)
                    product_jobs[batch_job_id]["completed_files"] = len(completed_results)
                    
                    logger.info(f"Batch {batch_job_id}: File {filename} completed successfully")
                    
                finally:
                    # Clean up temporary files for this file
                    try:
                        os.unlink(temp_psd_path)
                        if os.path.exists(temp_output_path):
                            os.unlink(temp_output_path)
                    except Exception as cleanup_error:
                        logger.warning(f"Could not clean up temporary files for {filename}: {cleanup_error}")
            
            except Exception as file_error:
                # Handle individual file failure
                logger.error(f"Batch {batch_job_id}: File {filename} failed: {str(file_error)}")
                
                failed_file = {
                    "filename": filename,
                    "status": "failed",
                    "error": str(file_error)
                }
                
                failed_files.append(failed_file)
                product_jobs[batch_job_id]["failed_files"] = len(failed_files)
                
                # Continue processing other files even if one fails
                continue
        
        # Step 5: Update final batch results
        final_batch_result = {
            "batch_job_id": batch_job_id,
            "status": "completed" if len(failed_files) == 0 else "partially_completed",
            "product_type": product_type,
            "total_files": len(file_data),
            "completed_files": len(completed_results),
            "failed_files": len(failed_files),
            "completed_results": completed_results,
            "failed_results": failed_files,
            "processing_summary": {
                "total_original_size": sum([fd['size'] for fd in file_data]),
                "total_optimized_size": sum([r.get("conversion_info", {}).get("optimized_size", 0) for r in completed_results]),
                "average_compression_ratio": sum([r.get("conversion_info", {}).get("compression_ratio", 1) for r in completed_results]) / max(len(completed_results), 1),
                "format": output_format,
                "quality": quality
            }
        }
        
        success_rate = (len(completed_results) / len(file_data)) * 100
        
        product_jobs[batch_job_id].update({
            "status": "completed" if len(failed_files) == 0 else "partially_completed",
            "progress": 100.0,
            "message": f"Batch processing completed: {len(completed_results)}/{len(file_data)} files successful ({success_rate:.1f}%)",
            "results": final_batch_result
        })
        
        logger.info(f"Batch upload job {batch_job_id} completed: {len(completed_results)} successful, {len(failed_files)} failed")
        
    except Exception as e:
        logger.error(f"Batch upload job {batch_job_id} failed completely: {str(e)}")
        product_jobs[batch_job_id].update({
            "status": "failed",
            "progress": 0.0,
            "message": f"Batch processing failed: {str(e)}",
            "error": str(e)
        })


# ============================================================================
# Debug/Test Endpoints
# ============================================================================

@app.post("/debug/upload-test")
async def debug_upload_test(
    files: List[UploadFile] = File(default=[]),
    product_type: Optional[str] = Form(None),
    quality: Optional[int] = Form(None),
    format: Optional[str] = Form(None)
):
    """
    Debug endpoint to test multipart form data parsing.
    Returns what was received without processing files.
    """
    try:
        result = {
            "received_files": None,
            "received_product_type": product_type,
            "received_quality": quality,
            "received_format": format,
            "fallbacks_applied": {}
        }
        
        # Handle files (files is always a list now)
        if not files or len(files) == 0:
            result["received_files"] = "No files received"
        else:
            result["received_files"] = {
                "type": "list",
                "count": len(files),
                "filenames": [f.filename if f else "None" for f in files]
            }
        
        # Apply fallbacks and show what changed
        if product_type is None or product_type.strip() == "":
            result["fallbacks_applied"]["product_type"] = f"Applied fallback: {DEFAULT_PRODUCT_TYPE}"
            product_type = DEFAULT_PRODUCT_TYPE
        
        if quality is None:
            result["fallbacks_applied"]["quality"] = "Applied fallback: 75"
            quality = 75
            
        if format is None or format.strip() == "":
            result["fallbacks_applied"]["format"] = "Applied fallback: jpeg"
            format = "jpeg"
        
        result["final_values"] = {
            "product_type": product_type,
            "quality": quality,
            "format": format
        }
        
        return result
        
    except Exception as e:
        return {
            "error": str(e),
            "message": "Debug endpoint failed"
        }


# ============================================================================
# Job Status Endpoints
# ============================================================================

@app.get("/job/status/{job_id}")
async def get_job_status(job_id: str):
    """
    Get the status of a job (single file or batch).
    
    Args:
        job_id: Job ID or batch job ID
        
    Returns:
        Job status and results
    """
    try:
        if job_id not in product_jobs:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        job_info = product_jobs[job_id]
        
        return {
            "job_id": job_id,
            "status": job_info["status"],
            "progress": job_info["progress"],
            "message": job_info["message"],
            "is_batch": job_info.get("is_batch", False),
            "created_at": job_info["created_at"],
            "error": job_info.get("error"),
            "result": job_info.get("result"),
            "results": job_info.get("results"),  # For batch jobs
            "completed_files": job_info.get("completed_files"),
            "failed_files": job_info.get("failed_files"),
            "total_files": job_info.get("total_files"),
            "current_file": job_info.get("current_file")  # Current file being processed in batch
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs")
async def list_jobs(status: Optional[str] = None, is_batch: Optional[bool] = None):
    """
    List all jobs with optional filtering.
    
    Args:
        status: Filter by status (processing, completed, failed, partially_completed)
        is_batch: Filter by job type (True for batch jobs, False for single file jobs)
        
    Returns:
        List of jobs with their status
    """
    try:
        filtered_jobs = []
        
        for job_id, job_info in product_jobs.items():
            # Apply filters
            if status and job_info["status"] != status:
                continue
            if is_batch is not None and job_info.get("is_batch", False) != is_batch:
                continue
            
            filtered_jobs.append({
                "job_id": job_id,
                "status": job_info["status"],
                "progress": job_info["progress"],
                "message": job_info["message"],
                "is_batch": job_info.get("is_batch", False),
                "created_at": job_info["created_at"],
                "completed_files": job_info.get("completed_files"),
                "failed_files": job_info.get("failed_files"),
                "total_files": job_info.get("total_files")
            })
        
        return {
            "jobs": filtered_jobs,
            "total": len(filtered_jobs),
            "filters": {
                "status": status,
                "is_batch": is_batch
            }
        }
        
    except Exception as e:
        logger.error(f"Error listing jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    import os
    
    # Get port from environment (Azure sets this automatically)
    port = int(os.getenv("PORT", 8000))
    
    # Check if we're in production mode (Azure automatically sets this)
    is_production = os.getenv("PRODUCTION", "true").lower() == "true"
    
    # Production settings: no reload, optimized for Azure
    if is_production:
        uvicorn.run(
            "main:app", 
            host="0.0.0.0", 
            port=port, 
            reload=False,
            log_level="warning",
            workers=1
        )
    else:
        # Development settings
        uvicorn.run(
            "main:app", 
            host="0.0.0.0", 
            port=port, 
            reload=True,
            log_level="info",
            reload_excludes=["*.log", "storage/*", "__pycache__/*"]
        )
