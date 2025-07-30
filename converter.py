"""
PSD to JPEG/WebP/AVIF converter module.
Handles the core conversion logic using psd-tools and Pillow.
"""

import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import logging
from PIL import Image, ImageOps
from psd_tools import PSDImage
import imagehash

from utils import get_file_hash, ensure_directory
from storage_optimizer import StorageOptimizer
from deduplication import DuplicationDetector, DeduplicationManager

logger = logging.getLogger(__name__)


class PSDConverter:
    """Handles PSD file conversion to various compressed formats with advanced storage optimization and deduplication."""
    
    def __init__(self, enable_deduplication: bool = True):
        self.supported_formats = ['jpeg', 'webp', 'avif']
        self.default_quality = 75
        self.storage_optimizer = StorageOptimizer()
        self.enable_deduplication = enable_deduplication
        
        # Initialize deduplication if enabled
        if enable_deduplication:
            self.dedup_detector = DuplicationDetector()
            logger.info("Deduplication enabled for PSD converter")
        else:
            self.dedup_detector = None
            logger.info("Deduplication disabled for PSD converter")
    
    def convert_psd_to_image_with_dedup(
        self,
        psd_path: str,
        output_path: str,
        quality: int = 75,
        output_format: str = 'jpeg',
        quality_profile: str = 'storage_optimized',
        max_resolution: Optional[Tuple[int, int]] = None,
        strip_metadata: bool = True,
        generate_thumbnails: bool = True,
        use_case: str = 'web',
        enable_deduplication: bool = True
    ) -> Dict[str, Any]:
        """
        Convert PSD to optimized image with deduplication support.
        
        This method includes Step 10: Deduplication features:
        - Generates perceptual hashes (pHash) for final images
        - Compares against stored hashes to detect duplicates
        - Uses hash-based filenames to avoid overwrites
        
        Args:
            psd_path: Path to the PSD file
            output_path: Path for the output image
            quality: Custom quality override (1-100)
            output_format: Output format (jpeg, webp, avif)
            quality_profile: Predefined quality profile
            max_resolution: Maximum resolution (width, height)
            strip_metadata: Remove all metadata
            generate_thumbnails: Create thumbnail variants
            use_case: Use case for optimization recommendations
            enable_deduplication: Enable duplicate detection for this conversion
            
        Returns:
            Dictionary with conversion, optimization, and deduplication results
        """
        try:
            logger.info(f"Converting PSD with optimization and deduplication: {psd_path}")
            
            # First perform standard optimized conversion
            conversion_result = self.convert_psd_to_image_optimized(
                psd_path=psd_path,
                output_path=output_path,
                quality=quality,
                output_format=output_format,
                quality_profile=quality_profile,
                max_resolution=max_resolution,
                strip_metadata=strip_metadata,
                generate_thumbnails=generate_thumbnails,
                use_case=use_case
            )
            
            # Add deduplication if enabled and detector available
            if enable_deduplication and self.dedup_detector:
                logger.info("Performing deduplication check...")
                
                dedup_results = {}
                duplicate_references = {}
                files_to_check = []
                
                # Collect all output files for deduplication
                if conversion_result.get('success') and os.path.exists(output_path):
                    files_to_check.append(output_path)
                
                # Check thumbnail files if generated
                if 'optimization_info' in conversion_result:
                    thumbnails = conversion_result['optimization_info'].get('thumbnails', [])
                    for thumb_info in thumbnails:
                        if 'path' in thumb_info and os.path.exists(thumb_info['path']):
                            files_to_check.append(thumb_info['path'])
                
                # Process each file for deduplication
                for file_path in files_to_check:
                    try:
                        dedup_result = self.dedup_detector.check_for_duplicate(file_path)
                        file_key = os.path.basename(file_path)
                        dedup_results[file_key] = dedup_result
                        
                        # Handle duplicates
                        if dedup_result['is_duplicate']:
                            logger.warning(f"Duplicate detected: {file_key} "
                                         f"(distance: {dedup_result['similar_images'][0][1]})")
                            
                            # Get reference to existing duplicate
                            closest_match = dedup_result['similar_images'][0]
                            existing_file_info = closest_match[2]  # File info from deduplication
                            
                            # Record duplicate information but keep the file for this job
                            if dedup_result['action'] == 'skip_duplicate':
                                logger.info(f"Duplicate detected but keeping for job: {file_key}")
                                
                                # Store reference to existing file instead of removing
                                duplicate_references[file_key] = {
                                    'original_path': file_path,
                                    'existing_file': existing_file_info,
                                    'hash': closest_match[0],
                                    'distance': closest_match[1],
                                    'action': 'kept_for_job'
                                }
                                
                                # Keep the file but mark it as duplicate
                                # Don't remove it so the job has something to store
                        else:
                            # Generate hash-based filename for unique files
                            if dedup_result.get('recommended_filename'):
                                hash_filename = dedup_result['recommended_filename']
                                hash_path = os.path.join(os.path.dirname(file_path), hash_filename)
                                
                                # Rename file to hash-based name
                                os.rename(file_path, hash_path)
                                logger.info(f"Renamed to hash-based filename: {hash_filename}")
                                
                                # Update paths in results
                                if file_path == output_path:
                                    conversion_result['final_output_path'] = hash_path
                                
                    except Exception as e:
                        logger.error(f"Deduplication error for {file_path}: {e}")
                        dedup_results[os.path.basename(file_path)] = {
                            'error': str(e),
                            'is_duplicate': False
                        }
                
                # Add deduplication info to results
                conversion_result['deduplication_info'] = {
                    'enabled': True,
                    'files_checked': len(files_to_check),
                    'duplicates_found': sum(1 for r in dedup_results.values() 
                                          if r.get('is_duplicate', False)),
                    'unique_files': sum(1 for r in dedup_results.values() 
                                      if not r.get('is_duplicate', False) and not r.get('error')),
                    'results': dedup_results,
                    'duplicate_references': duplicate_references
                }
                
                logger.info(f"Deduplication complete: {conversion_result['deduplication_info']['duplicates_found']} duplicates, "
                           f"{conversion_result['deduplication_info']['unique_files']} unique files")
            else:
                conversion_result['deduplication_info'] = {
                    'enabled': False,
                    'message': 'Deduplication disabled or not available'
                }
            
            return conversion_result
            
        except Exception as e:
            logger.error(f"Error in PSD conversion with deduplication: {e}")
            return {
                'success': False,
                'error': str(e),
                'deduplication_info': {'enabled': enable_deduplication, 'error': str(e)}
            }
        
    def convert_psd_to_image_optimized(
        self,
        psd_path: str,
        output_path: str,
        quality: int = 75,
        output_format: str = 'jpeg',
        quality_profile: str = 'storage_optimized',
        max_resolution: Optional[Tuple[int, int]] = None,
        strip_metadata: bool = True,
        generate_thumbnails: bool = True,
        use_case: str = 'web'
    ) -> Dict[str, Any]:
        """
        Convert PSD to optimized image with advanced storage optimization.
        
        Args:
            psd_path: Path to the PSD file
            output_path: Path for the output image
            quality: Custom quality override (1-100)
            output_format: Output format (jpeg, webp, avif)
            quality_profile: Predefined quality profile
            max_resolution: Maximum resolution (width, height)
            strip_metadata: Remove all metadata
            generate_thumbnails: Create thumbnail variants
            use_case: Use case for optimization recommendations
            
        Returns:
            Dictionary with conversion and optimization results
        """
        try:
            logger.info(f"Converting PSD with storage optimization: {psd_path} to {output_format}")
            
            # Validate input file
            if not os.path.exists(psd_path):
                raise FileNotFoundError(f"PSD file not found: {psd_path}")
            
            file_size = os.path.getsize(psd_path)
            if file_size == 0:
                raise ValueError("PSD file is empty")
            
            logger.info(f"Input PSD size: {file_size} bytes")
            
            # Open and process PSD
            psd = PSDImage.open(psd_path)
            logger.info(f"PSD opened successfully - Size: {psd.size}")
            
            # Get optimization recommendations
            recommendations = self.storage_optimizer.get_optimization_recommendations(
                psd.size, file_size, use_case
            )
            logger.info(f"Optimization recommendations: {recommendations['reasoning']}")
            
            # Apply recommendations if not overridden
            if quality_profile == 'auto':
                quality_profile = recommendations['quality_profile']
            
            if max_resolution is None and recommendations['should_downscale']:
                max_resolution = recommendations['recommended_max_resolution']
            
            # Composite PSD layers
            logger.info("Compositing PSD layers...")
            try:
                composite_image = psd.composite()
                if composite_image is None:
                    # Fallback: create white background
                    logger.warning("PSD composite returned None, creating white background")
                    composite_image = Image.new('RGB', psd.size, 'white')
                
                logger.info(f"Composite image created - Mode: {composite_image.mode}, Size: {composite_image.size}")
                
            except Exception as e:
                logger.error(f"Error compositing PSD: {e}")
                raise ValueError(f"Failed to composite PSD layers: {str(e)}")
            
            # Convert to RGB if needed
            if composite_image.mode == 'RGBA':
                # Create white background for transparency
                background = Image.new('RGB', composite_image.size, 'white')
                background.paste(composite_image, mask=composite_image.split()[-1])
                composite_image = background
            elif composite_image.mode != 'RGB':
                composite_image = composite_image.convert('RGB')
            
            # Apply storage optimization
            optimization_result = self.storage_optimizer.optimize_image_for_storage(
                image=composite_image,
                output_path=output_path,
                format=output_format,
                quality_profile=quality_profile,
                custom_quality=quality if quality != 75 else None,  # Only override if changed
                max_resolution=max_resolution,
                strip_metadata=strip_metadata,
                generate_thumbnails=generate_thumbnails
            )
            
            if not optimization_result['success']:
                raise ValueError(f"Storage optimization failed: {optimization_result.get('error', 'Unknown error')}")
            
            # Calculate comprehensive metrics
            original_size = os.path.getsize(psd_path)
            optimized_size = optimization_result['optimized_size']
            compression_ratio = (1 - optimized_size / original_size) * 100 if original_size > 0 else 0
            
            # Generate image hash for duplicate detection
            image_hash = str(imagehash.average_hash(composite_image))
            
            result = {
                'success': True,
                'conversion_info': {
                    'input_file': psd_path,
                    'output_file': output_path,
                    'original_size': original_size,
                    'optimized_size': optimized_size,
                    'compression_ratio': round(compression_ratio, 2),
                    'format': output_format,
                    'image_hash': image_hash,
                    'file_hash': get_file_hash(output_path) if os.path.exists(output_path) else None
                },
                'optimization_info': optimization_result,
                'recommendations_used': recommendations
            }
            
            logger.info(f"Successfully converted {psd_path}")
            logger.info(f"Compression: {original_size} → {optimized_size} bytes ({compression_ratio:.1f}% reduction)")
            
            return result
            
        except Exception as e:
            logger.error(f"Error converting PSD {psd_path}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'input_file': psd_path,
                'output_file': output_path
            }
    
    def convert_psd_to_image(
        self,
        psd_path: str,
        output_path: str,
        quality: int = 75,
        output_format: str = 'jpeg',
        optimize: bool = True,
        progressive: bool = True
    ) -> Dict[str, Any]:
        """
        Convert a single PSD file to the specified image format.
        
        Args:
            psd_path: Path to the PSD file
            output_path: Path for the output image
            quality: Compression quality (1-100)
            output_format: Output format (jpeg, webp, avif)
            optimize: Enable optimization
            progressive: Enable progressive encoding (JPEG only)
            
        Returns:
            Dictionary with conversion results and metadata
        """
        try:
            logger.info(f"Converting PSD: {psd_path} to {output_format}")
            
            # Validate input file
            if not os.path.exists(psd_path):
                raise FileNotFoundError(f"PSD file not found: {psd_path}")
            
            file_size = os.path.getsize(psd_path)
            if file_size == 0:
                raise ValueError("PSD file is empty")
            
            logger.info(f"Input PSD size: {file_size} bytes")
            
            # Open and validate PSD file
            try:
                psd = PSDImage.open(psd_path)
                logger.info(f"PSD opened successfully - Size: {psd.size}")
                
                # Get color mode from PSD header if available
                psd_mode = getattr(psd, 'color_mode', 'Unknown')
                logger.info(f"PSD color mode: {psd_mode}")
            except Exception as e:
                raise ValueError(f"Failed to open PSD file: {str(e)}")
            
            # Check if PSD has valid dimensions
            if not psd.size or psd.size[0] == 0 or psd.size[1] == 0:
                raise ValueError("PSD has invalid dimensions")
            
            # Log PSD information
            logger.info(f"PSD dimensions: {psd.size[0]}x{psd.size[1]} pixels")
            logger.info(f"PSD color mode: {psd_mode}")
            
            # Composite all layers into a single PIL Image
            logger.info("Compositing PSD layers...")
            composite_image = psd.composite()
            
            if composite_image is None:
                raise ValueError("Failed to composite PSD layers - no visible content")
            
            logger.info(f"Composite image created - Mode: {composite_image.mode}, Size: {composite_image.size}")
            
            # Convert to RGB if necessary (required for JPEG)
            if composite_image.mode in ('RGBA', 'LA'):
                logger.info("Converting RGBA/LA to RGB with white background")
                # Create white background for transparency
                background = Image.new('RGB', composite_image.size, (255, 255, 255))
                if composite_image.mode == 'RGBA':
                    background.paste(composite_image, mask=composite_image.split()[-1])
                else:
                    background.paste(composite_image)
                composite_image = background
            elif composite_image.mode == 'CMYK':
                logger.info("Converting CMYK to RGB")
                composite_image = composite_image.convert('RGB')
            elif composite_image.mode == 'L':
                logger.info("Converting grayscale to RGB")
                composite_image = composite_image.convert('RGB')
            elif composite_image.mode != 'RGB':
                logger.info(f"Converting {composite_image.mode} to RGB")
                composite_image = composite_image.convert('RGB')
            
            # Auto-orient image based on EXIF data
            composite_image = ImageOps.exif_transpose(composite_image)
            
            # Ensure output directory exists
            ensure_directory(os.path.dirname(output_path))
            
            # Apply any pre-processing optimizations
            composite_image = self._optimize_image_for_compression(composite_image, quality)
            
            # Save with format-specific settings
            logger.info(f"Saving as {output_format} with quality {quality}")
            save_kwargs = self._get_save_kwargs(output_format, quality, optimize, progressive)
            composite_image.save(output_path, **save_kwargs)
            
            # Verify output file was created
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                raise ValueError("Failed to create output file or file is empty")
            
            # Generate metadata
            original_size = os.path.getsize(psd_path)
            converted_size = os.path.getsize(output_path)
            compression_ratio = (1 - converted_size / original_size) * 100 if original_size > 0 else 0
            
            # Generate image hash for duplicate detection
            image_hash = str(imagehash.average_hash(composite_image))
            
            result = {
                'success': True,
                'input_file': psd_path,
                'output_file': output_path,
                'original_size': original_size,
                'converted_size': converted_size,
                'compression_ratio': round(compression_ratio, 2),
                'format': output_format,
                'quality': quality,
                'dimensions': composite_image.size,
                'image_hash': image_hash,
                'file_hash': get_file_hash(output_path),
                'psd_mode': psd_mode,
                'final_mode': 'RGB'
            }
            
            logger.info(f"Successfully converted {psd_path}")
            logger.info(f"Compression: {original_size} → {converted_size} bytes ({compression_ratio:.1f}% reduction)")
            return result
            
        except Exception as e:
            logger.error(f"Error converting PSD {psd_path}: {str(e)}")
            return {
                'success': False,
                'input_file': psd_path,
                'error': str(e)
            }
    
    def _optimize_image_for_compression(self, image: Image.Image, quality: int) -> Image.Image:
        """
        Apply optimizations to improve compression while maintaining quality.
        
        Args:
            image: PIL Image to optimize
            quality: Target quality level
            
        Returns:
            Optimized PIL Image
        """
        try:
            # For very low quality settings, consider resizing for better compression
            if quality < 50:
                # Calculate if resizing would be beneficial
                width, height = image.size
                if width > 2048 or height > 2048:
                    # Resize large images for low quality outputs
                    max_size = 1920 if quality < 30 else 2048
                    ratio = min(max_size / width, max_size / height)
                    if ratio < 1:
                        new_width = int(width * ratio)
                        new_height = int(height * ratio)
                        logger.info(f"Resizing for compression: {width}x{height} → {new_width}x{new_height}")
                        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Apply any other optimizations based on content
            # For now, just return the image as-is for most cases
            return image
            
        except Exception as e:
            logger.warning(f"Error optimizing image: {str(e)}")
            return image
    
    def _get_save_kwargs(
        self,
        output_format: str,
        quality: int,
        optimize: bool,
        progressive: bool
    ) -> Dict[str, Any]:
        """
        Get format-specific save parameters.
        
        Args:
            output_format: Target format
            quality: Compression quality
            optimize: Enable optimization
            progressive: Enable progressive encoding
            
        Returns:
            Dictionary of save parameters
        """
        if output_format.lower() == 'jpeg':
            # Enhanced JPEG settings for optimal compression
            jpeg_kwargs = {
                'format': 'JPEG',
                'quality': quality,
                'optimize': optimize,
                'progressive': progressive,
                'dpi': (72, 72),  # Standard web DPI
            }
            
            # Additional JPEG optimizations based on quality
            if quality >= 90:
                # High quality: preserve detail
                jpeg_kwargs['subsampling'] = 0  # No chroma subsampling
            elif quality >= 75:
                # Medium-high quality: slight optimization
                jpeg_kwargs['subsampling'] = 1  # Medium chroma subsampling  
            else:
                # Lower quality: maximum compression
                jpeg_kwargs['subsampling'] = 2  # High chroma subsampling
            
            return jpeg_kwargs
        elif output_format.lower() == 'webp':
            return {
                'format': 'WebP',
                'quality': quality,
                'optimize': optimize,
                'method': 6  # Best compression method
            }
        elif output_format.lower() == 'avif':
            return {
                'format': 'AVIF',
                'quality': quality,
                'speed': 4  # Balance between speed and compression
            }
        else:
            raise ValueError(f"Unsupported format: {output_format}")
    
    def batch_convert(
        self,
        psd_files: list,
        output_directory: str,
        quality: int = 75,
        output_format: str = 'jpeg',
        callback=None
    ) -> list:
        """
        Convert multiple PSD files in batch.
        
        Args:
            psd_files: List of PSD file paths
            output_directory: Directory for output files
            quality: Compression quality
            output_format: Output format
            callback: Optional callback function for progress updates
            
        Returns:
            List of conversion results
        """
        results = []
        total_files = len(psd_files)
        
        logger.info(f"Starting batch conversion of {total_files} files")
        
        for i, psd_file in enumerate(psd_files):
            try:
                # Generate output filename
                base_name = Path(psd_file).stem
                extension = 'jpg' if output_format == 'jpeg' else output_format
                output_file = os.path.join(output_directory, f"{base_name}.{extension}")
                
                # Convert file
                result = self.convert_psd_to_image(
                    psd_file,
                    output_file,
                    quality=quality,
                    output_format=output_format
                )
                
                results.append(result)
                
                # Call progress callback if provided
                if callback:
                    progress = ((i + 1) / total_files) * 100
                    callback(progress, i + 1, total_files, result)
                    
            except Exception as e:
                logger.error(f"Error in batch conversion for {psd_file}: {str(e)}")
                results.append({
                    'success': False,
                    'input_file': psd_file,
                    'error': str(e)
                })
        
        successful_conversions = sum(1 for r in results if r.get('success', False))
        logger.info(f"Batch conversion completed: {successful_conversions}/{total_files} successful")
        
        return results
    
    def estimate_output_size(self, psd_path: str, quality: int = 75) -> Optional[int]:
        """
        Estimate the output file size without full conversion.
        
        Args:
            psd_path: Path to PSD file
            quality: Target quality
            
        Returns:
            Estimated file size in bytes, or None if estimation fails
        """
        try:
            psd = PSDImage.open(psd_path)
            
            if psd.size:
                # Rough estimation based on dimensions and quality
                width, height = psd.size
                pixels = width * height
                
                # Approximate bytes per pixel based on quality
                if quality >= 90:
                    bpp = 3.0
                elif quality >= 75:
                    bpp = 2.0
                elif quality >= 50:
                    bpp = 1.5
                else:
                    bpp = 1.0
                
                estimated_size = int(pixels * bpp)
                return estimated_size
                
        except Exception as e:
            logger.warning(f"Could not estimate size for {psd_path}: {str(e)}")
            
        return None
