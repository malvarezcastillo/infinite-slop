#!/usr/bin/env python3
"""
Animal and insect detection script based on YOLOv8

This script uses the YOLOv8 model with COCO dataset classes to detect animals in images.
It's designed to help identify and review images containing living subjects (animals, birds)
in an image gallery, allowing for manual review and removal if needed.

The script supports:
- Detection of all animal classes in the COCO dataset (classes 14-23)
- Caching of detection results for improved performance on repeated runs
- Organization of detected images by animal type for easy review
- Dry-run mode to preview actions before moving files
- Multiple model sizes for accuracy vs speed tradeoffs

Note: The standard COCO dataset only includes 10 animal classes. For detection of 
insects or more animal species, a specialized model would be required.
"""

import os
import argparse
import json
import shutil
import hashlib
import pickle
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from PIL import Image
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# COCO dataset class indices
# The COCO (Common Objects in Context) dataset defines 80 object classes.
# Classes 14-23 are all the animal classes in the dataset.
# Classes 24-28 are non-living objects, documented here for reference.
ANIMAL_CLASSES = {
    # Animal classes in COCO dataset (these are ALL the animals in standard COCO)
    14: 'bird',
    15: 'cat', 
    16: 'dog',
    17: 'horse',
    18: 'sheep',
    19: 'cow',
    20: 'elephant',
    21: 'bear',
    22: 'zebra',
    23: 'giraffe',
    
    # Non-living objects (classes 24-28) - documented for reference
    # These immediately follow the animal classes in COCO but are NOT animals
    24: 'backpack',  # Non-living object - excluded from detection
    25: 'umbrella',  # Non-living object - excluded from detection
    26: 'handbag',   # Non-living object - excluded from detection
    27: 'tie',       # Non-living object - excluded from detection
    28: 'suitcase',  # Non-living object - excluded from detection
    
    # Note: COCO does not include insects or many other animal species.
    # For broader animal/insect detection, consider using:
    # - iNaturalist dataset models
    # - Custom trained models
    # - Specialized wildlife detection models
}

# Define which classes are actually living subjects we want to detect
# This set contains ONLY the animal classes from COCO (14-23)
LIVING_SUBJECT_CLASSES = {14, 15, 16, 17, 18, 19, 20, 21, 22, 23}  # All animal classes in COCO


class DetectionCache:
    """Simple file-based cache for detection results
    
    This cache stores detection results to avoid re-processing images that haven't changed.
    Cache keys are based on file path, modification time, and file size to ensure
    cache invalidation when files are modified.
    
    Attributes:
        cache_dir: Directory where cache files are stored
        stats: Dictionary tracking cache hits, misses, and invalid entries
    """
    def __init__(self, cache_dir: Path = Path('.animal_detection_cache')):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(exist_ok=True)
        self.stats = {'hits': 0, 'misses': 0, 'invalid': 0}
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Generate hash based on file path and modification time"""
        stat = file_path.stat()
        key = f"{file_path}_{stat.st_mtime}_{stat.st_size}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def _get_cache_path(self, file_hash: str) -> Path:
        """Get cache file path for given hash"""
        return self.cache_dir / f"{file_hash}.pkl"
    
    def get(self, file_path: Path) -> Optional[Dict]:
        """Get cached result for file"""
        try:
            file_hash = self._get_file_hash(file_path)
            cache_path = self._get_cache_path(file_hash)
            
            if cache_path.exists():
                with open(cache_path, 'rb') as f:
                    cached = pickle.load(f)
                    # Verify the path matches (extra safety)
                    if cached.get('path') == str(file_path):
                        self.stats['hits'] += 1
                        return cached
                    else:
                        self.stats['invalid'] += 1
            
            self.stats['misses'] += 1
            return None
        except Exception as e:
            logger.debug(f"Cache read error for {file_path}: {e}")
            self.stats['invalid'] += 1
            return None
    
    def set(self, file_path: Path, result: Dict):
        """Cache result for file"""
        try:
            file_hash = self._get_file_hash(file_path)
            cache_path = self._get_cache_path(file_hash)
            
            with open(cache_path, 'wb') as f:
                pickle.dump(result, f)
        except Exception as e:
            logger.debug(f"Cache write error for {file_path}: {e}")
    
    def clear(self):
        """Clear all cache files"""
        for cache_file in self.cache_dir.glob('*.pkl'):
            cache_file.unlink()
        logger.info(f"Cleared cache directory: {self.cache_dir}")
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return self.stats.copy()


class AnimalDetector:
    """Animal detection using YOLOv8 with COCO classes
    
    This detector uses the standard YOLOv8 model trained on the COCO dataset
    to identify animals in images. It supports multiple model sizes for 
    different speed/accuracy tradeoffs and includes caching for performance.
    
    The detector will identify these animal types:
    - bird, cat, dog, horse, sheep, cow, elephant, bear, zebra, giraffe
    
    Note: This uses the standard COCO model which has limited animal classes.
    For detecting insects or more animal species, a specialized model would
    be needed.
    """
    def __init__(self, confidence_threshold=0.5, use_cache=True, cache_dir=None, model_size='nano'):
        """Initialize animal detector with YOLOv8 model
        
        Args:
            confidence_threshold: Minimum confidence for detection (0.0-1.0)
            use_cache: Whether to use caching for repeated detections
            cache_dir: Custom cache directory (default: .animal_detection_cache)
            model_size: Model size - 'nano' (fastest), 'small', 'medium', 
                       'large', or 'xlarge' (most accurate)
        """
        logger.info("Initializing animal detector...")
        
        try:
            from ultralytics import YOLO
            
            # Map size names to model suffixes
            size_map = {
                'nano': 'n',
                'small': 's',
                'medium': 'm',
                'large': 'l',
                'xlarge': 'x'
            }
            size_suffix = size_map.get(model_size, 'n')
            
            # Load standard YOLOv8 model (includes animal classes)
            model_name = f'yolov8{size_suffix}.pt'
            self.model = YOLO(model_name)
            logger.info(f"Using YOLOv8{size_suffix} model for animal detection")
                    
        except ImportError:
            logger.error("ultralytics not installed. Run: pip install ultralytics")
            raise
        
        self.confidence_threshold = confidence_threshold
        
        # Initialize cache
        self.use_cache = use_cache
        if use_cache:
            if cache_dir:
                cache_path = Path(cache_dir)
            else:
                cache_path = Path('.animal_detection_cache')
            self.cache = DetectionCache(cache_path)
        
        logger.info("Animal detector initialized successfully")
    
    def detect(self, image_path: str, check_cache: bool = True) -> Dict:
        """Detect animals in a single image
        
        Args:
            image_path: Path to the image file
            check_cache: Whether to check cache first (can be disabled when pre-filtering)
            
        Returns:
            Dict containing:
                - path: Image file path
                - width: Image width in pixels
                - height: Image height in pixels
                - detections: List of detected animals with bbox, confidence, class
                - count: Number of animals detected
                - has_detections: Boolean indicating if any animals were found
                - animal_types: List of unique animal types detected
                - error: Error message if detection failed (optional)
        """
        image_path = Path(image_path)
        
        # Check cache first (can be disabled when pre-filtering)
        if self.use_cache and check_cache:
            cached_result = self.cache.get(image_path)
            if cached_result is not None:
                logger.debug(f"Cache hit for {image_path.name}")
                return cached_result
        
        try:
            # Get image info
            img = Image.open(image_path)
            width, height = img.size
            
            # Run detection
            results = self.model(image_path, verbose=False)
            detections = []
            
            for result in results:
                if result.boxes is not None:
                    for box in result.boxes:
                        class_id = int(box.cls[0])
                        
                        # Only include living subjects
                        if class_id in LIVING_SUBJECT_CLASSES:
                            confidence = float(box.conf[0])
                            if confidence >= self.confidence_threshold:
                                x1, y1, x2, y2 = box.xyxy[0].tolist()
                                class_name = ANIMAL_CLASSES.get(class_id, f'animal_class_{class_id}')
                                detections.append({
                                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                                    'confidence': confidence,
                                    'class': class_id,
                                    'class_name': class_name
                                })
            
            result = {
                'path': str(image_path),
                'width': width,
                'height': height,
                'detections': detections,
                'count': len(detections),
                'has_detections': len(detections) > 0,
                'animal_types': list(set(d['class_name'] for d in detections))
            }
            
            # Cache the result
            if self.use_cache:
                self.cache.set(image_path, result)
            
            return result
        
        except Exception as e:
            logger.error(f"Error analyzing {image_path}: {e}")
            return {
                'path': str(image_path),
                'error': str(e),
                'has_detections': False,
                'count': 0,
                'animal_types': []
            }


def scan_directory(directory: Path, detector: AnimalDetector, 
                  extensions: List[str] = ['.jpg', '.jpeg', '.png']) -> Tuple[List[Dict], Dict[str, int]]:
    """Scan directory for images and detect animals
    
    Recursively scans the given directory for image files and runs animal
    detection on each one. Results are cached for performance.
    
    Args:
        directory: Path to directory to scan
        detector: AnimalDetector instance to use
        extensions: List of image file extensions to process
        
    Returns:
        Tuple of:
            - List of detection results for all images
            - Cache statistics dictionary (hits, misses, invalid)
    """
    results = []
    image_files = []
    
    # Collect all image files
    for ext in extensions:
        image_files.extend(directory.glob(f"**/*{ext}"))
        image_files.extend(directory.glob(f"**/*{ext.upper()}"))
    
    logger.info(f"Found {len(image_files)} images in {directory}")
    
    # Pre-filter cached files if cache is enabled
    files_to_process = []
    if detector.use_cache:
        logger.info("Checking cache for already processed files...")
        for image_path in image_files:
            cached_result = detector.cache.get(image_path)
            if cached_result is not None:
                # Use cached result directly
                results.append(cached_result)
                if cached_result.get('has_detections'):
                    animals = ', '.join(cached_result['animal_types'])
                    logger.debug(f"Cache hit (with {animals}): {image_path.name}")
            else:
                # Need to process this file
                files_to_process.append(image_path)
        
        logger.info(f"Found {len(results)} cached results, {len(files_to_process)} files need processing")
    else:
        files_to_process = image_files
    
    # Process only uncached images
    for i, image_path in enumerate(files_to_process, 1):
        if i % 10 == 0:
            logger.info(f"Processing new image {i}/{len(files_to_process)}...")
        
        result = detector.detect(image_path, check_cache=False)
        results.append(result)
        
        if result.get('has_detections'):
            animals = ', '.join(result['animal_types'])
            logger.info(f"Found {result['count']} animals ({animals}) in: {image_path.name}")
    
    # Get cache statistics if available
    cache_stats = detector.cache.get_stats() if detector.use_cache else None
    
    return results, cache_stats


def move_to_review(results: List[Dict], review_dir: Path, dry_run: bool = True, use_symlinks: bool = False) -> Dict[str, int]:
    """Move detected images to review directory organized by animal type
    
    Organizes images containing animals into a review directory structure:
    - by_animal_type/: Images with single animal type (subdirs for each type)
    - mixed_animals/: Images containing multiple different animal types
    
    Creates a summary report and README in the review directory.
    
    Args:
        results: List of detection results from scan_directory
        review_dir: Path to create review directory structure
        dry_run: If True, only simulate moves without actually moving files
        use_symlinks: If True, create symlinks instead of moving files
        
    Returns:
        Dictionary containing summary statistics and movement details
    """
    # Create review directory structure
    by_type_dir = review_dir / "by_animal_type"
    mixed_dir = review_dir / "mixed_animals"
    
    if not dry_run:
        by_type_dir.mkdir(parents=True, exist_ok=True)
        mixed_dir.mkdir(parents=True, exist_ok=True)
    
    # Track movements
    movements = {
        'by_type': {},
        'mixed': [],
        'errors': []
    }
    
    # Process each detected image
    for result in results:
        if not result.get('has_detections'):
            continue
        
        try:
            source_path = Path(result['path'])
            animal_types = result.get('animal_types', [])
            
            # Determine target directory
            if len(animal_types) == 1:
                # Single animal type - organize by type
                animal_type = animal_types[0]
                target_dir = by_type_dir / animal_type
                
                if animal_type not in movements['by_type']:
                    movements['by_type'][animal_type] = []
                
                category = 'by_type'
                sub_category = animal_type
            else:
                # Multiple animal types - put in mixed
                target_dir = mixed_dir
                category = 'mixed'
                sub_category = None
            
            # Create subdirectory matching source structure
            relative_dir = source_path.parent.relative_to(source_path.parent.parts[0])
            target_subdir = target_dir / relative_dir
            
            if not dry_run:
                target_subdir.mkdir(parents=True, exist_ok=True)
            
            # Target file path
            target_path = target_subdir / source_path.name
            
            # Record the movement
            movement_info = {
                'source': str(source_path),
                'target': str(target_path),
                'count': result.get('count', 0),
                'types': animal_types,
                'max_confidence': max(d['confidence'] for d in result.get('detections', []))
            }
            
            if category == 'by_type':
                movements['by_type'][sub_category].append(movement_info)
            else:
                movements['mixed'].append(movement_info)
            
            # Actually move/link the file if not dry run
            if not dry_run:
                if use_symlinks:
                    # Create symlink instead of moving
                    if target_path.exists():
                        target_path.unlink()
                    target_path.symlink_to(source_path.absolute())
                    logger.info(f"Linked: {source_path.name} -> {target_path}")
                else:
                    # Move the file
                    shutil.move(str(source_path), str(target_path))
                    logger.info(f"Moved: {source_path.name} -> {target_path}")
        
        except Exception as e:
            logger.error(f"Error processing {result['path']}: {e}")
            movements['errors'].append({
                'path': result['path'],
                'error': str(e)
            })
    
    # Generate summary report
    total_by_type = sum(len(files) for files in movements['by_type'].values())
    summary = {
        'timestamp': datetime.now().isoformat(),
        'dry_run': dry_run,
        'use_symlinks': use_symlinks,
        'total_candidates': total_by_type + len(movements['mixed']),
        'by_animal_type': {k: len(v) for k, v in movements['by_type'].items()},
        'mixed_animals': len(movements['mixed']),
        'errors': len(movements['errors']),
        'movements': movements
    }
    
    # Save summary report
    if not dry_run:
        summary_path = review_dir / 'review_summary.json'
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Create human-readable summary
        readme_path = review_dir / 'README.txt'
        with open(readme_path, 'w') as f:
            f.write("Animal/Insect Detection Review Directory\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"Generated: {summary['timestamp']}\n")
            f.write(f"Mode: {'DRY RUN' if dry_run else 'ACTUAL MOVE'}\n")
            f.write(f"Method: {'SYMLINKS' if use_symlinks else 'MOVED FILES'}\n\n")
            
            f.write("Summary:\n")
            f.write(f"- Total candidates: {summary['total_candidates']}\n")
            f.write(f"- Images with single animal type: {total_by_type}\n")
            f.write(f"- Images with multiple animal types: {summary['mixed_animals']}\n")
            if summary['errors']:
                f.write(f"- Errors: {summary['errors']}\n")
            
            f.write("\nBy Animal Type:\n")
            for animal_type, count in sorted(summary['by_animal_type'].items()):
                f.write(f"- {animal_type}: {count} images\n")
            
            f.write("\nDirectories:\n")
            f.write("- by_animal_type/: Images organized by detected animal type\n")
            f.write("- mixed_animals/: Images with multiple animal types\n")
            
            f.write("\nReview these images and delete the ones with animals/insects.\n")
    
    return summary




def main():
    parser = argparse.ArgumentParser(
        description='Detect animals and insects in gallery images',
        epilog='''Examples:
  # Detect animals with default settings
  python detect_animals.py
  
  # Move detected images to review directory
  python detect_animals.py --move
  
  # Use larger model for better accuracy
  python detect_animals.py --model-size large --move
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--gallery-dir', type=str, default='gallery',
                       help='Path to gallery directory')
    parser.add_argument('--confidence', type=float, default=0.5,
                       help='Confidence threshold for detection (0.0-1.0)')
    parser.add_argument('--subdirs', nargs='+', help='Specific subdirectories to scan')
    parser.add_argument('--review-dir', type=str, default='review_animals',
                       help='Directory to move detected images for review')
    parser.add_argument('--move', action='store_true',
                       help='Actually move files (default is dry run)')
    parser.add_argument('--symlinks', action='store_true',
                       help='Create symlinks instead of moving files')
    parser.add_argument('--no-cache', action='store_true',
                       help='Disable caching of detection results')
    parser.add_argument('--clear-cache', action='store_true',
                       help='Clear cache before running')
    parser.add_argument('--cache-dir', type=str,
                       help='Custom cache directory (default: .animal_detection_cache)')
    parser.add_argument('--model-size', type=str, default='nano',
                       choices=['nano', 'small', 'medium', 'large', 'xlarge'],
                       help='Model size (nano=fastest, xlarge=most accurate)')
    
    args = parser.parse_args()
    
    # Validate gallery directory
    gallery_path = Path(args.gallery_dir)
    if not gallery_path.exists():
        logger.error(f"Gallery directory not found: {gallery_path}")
        return
    
    # Initialize detector
    try:
        detector = AnimalDetector(
            confidence_threshold=args.confidence,
            use_cache=not args.no_cache,
            cache_dir=args.cache_dir,
            model_size=args.model_size
        )
        
        # Clear cache if requested
        if args.clear_cache and detector.use_cache:
            detector.cache.clear()
            print("Cache cleared.")
    except Exception as e:
        logger.error(f"Failed to initialize detector: {e}")
        logger.error("Make sure to install requirements: pip install ultralytics pillow")
        return
    
    # Determine directories to scan
    if args.subdirs:
        directories = [gallery_path / subdir for subdir in args.subdirs]
    else:
        # Scan all subdirectories
        directories = [d for d in gallery_path.iterdir() if d.is_dir()]
        if not directories:
            directories = [gallery_path]  # Scan root if no subdirs
    
    # Scan all directories
    all_results = []
    total_cache_stats = {'hits': 0, 'misses': 0, 'invalid': 0}
    
    for directory in directories:
        if directory.exists():
            logger.info(f"\nScanning directory: {directory}")
            results, cache_stats = scan_directory(directory, detector)
            all_results.extend(results)
            
            # Aggregate cache stats
            if cache_stats:
                for key in total_cache_stats:
                    total_cache_stats[key] += cache_stats.get(key, 0)
        else:
            logger.warning(f"Directory not found: {directory}")
    
    
    # Move files to review directory if requested
    images_with_detections = [r for r in all_results if r.get('has_detections')]
    
    if images_with_detections:
        print(f"\n⚠️  Found {len(images_with_detections)} images with animals/insects!")
        print(f"Total animals detected: {sum(r.get('count', 0) for r in images_with_detections)}")
        
        # Display animal type summary
        animal_summary = {}
        for result in images_with_detections:
            for animal_type in result.get('animal_types', []):
                animal_summary[animal_type] = animal_summary.get(animal_type, 0) + 1
        
        print(f"\nAnimal types found:")
        for animal_type, count in sorted(animal_summary.items()):
            print(f"  - {animal_type}: {count} images")
        
        # Display cache statistics
        if detector.use_cache and total_cache_stats['hits'] + total_cache_stats['misses'] > 0:
            total_processed = total_cache_stats['hits'] + total_cache_stats['misses']
            cache_rate = (total_cache_stats['hits'] / total_processed) * 100
            print(f"\nCache statistics:")
            print(f"  - Cache hits: {total_cache_stats['hits']} ({cache_rate:.1f}%)")
            print(f"  - Cache misses: {total_cache_stats['misses']}")
            print(f"  - Invalid entries: {total_cache_stats['invalid']}")
        
        # Move to review directory
        review_path = Path(args.review_dir)
        dry_run = not args.move
        
        print(f"\n{'DRY RUN - ' if dry_run else ''}Moving images to review directory: {review_path}")
        
        summary = move_to_review(
            all_results, 
            review_path, 
            dry_run=dry_run,
            use_symlinks=args.symlinks
        )
        
        print(f"\nReview directory organization:")
        print(f"  - Images organized by animal type in: by_animal_type/")
        print(f"  - Images with multiple animals in: mixed_animals/")
        
        if dry_run:
            print(f"\nThis was a DRY RUN. To actually move files, add --move flag")
        else:
            print(f"\nFiles {'linked' if args.symlinks else 'moved'} to: {review_path}")
            print(f"Review the images in each folder and delete as appropriate.")
    else:
        print(f"\n✅ No animals or insects detected in any images!")
        
        # Still show cache stats even if no detections
        if detector.use_cache and total_cache_stats['hits'] + total_cache_stats['misses'] > 0:
            total_processed = total_cache_stats['hits'] + total_cache_stats['misses']
            cache_rate = (total_cache_stats['hits'] / total_processed) * 100
            print(f"\nCache statistics:")
            print(f"  - Cache hits: {total_cache_stats['hits']} ({cache_rate:.1f}%)")
            print(f"  - Cache misses: {total_cache_stats['misses']}")


if __name__ == '__main__':
    main()