"""
Step 10: Deduplication system using perceptual hashing.
Detects and prevents storing duplicate images using pHash.
"""

import os
import json
import hashlib
import logging
from typing import Dict, List, Optional, Tuple, Set
from pathlib import Path
from datetime import datetime, timedelta

import imagehash
from PIL import Image

logger = logging.getLogger(__name__)


class DuplicationDetector:
    """
    Advanced deduplication system using perceptual hashing.
    
    Features:
    - pHash (perceptual hash) for visual similarity detection
    - Hash-based filename generation
    - Duplicate detection with similarity thresholds
    - Hash database management
    - Collision handling and resolution
    """
    
    def __init__(self, hash_db_path: str = None, similarity_threshold: int = 5):
        """
        Initialize the deduplication system.
        
        Args:
            hash_db_path: Path to store hash database
            similarity_threshold: Hamming distance threshold for duplicates (0-64)
        """
        self.similarity_threshold = similarity_threshold
        self.hash_db_path = hash_db_path or "/tmp/hash_database.json"
        self.hash_database = self._load_hash_database()
        
        # Statistics
        self.stats = {
            'total_processed': 0,
            'duplicates_found': 0,
            'unique_images': 0,
            'hash_collisions': 0
        }
        
        logger.info(f"Deduplication system initialized with threshold: {similarity_threshold}")
    
    def _load_hash_database(self) -> Dict:
        """Load the hash database from disk."""
        try:
            if os.path.exists(self.hash_db_path):
                with open(self.hash_db_path, 'r') as f:
                    db = json.load(f)
                    logger.info(f"Loaded hash database with {len(db.get('hashes', {}))} entries")
                    return db
        except Exception as e:
            logger.warning(f"Could not load hash database: {e}")
        
        # Return empty database structure
        return {
            'hashes': {},  # phash_str -> image_info
            'created_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            'version': '1.0'
        }
    
    def _save_hash_database(self) -> None:
        """Save the hash database to disk."""
        try:
            self.hash_database['last_updated'] = datetime.now().isoformat()
            self.hash_database['stats'] = self.stats
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.hash_db_path), exist_ok=True)
            
            with open(self.hash_db_path, 'w') as f:
                json.dump(self.hash_database, f, indent=2)
                
            logger.debug(f"Hash database saved to {self.hash_db_path}")
            
        except Exception as e:
            logger.error(f"Failed to save hash database: {e}")
    
    def generate_perceptual_hash(self, image_path: str) -> Tuple[str, Dict]:
        """
        Generate perceptual hash for an image.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Tuple of (hash_string, hash_info)
        """
        try:
            # Open image
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Generate multiple hash types for better accuracy
                phash = imagehash.phash(img, hash_size=8)
                ahash = imagehash.average_hash(img, hash_size=8)
                dhash = imagehash.dhash(img, hash_size=8)
                whash = imagehash.whash(img, hash_size=8)
                
                # Primary hash (pHash) as string
                primary_hash = str(phash)
                
                # Hash information
                hash_info = {
                    'phash': str(phash),
                    'ahash': str(ahash),
                    'dhash': str(dhash),
                    'whash': str(whash),
                    'image_size': img.size,
                    'image_mode': img.mode,
                    'file_size': os.path.getsize(image_path),
                    'created_at': datetime.now().isoformat(),
                    'source_path': image_path
                }
                
                logger.debug(f"Generated hashes for {os.path.basename(image_path)}: {primary_hash}")
                return primary_hash, hash_info
                
        except Exception as e:
            logger.error(f"Failed to generate hash for {image_path}: {e}")
            raise
    
    def calculate_hash_distance(self, hash1: str, hash2: str) -> int:
        """
        Calculate Hamming distance between two hashes.
        
        Args:
            hash1: First hash string
            hash2: Second hash string
            
        Returns:
            Hamming distance (0 = identical, 64 = completely different)
        """
        try:
            # Convert hex strings to imagehash objects for comparison
            h1 = imagehash.hex_to_hash(hash1)
            h2 = imagehash.hex_to_hash(hash2)
            return h1 - h2
        except Exception as e:
            logger.error(f"Failed to calculate hash distance: {e}")
            return 64  # Maximum distance on error
    
    def find_similar_images(self, target_hash: str) -> List[Tuple[str, int, Dict]]:
        """
        Find images similar to the target hash.
        
        Args:
            target_hash: Hash to search for
            
        Returns:
            List of (hash, distance, image_info) tuples for similar images
        """
        similar_images = []
        
        for stored_hash, image_info in self.hash_database['hashes'].items():
            distance = self.calculate_hash_distance(target_hash, stored_hash)
            
            if distance <= self.similarity_threshold:
                similar_images.append((stored_hash, distance, image_info))
        
        # Sort by distance (most similar first)
        similar_images.sort(key=lambda x: x[1])
        
        return similar_images
    
    def generate_hash_based_filename(self, original_path: str, phash: str, file_extension: str = None) -> str:
        """
        Generate a hash-based filename to avoid overwrites.
        
        Args:
            original_path: Original file path
            phash: Perceptual hash
            file_extension: File extension to use
            
        Returns:
            Hash-based filename
        """
        if file_extension is None:
            file_extension = os.path.splitext(original_path)[1]
        
        # Ensure extension starts with dot
        if not file_extension.startswith('.'):
            file_extension = f'.{file_extension}'
        
        # Create hash-based filename
        # Format: phash_first8chars_originalname_timestamp.ext
        original_name = os.path.splitext(os.path.basename(original_path))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        hash_based_name = f"{phash[:8]}_{original_name}_{timestamp}{file_extension}"
        
        return hash_based_name
    
    def check_for_duplicate(self, image_path: str) -> Dict:
        """
        Check if an image is a duplicate of an existing image.
        
        Args:
            image_path: Path to the image to check
            
        Returns:
            Dictionary with duplicate detection results
        """
        self.stats['total_processed'] += 1
        
        try:
            # Generate hash for the image
            phash, hash_info = self.generate_perceptual_hash(image_path)
            
            # Find similar images
            similar_images = self.find_similar_images(phash)
            
            result = {
                'is_duplicate': len(similar_images) > 0,
                'phash': phash,
                'hash_info': hash_info,
                'similar_images': similar_images,
                'recommended_filename': None,
                'action': None
            }
            
            if similar_images:
                # Found duplicates
                self.stats['duplicates_found'] += 1
                closest_match = similar_images[0]
                
                result.update({
                    'action': 'skip_duplicate',
                    'closest_match': {
                        'hash': closest_match[0],
                        'distance': closest_match[1],
                        'info': closest_match[2]
                    },
                    'message': f"Duplicate found (distance: {closest_match[1]})"
                })
                
                logger.info(f"Duplicate detected: {os.path.basename(image_path)} "
                           f"(distance: {closest_match[1]} to existing image)")
                
            else:
                # Unique image
                self.stats['unique_images'] += 1
                
                # Generate hash-based filename
                hash_filename = self.generate_hash_based_filename(
                    image_path, phash, os.path.splitext(image_path)[1]
                )
                
                result.update({
                    'action': 'store_unique',
                    'recommended_filename': hash_filename,
                    'message': "Unique image, safe to store"
                })
                
                # Store in database
                self.hash_database['hashes'][phash] = hash_info
                self._save_hash_database()
                
                logger.debug(f"Unique image registered: {os.path.basename(image_path)} -> {hash_filename}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking for duplicate: {e}")
            return {
                'is_duplicate': False,
                'error': str(e),
                'action': 'store_with_error',
                'message': f"Error during duplicate check: {e}"
            }
    
    def batch_deduplicate(self, image_paths: List[str]) -> Dict:
        """
        Perform batch deduplication on multiple images.
        
        Args:
            image_paths: List of image paths to process
            
        Returns:
            Batch deduplication results
        """
        results = {
            'processed': [],
            'duplicates': [],
            'unique': [],
            'errors': [],
            'summary': {}
        }
        
        logger.info(f"Starting batch deduplication of {len(image_paths)} images")
        
        for i, image_path in enumerate(image_paths):
            try:
                result = self.check_for_duplicate(image_path)
                result['image_path'] = image_path
                
                results['processed'].append(result)
                
                if result.get('is_duplicate'):
                    results['duplicates'].append(result)
                elif result.get('action') == 'store_unique':
                    results['unique'].append(result)
                else:
                    results['errors'].append(result)
                
                # Progress logging
                if (i + 1) % 10 == 0 or (i + 1) == len(image_paths):
                    logger.info(f"Processed {i + 1}/{len(image_paths)} images")
                    
            except Exception as e:
                error_result = {
                    'image_path': image_path,
                    'error': str(e),
                    'action': 'error'
                }
                results['errors'].append(error_result)
                logger.error(f"Error processing {image_path}: {e}")
        
        # Generate summary
        results['summary'] = {
            'total_processed': len(results['processed']),
            'duplicates_found': len(results['duplicates']),
            'unique_images': len(results['unique']),
            'errors': len(results['errors']),
            'duplicate_rate': len(results['duplicates']) / len(image_paths) * 100 if image_paths else 0
        }
        
        logger.info(f"Batch deduplication complete: {results['summary']}")
        return results
    
    def cleanup_database(self, max_age_days: int = 30) -> int:
        """
        Clean up old entries from the hash database.
        
        Args:
            max_age_days: Maximum age in days for keeping entries
            
        Returns:
            Number of entries removed
        """
        if 'hashes' not in self.hash_database:
            return 0
        
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        initial_count = len(self.hash_database['hashes'])
        
        # Filter out old entries
        filtered_hashes = {}
        for hash_str, info in self.hash_database['hashes'].items():
            try:
                created_at = datetime.fromisoformat(info['created_at'])
                if created_at >= cutoff_date:
                    filtered_hashes[hash_str] = info
            except (KeyError, ValueError):
                # Keep entries without valid timestamps
                filtered_hashes[hash_str] = info
        
        self.hash_database['hashes'] = filtered_hashes
        removed_count = initial_count - len(filtered_hashes)
        
        if removed_count > 0:
            self._save_hash_database()
            logger.info(f"Cleaned up {removed_count} old hash database entries")
        
        return removed_count
    
    def get_statistics(self) -> Dict:
        """Get deduplication statistics."""
        return {
            'runtime_stats': self.stats.copy(),
            'database_stats': {
                'total_hashes': len(self.hash_database.get('hashes', {})),
                'database_size_mb': os.path.getsize(self.hash_db_path) / 1024 / 1024 
                                   if os.path.exists(self.hash_db_path) else 0,
                'threshold': self.similarity_threshold
            },
            'efficiency': {
                'duplicate_rate': (self.stats['duplicates_found'] / max(self.stats['total_processed'], 1)) * 100,
                'storage_saved': self.stats['duplicates_found']  # Simplified metric
            }
        }
    
    def export_database(self, export_path: str) -> bool:
        """Export hash database to a different location."""
        try:
            with open(export_path, 'w') as f:
                json.dump(self.hash_database, f, indent=2)
            logger.info(f"Hash database exported to {export_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export database: {e}")
            return False


class DeduplicationManager:
    """
    High-level manager for deduplication operations.
    Integrates with the existing converter and storage systems.
    """
    
    def __init__(self, storage_dir: str, hash_db_path: str = None):
        """
        Initialize the deduplication manager.
        
        Args:
            storage_dir: Base storage directory
            hash_db_path: Path to hash database
        """
        self.storage_dir = Path(storage_dir)
        self.detector = DuplicationDetector(
            hash_db_path=hash_db_path or str(self.storage_dir / 'hash_database.json')
        )
        
        # Create deduplication storage structure
        self.unique_dir = self.storage_dir / 'unique'
        self.duplicate_dir = self.storage_dir / 'duplicates'
        self.unique_dir.mkdir(parents=True, exist_ok=True)
        self.duplicate_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Deduplication manager initialized for {storage_dir}")
    
    def process_image_with_dedup(self, image_path: str, job_id: str) -> Dict:
        """
        Process an image with deduplication.
        
        Args:
            image_path: Path to the image to process
            job_id: Associated job ID
            
        Returns:
            Processing result with deduplication info
        """
        try:
            # Check for duplicates
            dedup_result = self.detector.check_for_duplicate(image_path)
            
            if dedup_result['is_duplicate']:
                # Handle duplicate
                duplicate_info_path = self.duplicate_dir / f"{job_id}_duplicate_info.json"
                with open(duplicate_info_path, 'w') as f:
                    json.dump(dedup_result, f, indent=2)
                
                return {
                    'action': 'duplicate_skipped',
                    'original_path': image_path,
                    'dedup_info': dedup_result,
                    'stored_path': None,
                    'message': 'Image skipped as duplicate'
                }
            
            else:
                # Store unique image with hash-based filename
                hash_filename = dedup_result['recommended_filename']
                unique_image_path = self.unique_dir / hash_filename
                
                # Copy or move the image
                import shutil
                shutil.copy2(image_path, unique_image_path)
                
                return {
                    'action': 'unique_stored',
                    'original_path': image_path,
                    'stored_path': str(unique_image_path),
                    'hash_filename': hash_filename,
                    'dedup_info': dedup_result,
                    'message': 'Unique image stored successfully'
                }
                
        except Exception as e:
            logger.error(f"Error in deduplication processing: {e}")
            return {
                'action': 'error',
                'original_path': image_path,
                'error': str(e),
                'message': f'Deduplication error: {e}'
            }
    
    def get_deduplication_report(self) -> Dict:
        """Generate a comprehensive deduplication report."""
        stats = self.detector.get_statistics()
        
        return {
            'deduplication_summary': stats,
            'storage_structure': {
                'unique_images': len(list(self.unique_dir.glob('*'))),
                'duplicate_records': len(list(self.duplicate_dir.glob('*'))),
                'total_storage_saved_mb': stats['efficiency']['storage_saved'] * 2.5  # Estimated
            },
            'recommendations': self._generate_recommendations(stats)
        }
    
    def _generate_recommendations(self, stats: Dict) -> List[str]:
        """Generate optimization recommendations based on statistics."""
        recommendations = []
        
        duplicate_rate = stats['efficiency']['duplicate_rate']
        
        if duplicate_rate > 20:
            recommendations.append("High duplicate rate detected - consider reviewing source data")
        
        if duplicate_rate < 5:
            recommendations.append("Low duplicate rate - deduplication is working efficiently")
        
        if stats['database_stats']['total_hashes'] > 10000:
            recommendations.append("Large hash database - consider periodic cleanup")
        
        return recommendations
