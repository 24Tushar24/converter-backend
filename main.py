"""
FastAPI application for PSD to JPEG converter backend.
Handles file uploads and coordinates conversion ta            "download_product": "GET /download/product/{document_id}",
            "download_job": "GET /download/job/{job_id}",
            "download_custom": "POST /download/custom"s.
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import time
from typing import List, Optional
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.enhanced')

from converter import PSDConverter
from zip_handler import ZipHandler
from enhanced_tasks import EnhancedTaskManager, TaskConfig, ConcurrencyMode
from storage import StorageManager
from image_storage import ImageStorageService
from utils import setup_logging, generate_job_id, get_env_var, format_file_size

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="PSD Converter Backend",
    description="Convert PSD files to compressed JPEG format",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize managers
converter = PSDConverter()
zip_handler = ZipHandler()

# Configure enhanced task manager based on environment
task_config = TaskConfig(
    max_workers=get_env_var("MAX_WORKERS", 4, int),
    concurrency_mode=ConcurrencyMode(get_env_var("CONCURRENCY_MODE", "threading", str)),
    timeout_seconds=get_env_var("TASK_TIMEOUT", 300, int),
    queue_size=get_env_var("QUEUE_SIZE", 100, int),
    batch_size=get_env_var("BATCH_SIZE", 1, int),
    enable_monitoring=get_env_var("ENABLE_MONITORING", True, bool)
)

# Use enhanced task manager for better concurrency
task_manager = EnhancedTaskManager(task_config)
storage_manager = StorageManager()
image_storage = ImageStorageService()

# Simple job tracking for product uploads
product_jobs = {}

# Configuration settings
MAX_FILE_SIZE = get_env_var("MAX_UPLOAD_SIZE_MB", 500, int) * 1024 * 1024  # Convert MB to bytes - Increased for testing
ALLOWED_EXTENSIONS = ['psd', 'zip']


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "PSD Converter Backend is running"}


@app.get("/info")
async def get_api_info():
    """
    Get API configuration and supported file types.
    
    Returns:
        API configuration information
    """
    return {
        "title": "PSD Converter Backend",
        "version": "1.0.0",
        "max_file_size": format_file_size(MAX_FILE_SIZE),
        "supported_extensions": ALLOWED_EXTENSIONS,
        "supported_output_formats": ["jpeg", "webp", "avif"],
        "default_quality": 75,
        "concurrency": {
            "mode": task_config.concurrency_mode.value,
            "max_workers": task_config.max_workers,
            "queue_size": task_config.queue_size,
            "timeout_seconds": task_config.timeout_seconds
        },
        "endpoints": {
            "upload": "POST /upload",
            "batch_upload": "POST /batch",
            "status": "GET /status/{job_id}",
            "metrics": "GET /metrics",
            "download": "GET /download/{job_id}",
            "info": "GET /info",
            "product_upload": "POST /product/upload",
            "get_products": "GET /products",
            "get_products_by_type": "GET /products/{product_type}",
            "delete_product": "DELETE /products/{document_id}",
            "download_product": "GET /download/product/{document_id}",
            "download_job": "GET /download/job/{job_id}"
        },
        "step_11_features": {
            "cloudinary_integration": True,
            "mongodb_storage": True,
            "product_workflow": "PSD → JPEG → Cloudinary → MongoDB"
        }
    }


@app.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    quality: Optional[int] = 75,
    format: Optional[str] = "jpeg",
    optimize_storage: Optional[bool] = True,
    quality_profile: Optional[str] = "storage_optimized",
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    strip_metadata: Optional[bool] = True,
    generate_thumbnails: Optional[bool] = True,
    use_case: Optional[str] = "web",
    enable_deduplication: Optional[bool] = True
):
    """
    Upload and convert PSD files or ZIP archives containing PSD files with advanced storage optimization and deduplication.
    
    Args:
        file: Uploaded file (PSD or ZIP)
        quality: JPEG quality (1-100, default: 75)
        format: Output format (jpeg, webp, avif - default: jpeg)
        optimize_storage: Enable advanced storage optimization (default: True)
        quality_profile: Quality profile (storage_optimized, web_optimized, maximum_compression, high_quality, auto)
        max_width: Maximum output width in pixels
        max_height: Maximum output height in pixels
        strip_metadata: Remove EXIF and other metadata (default: True)
        generate_thumbnails: Create thumbnail variants (default: True)
        use_case: Optimization use case (web, archive, print - default: web)
        enable_deduplication: Enable perceptual hash deduplication (default: True)
    
    Returns:
        Job ID for tracking conversion progress
    """
    try:
        # Validate file presence
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Validate file size
        content = await file.read()
        file_size = len(content)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large: {format_file_size(file_size)}. Maximum allowed: {format_file_size(MAX_FILE_SIZE)}"
            )
        
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Empty file provided")
        
        # Generate job ID
        job_id = generate_job_id()
        
        # Validate file type
        file_extension = file.filename.lower().split('.')[-1]
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: .{file_extension}. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # Validate parameters
        if not (1 <= quality <= 100):
            raise HTTPException(
                status_code=400,
                detail="Quality must be between 1 and 100"
            )
        
        if format not in ['jpeg', 'webp', 'avif']:
            raise HTTPException(
                status_code=400,
                detail="Format must be jpeg, webp, or avif"
            )
        
        if quality_profile not in ['storage_optimized', 'web_optimized', 'maximum_compression', 'high_quality', 'auto']:
            raise HTTPException(
                status_code=400,
                detail="Invalid quality profile"
            )
        
        if use_case not in ['web', 'archive', 'print']:
            raise HTTPException(
                status_code=400,
                detail="Use case must be web, archive, or print"
            )
        
        # Validate resolution limits
        if max_width and (max_width < 100 or max_width > 16000):
            raise HTTPException(
                status_code=400,
                detail="Max width must be between 100 and 16000 pixels"
            )
        
        if max_height and (max_height < 100 or max_height > 16000):
            raise HTTPException(
                status_code=400,
                detail="Max height must be between 100 and 16000 pixels"
            )
        
        logger.info(f"Starting conversion job {job_id} for file: {file.filename}")
        logger.info(f"Optimization settings: profile={quality_profile}, optimize_storage={optimize_storage}")
        
        # Prepare optimization parameters
        max_resolution = None
        if max_width and max_height:
            max_resolution = (max_width, max_height)
        elif max_width:
            max_resolution = (max_width, 8192)  # Keep aspect ratio
        elif max_height:
            max_resolution = (8192, max_height)  # Keep aspect ratio
        
        # Start enhanced background conversion task with priority support
        # Large files get higher priority
        priority = 10 if file_size > 50 * 1024 * 1024 else 5  # >50MB gets priority 10
        
        background_tasks.add_task(
            task_manager.process_upload_enhanced,
            job_id=job_id,
            file_content=content,
            filename=file.filename,
            quality=quality,
            output_format=format,
            priority=priority,
            optimize_storage=optimize_storage,
            quality_profile=quality_profile,
            max_resolution=max_resolution,
            strip_metadata=strip_metadata,
            generate_thumbnails=generate_thumbnails,
            use_case=use_case,
            enable_deduplication=enable_deduplication
        )
        
        return JSONResponse(
            status_code=202,
            content={
                "job_id": job_id,
                "message": "File upload accepted, conversion started",
                "filename": file.filename,
                "status": "processing"
            }
        )
        
    except Exception as e:
        logger.error(f"Error in upload endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def get_system_metrics():
    """
    Get comprehensive system performance metrics.
    
    Returns:
        System metrics including task statistics and performance data
    """
    try:
        metrics = task_manager.get_system_metrics()
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting system metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/batch")
async def batch_upload(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    quality: Optional[int] = 75,
    format: Optional[str] = "jpeg"
):
    """
    Upload and convert multiple PSD files or ZIP archives in batch.
    
    Args:
        files: List of uploaded files (PSD or ZIP)
        quality: JPEG quality (1-100, default: 75)
        format: Output format (jpeg, webp, avif - default: jpeg)
    
    Returns:
        Batch job information with individual job IDs
    """
    try:
        # Validate parameters
        if not (1 <= quality <= 100):
            raise HTTPException(
                status_code=400,
                detail="Quality must be between 1 and 100"
            )
        
        if format not in ['jpeg', 'webp', 'avif']:
            raise HTTPException(
                status_code=400,
                detail="Format must be jpeg, webp, or avif"
            )
        
        # Validate files
        if len(files) > 10:  # Limit batch size
            raise HTTPException(
                status_code=400,
                detail="Maximum 10 files allowed per batch"
            )
        
        batch_id = generate_job_id("batch")
        job_items = []
        total_size = 0
        
        for file in files:
            if not file.filename:
                continue
                
            # Validate file type
            file_extension = file.filename.lower().split('.')[-1]
            if file_extension not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: .{file_extension} in {file.filename}"
                )
            
            # Read file content
            content = await file.read()
            file_size = len(content)
            total_size += file_size
            
            # Check individual file size
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"File {file.filename} too large: {format_file_size(file_size)}"
                )
            
            # Create job item for batch processing
            job_id = generate_job_id()
            job_items.append({
                'job_id': job_id,
                'file_content': content,
                'filename': file.filename,
                'quality': quality,
                'output_format': format,
                'priority': 5  # Standard priority for batch jobs
            })
        
        if not job_items:
            raise HTTPException(status_code=400, detail="No valid files provided")
        
        # Check total batch size
        if total_size > MAX_FILE_SIZE * len(files):
            raise HTTPException(
                status_code=413,
                detail=f"Batch too large: {format_file_size(total_size)}"
            )
        
        logger.info(f"Starting batch job {batch_id} with {len(job_items)} files")
        
        # Start batch processing
        background_tasks.add_task(
            task_manager.batch_process,
            job_items
        )
        
        return JSONResponse(
            status_code=202,
            content={
                "batch_id": batch_id,
                "message": "Batch upload accepted, processing started",
                "total_files": len(job_items),
                "job_ids": [item['job_id'] for item in job_items],
                "total_size": format_file_size(total_size),
                "status": "processing"
            }
        )
        
    except Exception as e:
        logger.error(f"Error in batch upload endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """
    Get the status of a conversion job.
    
    Args:
        job_id: The job ID returned from upload
        
    Returns:
        Job status and progress information
    """
    try:
        # Check if it's a product job (starts with "product_")
        if job_id.startswith("product_") and job_id in product_jobs:
            return product_jobs[job_id]
        
        # Otherwise check regular task manager
        status = task_manager.get_job_status(job_id)
        if not status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download/{job_id}")
async def download_result(job_id: str):
    """
    Download the converted files for a completed job.
    
    Args:
        job_id: The job ID
        
    Returns:
        Download URL or file information
    """
    try:
        result = storage_manager.get_download_info(job_id)
        if not result:
            raise HTTPException(status_code=404, detail="Job results not found")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in download endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Step 11: Product Image Storage API Routes (Cloudinary + MongoDB)
# ============================================================================

@app.post("/product/upload")
async def upload_product_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    product_type: str = "tshirt",
    quality: Optional[int] = 75,
    format: Optional[str] = "jpeg"
):
    """
    Step 11: Upload PSD file, convert to JPEG, upload to Cloudinary, and save metadata to MongoDB.
    
    This endpoint provides the complete workflow:
    1. Upload PSD file
    2. Convert to optimized JPEG
    3. Upload JPEG to Cloudinary
    4. Save minimal metadata to MongoDB
    
    Args:
        file: PSD file to upload
        product_type: Type of product (e.g., "tshirt", "hoodie", "mug", etc.)
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
        if file_extension not in ['psd']:
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
        
        # Clean product type (lowercase, alphanumeric only)
        product_type = ''.join(c.lower() for c in product_type if c.isalnum())
        if not product_type:
            raise HTTPException(status_code=400, detail="Product type must contain alphanumeric characters")
        
        # Generate job ID
        job_id = generate_job_id("product")
        
        logger.info(f"Starting product upload job {job_id} for {product_type}: {file.filename}")
        
        # Start background processing with Step 11 workflow
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
        
    except Exception as e:
        logger.error(f"Error in product upload endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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


@app.get("/products/{product_type}")
async def get_products_by_type(product_type: str):
    """
    Get products filtered by specific type.
    
    Args:
        product_type: Product type to filter by
        
    Returns:
        List of products for the specified type
    """
    try:
        products = await image_storage.get_products(product_type)
        
        return {
            "product_type": product_type,
            "products": products,
            "count": len(products)
        }
        
    except Exception as e:
        logger.error(f"Error getting products by type: {str(e)}")
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


@app.get("/download/product/{document_id}")
async def download_product_image(document_id: str):
    """
    Download the converted JPEG image for a product.
    
    Args:
        document_id: MongoDB document ID of the product
        
    Returns:
        FileResponse with the JPEG image
    """
    try:
        # Get product details from MongoDB
        products = await image_storage.get_products()
        product = None
        
        for p in products:
            if str(p.get("_id")) == document_id:
                product = p
                break
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Get the Cloudinary URL
        image_url = product.get("image_url")
        if not image_url:
            raise HTTPException(status_code=404, detail="Product image URL not found")
        
        # Download the image from Cloudinary
        import requests
        import tempfile
        
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        # Extract original filename from the Cloudinary URL or use a default
        # URL format: .../product_product_jobid_originalname_cloudinaryid.jpg
        cloudinary_filename = image_url.split('/')[-1]
        if '_' in cloudinary_filename:
            # Try to extract original name from the pattern
            parts = cloudinary_filename.split('_')
            if len(parts) >= 4:
                # Find the original filename part
                original_name_part = '_'.join(parts[3:-1])  # Everything between job ID and Cloudinary ID
                if original_name_part:
                    # Remove .psd extension if present and add .jpeg
                    base_name = original_name_part.replace('.psd', '').replace('.PSD', '')
                    download_filename = f"{base_name}.jpeg"
                else:
                    download_filename = f"product_{document_id}.jpeg"
            else:
                download_filename = f"product_{document_id}.jpeg"
        else:
            download_filename = f"product_{document_id}.jpeg"
        
        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpeg')
        temp_file.write(response.content)
        temp_file.close()
        
        # Return file response with proper cleanup
        return FileResponse(
            temp_file.name,
            media_type='image/jpeg',
            filename=download_filename,
            background=BackgroundTasks()  # This will clean up the temp file
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading product image: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download/job/{job_id}")
async def download_job_result(job_id: str):
    """
    Download the converted image for a completed job.
    
    Args:
        job_id: Job ID from product upload
        
    Returns:
        FileResponse with the converted image
    """
    try:
        # Check if it's a product job
        if job_id.startswith("product_") and job_id in product_jobs:
            job_status = product_jobs[job_id]
            
            if job_status.get("status") != "completed":
                raise HTTPException(status_code=400, detail="Job not completed yet")
            
            result = job_status.get("result", {})
            image_url = result.get("image_url")
            
            if not image_url:
                raise HTTPException(status_code=404, detail="Image URL not found in job result")
            
            # Download the image from Cloudinary
            import requests
            import tempfile
            
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Generate filename from job result
            original_filename = result.get("original_filename", "converted")
            if original_filename.lower().endswith('.psd'):
                base_name = original_filename[:-4]  # Remove .psd
            else:
                base_name = original_filename
            
            output_format = result.get("conversion_info", {}).get("format", "jpeg")
            download_filename = f"{base_name}.{output_format}"
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{output_format}')
            temp_file.write(response.content)
            temp_file.close()
            
            # Return file response
            return FileResponse(
                temp_file.name,
                media_type=f'image/{output_format}',
                filename=download_filename,
                background=BackgroundTasks()
            )
        else:
            # Handle regular task manager jobs
            status = task_manager.get_job_status(job_id)
            if not status:
                raise HTTPException(status_code=404, detail="Job not found")
            
            # This would need to be implemented based on your existing download logic
            raise HTTPException(status_code=501, detail="Download for regular jobs not implemented yet")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading job result: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/download/custom")
async def download_custom(request: dict):
    """
    Custom download endpoint that allows frontend to specify download preferences.
    
    Request body:
    {
        "source_type": "product|job",
        "source_id": "document_id or job_id",
        "download_options": {
            "filename": "custom_name.jpeg",
            "format": "jpeg|png|webp",
            "quality": 85,
            "resize": {"width": 1920, "height": 1080},
            "metadata": {
                "title": "Custom Title",
                "description": "Custom Description"
            }
        }
    }
    
    Returns:
        FileResponse with customized image
    """
    try:
        source_type = request.get("source_type")
        source_id = request.get("source_id")
        download_options = request.get("download_options", {})
        
        if not source_type or not source_id:
            raise HTTPException(status_code=400, detail="source_type and source_id are required")
        
        # Get the image URL based on source type
        image_url = None
        original_filename = "converted"
        
        if source_type == "product":
            # Get from MongoDB
            products = await image_storage.get_products()
            product = next((p for p in products if p["_id"] == source_id), None)
            if not product:
                raise HTTPException(status_code=404, detail="Product not found")
            image_url = product["image_url"]
            original_filename = product.get("filename", "converted")
            
        elif source_type == "job":
            # Get from job results
            if source_id.startswith("product_") and source_id in product_jobs:
                job_status = product_jobs[source_id]
                if job_status.get("status") != "completed":
                    raise HTTPException(status_code=400, detail="Job not completed yet")
                result = job_status.get("result", {})
                image_url = result.get("image_url")
                original_filename = result.get("original_filename", "converted")
            else:
                raise HTTPException(status_code=404, detail="Job not found")
        else:
            raise HTTPException(status_code=400, detail="source_type must be 'product' or 'job'")
        
        if not image_url:
            raise HTTPException(status_code=404, detail="Image not found")
        
        # Download the image from Cloudinary
        import requests
        import tempfile
        from PIL import Image
        import io
        
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        # Load image for processing
        image = Image.open(io.BytesIO(response.content))
        
        # Apply custom options
        output_format = download_options.get("format", "jpeg").lower()
        quality = download_options.get("quality", 85)
        
        # Resize if requested
        resize_options = download_options.get("resize")
        if resize_options and "width" in resize_options and "height" in resize_options:
            new_size = (resize_options["width"], resize_options["height"])
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Determine filename
        custom_filename = download_options.get("filename")
        if custom_filename:
            download_filename = custom_filename
        else:
            # Use original filename with new format
            if original_filename.lower().endswith('.psd'):
                base_name = original_filename[:-4]
            else:
                base_name = original_filename.split('.')[0]
            download_filename = f"{base_name}.{output_format}"
        
        # Save processed image to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{output_format}')
        
        # Set image format and quality
        save_kwargs = {"format": output_format.upper()}
        if output_format in ["jpeg", "jpg"]:
            save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True
        elif output_format == "png":
            save_kwargs["optimize"] = True
        elif output_format == "webp":
            save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True
        
        image.save(temp_file.name, **save_kwargs)
        temp_file.close()
        
        # Return customized file
        return FileResponse(
            path=temp_file.name,
            media_type=f"image/{output_format}",
            filename=download_filename,
            background=BackgroundTasks()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in custom download: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Background Task for Step 11 Product Processing
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
    Background task for processing product uploads with Step 11 workflow.
    
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


@app.post("/admin/cleanup")
async def cleanup_old_jobs(
    max_age_hours: Optional[int] = 24
):
    """
    Admin endpoint to cleanup old job files and data.
    
    Args:
        max_age_hours: Maximum age in hours for jobs to keep
        
    Returns:
        Cleanup results
    """
    try:
        # This would typically require admin authentication
        cleanup_results = await task_manager.cleanup_old_jobs(max_age_hours)
        return {
            "message": "Cleanup completed",
            "results": cleanup_results
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """Application startup event handler."""
    logger.info("PSD Converter Backend starting up...")
    logger.info(f"Configuration: {task_config.concurrency_mode.value} mode with {task_config.max_workers} workers")
    
    # Initialize image storage service (Step 11)
    try:
        await image_storage.initialize()
        logger.info("Image storage service (Cloudinary + MongoDB) initialized")
    except Exception as e:
        logger.warning(f"Image storage service initialization failed: {e}")
        logger.warning("Step 11 features (product upload) may not work properly")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event handler."""
    logger.info("PSD Converter Backend shutting down...")
    await task_manager.shutdown()
    await image_storage.shutdown()
    logger.info("All services shutdown complete")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
