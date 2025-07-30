"""
Step 11: Cloudinary and MongoDB integration for final image storage.
Handles image upload to Cloudinary and metadata storage in MongoDB.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pathlib import Path

import cloudinary
import cloudinary.uploader
import cloudinary.api
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

from utils import get_env_var

logger = logging.getLogger(__name__)


class CloudinaryService:
    """
    Service for uploading images to Cloudinary.
    """
    
    def __init__(self):
        """Initialize Cloudinary configuration."""
        # Configure Cloudinary
        cloudinary.config(
            cloud_name=get_env_var("CLOUDINARY_CLOUD_NAME", ""),
            api_key=get_env_var("CLOUDINARY_API_KEY", ""),
            api_secret=get_env_var("CLOUDINARY_API_SECRET", ""),
            secure=True
        )
        
        self.cloud_name = get_env_var("CLOUDINARY_CLOUD_NAME", "")
        logger.info(f"Cloudinary service initialized for cloud: {self.cloud_name}")
    
    async def upload_image(self, image_path: str, product_type: str = None, original_filename: str = None) -> Dict:
        """
        Upload image to Cloudinary.
        
        Args:
            image_path: Path to the image file to upload
            product_type: Optional product type for organizing uploads
            original_filename: Original PSD filename for better naming
            
        Returns:
            Dict containing upload result with secure_url
        """
        try:
            # Prepare upload options
            upload_options = {
                "resource_type": "image",
                "quality": "auto:good",
                "format": "jpg",
                "use_filename": True,
                "unique_filename": True,
                "overwrite": False
            }
            
            # Use original filename if provided
            if original_filename:
                # Remove .psd extension and use as public_id base
                base_name = os.path.splitext(original_filename)[0]
                upload_options["public_id"] = f"product_{base_name}"
                upload_options["use_filename"] = False  # We're setting our own public_id
            
            # Add folder organization if product_type provided
            if product_type:
                upload_options["folder"] = f"products/{product_type}"
            
            # Upload to Cloudinary
            logger.info(f"Uploading image to Cloudinary: {os.path.basename(image_path)}")
            result = cloudinary.uploader.upload(image_path, **upload_options)
            
            logger.info(f"Successfully uploaded to Cloudinary: {result.get('secure_url')}")
            
            return {
                "success": True,
                "secure_url": result["secure_url"],
                "public_id": result["public_id"],
                "width": result.get("width"),
                "height": result.get("height"),
                "bytes": result.get("bytes"),
                "format": result.get("format"),
                "created_at": result.get("created_at")
            }
            
        except Exception as e:
            logger.error(f"Failed to upload image to Cloudinary: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_image(self, public_id: str) -> Dict:
        """
        Delete image from Cloudinary.
        
        Args:
            public_id: Cloudinary public ID of the image to delete
            
        Returns:
            Dict containing deletion result
        """
        try:
            result = cloudinary.uploader.destroy(public_id)
            logger.info(f"Deleted image from Cloudinary: {public_id}")
            return {"success": True, "result": result}
            
        except Exception as e:
            logger.error(f"Failed to delete image from Cloudinary: {str(e)}")
            return {"success": False, "error": str(e)}


class MongoDBService:
    """
    Service for storing product image metadata in MongoDB.
    """
    
    def __init__(self):
        """Initialize MongoDB connection."""
        self.connection_string = get_env_var("MONGODB_CONNECTION_STRING", "mongodb://localhost:27017")
        self.database_name = get_env_var("MONGODB_DATABASE", "psd_converter")
        self.collection_name = get_env_var("MONGODB_COLLECTION", "product_images")
        
        self.client = None
        self.db = None
        self.collection = None
        
        logger.info(f"MongoDB service initialized for database: {self.database_name}")
    
    async def connect(self):
        """Establish connection to MongoDB."""
        try:
            self.client = AsyncIOMotorClient(self.connection_string)
            self.db = self.client[self.database_name]
            self.collection = self.db[self.collection_name]
            
            # Test connection
            await self.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise
    
    async def disconnect(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
    
    async def save_product_image(self, product_type: str, image_url: str, filename: str = None) -> Dict:
        """
        Save product image metadata to MongoDB.
        
        Args:
            product_type: Type of product (e.g., "tshirt", "hoodie", etc.)
            image_url: Cloudinary secure URL of the uploaded image
            filename: Original filename (e.g., "11626499.jpeg")
            
        Returns:
            Dict containing save result with document ID
        """
        try:
            # Ensure connection is established
            if self.collection is None:
                await self.connect()
            
            # Create document according to Step 11 requirements
            document = {
                "product_type": product_type,
                "image_url": image_url,
                "uploaded_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Add filename if provided
            if filename:
                document["filename"] = filename
            
            # Insert document
            result = await self.collection.insert_one(document)
            
            logger.info(f"Saved product image metadata: {result.inserted_id}")
            
            return {
                "success": True,
                "document_id": str(result.inserted_id),
                "product_type": product_type,
                "image_url": image_url
            }
            
        except PyMongoError as e:
            logger.error(f"MongoDB error saving product image: {str(e)}")
            return {
                "success": False,
                "error": f"Database error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Failed to save product image metadata: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_product_images(self, product_type: str = None, limit: int = 100) -> List[Dict]:
        """
        Retrieve product images from MongoDB.
        
        Args:
            product_type: Optional filter by product type
            limit: Maximum number of documents to return
            
        Returns:
            List of product image documents
        """
        try:
            # Ensure connection is established
            if self.collection is None:
                await self.connect()
            
            # Build query
            query = {}
            if product_type:
                query["product_type"] = product_type
            
            # Execute query
            cursor = self.collection.find(query).limit(limit).sort("uploaded_at", -1)
            documents = await cursor.to_list(length=limit)
            
            # Convert ObjectId to string for JSON serialization
            for doc in documents:
                doc["_id"] = str(doc["_id"])
            
            logger.info(f"Retrieved {len(documents)} product images")
            return documents
            
        except Exception as e:
            logger.error(f"Failed to retrieve product images: {str(e)}")
            return []
    
    async def delete_product_image(self, document_id: str) -> Dict:
        """
        Delete product image metadata from MongoDB.
        
        Args:
            document_id: MongoDB document ID
            
        Returns:
            Dict containing deletion result
        """
        try:
            from bson import ObjectId
            
            # Ensure connection is established
            if self.collection is None:
                await self.connect()
            
            # Delete document
            result = await self.collection.delete_one({"_id": ObjectId(document_id)})
            
            if result.deleted_count > 0:
                logger.info(f"Deleted product image metadata: {document_id}")
                return {"success": True, "deleted": True}
            else:
                return {"success": False, "error": "Document not found"}
                
        except Exception as e:
            logger.error(f"Failed to delete product image metadata: {str(e)}")
            return {"success": False, "error": str(e)}


class ImageStorageService:
    """
    Combined service for handling complete image storage workflow.
    Coordinates between Cloudinary and MongoDB services.
    """
    
    def __init__(self):
        """Initialize the combined storage service."""
        self.cloudinary = CloudinaryService()
        self.mongodb = MongoDBService()
        logger.info("Image storage service initialized")
    
    async def initialize(self):
        """Initialize connections to external services."""
        try:
            await self.mongodb.connect()
            logger.info("Image storage service ready")
        except Exception as e:
            logger.error(f"Failed to initialize image storage service: {str(e)}")
            raise
    
    async def store_product_image(self, image_path: str, product_type: str, original_filename: str = None) -> Dict:
        """
        Complete workflow: Upload to Cloudinary and save metadata to MongoDB.
        
        Args:
            image_path: Path to the converted image file
            product_type: Type of product (from designer)
            original_filename: Original PSD filename for better naming
            
        Returns:
            Dict containing complete storage result
        """
        try:
            # Step 1: Upload to Cloudinary
            logger.info(f"Starting storage workflow for {product_type} image")
            
            cloudinary_result = await self.cloudinary.upload_image(image_path, product_type, original_filename)
            
            if not cloudinary_result.get("success"):
                return {
                    "success": False,
                    "error": f"Cloudinary upload failed: {cloudinary_result.get('error')}"
                }
            
            image_url = cloudinary_result["secure_url"]
            
            # Extract filename from original_filename (convert .psd to .jpeg)
            if original_filename:
                # Remove .psd extension and add .jpeg
                base_name = original_filename.rsplit('.', 1)[0] if '.' in original_filename else original_filename
                converted_filename = f"{base_name}.jpeg"
            else:
                converted_filename = None
            
            # Step 2: Save metadata to MongoDB
            mongodb_result = await self.mongodb.save_product_image(product_type, image_url, converted_filename)
            
            if not mongodb_result.get("success"):
                # Rollback: Delete from Cloudinary if MongoDB save fails
                await self.cloudinary.delete_image(cloudinary_result["public_id"])
                return {
                    "success": False,
                    "error": f"MongoDB save failed: {mongodb_result.get('error')}"
                }
            
            logger.info(f"Successfully stored product image: {image_url}")
            
            return {
                "success": True,
                "image_url": image_url,
                "product_type": product_type,
                "document_id": mongodb_result["document_id"],
                "cloudinary_public_id": cloudinary_result["public_id"],
                "uploaded_at": mongodb_result.get("uploaded_at")
            }
            
        except Exception as e:
            logger.error(f"Failed to store product image: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_products(self, product_type: str = None) -> List[Dict]:
        """
        Retrieve product images.
        
        Args:
            product_type: Optional filter by product type
            
        Returns:
            List of product image records
        """
        return await self.mongodb.get_product_images(product_type)
    
    async def delete_product(self, document_id: str, cloudinary_public_id: str = None) -> Dict:
        """
        Delete product image from both Cloudinary and MongoDB.
        
        Args:
            document_id: MongoDB document ID
            cloudinary_public_id: Optional Cloudinary public ID for cleanup
            
        Returns:
            Dict containing deletion result
        """
        try:
            # Delete from MongoDB
            mongodb_result = await self.mongodb.delete_product_image(document_id)
            
            # Delete from Cloudinary if public_id provided
            cloudinary_result = None
            if cloudinary_public_id:
                cloudinary_result = await self.cloudinary.delete_image(cloudinary_public_id)
            
            return {
                "success": mongodb_result.get("success", False),
                "mongodb_result": mongodb_result,
                "cloudinary_result": cloudinary_result
            }
            
        except Exception as e:
            logger.error(f"Failed to delete product: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def shutdown(self):
        """Cleanup connections."""
        await self.mongodb.disconnect()
        logger.info("Image storage service shutdown complete")
