"""
Advanced storage optimization for converted images.
Implements aggressive compression, metadata stripping, and multi-resolution outputs.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
from PIL import Image, ImageOps, ImageFilter
from PIL.ExifTags import TAGS
import logging
import math

logger = logging.getLogger(__name__)


class StorageOptimizer:
    """Advanced image optimization for storage efficiency."""
    
    def __init__(self):
        self.mozjpeg_available = self._check_mozjpeg_availability()
        self.webp_available = self._check_webp_availability()
        
        # Optimization thresholds
        self.high_res_threshold = (4000, 4000)  # Above this, consider downscaling
        self.max_resolution = (8192, 8192)      # Maximum allowed resolution
        self.thumbnail_sizes = [(150, 150), (300, 300), (800, 600)]  # Thumbnail variants
        
        # Quality profiles for different use cases
        self.quality_profiles = {
            'web_optimized': {'jpeg': 85, 'webp': 80, 'avif': 75},
            'storage_optimized': {'jpeg': 75, 'webp': 70, 'avif': 65},
            'maximum_compression': {'jpeg': 65, 'webp': 60, 'avif': 55},
            'high_quality': {'jpeg': 95, 'webp': 90, 'avif': 85}
        }
    
    def _check_mozjpeg_availability(self) -> bool:
        """Check if MozJPEG is available on the system."""
        try:
            result = subprocess.run(['cjpeg', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            available = 'mozjpeg' in result.stderr.lower() or 'mozjpeg' in result.stdout.lower()
            if available:
                logger.info("MozJPEG available for enhanced compression")
            else:
                logger.info("MozJPEG not available, using PIL JPEG compression")
            return available
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            logger.info("MozJPEG not found, using standard JPEG compression")
            return False
    
    def _check_webp_availability(self) -> bool:
        """Check if WebP tools are available."""
        try:
            subprocess.run(['cwebp', '-version'], 
                          capture_output=True, timeout=5)
            logger.info("WebP tools available for enhanced compression")
            return True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            logger.info("WebP tools not found, using PIL WebP support")
            return False
    
    def optimize_image_for_storage(
        self,
        image: Image.Image,
        output_path: str,
        format: str = 'jpeg',
        quality_profile: str = 'storage_optimized',
        custom_quality: Optional[int] = None,
        max_resolution: Optional[Tuple[int, int]] = None,
        strip_metadata: bool = True,
        generate_thumbnails: bool = True
    ) -> Dict[str, Any]:
        """
        Optimize image for storage with advanced compression techniques.
        
        Args:
            image: PIL Image object
            output_path: Output file path
            format: Output format (jpeg, webp, avif)
            quality_profile: Predefined quality profile
            custom_quality: Override quality setting
            max_resolution: Maximum resolution (width, height)
            strip_metadata: Remove all metadata
            generate_thumbnails: Create thumbnail variants
            
        Returns:
            Dictionary with optimization results
        """
        try:
            logger.info(f"Optimizing image for storage: {format} format")
            
            # Store original info
            original_size = image.size
            original_mode = image.mode
            
            # Strip metadata if requested
            if strip_metadata:
                image = self._strip_metadata(image)
            
            # Optimize image for compression
            image = self._pre_compression_optimization(image)
            
            # Handle resolution optimization
            if max_resolution or self._should_downscale(image.size):
                target_resolution = max_resolution or self.high_res_threshold
                image = self._smart_downscale(image, target_resolution)
                logger.info(f"Downscaled from {original_size} to {image.size}")
            
            # Determine quality settings
            quality = custom_quality or self.quality_profiles[quality_profile][format]
            
            # Create output directory
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Optimize based on format
            optimization_result = self._format_specific_optimization(
                image, output_path, format, quality
            )
            
            # Generate thumbnails if requested
            thumbnail_info = []
            if generate_thumbnails:
                thumbnail_info = self._generate_thumbnails(
                    image, output_path, format, quality_profile
                )
            
            # Calculate optimization metrics
            if os.path.exists(output_path):
                optimized_size = os.path.getsize(output_path)
                # Estimate original uncompressed size
                uncompressed_size = original_size[0] * original_size[1] * 3  # RGB bytes
                compression_ratio = (1 - optimized_size / uncompressed_size) * 100
            else:
                optimized_size = 0
                compression_ratio = 0
            
            result = {
                'success': True,
                'output_path': output_path,
                'original_dimensions': original_size,
                'final_dimensions': image.size,
                'original_mode': original_mode,
                'final_mode': image.mode,
                'format': format,
                'quality': quality,
                'quality_profile': quality_profile,
                'estimated_uncompressed_size': uncompressed_size if 'uncompressed_size' in locals() else 0,
                'optimized_size': optimized_size,
                'compression_ratio': round(compression_ratio, 2),
                'metadata_stripped': strip_metadata,
                'resolution_optimized': original_size != image.size,
                'mozjpeg_used': optimization_result.get('mozjpeg_used', False),
                'thumbnails': thumbnail_info,
                'optimization_techniques': optimization_result.get('techniques', [])
            }
            
            logger.info(f"Storage optimization complete: {compression_ratio:.1f}% compression")
            return result
            
        except Exception as e:
            logger.error(f"Storage optimization failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'output_path': output_path
            }
    
    def _strip_metadata(self, image: Image.Image) -> Image.Image:
        """Remove all metadata from image."""
        try:
            # Create new image without EXIF/metadata
            if hasattr(image, '_getexif') and image._getexif() is not None:
                logger.info("Stripping EXIF data")
            
            # Create clean image data
            clean_image = Image.new(image.mode, image.size)
            clean_image.putdata(list(image.getdata()))
            
            return clean_image
            
        except Exception as e:
            logger.warning(f"Failed to strip metadata: {e}")
            return image
    
    def _pre_compression_optimization(self, image: Image.Image) -> Image.Image:
        """Apply pre-compression optimizations."""
        try:
            # Convert to RGB if not already
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Apply slight sharpening for better compression
            if min(image.size) > 1000:  # Only for larger images
                image = image.filter(ImageFilter.UnsharpMask(
                    radius=0.5, percent=50, threshold=3
                ))
            
            return image
            
        except Exception as e:
            logger.warning(f"Pre-compression optimization failed: {e}")
            return image
    
    def _should_downscale(self, size: Tuple[int, int]) -> bool:
        """Determine if image should be downscaled."""
        width, height = size
        threshold_width, threshold_height = self.high_res_threshold
        
        return width > threshold_width or height > threshold_height
    
    def _smart_downscale(
        self, 
        image: Image.Image, 
        max_size: Tuple[int, int]
    ) -> Image.Image:
        """Intelligently downscale image while preserving aspect ratio."""
        try:
            current_width, current_height = image.size
            max_width, max_height = max_size
            
            # Calculate scaling factor
            width_ratio = max_width / current_width
            height_ratio = max_height / current_height
            scale_factor = min(width_ratio, height_ratio, 1.0)  # Don't upscale
            
            if scale_factor < 1.0:
                new_width = int(current_width * scale_factor)
                new_height = int(current_height * scale_factor)
                
                # Use high-quality resampling
                image = image.resize(
                    (new_width, new_height), 
                    Image.Resampling.LANCZOS
                )
                
                logger.info(f"Downscaled to {new_width}x{new_height} (factor: {scale_factor:.2f})")
            
            return image
            
        except Exception as e:
            logger.warning(f"Smart downscaling failed: {e}")
            return image
    
    def _format_specific_optimization(
        self,
        image: Image.Image,
        output_path: str,
        format: str,
        quality: int
    ) -> Dict[str, Any]:
        """Apply format-specific optimization techniques."""
        techniques = []
        mozjpeg_used = False
        
        try:
            if format.lower() == 'jpeg':
                # Try MozJPEG if available for superior compression
                if self.mozjpeg_available:
                    mozjpeg_used = self._optimize_with_mozjpeg(
                        image, output_path, quality
                    )
                    if mozjpeg_used:
                        techniques.append('mozjpeg_compression')
                
                if not mozjpeg_used:
                    # Use PIL with optimized settings
                    image.save(
                        output_path,
                        'JPEG',
                        quality=quality,
                        optimize=True,
                        progressive=True,
                        subsampling='4:2:0',  # Chroma subsampling for better compression
                        qtables='web_high'    # Optimized quantization tables
                    )
                    techniques.append('pil_optimized_jpeg')
                    
            elif format.lower() == 'webp':
                # WebP with advanced options
                if self.webp_available:
                    success = self._optimize_with_cwebp(image, output_path, quality)
                    if success:
                        techniques.append('cwebp_optimization')
                    else:
                        # Fallback to PIL
                        image.save(
                            output_path,
                            'WEBP',
                            quality=quality,
                            optimize=True,
                            method=6,  # Best compression method
                            lossless=False
                        )
                        techniques.append('pil_webp')
                else:
                    image.save(
                        output_path,
                        'WEBP',
                        quality=quality,
                        optimize=True,
                        method=6
                    )
                    techniques.append('pil_webp')
                    
            elif format.lower() == 'avif':
                # AVIF with high compression
                image.save(
                    output_path,
                    'AVIF',
                    quality=quality,
                    optimize=True,
                    speed=0  # Slowest but best compression
                )
                techniques.append('avif_optimized')
            
            return {
                'mozjpeg_used': mozjpeg_used,
                'techniques': techniques
            }
            
        except Exception as e:
            logger.error(f"Format-specific optimization failed: {e}")
            # Fallback to basic save
            image.save(output_path, format.upper(), quality=quality)
            return {
                'mozjpeg_used': False,
                'techniques': ['fallback_basic']
            }
    
    def _optimize_with_mozjpeg(
        self,
        image: Image.Image,
        output_path: str,
        quality: int
    ) -> bool:
        """Use MozJPEG for superior JPEG compression."""
        try:
            with tempfile.NamedTemporaryFile(suffix='.ppm', delete=False) as temp_input:
                # Save as PPM for MozJPEG input
                image.save(temp_input.name, 'PPM')
                temp_input_path = temp_input.name
            
            # Run MozJPEG cjpeg
            cmd = [
                'cjpeg',
                '-quality', str(quality),
                '-optimize',
                '-progressive',
                '-outfile', output_path,
                temp_input_path
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=60
            )
            
            # Cleanup temp file
            os.unlink(temp_input_path)
            
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info("MozJPEG compression successful")
                return True
            else:
                logger.warning(f"MozJPEG failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.warning(f"MozJPEG optimization failed: {e}")
            return False
    
    def _optimize_with_cwebp(
        self,
        image: Image.Image,
        output_path: str,
        quality: int
    ) -> bool:
        """Use Google's cwebp for optimized WebP compression."""
        try:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_input:
                image.save(temp_input.name, 'PNG')
                temp_input_path = temp_input.name
            
            cmd = [
                'cwebp',
                '-q', str(quality),
                '-m', '6',  # Best compression method
                '-pass', '10',  # Multiple passes for better compression
                '-mt',  # Multi-threading
                temp_input_path,
                '-o', output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            os.unlink(temp_input_path)
            
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info("cwebp optimization successful")
                return True
            else:
                logger.warning(f"cwebp failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.warning(f"cwebp optimization failed: {e}")
            return False
    
    def _generate_thumbnails(
        self,
        image: Image.Image,
        base_output_path: str,
        format: str,
        quality_profile: str
    ) -> List[Dict[str, Any]]:
        """Generate multiple thumbnail sizes."""
        thumbnails = []
        base_name = os.path.splitext(base_output_path)[0]
        
        for size in self.thumbnail_sizes:
            try:
                # Create thumbnail
                thumbnail = image.copy()
                thumbnail.thumbnail(size, Image.Resampling.LANCZOS)
                
                # Thumbnail path
                thumb_path = f"{base_name}_thumb_{size[0]}x{size[1]}.{format}"
                
                # Use slightly higher quality for thumbnails
                thumb_quality = min(
                    self.quality_profiles[quality_profile][format] + 10, 
                    95
                )
                
                # Save thumbnail
                if format.lower() == 'jpeg':
                    thumbnail.save(
                        thumb_path,
                        'JPEG',
                        quality=thumb_quality,
                        optimize=True
                    )
                else:
                    thumbnail.save(
                        thumb_path,
                        format.upper(),
                        quality=thumb_quality,
                        optimize=True
                    )
                
                if os.path.exists(thumb_path):
                    thumbnails.append({
                        'size': size,
                        'path': thumb_path,
                        'file_size': os.path.getsize(thumb_path),
                        'dimensions': thumbnail.size
                    })
                    
                    logger.info(f"Generated thumbnail: {size} -> {thumbnail.size}")
                
            except Exception as e:
                logger.warning(f"Failed to generate thumbnail {size}: {e}")
        
        return thumbnails
    
    def get_optimization_recommendations(
        self, 
        image_size: Tuple[int, int],
        file_size: int,
        use_case: str = 'web'
    ) -> Dict[str, Any]:
        """Get optimization recommendations based on image characteristics."""
        width, height = image_size
        megapixels = (width * height) / 1_000_000
        
        recommendations = {
            'quality_profile': 'web_optimized',
            'should_downscale': False,
            'recommended_max_resolution': None,
            'recommended_formats': ['jpeg'],
            'generate_thumbnails': True,
            'strip_metadata': True,
            'reasoning': []
        }
        
        # Size-based recommendations
        if megapixels > 50:  # Very large images
            recommendations['quality_profile'] = 'maximum_compression'
            recommendations['should_downscale'] = True
            recommendations['recommended_max_resolution'] = (6000, 6000)
            recommendations['reasoning'].append('Very large image - aggressive compression recommended')
            
        elif megapixels > 20:  # Large images
            recommendations['quality_profile'] = 'storage_optimized'
            recommendations['should_downscale'] = True
            recommendations['recommended_max_resolution'] = (4000, 4000)
            recommendations['reasoning'].append('Large image - storage optimization recommended')
            
        elif megapixels < 1:  # Small images
            recommendations['quality_profile'] = 'high_quality'
            recommendations['generate_thumbnails'] = False
            recommendations['reasoning'].append('Small image - preserve quality')
        
        # Use case specific
        if use_case == 'archive':
            recommendations['quality_profile'] = 'maximum_compression'
            recommendations['strip_metadata'] = False
            recommendations['reasoning'].append('Archive use - prioritize compression over metadata')
            
        elif use_case == 'web':
            recommendations['recommended_formats'] = ['webp', 'jpeg']
            recommendations['reasoning'].append('Web use - modern formats preferred')
            
        elif use_case == 'print':
            recommendations['quality_profile'] = 'high_quality'
            recommendations['should_downscale'] = False
            recommendations['reasoning'].append('Print use - preserve resolution and quality')
        
        return recommendations
