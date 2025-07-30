"""
ZIP file handler for extracting and processing multiple PSD files.
Handles ZIP extraction, validation, and batch processing coordination.
"""

import os
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from converter import PSDConverter
from utils import ensure_directory, get_file_hash, cleanup_directory

logger = logging.getLogger(__name__)


class ZipHandler:
    """Handles ZIP file extraction and batch PSD processing."""
    
    def __init__(self, max_workers: int = 4):
        self.converter = PSDConverter()
        self.max_workers = max_workers
        self.supported_extensions = ['.psd']
        self.max_zip_size = 500 * 1024 * 1024  # 500MB limit
        self.max_files_per_zip = 100  # Limit number of files
    
    def extract_and_process_zip(
        self,
        zip_file_path: str,
        output_directory: str,
        quality: int = 75,
        output_format: str = 'jpeg',
        callback=None
    ) -> Dict[str, Any]:
        """
        Extract ZIP file and process all PSD files within it.
        
        Args:
            zip_file_path: Path to the ZIP file
            output_directory: Directory for converted files
            quality: Compression quality for output
            output_format: Output image format
            callback: Progress callback function
            
        Returns:
            Dictionary with processing results and statistics
        """
        temp_dir = None
        try:
            logger.info(f"Processing ZIP file: {zip_file_path}")
            
            # Validate ZIP file
            validation_result = self._validate_zip_file(zip_file_path)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': validation_result['error'],
                    'zip_file': zip_file_path
                }
            
            # Create temporary directory for extraction
            temp_dir = tempfile.mkdtemp(prefix='psd_zip_')
            
            # Extract ZIP file
            extracted_files = self._extract_zip(zip_file_path, temp_dir)
            if not extracted_files:
                return {
                    'success': False,
                    'error': 'No PSD files found in ZIP archive',
                    'zip_file': zip_file_path
                }
            
            logger.info(f"Extracted {len(extracted_files)} PSD files from ZIP")
            
            # Ensure output directory exists
            ensure_directory(output_directory)
            
            # Process files concurrently
            results = self._process_files_concurrent(
                extracted_files,
                output_directory,
                quality,
                output_format,
                callback
            )
            
            # Generate summary statistics
            summary = self._generate_summary(results, zip_file_path)
            
            return summary
            
        except Exception as e:
            logger.error(f"Error processing ZIP file {zip_file_path}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'zip_file': zip_file_path
            }
        finally:
            # Cleanup temporary directory
            if temp_dir and os.path.exists(temp_dir):
                cleanup_directory(temp_dir)
    
    def _validate_zip_file(self, zip_file_path: str) -> Dict[str, Any]:
        """
        Validate ZIP file before processing.
        
        Args:
            zip_file_path: Path to ZIP file
            
        Returns:
            Validation result dictionary
        """
        try:
            # Check file size
            file_size = os.path.getsize(zip_file_path)
            if file_size > self.max_zip_size:
                return {
                    'valid': False,
                    'error': f'ZIP file too large: {file_size / (1024*1024):.1f}MB (max: {self.max_zip_size / (1024*1024):.1f}MB)'
                }
            
            # Test ZIP file integrity
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                # Test the ZIP file
                test_result = zip_ref.testzip()
                if test_result:
                    return {
                        'valid': False,
                        'error': f'Corrupted ZIP file: {test_result}'
                    }
                
                # Count PSD files
                psd_files = [f for f in zip_ref.namelist() 
                           if f.lower().endswith('.psd') and not f.startswith('__MACOSX/')]
                
                if len(psd_files) == 0:
                    return {
                        'valid': False,
                        'error': 'No PSD files found in ZIP archive'
                    }
                
                if len(psd_files) > self.max_files_per_zip:
                    return {
                        'valid': False,
                        'error': f'Too many files: {len(psd_files)} (max: {self.max_files_per_zip})'
                    }
                
                return {
                    'valid': True,
                    'psd_count': len(psd_files),
                    'total_files': len(zip_ref.namelist())
                }
                
        except zipfile.BadZipFile:
            return {
                'valid': False,
                'error': 'Invalid ZIP file format'
            }
        except Exception as e:
            return {
                'valid': False,
                'error': f'Validation error: {str(e)}'
            }
    
    def _extract_zip(self, zip_file_path: str, extract_dir: str) -> List[str]:
        """
        Extract and validate PSD files from ZIP archive.
        
        Args:
            zip_file_path: Path to ZIP file
            extract_dir: Directory to extract files to
            
        Returns:
            List of extracted and validated PSD file paths
        """
        extracted_files = []
        
        try:
            logger.info(f"Extracting ZIP file: {zip_file_path}")
            
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                # Get all file infos and filter PSD files
                all_files = zip_ref.infolist()
                psd_files = [f for f in all_files if self._is_valid_psd_entry(f)]
                
                logger.info(f"Found {len(psd_files)} PSD files in {len(all_files)} total files")
                
                for file_info in psd_files:
                    filename = file_info.filename
                    
                    try:
                        # Extract file with sanitized path
                        safe_filename = self._sanitize_extracted_filename(filename)
                        extracted_path = os.path.join(extract_dir, safe_filename)
                        
                        # Ensure subdirectory exists if needed
                        ensure_directory(os.path.dirname(extracted_path))
                        
                        # Extract file content
                        with zip_ref.open(file_info) as source, open(extracted_path, 'wb') as target:
                            shutil.copyfileobj(source, target)
                        
                        # Validate extracted file
                        if self._validate_extracted_psd(extracted_path):
                            extracted_files.append(extracted_path)
                            logger.debug(f"Successfully extracted and validated: {safe_filename}")
                        else:
                            logger.warning(f"Extracted file failed validation: {safe_filename}")
                            if os.path.exists(extracted_path):
                                os.unlink(extracted_path)
                            
                    except Exception as e:
                        logger.error(f"Error extracting {filename}: {str(e)}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error extracting ZIP file: {str(e)}")
            raise
        
        logger.info(f"Successfully extracted {len(extracted_files)} valid PSD files")
        return extracted_files
    
    def _is_valid_psd_entry(self, file_info) -> bool:
        """
        Check if a ZIP entry is a valid PSD file candidate.
        
        Args:
            file_info: ZipInfo object
            
        Returns:
            True if the entry should be processed as a PSD file
        """
        filename = file_info.filename
        
        # Skip directories
        if file_info.is_dir():
            return False
        
        # Skip system files and hidden files
        if (filename.startswith('__MACOSX/') or
            filename.startswith('.') or
            '/.DS_Store' in filename or
            '/Thumbs.db' in filename.lower()):
            return False
        
        # Check file extension
        if not filename.lower().endswith('.psd'):
            return False
        
        # Check file size (avoid processing tiny files that are likely corrupted)
        if file_info.file_size < 1024:  # Less than 1KB
            logger.warning(f"Skipping tiny file: {filename} ({file_info.file_size} bytes)")
            return False
        
        return True
    
    def _sanitize_extracted_filename(self, filename: str) -> str:
        """
        Sanitize extracted filename to prevent directory traversal and naming issues.
        
        Args:
            filename: Original filename from ZIP
            
        Returns:
            Safe filename for extraction
        """
        # Remove directory path and keep only filename
        safe_name = os.path.basename(filename)
        
        # Replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            safe_name = safe_name.replace(char, '_')
        
        # Ensure filename is not empty
        if not safe_name or safe_name == '.psd':
            safe_name = f"extracted_{len(filename)}.psd"
        
        return safe_name
    
    def _validate_extracted_psd(self, file_path: str) -> bool:
        """
        Validate that an extracted file is a proper PSD file.
        
        Args:
            file_path: Path to extracted file
            
        Returns:
            True if file is a valid PSD
        """
        try:
            # Check file exists and has content
            if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                return False
            
            # Check PSD signature (first 4 bytes should be "8BPS")
            with open(file_path, 'rb') as f:
                signature = f.read(4)
                if signature != b'8BPS':
                    logger.warning(f"Invalid PSD signature in {file_path}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating PSD file {file_path}: {str(e)}")
            return False
    
    def _process_files_concurrent(
        self,
        psd_files: List[str],
        output_directory: str,
        quality: int,
        output_format: str,
        callback=None
    ) -> List[Dict[str, Any]]:
        """
        Process multiple PSD files concurrently.
        
        Args:
            psd_files: List of PSD file paths
            output_directory: Output directory
            quality: Image quality
            output_format: Output format
            callback: Progress callback
            
        Returns:
            List of conversion results
        """
        results = []
        total_files = len(psd_files)
        completed = 0
        
        # Use ThreadPoolExecutor for concurrent processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all conversion tasks
            future_to_file = {}
            for psd_file in psd_files:
                # Generate output filename
                base_name = Path(psd_file).stem
                extension = 'jpg' if output_format == 'jpeg' else output_format
                output_file = os.path.join(output_directory, f"{base_name}.{extension}")
                
                # Submit conversion task
                future = executor.submit(
                    self.converter.convert_psd_to_image,
                    psd_file,
                    output_file,
                    quality,
                    output_format
                )
                future_to_file[future] = psd_file
            
            # Collect results as they complete
            for future in as_completed(future_to_file):
                psd_file = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1
                    
                    # Call progress callback
                    if callback:
                        progress = (completed / total_files) * 100
                        callback(progress, completed, total_files, result)
                        
                except Exception as e:
                    logger.error(f"Error processing {psd_file}: {str(e)}")
                    results.append({
                        'success': False,
                        'input_file': psd_file,
                        'error': str(e)
                    })
                    completed += 1
        
        return results
    
    def _generate_summary(self, results: List[Dict[str, Any]], zip_file_path: str) -> Dict[str, Any]:
        """
        Generate processing summary from results.
        
        Args:
            results: List of conversion results
            zip_file_path: Original ZIP file path
            
        Returns:
            Summary dictionary
        """
        successful_results = [r for r in results if r.get('success', False)]
        failed_results = [r for r in results if not r.get('success', False)]
        
        total_original_size = sum(r.get('original_size', 0) for r in successful_results)
        total_converted_size = sum(r.get('converted_size', 0) for r in successful_results)
        
        overall_compression = 0
        if total_original_size > 0:
            overall_compression = (1 - total_converted_size / total_original_size) * 100
        
        summary = {
            'success': len(failed_results) == 0,
            'zip_file': zip_file_path,
            'total_files': len(results),
            'successful_conversions': len(successful_results),
            'failed_conversions': len(failed_results),
            'total_original_size': total_original_size,
            'total_converted_size': total_converted_size,
            'overall_compression_ratio': round(overall_compression, 2),
            'results': results
        }
        
        if failed_results:
            summary['errors'] = [r.get('error', 'Unknown error') for r in failed_results]
        
        logger.info(f"ZIP processing complete: {len(successful_results)}/{len(results)} files converted")
        
        return summary
    
    def get_zip_info(self, zip_file_path: str) -> Dict[str, Any]:
        """
        Get information about a ZIP file without extracting it.
        
        Args:
            zip_file_path: Path to ZIP file
            
        Returns:
            ZIP file information
        """
        try:
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                all_files = zip_ref.namelist()
                psd_files = [f for f in all_files if f.lower().endswith('.psd')]
                
                total_size = sum(info.file_size for info in zip_ref.infolist())
                compressed_size = sum(info.compress_size for info in zip_ref.infolist())
                
                return {
                    'total_files': len(all_files),
                    'psd_files': len(psd_files),
                    'total_size': total_size,
                    'compressed_size': compressed_size,
                    'compression_ratio': (1 - compressed_size / total_size) * 100 if total_size > 0 else 0,
                    'psd_filenames': [Path(f).name for f in psd_files]
                }
                
        except Exception as e:
            logger.error(f"Error getting ZIP info: {str(e)}")
            return {'error': str(e)}
