"""
Enhanced background task management with improved concurrency handling.
Supports threading, multiprocessing, and scalable task execution.
"""

import asyncio
import concurrent.futures
import multiprocessing as mp
import queue
import threading
import time
import os
import tempfile
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, Callable, Union, Tuple
import logging
from datetime import datetime

from utils import cleanup_directory

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Job execution status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobInfo:
    """Information about a job."""
    id: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    error_message: Optional[str] = None
    result: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = None


class TaskManager:
    """Base task manager class."""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.jobs: Dict[str, JobInfo] = {}
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status information."""
        if job_id not in self.jobs:
            return None
        
        job = self.jobs[job_id]
        return {
            "job_id": job_id,
            "status": job.status.value,
            "progress": job.progress,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_message": job.error_message,
            "result": job.result,
            "metadata": job.metadata
        }
    
    def _update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: Optional[float] = None,
        error_message: Optional[str] = None,
        result: Optional[Any] = None
    ):
        """Update job status."""
        if job_id in self.jobs:
            job = self.jobs[job_id]
            job.status = status
            if progress is not None:
                job.progress = progress
            if error_message:
                job.error_message = error_message
            if result is not None:
                job.result = result
            
            if status == JobStatus.PROCESSING and not job.started_at:
                job.started_at = datetime.now()
            elif status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                job.completed_at = datetime.now()


class ConcurrencyMode(Enum):
    """Concurrency execution modes."""
    THREADING = "threading"
    MULTIPROCESSING = "multiprocessing"
    ASYNC = "async"
    HYBRID = "hybrid"


@dataclass
class TaskConfig:
    """Configuration for task execution."""
    max_workers: int = 4
    concurrency_mode: ConcurrencyMode = ConcurrencyMode.THREADING
    timeout_seconds: int = 300  # 5 minutes
    queue_size: int = 100
    batch_size: int = 1
    enable_monitoring: bool = True


class EnhancedTaskManager(TaskManager):
    """Enhanced task manager with advanced concurrency support."""
    
    def __init__(self, config: TaskConfig = None):
        if config is None:
            config = TaskConfig()
        
        self.config = config
        super().__init__(max_workers=config.max_workers)
        
        # Initialize required components
        from storage import StorageManager
        from converter import PSDConverter
        self.storage_manager = StorageManager()
        self.converter = PSDConverter()
        
        # Additional executors
        self.process_executor = None
        self.task_queue = asyncio.Queue(maxsize=config.queue_size)
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.task_metrics = {
            'total_submitted': 0,
            'total_completed': 0,
            'total_failed': 0,
            'active_count': 0,
            'queue_size': 0
        }
        
        # Initialize executors based on configuration
        self._init_executors()
        
        # Start task processing workers
        self._start_workers()
    
    def _init_executors(self):
        """Initialize executors based on configuration."""
        if self.config.concurrency_mode in [ConcurrencyMode.MULTIPROCESSING, ConcurrencyMode.HYBRID]:
            # Use fewer processes than cores to avoid overwhelming the system
            max_processes = min(self.config.max_workers, mp.cpu_count() - 1)
            self.process_executor = ProcessPoolExecutor(max_workers=max_processes)
            logger.info(f"Initialized ProcessPoolExecutor with {max_processes} workers")
        
        logger.info(f"Initialized ThreadPoolExecutor with {self.config.max_workers} workers")
    
    def _start_workers(self):
        """Start background workers for task processing."""
        # Background tasks will be started when the first task is submitted
        self._background_tasks_started = False
        self._cleanup_task_started = False
    
    async def _ensure_background_tasks_started(self):
        """Ensure background tasks are started (called when first task is submitted)."""
        if not self._background_tasks_started and self.config.enable_monitoring:
            asyncio.create_task(self._monitor_tasks())
            self._background_tasks_started = True
    
    def _ensure_cleanup_task_started(self):
        """Ensure cleanup task is started for old job cleanup."""
        if not self._cleanup_task_started:
            # Start a background task to clean up old job files periodically
            asyncio.create_task(self._cleanup_old_jobs())
            self._cleanup_task_started = True
    
    async def _cleanup_old_jobs(self):
        """Background task to clean up old job files and metadata."""
        while True:
            try:
                # Wait 1 hour between cleanup cycles
                await asyncio.sleep(3600)
                
                # Clean up jobs older than 24 hours
                cutoff_time = datetime.now() - timedelta(hours=24)
                
                # Get storage manager to clean up old files
                from storage import StorageManager
                storage = StorageManager()
                
                # Clean up old job directories
                jobs_dir = storage.jobs_dir
                if os.path.exists(jobs_dir):
                    for job_folder in os.listdir(jobs_dir):
                        job_path = os.path.join(jobs_dir, job_folder)
                        if os.path.isdir(job_path):
                            # Check creation time
                            creation_time = datetime.fromtimestamp(os.path.getctime(job_path))
                            if creation_time < cutoff_time:
                                try:
                                    import shutil
                                    shutil.rmtree(job_path)
                                    logger.info(f"Cleaned up old job directory: {job_folder}")
                                except Exception as e:
                                    logger.warning(f"Failed to clean up job directory {job_folder}: {e}")
                
                logger.debug("Completed cleanup cycle for old jobs")
                
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                # Continue running even if cleanup fails
                await asyncio.sleep(3600)
    
    async def _save_file_content(self, file_content: bytes, filename: str) -> str:
        """Save file content to a temporary file and return the path."""
        import tempfile
        
        # Get file extension
        file_extension = filename.lower().split('.')[-1]
        suffix = f".{file_extension}"
        
        # Create temporary file
        fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=f"upload_{int(time.time())}_")
        
        try:
            with os.fdopen(fd, 'wb') as temp_file:
                temp_file.write(file_content)
            
            logger.debug(f"Saved file content to temporary path: {temp_path}")
            return temp_path
            
        except Exception as e:
            # Clean up on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise Exception(f"Failed to save file content: {e}")
    
    async def submit_task(
        self,
        job_id: str,
        task_func: Callable,
        *args,
        priority: int = 0,
        **kwargs
    ) -> None:
        """
        Submit a task for background execution with priority support.
        
        Args:
            job_id: Unique job identifier
            task_func: Function to execute
            priority: Task priority (higher = more important)
            *args, **kwargs: Arguments for task_func
        """
        try:
            # Ensure background tasks are started
            await self._ensure_background_tasks_started()
            
            task_item = {
                'job_id': job_id,
                'func': task_func,
                'args': args,
                'kwargs': kwargs,
                'priority': priority,
                'submitted_at': time.time()
            }
            
            await self.task_queue.put(task_item)
            self.task_metrics['total_submitted'] += 1
            self.task_metrics['queue_size'] = self.task_queue.qsize()
            
            logger.debug(f"Task {job_id} submitted to queue (priority: {priority})")
            
        except asyncio.QueueFull:
            logger.error(f"Task queue full, rejecting task {job_id}")
            raise Exception("Task queue is full, please try again later")
    
    async def process_upload_enhanced(
        self,
        job_id: str,
        file_content: bytes,
        filename: str,
        quality: int = 75,
        output_format: str = 'jpeg',
        priority: int = 0,
        optimize_storage: bool = True,
        quality_profile: str = 'storage_optimized',
        max_resolution: Optional[Tuple[int, int]] = None,
        strip_metadata: bool = True,
        generate_thumbnails: bool = True,
        use_case: str = 'web',
        enable_deduplication: bool = True
    ) -> None:
        """
        Enhanced upload processing with improved concurrency, storage optimization, and deduplication.
        
        Args:
            job_id: Unique job identifier
            file_content: Raw file content
            filename: Original filename
            quality: Compression quality
            output_format: Output format
            priority: Task priority
            optimize_storage: Enable advanced storage optimization
            quality_profile: Quality profile for optimization
            max_resolution: Maximum resolution (width, height)
            strip_metadata: Remove metadata
            generate_thumbnails: Create thumbnails
            use_case: Optimization use case
            enable_deduplication: Enable perceptual hash deduplication
        """
        # Store optimization parameters for use in processing
        optimization_params = {
            'optimize_storage': optimize_storage,
            'quality_profile': quality_profile,
            'max_resolution': max_resolution,
            'strip_metadata': strip_metadata,
            'generate_thumbnails': generate_thumbnails,
            'use_case': use_case,
            'enable_deduplication': enable_deduplication
        }
        # Determine processing strategy based on file size and type
        file_size = len(file_content)
        file_extension = filename.lower().split('.')[-1]
        
        # Large files or CPU-intensive tasks use multiprocessing
        if (file_size > 50 * 1024 * 1024 or  # >50MB
            self.config.concurrency_mode == ConcurrencyMode.MULTIPROCESSING):
            await self._process_with_multiprocessing(
                job_id, file_content, filename, quality, output_format, optimization_params
            )
        # Medium files use threading
        elif self.config.concurrency_mode == ConcurrencyMode.THREADING:
            await self._process_with_threading(
                job_id, file_content, filename, quality, output_format, optimization_params
            )
        # Small files or I/O intensive use async
        else:
            await self.process_upload_with_optimization(
                job_id, file_content, filename, quality, output_format, optimization_params
            )
    
    async def _process_with_threading(
        self,
        job_id: str,
        file_content: bytes,
        filename: str,
        quality: int,
        output_format: str,
        optimization_params: Dict[str, Any]
    ) -> None:
        """Process task using ThreadPoolExecutor."""
        loop = asyncio.get_event_loop()
        
        try:
            # Run the blocking operation in a thread
            await loop.run_in_executor(
                self.executor,
                self._sync_process_upload_optimized,
                job_id, file_content, filename, quality, output_format, optimization_params
            )
        except Exception as e:
            logger.error(f"Threading execution failed for job {job_id}: {e}")
            self._update_job_status(job_id, JobStatus.FAILED, error_message=str(e))
    
    async def _process_with_multiprocessing(
        self,
        job_id: str,
        file_content: bytes,
        filename: str,
        quality: int,
        output_format: str,
        optimization_params: Dict
    ) -> None:
        """Process task using ProcessPoolExecutor for CPU-intensive work."""
        if not self.process_executor:
            logger.warning("Process executor not available, falling back to threading")
            await self._process_with_threading(job_id, file_content, filename, quality, output_format, optimization_params)
            return
        
        loop = asyncio.get_event_loop()
        
        try:
            # Run the CPU-intensive operation in a separate process
            await loop.run_in_executor(
                self.process_executor,
                process_psd_in_subprocess,
                job_id, file_content, filename, quality, output_format, optimization_params
            )
        except Exception as e:
            logger.error(f"Multiprocessing execution failed for job {job_id}: {e}")
            self._update_job_status(job_id, JobStatus.FAILED, error_message=str(e))
    
    def _sync_process_upload_optimized(
        self,
        job_id: str,
        file_content: bytes,
        filename: str,
        quality: int,
        output_format: str,
        optimization_params: Dict[str, Any]
    ) -> None:
        """Synchronous version of optimized process_upload for executor use."""
        # Create a new event loop for this thread
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self.process_upload_with_optimization(
                    job_id, file_content, filename, quality, output_format, optimization_params
                )
            )
        finally:
            loop.close()
    
    async def process_upload_with_optimization(
        self,
        job_id: str,
        file_content: bytes,
        filename: str,
        quality: int = 75,
        output_format: str = 'jpeg',
        optimization_params: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Process uploaded file content with advanced storage optimization.
        
        Args:
            job_id: Unique job identifier
            file_content: Raw file content as bytes
            filename: Original filename
            quality: Compression quality
            output_format: Output image format
            optimization_params: Storage optimization parameters
        """
        temp_input_path = None
        temp_output_dir = None
        
        try:
            # Default optimization parameters
            if optimization_params is None:
                optimization_params = {
                    'optimize_storage': True,
                    'quality_profile': 'storage_optimized',
                    'max_resolution': None,
                    'strip_metadata': True,
                    'generate_thumbnails': True,
                    'use_case': 'web'
                }
            
            # Ensure cleanup task is running
            self._ensure_cleanup_task_started()
            
            # Initialize job
            file_extension = filename.lower().split('.')[-1]
            job_info = JobInfo(
                id=job_id,
                status=JobStatus.PENDING,
                created_at=datetime.now(),
                metadata={
                    'filename': filename,
                    'file_type': file_extension,
                    'quality': quality,
                    'output_format': output_format,
                    'optimization_params': optimization_params
                }
            )
            self.jobs[job_id] = job_info
            
            logger.info(f"Starting optimized job {job_id} for file: {filename}")
            logger.info(f"Optimization params: {optimization_params}")
            
            # Save file content to temporary location
            temp_input_path = await self._save_file_content(file_content, filename)
            
            # Create temporary output directory
            temp_output_dir = tempfile.mkdtemp(prefix=f'job_{job_id}_')
            
            # Update job status
            self._update_job_status(job_id, JobStatus.PROCESSING, progress=0.0)
            
            # Process based on file type with optimization
            if file_extension == 'psd':
                await self._process_single_psd_optimized(
                    job_id, temp_input_path, temp_output_dir, 
                    quality, output_format, optimization_params
                )
            elif file_extension == 'zip':
                await self._process_zip_file_optimized(
                    job_id, temp_input_path, temp_output_dir, 
                    quality, output_format, optimization_params
                )
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")
            
            # Store results and update job
            job_info = self.jobs[job_id]
            if job_info.status != JobStatus.FAILED:
                storage_result = await self.storage_manager.store_job_results(
                    job_id, temp_output_dir
                )
                job_info.result = storage_result
                self._update_job_status(job_id, JobStatus.COMPLETED, progress=100.0)
                
                logger.info(f"Optimized job {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Error processing optimized job {job_id}: {str(e)}")
            self._update_job_status(
                job_id, 
                JobStatus.FAILED, 
                error_message=str(e)
            )
        finally:
            # Cleanup temporary files
            if temp_input_path and os.path.exists(temp_input_path):
                os.unlink(temp_input_path)
            if temp_output_dir and os.path.exists(temp_output_dir):
                cleanup_directory(temp_output_dir)
    
    async def _process_single_psd_optimized(
        self,
        job_id: str,
        psd_path: str,
        output_dir: str,
        quality: int,
        output_format: str,
        optimization_params: Dict[str, Any]
    ) -> None:
        """Process a single PSD file with storage optimization."""
        try:
            logger.info(f"Processing single PSD file with optimization: {psd_path}")
            
            # Get file info
            file_size = os.path.getsize(psd_path)
            logger.info(f"PSD file size: {file_size / 1024 / 1024:.1f} MB")
            
            # Determine output filename
            base_name = os.path.splitext(os.path.basename(psd_path))[0]
            output_filename = f"{base_name}.{output_format}"
            output_path = os.path.join(output_dir, output_filename)
            
            logger.info(f"Converting {os.path.basename(psd_path)} -> {output_filename}")
            
            # Update progress
            self._update_job_status(job_id, JobStatus.PROCESSING, progress=20.0)
            
            # Use optimized conversion with deduplication if storage optimization is enabled
            if optimization_params.get('optimize_storage', True):
                # Check if deduplication should be enabled
                enable_dedup = optimization_params.get('enable_deduplication', True)
                
                if enable_dedup and hasattr(self.converter, 'convert_psd_to_image_with_dedup'):
                    # Use deduplication-enabled conversion
                    result = self.converter.convert_psd_to_image_with_dedup(
                        psd_path=psd_path,
                        output_path=output_path,
                        quality=quality,
                        output_format=output_format,
                        quality_profile=optimization_params.get('quality_profile', 'storage_optimized'),
                        max_resolution=optimization_params.get('max_resolution'),
                        strip_metadata=optimization_params.get('strip_metadata', True),
                        generate_thumbnails=optimization_params.get('generate_thumbnails', True),
                        use_case=optimization_params.get('use_case', 'web'),
                        enable_deduplication=True
                    )
                else:
                    # Standard optimized conversion
                    result = self.converter.convert_psd_to_image_optimized(
                        psd_path=psd_path,
                        output_path=output_path,
                        quality=quality,
                        output_format=output_format,
                        quality_profile=optimization_params.get('quality_profile', 'storage_optimized'),
                        max_resolution=optimization_params.get('max_resolution'),
                        strip_metadata=optimization_params.get('strip_metadata', True),
                        generate_thumbnails=optimization_params.get('generate_thumbnails', True),
                        use_case=optimization_params.get('use_case', 'web')
                    )
            else:
                # Fall back to standard conversion
                result = self.converter.convert_psd_to_image(
                    psd_path, output_path, quality, output_format
                )
            
            if not result.get('success', False):
                raise ValueError(f"Conversion failed: {result.get('error', 'Unknown error')}")
            
            # Update progress
            self._update_job_status(job_id, JobStatus.PROCESSING, progress=90.0)
            
            # Log optimization results
            if 'optimization_info' in result:
                opt_info = result['optimization_info']
                logger.info(f"Storage optimization complete:")
                logger.info(f"  - Compression: {opt_info['compression_ratio']:.1f}%")
                logger.info(f"  - Techniques: {opt_info.get('optimization_techniques', [])}")
                logger.info(f"  - Thumbnails: {len(opt_info.get('thumbnails', []))}")
            
            # Log deduplication results
            if 'deduplication_info' in result:
                dedup_info = result['deduplication_info']
                if dedup_info.get('enabled'):
                    logger.info(f"Deduplication results:")
                    logger.info(f"  - Files checked: {dedup_info.get('files_checked', 0)}")
                    logger.info(f"  - Duplicates found: {dedup_info.get('duplicates_found', 0)}")
                    logger.info(f"  - Unique files: {dedup_info.get('unique_files', 0)}")
                else:
                    logger.debug("Deduplication was disabled for this conversion")
                
        except Exception as e:
            logger.error(f"Error processing single PSD in job {job_id}: {str(e)}")
            raise
    
    async def _process_zip_file_optimized(
        self,
        job_id: str,
        zip_path: str,
        output_dir: str,
        quality: int,
        output_format: str,
        optimization_params: Dict[str, Any]
    ) -> None:
        """Process ZIP file containing PSDs with storage optimization."""
        # For now, delegate to the existing ZIP handler with optimization
        # The zip_handler would need to be updated to support optimization params
        try:
            await super()._process_zip_file(job_id, zip_path, output_dir, quality, output_format)
        except AttributeError:
            # Fallback if parent method doesn't exist
            logger.warning("ZIP processing with optimization not yet implemented")
            raise NotImplementedError("ZIP file optimization processing not yet implemented")
    
    def _sync_process_upload(
        self,
        job_id: str,
        file_content: bytes,
        filename: str,
        quality: int,
        output_format: str
    ) -> None:
        """Synchronous version of process_upload for executor use."""
        # Create a new event loop for this thread
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self.process_upload(job_id, file_content, filename, quality, output_format)
            )
        finally:
            loop.close()
    
    async def _monitor_tasks(self):
        """Background task for monitoring system performance."""
        while True:
            try:
                # Update metrics
                self.task_metrics['active_count'] = len(self.active_tasks)
                self.task_metrics['queue_size'] = self.task_queue.qsize()
                
                # Log metrics every 30 seconds
                if self.task_metrics['total_submitted'] > 0:
                    success_rate = (self.task_metrics['total_completed'] / 
                                  self.task_metrics['total_submitted']) * 100
                    
                    logger.info(f"Task Metrics: "
                              f"Active: {self.task_metrics['active_count']}, "
                              f"Queue: {self.task_metrics['queue_size']}, "
                              f"Success Rate: {success_rate:.1f}%")
                
                await asyncio.sleep(30)  # Monitor every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in task monitoring: {e}")
                await asyncio.sleep(60)  # Back off on error
    
    async def batch_process(
        self,
        job_items: list,
        batch_size: int = None
    ) -> Dict[str, Any]:
        """
        Process multiple jobs in batches for improved efficiency.
        
        Args:
            job_items: List of job dictionaries
            batch_size: Number of items per batch
            
        Returns:
            Batch processing results
        """
        if batch_size is None:
            batch_size = self.config.batch_size
        
        results = {'success': [], 'failed': [], 'total': len(job_items)}
        
        # Process in batches
        for i in range(0, len(job_items), batch_size):
            batch = job_items[i:i + batch_size]
            
            # Submit all jobs in batch
            tasks = []
            for item in batch:
                task = asyncio.create_task(
                    self.process_upload_enhanced(**item)
                )
                tasks.append((item['job_id'], task))
            
            # Wait for batch completion
            for job_id, task in tasks:
                try:
                    await task
                    results['success'].append(job_id)
                except Exception as e:
                    logger.error(f"Batch job {job_id} failed: {e}")
                    results['failed'].append({'job_id': job_id, 'error': str(e)})
        
        return results
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get comprehensive system metrics."""
        return {
            'task_metrics': self.task_metrics.copy(),
            'executor_status': {
                'thread_pool_active': not self.executor._shutdown,
                'process_pool_active': (self.process_executor and 
                                      not self.process_executor._shutdown) if self.process_executor else False,
            },
            'configuration': {
                'max_workers': self.config.max_workers,
                'concurrency_mode': self.config.concurrency_mode.value,
                'queue_size': self.config.queue_size,
                'timeout_seconds': self.config.timeout_seconds
            },
            'active_jobs': len(self.jobs),
            'job_statuses': {
                status.value: sum(1 for job in self.jobs.values() if job.status == status)
                for status in JobStatus
            }
        }
    
    async def shutdown(self):
        """Gracefully shutdown all executors and clean up resources."""
        logger.info("Shutting down Enhanced Task Manager...")
        
        # Cancel active tasks
        for task in self.active_tasks.values():
            task.cancel()
        
        # Shutdown executors
        if self.executor:
            self.executor.shutdown(wait=True)
        
        if self.process_executor:
            self.process_executor.shutdown(wait=True)
        
        logger.info("Enhanced Task Manager shutdown complete")


def process_psd_in_subprocess(
    job_id: str,
    file_content: bytes,
    filename: str,
    quality: int,
    output_format: str,
    optimization_params: Dict
) -> None:
    """
    Process PSD conversion in a separate process.
    This function needs to be at module level for multiprocessing.
    """
    import tempfile
    import os
    from converter import PSDConverter
    from storage import StorageManager
    
    temp_input_path = None
    temp_output_dir = None
    
    try:
        # Save file content
        suffix = f".{filename.split('.')[-1]}"
        fd, temp_input_path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, 'wb') as temp_file:
            temp_file.write(file_content)
        
        # Create output directory
        temp_output_dir = tempfile.mkdtemp(prefix=f'job_{job_id}_')
        
        # Convert PSD with optimization
        converter = PSDConverter()
        output_path = os.path.join(temp_output_dir, f"{os.path.splitext(filename)[0]}.{output_format}")
        
        # Use optimized conversion if optimization_params are provided
        if optimization_params and optimization_params.get('optimize_storage', False):
            converter.convert_psd_to_image_optimized(
                temp_input_path,
                output_path,
                output_format,
                quality,
                **optimization_params
            )
        else:
            converter.convert_psd_to_image(
                temp_input_path,
                output_path,
                output_format,
                quality
            )
        
        # Store results
        storage_manager = StorageManager()
        # Note: This is a simplified version for subprocess execution
        # In practice, you'd need to coordinate with the main process
        
        logger.info(f"Subprocess completed job {job_id}")
        
    except Exception as e:
        logger.error(f"Subprocess error for job {job_id}: {e}")
        raise
    finally:
        # Cleanup
        if temp_input_path and os.path.exists(temp_input_path):
            os.unlink(temp_input_path)
        if temp_output_dir and os.path.exists(temp_output_dir):
            import shutil
            shutil.rmtree(temp_output_dir, ignore_errors=True)
