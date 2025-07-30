"""
Storage management for converted files and job results.
Handles file storage, organization, and optional cloud upload.
"""

import os
import shutil
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
import json
import tempfile

from utils import ensure_directory, get_file_hash, cleanup_directory

logger = logging.getLogger(__name__)


class StorageManager:
    """Manages file storage for conversion results."""
    
    def __init__(self, base_storage_path: str = None):
        # Default storage path
        if base_storage_path is None:
            base_storage_path = os.path.join(os.getcwd(), 'storage')
        
        self.base_storage_path = base_storage_path
        self.jobs_dir = os.path.join(base_storage_path, 'jobs')
        self.downloads_dir = os.path.join(base_storage_path, 'downloads')
        self.metadata_dir = os.path.join(base_storage_path, 'metadata')
        
        # Create storage directories
        for directory in [self.jobs_dir, self.downloads_dir, self.metadata_dir]:
            ensure_directory(directory)
        
        # Storage configuration
        self.max_storage_size = 10 * 1024 * 1024 * 1024  # 10GB limit
        self.compress_results = True
        self.keep_individual_files = True
    
    async def store_job_results(
        self,
        job_id: str,
        source_directory: str
    ) -> Dict[str, Any]:
        """
        Store conversion results for a job.
        
        Args:
            job_id: Unique job identifier
            source_directory: Directory containing converted files
            
        Returns:
            Storage result information
        """
        try:
            logger.info(f"Storing results for job {job_id}")
            
            # Create job storage directory
            job_storage_dir = os.path.join(self.jobs_dir, job_id)
            ensure_directory(job_storage_dir)
            
            # Get list of files to store
            files_to_store = self._get_files_in_directory(source_directory)
            
            if not files_to_store:
                raise ValueError("No files to store")
            
            # Copy files to job storage
            stored_files = []
            total_size = 0
            
            for file_path in files_to_store:
                filename = os.path.basename(file_path)
                dest_path = os.path.join(job_storage_dir, filename)
                
                shutil.copy2(file_path, dest_path)
                file_size = os.path.getsize(dest_path)
                total_size += file_size
                
                file_info = {
                    'filename': filename,
                    'path': dest_path,
                    'size': file_size,
                    'hash': get_file_hash(dest_path),
                    'stored_at': datetime.now().isoformat()
                }
                stored_files.append(file_info)
            
            # Create downloadable archive if multiple files
            archive_path = None
            if len(stored_files) > 1:
                archive_path = await self._create_download_archive(job_id, stored_files)
            
            # Generate metadata
            metadata = {
                'job_id': job_id,
                'stored_at': datetime.now().isoformat(),
                'total_files': len(stored_files),
                'total_size': total_size,
                'files': stored_files,
                'archive_path': archive_path,
                'storage_directory': job_storage_dir
            }
            
            # Save metadata
            metadata_path = os.path.join(self.metadata_dir, f"{job_id}.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Stored {len(stored_files)} files for job {job_id} ({total_size} bytes)")
            
            return {
                'success': True,
                'job_id': job_id,
                'total_files': len(stored_files),
                'total_size': total_size,
                'files': stored_files,
                'archive_available': archive_path is not None,
                'download_url': f"/download/{job_id}"
            }
            
        except Exception as e:
            logger.error(f"Error storing job results for {job_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_files_in_directory(self, directory: str) -> List[str]:
        """Get list of files in directory."""
        files = []
        
        if not os.path.exists(directory):
            return files
        
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if os.path.isfile(item_path):
                files.append(item_path)
        
        return files
    
    async def _create_download_archive(
        self,
        job_id: str,
        stored_files: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Create a downloadable ZIP archive of all converted files.
        
        Args:
            job_id: Job identifier
            stored_files: List of stored file information
            
        Returns:
            Path to created archive or None
        """
        try:
            archive_filename = f"{job_id}_converted.zip"
            archive_path = os.path.join(self.downloads_dir, archive_filename)
            
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for file_info in stored_files:
                    file_path = file_info['path']
                    filename = file_info['filename']
                    
                    if os.path.exists(file_path):
                        zip_file.write(file_path, filename)
            
            logger.info(f"Created download archive: {archive_path}")
            return archive_path
            
        except Exception as e:
            logger.error(f"Error creating download archive for {job_id}: {str(e)}")
            return None
    
    def get_download_info(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get download information for a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Download information or None if not found
        """
        try:
            metadata_path = os.path.join(self.metadata_dir, f"{job_id}.json")
            
            if not os.path.exists(metadata_path):
                return None
            
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Check if files still exist
            available_files = []
            for file_info in metadata.get('files', []):
                if os.path.exists(file_info['path']):
                    available_files.append(file_info)
            
            if not available_files:
                return None
            
            # Check archive availability
            archive_available = False
            archive_path = metadata.get('archive_path')
            if archive_path and os.path.exists(archive_path):
                archive_available = True
            
            return {
                'job_id': job_id,
                'total_files': len(available_files),
                'total_size': sum(f['size'] for f in available_files),
                'files': available_files,
                'archive_available': archive_available,
                'archive_path': archive_path if archive_available else None,
                'stored_at': metadata.get('stored_at')
            }
            
        except Exception as e:
            logger.error(f"Error getting download info for {job_id}: {str(e)}")
            return None
    
    def get_file_path(self, job_id: str, filename: str) -> Optional[str]:
        """
        Get the path to a specific file for a job.
        
        Args:
            job_id: Job identifier
            filename: Name of the file
            
        Returns:
            File path or None if not found
        """
        try:
            download_info = self.get_download_info(job_id)
            if not download_info:
                return None
            
            for file_info in download_info['files']:
                if file_info['filename'] == filename:
                    return file_info['path']
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting file path for {job_id}/{filename}: {str(e)}")
            return None
    
    def get_archive_path(self, job_id: str) -> Optional[str]:
        """
        Get the path to the download archive for a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Archive path or None if not available
        """
        try:
            download_info = self.get_download_info(job_id)
            if download_info and download_info.get('archive_available'):
                return download_info.get('archive_path')
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting archive path for {job_id}: {str(e)}")
            return None
    
    async def cleanup_job_files(self, job_id: str) -> bool:
        """
        Clean up all files associated with a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if cleanup was successful
        """
        try:
            logger.info(f"Cleaning up files for job {job_id}")
            
            # Remove job storage directory
            job_storage_dir = os.path.join(self.jobs_dir, job_id)
            if os.path.exists(job_storage_dir):
                cleanup_directory(job_storage_dir)
            
            # Remove download archive
            archive_filename = f"{job_id}_converted.zip"
            archive_path = os.path.join(self.downloads_dir, archive_filename)
            if os.path.exists(archive_path):
                os.unlink(archive_path)
            
            # Remove metadata
            metadata_path = os.path.join(self.metadata_dir, f"{job_id}.json")
            if os.path.exists(metadata_path):
                os.unlink(metadata_path)
            
            logger.info(f"Successfully cleaned up files for job {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning up job {job_id}: {str(e)}")
            return False
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage usage statistics.
        
        Returns:
            Storage statistics
        """
        try:
            total_size = 0
            total_files = 0
            job_count = 0
            
            # Calculate jobs directory size
            if os.path.exists(self.jobs_dir):
                for job_dir in os.listdir(self.jobs_dir):
                    job_path = os.path.join(self.jobs_dir, job_dir)
                    if os.path.isdir(job_path):
                        job_count += 1
                        for file in os.listdir(job_path):
                            file_path = os.path.join(job_path, file)
                            if os.path.isfile(file_path):
                                total_size += os.path.getsize(file_path)
                                total_files += 1
            
            # Add downloads directory size
            if os.path.exists(self.downloads_dir):
                for file in os.listdir(self.downloads_dir):
                    file_path = os.path.join(self.downloads_dir, file)
                    if os.path.isfile(file_path):
                        total_size += os.path.getsize(file_path)
            
            return {
                'total_size': total_size,
                'total_files': total_files,
                'job_count': job_count,
                'max_storage_size': self.max_storage_size,
                'usage_percentage': (total_size / self.max_storage_size) * 100,
                'storage_path': self.base_storage_path
            }
            
        except Exception as e:
            logger.error(f"Error getting storage stats: {str(e)}")
            return {'error': str(e)}
    
    async def optimize_storage(self) -> Dict[str, Any]:
        """
        Optimize storage by removing old or duplicate files.
        
        Returns:
            Optimization results
        """
        try:
            logger.info("Starting storage optimization")
            
            # This is a placeholder for storage optimization logic
            # Could include:
            # - Removing old files
            # - Deduplicating identical files
            # - Compressing archives
            # - Moving files to cheaper storage tiers
            
            stats_before = self.get_storage_stats()
            
            # Implement optimization logic here
            
            stats_after = self.get_storage_stats()
            
            return {
                'success': True,
                'before': stats_before,
                'after': stats_after,
                'space_freed': stats_before.get('total_size', 0) - stats_after.get('total_size', 0)
            }
            
        except Exception as e:
            logger.error(f"Error optimizing storage: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
