#!/usr/bin/env python3
"""
Simplified face detection script using only YOLOv8-face
Faster and lighter than the dual-model approach
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


class DetectionCache:
    """Simple file-based cache for detection results"""
    def __init__(self, cache_dir: Path = Path('.face_detection_cache')):
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


class SimpleFaceDetector:
    def __init__(self, confidence_threshold=0.5, use_cache=True, cache_dir=None, 
                 model_type='auto', model_size='nano'):
        """Initialize face detector with YOLOv8 model
        
        Args:
            confidence_threshold: Minimum confidence for detection
            use_cache: Whether to use caching
            cache_dir: Custom cache directory
            model_type: 'face', 'person', or 'auto' (auto-detect)
            model_size: 'nano', 'small', 'medium', 'large', or 'xlarge'
        """
        logger.info("Initializing detector...")
        
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
            
            # Determine which model to load
            if model_type == 'face':
                # Try to load face model
                face_model_path = f'yolov8{size_suffix}-face-lindevs.pt'
                if Path(face_model_path).exists():
                    self.model = YOLO(face_model_path)
                    logger.info(f"Using YOLOv8{size_suffix}-face model (face detection)")
                    self.detection_type = 'face'
                else:
                    logger.warning(f"Face model {face_model_path} not found. Download from:")
                    logger.warning(f"https://github.com/lindevs/yolov8-face/releases/latest/download/{face_model_path}")
                    raise FileNotFoundError(f"Face model not found: {face_model_path}")
            
            elif model_type == 'person':
                # Load person detection model
                person_model = f'yolov8{size_suffix}.pt'
                self.model = YOLO(person_model)
                logger.info(f"Using YOLOv8{size_suffix} model (person detection)")
                self.detection_type = 'person'
                self.person_mode = True
            
            else:  # auto mode
                # Try face model first, fall back to person
                face_model_path = f'yolov8{size_suffix}-face-lindevs.pt'
                if Path(face_model_path).exists():
                    self.model = YOLO(face_model_path)
                    logger.info(f"Using YOLOv8{size_suffix}-face model (face detection)")
                    self.detection_type = 'face'
                else:
                    person_model = f'yolov8{size_suffix}.pt'
                    self.model = YOLO(person_model)
                    logger.info(f"Using YOLOv8{size_suffix} model (person detection)")
                    self.detection_type = 'person'
                    self.person_mode = True
                    
        except ImportError:
            logger.error("ultralytics not installed. Run: pip install ultralytics")
            raise
        
        self.confidence_threshold = confidence_threshold
        self.person_mode = hasattr(self, 'person_mode')
        
        # Initialize cache with model type in path
        self.use_cache = use_cache
        if use_cache:
            if cache_dir:
                cache_path = Path(cache_dir)
            else:
                # Separate cache for face vs person detection
                cache_path = Path(f'.face_detection_cache_{self.detection_type}')
            self.cache = DetectionCache(cache_path)
        
        logger.info(f"Detector initialized successfully ({self.detection_type} mode)")
    
    def detect(self, image_path: str) -> Dict:
        """Detect faces/people in a single image"""
        image_path = Path(image_path)
        
        # Check cache first
        if self.use_cache:
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
                        # In person mode, only count class 0 (person)
                        if self.person_mode and int(box.cls[0]) != 0:
                            continue
                        
                        confidence = float(box.conf[0])
                        if confidence >= self.confidence_threshold:
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            detections.append({
                                'bbox': [int(x1), int(y1), int(x2), int(y2)],
                                'confidence': confidence,
                                'class': int(box.cls[0])
                            })
            
            result = {
                'path': str(image_path),
                'width': width,
                'height': height,
                'detections': detections,
                'count': len(detections),
                'has_detections': len(detections) > 0
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
                'count': 0
            }


def scan_directory(directory: Path, detector: SimpleFaceDetector, 
                  extensions: List[str] = ['.jpg', '.jpeg', '.png']) -> Tuple[List[Dict], Dict[str, int]]:
    """Scan directory for images and detect faces"""
    results = []
    image_files = []
    
    # Collect all image files
    for ext in extensions:
        image_files.extend(directory.glob(f"**/*{ext}"))
        image_files.extend(directory.glob(f"**/*{ext.upper()}"))
    
    logger.info(f"Found {len(image_files)} images in {directory}")
    
    # Process each image
    for i, image_path in enumerate(image_files, 1):
        if i % 10 == 0:
            logger.info(f"Processing image {i}/{len(image_files)}...")
        
        result = detector.detect(image_path)
        results.append(result)
        
        if result.get('has_detections'):
            logger.info(f"Found {result['count']} detections in: {image_path.name}")
    
    # Get cache statistics if available
    cache_stats = detector.cache.get_stats() if detector.use_cache else None
    
    return results, cache_stats


def move_to_review(results: List[Dict], review_dir: Path, dry_run: bool = True, use_symlinks: bool = False) -> Dict[str, int]:
    """Move detected images to review directory organized by confidence"""
    # Create review directory structure
    high_conf_dir = review_dir / "high_confidence"
    medium_conf_dir = review_dir / "medium_confidence"
    low_conf_dir = review_dir / "low_confidence"
    
    if not dry_run:
        high_conf_dir.mkdir(parents=True, exist_ok=True)
        medium_conf_dir.mkdir(parents=True, exist_ok=True)
        low_conf_dir.mkdir(parents=True, exist_ok=True)
    
    # Track movements
    movements = {
        'high': [],
        'medium': [],
        'low': [],
        'errors': []
    }
    
    # Process each detected image
    for result in results:
        if not result.get('has_detections'):
            continue
        
        try:
            # Get highest confidence from detections
            max_confidence = max(d['confidence'] for d in result.get('detections', []))
            source_path = Path(result['path'])
            
            # Determine target directory based on confidence
            if max_confidence >= 0.8:
                target_dir = high_conf_dir
                category = 'high'
            elif max_confidence >= 0.5:
                target_dir = medium_conf_dir
                category = 'medium'
            else:
                target_dir = low_conf_dir
                category = 'low'
            
            # Create subdirectory matching source structure
            relative_dir = source_path.parent.relative_to(source_path.parent.parts[0])
            target_subdir = target_dir / relative_dir
            
            if not dry_run:
                target_subdir.mkdir(parents=True, exist_ok=True)
            
            # Target file path
            target_path = target_subdir / source_path.name
            
            # Record the movement
            movements[category].append({
                'source': str(source_path),
                'target': str(target_path),
                'confidence': max_confidence,
                'detections': result.get('count', 0)
            })
            
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
    summary = {
        'timestamp': datetime.now().isoformat(),
        'dry_run': dry_run,
        'use_symlinks': use_symlinks,
        'total_candidates': sum(len(m) for m in [movements['high'], movements['medium'], movements['low']]),
        'high_confidence': len(movements['high']),
        'medium_confidence': len(movements['medium']),
        'low_confidence': len(movements['low']),
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
            f.write("Face/Person Detection Review Directory\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"Generated: {summary['timestamp']}\n")
            f.write(f"Mode: {'DRY RUN' if dry_run else 'ACTUAL MOVE'}\n")
            f.write(f"Method: {'SYMLINKS' if use_symlinks else 'MOVED FILES'}\n\n")
            
            f.write("Summary:\n")
            f.write(f"- Total candidates: {summary['total_candidates']}\n")
            f.write(f"- High confidence (≥0.8): {summary['high_confidence']} images\n")
            f.write(f"- Medium confidence (0.5-0.8): {summary['medium_confidence']} images\n")
            f.write(f"- Low confidence (<0.5): {summary['low_confidence']} images\n")
            if summary['errors']:
                f.write(f"- Errors: {summary['errors']}\n")
            
            f.write("\nDirectories:\n")
            f.write("- high_confidence/: Images with ≥80% confidence\n")
            f.write("- medium_confidence/: Images with 50-80% confidence\n")
            f.write("- low_confidence/: Images with <50% confidence\n")
            
            f.write("\nReview these images and delete the ones you confirm have faces.\n")
            f.write("High confidence images are most likely to be true positives.\n")
    
    return summary


def generate_report(results: List[Dict], output_path: str, detector_type: str = "face"):
    """Generate a detailed report of detection results"""
    timestamp = datetime.now().isoformat()
    
    # Statistics
    total_images = len(results)
    images_with_detections = sum(1 for r in results if r.get('has_detections'))
    total_detections = sum(r.get('count', 0) for r in results)
    
    # Group by directory
    by_directory = {}
    for result in results:
        dir_path = str(Path(result['path']).parent)
        if dir_path not in by_directory:
            by_directory[dir_path] = []
        by_directory[dir_path].append(result)
    
    # Group by confidence levels
    confidence_ranges = {
        'high': [r for r in results if any(d['confidence'] >= 0.8 for d in r.get('detections', []))],
        'medium': [r for r in results if any(0.5 <= d['confidence'] < 0.8 for d in r.get('detections', []))],
        'low': [r for r in results if any(d['confidence'] < 0.5 for d in r.get('detections', []))]
    }
    
    report = {
        'timestamp': timestamp,
        'detector_type': detector_type,
        'summary': {
            'total_images_scanned': total_images,
            'images_with_detections': images_with_detections,
            'total_detections': total_detections,
            'average_detections_per_image': total_detections / total_images if total_images > 0 else 0
        },
        'by_directory': {
            dir_path: {
                'total_images': len(images),
                'with_detections': sum(1 for img in images if img.get('has_detections')),
                'total_detections': sum(img.get('count', 0) for img in images)
            }
            for dir_path, images in by_directory.items()
        },
        'by_confidence': {
            level: len(images) for level, images in confidence_ranges.items()
        },
        'detections': [r for r in results if r.get('has_detections')],
        'all_results': results
    }
    
    # Save JSON report
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Save human-readable report
    txt_path = output_path.replace('.json', '.txt')
    with open(txt_path, 'w') as f:
        f.write(f"Detection Report\n")
        f.write(f"Generated: {timestamp}\n")
        f.write(f"Detector Type: {detector_type}\n")
        f.write(f"{'='*60}\n\n")
        
        f.write(f"SUMMARY:\n")
        f.write(f"- Total images scanned: {total_images}\n")
        f.write(f"- Images with detections: {images_with_detections}\n")
        f.write(f"- Total detections: {total_detections}\n")
        f.write(f"- Average per image: {total_detections/total_images:.2f}\n\n")
        
        f.write(f"CONFIDENCE DISTRIBUTION:\n")
        f.write(f"- High (≥0.8): {len(confidence_ranges['high'])} images\n")
        f.write(f"- Medium (0.5-0.8): {len(confidence_ranges['medium'])} images\n")
        f.write(f"- Low (<0.5): {len(confidence_ranges['low'])} images\n\n")
        
        f.write(f"BY DIRECTORY:\n")
        for dir_path, stats in sorted(report['by_directory'].items()):
            f.write(f"\n{dir_path}:\n")
            f.write(f"  - Total images: {stats['total_images']}\n")
            f.write(f"  - With detections: {stats['with_detections']}\n")
            f.write(f"  - Total detections: {stats['total_detections']}\n")
        
        f.write(f"\n{'='*60}\n")
        f.write(f"IMAGES WITH DETECTIONS (sorted by confidence):\n\n")
        
        # Sort by highest confidence detection
        sorted_results = sorted(
            [r for r in results if r.get('has_detections')],
            key=lambda x: max(d['confidence'] for d in x.get('detections', [])),
            reverse=True
        )
        
        for result in sorted_results:
            f.write(f"{result['path']}\n")
            f.write(f"  - Detections: {result.get('count', 0)}\n")
            for i, detection in enumerate(result.get('detections', []), 1):
                conf = detection['confidence']
                bbox = detection['bbox']
                f.write(f"    {i}. Confidence: {conf:.3f}, ")
                f.write(f"Box: [{bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]}]\n")
            f.write("\n")
    
    # Save list of files to delete (high confidence only)
    delete_list_path = output_path.replace('.json', '_delete_candidates.txt')
    with open(delete_list_path, 'w') as f:
        f.write("# High-confidence detection candidates for deletion\n")
        f.write("# Review carefully before deleting!\n\n")
        
        high_confidence = [
            r for r in results 
            if r.get('has_detections') and 
            any(d['confidence'] >= 0.8 for d in r.get('detections', []))
        ]
        
        for result in high_confidence:
            max_conf = max(d['confidence'] for d in result.get('detections', []))
            f.write(f"{result['path']} # confidence: {max_conf:.3f}\n")
    
    logger.info(f"Reports saved:")
    logger.info(f"  - JSON: {output_path}")
    logger.info(f"  - Human-readable: {txt_path}")
    logger.info(f"  - Delete candidates: {delete_list_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Detect faces/people in gallery images',
        epilog='''Examples:
  # First pass: detect people (catches most photos with humans)
  python detect_faces_simple.py --model-type person --move
  
  # Second pass: detect faces only (catches close-ups missed by person detection)
  python detect_faces_simple.py --model-type face --move
  
  # Use larger model for better accuracy
  python detect_faces_simple.py --model-type person --model-size large
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--gallery-dir', type=str, default='gallery',
                       help='Path to gallery directory')
    parser.add_argument('--confidence', type=float, default=0.5,
                       help='Confidence threshold for detection (0.0-1.0)')
    parser.add_argument('--output', type=str, default='face_detection_report.json',
                       help='Output report file path')
    parser.add_argument('--subdirs', nargs='+', help='Specific subdirectories to scan')
    parser.add_argument('--review-dir', type=str, default='review_faces',
                       help='Directory to move detected images for review')
    parser.add_argument('--move', action='store_true',
                       help='Actually move files (default is dry run)')
    parser.add_argument('--symlinks', action='store_true',
                       help='Create symlinks instead of moving files')
    parser.add_argument('--report-only', action='store_true',
                       help='Only generate report, do not move files')
    parser.add_argument('--no-cache', action='store_true',
                       help='Disable caching of detection results')
    parser.add_argument('--clear-cache', action='store_true',
                       help='Clear cache before running')
    parser.add_argument('--cache-dir', type=str,
                       help='Custom cache directory (default: .face_detection_cache)')
    parser.add_argument('--model-type', type=str, default='auto',
                       choices=['face', 'person', 'auto'],
                       help='Detection type: face-only, person (full body), or auto')
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
        detector = SimpleFaceDetector(
            confidence_threshold=args.confidence,
            use_cache=not args.no_cache,
            cache_dir=args.cache_dir,
            model_type=args.model_type,
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
    
    # Generate report
    detector_type = detector.detection_type
    generate_report(all_results, args.output, detector_type)
    
    # Move files to review directory if requested
    images_with_detections = [r for r in all_results if r.get('has_detections')]
    
    if images_with_detections:
        print(f"\n⚠️  Found {len(images_with_detections)} images with {detector_type}!")
        print(f"Total {detector_type} detected: {sum(r.get('count', 0) for r in images_with_detections)}")
        
        # Display cache statistics
        if detector.use_cache and total_cache_stats['hits'] + total_cache_stats['misses'] > 0:
            total_processed = total_cache_stats['hits'] + total_cache_stats['misses']
            cache_rate = (total_cache_stats['hits'] / total_processed) * 100
            print(f"\nCache statistics:")
            print(f"  - Cache hits: {total_cache_stats['hits']} ({cache_rate:.1f}%)")
            print(f"  - Cache misses: {total_cache_stats['misses']}")
            print(f"  - Invalid entries: {total_cache_stats['invalid']}")
        
        if not args.report_only:
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
            print(f"  - High confidence (≥80%): {summary['high_confidence']} images")
            print(f"  - Medium confidence (50-80%): {summary['medium_confidence']} images")
            print(f"  - Low confidence (<50%): {summary['low_confidence']} images")
            
            if dry_run:
                print(f"\nThis was a DRY RUN. To actually move files, add --move flag")
            else:
                print(f"\nFiles {'linked' if args.symlinks else 'moved'} to: {review_path}")
                print(f"Review the images in each confidence folder and delete as appropriate.")
        else:
            print(f"\nReports saved:")
            print(f"  - {args.output.replace('.json', '.txt')} - Full report")
            print(f"  - {args.output.replace('.json', '_delete_candidates.txt')} - High-confidence candidates")
    else:
        print(f"\n✅ No {detector_type} detected in any images!")
        
        # Still show cache stats even if no detections
        if detector.use_cache and total_cache_stats['hits'] + total_cache_stats['misses'] > 0:
            total_processed = total_cache_stats['hits'] + total_cache_stats['misses']
            cache_rate = (total_cache_stats['hits'] / total_processed) * 100
            print(f"\nCache statistics:")
            print(f"  - Cache hits: {total_cache_stats['hits']} ({cache_rate:.1f}%)")
            print(f"  - Cache misses: {total_cache_stats['misses']}")


if __name__ == '__main__':
    main()