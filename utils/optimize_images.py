#!/usr/bin/env python3
"""
Aggressive Image Optimizer Script

This script:
- Takes image files from ./preprocessed_images
- Converts to JPEG with quality 85 (balanced compression)
- Optionally reduces dimensions to 75% (can be disabled with --no-resize)
- Adds a minimal watermark "slop.pictures" to bottom right corner
- Extracts ComfyUI prompt templates for categorization
- Automatically categorizes images based on keywords in prompts
- Removes all EXIF data from the optimized images
- Renames files to random UUID v7 strings
- Saves optimized files to ./gallery directory (or subdirectories based on category)
- Moves original files to ./raw_processed_images directory (gitignored)
- Processes files in parallel for improved performance
- Skips images that don't match any category (when skip_unmatched is true)
"""

import os
import uuid
import shutil
import json
from pathlib import Path
from PIL import Image, PngImagePlugin, ImageDraw, ImageFont
from PIL.ExifTags import TAGS
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from typing import Tuple, Optional

# Thread-safe counter for progress tracking
class ThreadSafeCounter:
    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()
    
    def increment(self):
        with self._lock:
            self._value += 1
            return self._value
    
    @property
    def value(self):
        return self._value


def generate_uuid7():
    """Generate a UUID v7 string (time-ordered UUID)"""
    # Python 3.12+ has native UUID v7, fallback for older versions
    try:
        return str(uuid.uuid7())
    except AttributeError:
        # Fallback to UUID v4 for older Python versions
        return str(uuid.uuid4())


def add_watermark(img, watermark_text="slop.pictures"):
    """
    Add a minimal, elegant watermark signature to the bottom right corner
    
    Args:
        img (PIL.Image): The image to add watermark to
        watermark_text (str): The text to use as watermark
        
    Returns:
        PIL.Image: Image with watermark added
    """
    # Create a copy to avoid modifying the original
    watermarked = img.copy()
    
    # Calculate font size - middle ground between small and large
    font_size = max(20, min(img.width, img.height) // 60)  # Middle ground size
    font = None
    
    # Try to load elegant system fonts - prioritize modern, clean fonts
    font_paths = [
        # macOS modern fonts
        "/System/Library/Fonts/SFNS.ttf",  # SF Pro (Apple's system font)
        "/System/Library/Fonts/SFCompact.ttf",  # SF Compact
        "/System/Library/Fonts/HelveticaNeue.ttc",  # Helvetica Neue
        "/System/Library/Fonts/Supplemental/Futura.ttc",  # Futura - classic minimal
        "/System/Library/Fonts/Supplemental/Optima.ttc",  # Optima - elegant serif
        "/System/Library/Fonts/Supplemental/Gill Sans.ttc",  # Gill Sans - clean
        "/System/Library/Fonts/Avenir.ttc",  # Avenir
        "/System/Library/Fonts/Helvetica.ttc",  # Classic Helvetica
        
        # Linux fonts
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        
        # Windows fonts  
        "C:\\Windows\\Fonts\\calibril.ttf",  # Calibri Light
        "C:\\Windows\\Fonts\\segoeuil.ttf",  # Segoe UI Light
        "C:\\Windows\\Fonts\\calibri.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, font_size)
                break
            except:
                continue
    
    # If no font found, use default
    if font is None:
        font = ImageFont.load_default()
    
    # Create an RGBA image for the watermark with transparency
    txt_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(txt_layer)
    
    # Get text bounding box
    bbox = draw.textbbox((0, 0), watermark_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Position in bottom right corner with minimal padding
    padding = int(font_size * 0.8)  # Reduced padding to move closer to corner
    x = img.width - text_width - padding
    y = img.height - text_height - padding
    
    # Draw the text with subtle opacity for elegant look
    # Use white with transparency for light images, adjust dynamically
    draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255, 180))  # Semi-transparent white
    
    # Convert the original image to RGBA if needed
    if img.mode != 'RGBA':
        watermarked = watermarked.convert('RGBA')
    
    # Composite the watermark over the image
    watermarked = Image.alpha_composite(watermarked, txt_layer)
    
    # Convert back to RGB for JPEG saving
    return watermarked.convert('RGB')


def extract_prompt_template(image_path):
    """
    Extract the prompt template from ComfyUI metadata (specifically from DPRandomGenerator)
    
    Args:
        image_path (Path): Path to the image file
        
    Returns:
        str or None: The extracted prompt template text, or None if not found
    """
    try:
        with Image.open(image_path) as img:
            # Check if it's a PNG with metadata
            if hasattr(img, 'info') and img.info:
                # Look for ComfyUI prompt in PNG metadata
                if 'prompt' in img.info:
                    prompt_data = img.info.get('prompt', '')
                    try:
                        # Parse the JSON prompt data
                        prompt_json = json.loads(prompt_data)
                        
                        # Look for DPRandomGenerator which contains the prompt template
                        for node_id, node_data in prompt_json.items():
                            if node_data.get('class_type') == 'DPRandomGenerator':
                                inputs = node_data.get('inputs', {})
                                if 'text' in inputs:
                                    return inputs['text'].strip()
                                    
                    except json.JSONDecodeError:
                        pass
                                
    except Exception as e:
        # Silently fail - not all images will have ComfyUI metadata
        pass
    
    return None


def optimize_image(input_path, output_path, resize=True, add_watermark_flag=True):
    """
    Aggressively optimize image by converting to JPEG, optionally resizing, and compressing
    
    Args:
        input_path (Path): Source image file path
        output_path (Path): Destination JPEG file path
        resize (bool): Whether to resize the image to 75% of original dimensions
        add_watermark_flag (bool): Whether to add watermark to the image
    """
    try:
        # Open the image
        with Image.open(input_path) as img:
            # Calculate new dimensions (75% of original for better quality) if resizing is enabled
            if resize:
                new_width = int(img.width * 0.75)
                new_height = int(img.height * 0.75)
            else:
                new_width = img.width
                new_height = img.height
            
            # Convert to RGB if necessary (JPEG doesn't support transparency)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                # Paste image on white background if it has transparency
                if img.mode == 'RGBA' or 'transparency' in img.info:
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                else:
                    rgb_img.paste(img)
                img = rgb_img
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize image using high-quality Lanczos resampling (only if dimensions changed)
            if resize and (new_width != img.width or new_height != img.height):
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            else:
                resized_img = img
            
            # Add watermark to the image if enabled
            if add_watermark_flag:
                final_img = add_watermark(resized_img)
            else:
                final_img = resized_img
            
            # Save as JPEG with balanced compression
            # Quality 85-90 maintains good visual quality while still achieving significant compression
            final_img.save(
                output_path,
                'JPEG',
                quality=90,
                optimize=True,
                progressive=True,
                subsampling=2  # Less aggressive chroma subsampling for better quality
            )
            
        return True
        
    except Exception as e:
        print(f"Error optimizing {input_path}: {e}")
        return False


def categorize_by_prompt(prompt: str, category_mapping: dict) -> Optional[str]:
    """
    Determine the category for an image based on its prompt
    
    Args:
        prompt (str): The image prompt text
        category_mapping (dict): Category mapping configuration
        
    Returns:
        Optional[str]: The category directory name, or None if no match
    """
    if not prompt:
        return None
        
    # Convert prompt to lowercase if case insensitive
    check_prompt = prompt.lower() if not category_mapping.get('case_sensitive', False) else prompt
    
    # Check each category's keywords
    for category_name, category_data in category_mapping.get('categories', {}).items():
        keywords = category_data.get('keywords', [])
        for keyword in keywords:
            check_keyword = keyword.lower() if not category_mapping.get('case_sensitive', False) else keyword
            if check_keyword in check_prompt:
                return category_data.get('directory', category_name)
    
    return None


def optimize_single_image(image_file: Path, target_path: Path, counter: ThreadSafeCounter, total_files: int, resize: bool = True, add_watermark: bool = True, category_mapping: dict = None) -> Tuple[bool, str, int, int, Optional[str]]:
    """
    Optimize a single image file
    
    Args:
        image_file (Path): Source image file path
        target_path (Path): Target directory path
        counter (ThreadSafeCounter): Thread-safe counter for progress tracking
        total_files (int): Total number of files being processed
        resize (bool): Whether to resize the image to 75% of original dimensions
        add_watermark (bool): Whether to add watermark to the image
        category_mapping (dict): Category mapping configuration for auto-categorization
        
    Returns:
        Tuple[bool, str, int, int, Optional[str]]: (success, message, original_size, optimized_size, category)
    """
    try:
        # Get original file size
        original_size = image_file.stat().st_size
        
        # Extract prompt template before processing (from the original image)
        prompt_template = extract_prompt_template(image_file)
        
        # Determine category if mapping is provided
        category_dir = None
        if category_mapping and prompt_template:
            category_dir = categorize_by_prompt(prompt_template, category_mapping)
            
            # If skip_unmatched is true and no category found, skip this image
            if category_mapping.get('skip_unmatched', False) and not category_dir:
                current = counter.increment()
                message = f"[{current}/{total_files}] ⚠️  Skipped: {image_file.name} - No matching category"
                return False, message, original_size, 0, None
        
        # Determine the actual output directory
        if category_dir:
            output_dir = target_path / category_dir
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = target_path
        
        # Generate new filename with UUID v7
        uuid_name = generate_uuid7()
        new_filename = f"{uuid_name}.jpg"
        output_path = output_dir / new_filename
        
        # Optimize the image
        if optimize_image(image_file, output_path, resize, add_watermark):
            # Get optimized file size
            optimized_size = output_path.stat().st_size
            size_reduction = ((original_size - optimized_size) / original_size) * 100
            
            # Move original file to raw_processed_images directory
            raw_dir = Path("./raw_processed_images")
            raw_dir.mkdir(exist_ok=True)
            shutil.move(str(image_file), str(raw_dir / image_file.name))
            
            # Update progress counter
            current = counter.increment()
            
            # Simplified message - just show file processing progress
            category_info = f" -> {category_dir}/" if category_dir else ""
            message = f"[{current}/{total_files}] ✓ {image_file.name} -> {category_info}{new_filename}"
            
            return True, message, original_size, optimized_size, category_dir
        else:
            current = counter.increment()
            message = f"[{current}/{total_files}] ✗ Failed to optimize {image_file.name}"
            return False, message, original_size, 0, None
            
    except Exception as e:
        current = counter.increment()
        message = f"[{current}/{total_files}] ✗ Error processing {image_file.name}: {e}"
        return False, message, 0, 0, None


def process_images(source_dir="./preprocessed_images", target_dir="./gallery", max_workers=None, resize=True, add_watermark=True, use_categorization=True):
    """
    Process all image files in source directory using parallel processing
    
    Args:
        source_dir (str): Directory containing source image files
        target_dir (str): Directory to move optimized files to
        max_workers (int): Maximum number of worker threads (None for auto)
        resize (bool): Whether to resize images to 75% of original dimensions
        add_watermark (bool): Whether to add watermark to images
        use_categorization (bool): Whether to use automatic categorization based on prompts
    """
    source_path = Path(source_dir)
    target_path = Path(target_dir)
    
    # Create target directory if it doesn't exist
    target_path.mkdir(exist_ok=True)
    
    # Load category mapping if categorization is enabled
    category_mapping = None
    if use_categorization:
        mapping_file = Path("./category_mapping.json")
        if mapping_file.exists():
            try:
                with open(mapping_file, 'r') as f:
                    category_mapping = json.load(f)
                print(f"Loaded category mapping from {mapping_file}")
                print(f"Categories: {', '.join(category_mapping['categories'].keys())}")
                if category_mapping.get('skip_unmatched', False):
                    print("⚠️  Images without matching categories will be skipped")
                print()
            except Exception as e:
                print(f"Warning: Failed to load category mapping: {e}")
                print("Proceeding without categorization")
                print()
        else:
            print(f"Category mapping file not found at {mapping_file}")
            print("Proceeding without categorization")
            print()
    
    # Find all image files in source directory (PNG, JPG, JPEG)
    image_extensions = ['*.png', '*.PNG', '*.jpg', '*.JPG', '*.jpeg', '*.JPEG']
    image_files = []
    for ext in image_extensions:
        image_files.extend(source_path.glob(ext))
    
    if not image_files:
        print(f"No image files found in {source_dir}")
        return
    
    total_files = len(image_files)
    print(f"Found {total_files} image file(s) to process")
    
    if max_workers:
        print(f"Using {max_workers} worker threads")
    else:
        print(f"Using auto-determined number of worker threads")
    
    print("Processing files in parallel...")
    if resize:
        print("Converting to JPEG with 85% quality and 75% dimension retention...")
    else:
        print("Converting to JPEG with 85% quality and original dimensions...")
    print()
    
    # Initialize counters
    counter = ThreadSafeCounter()
    processed_count = 0
    skipped_count = 0
    total_original_size = 0
    total_optimized_size = 0
    category_counts = {}
    
    # Process files in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(optimize_single_image, image_file, target_path, counter, total_files, resize, add_watermark, category_mapping): image_file 
            for image_file in image_files
        }
        
        # Process completed tasks as they finish
        for future in as_completed(future_to_file):
            success, message, original_size, optimized_size, category = future.result()
            print(message)
            
            if success:
                processed_count += 1
                total_original_size += original_size
                total_optimized_size += optimized_size
                # Track category counts
                if category:
                    category_counts[category] = category_counts.get(category, 0) + 1
                else:
                    category_counts['uncategorized'] = category_counts.get('uncategorized', 0) + 1
            elif "Skipped" in message:
                skipped_count += 1
    
    print()
    print("=" * 50)
    print(f"Processing complete: {processed_count}/{total_files} files processed successfully")
    if skipped_count > 0:
        print(f"Skipped {skipped_count} files due to no matching category")
    
    if processed_count > 0:
        total_reduction = ((total_original_size - total_optimized_size) / total_original_size) * 100
        print(f"Total size reduction: {total_original_size:,} -> {total_optimized_size:,} bytes ({total_reduction:.1f}%)")
        
        # Show category summary
        if category_mapping and category_counts:
            print("\nCategory Summary:")
            print("-" * 30)
            
            # Count existing files in each category directory
            for category_name, category_data in category_mapping.get('categories', {}).items():
                category_dir = category_data.get('directory', category_name)
                category_path = target_path / category_dir
                
                # Count existing files
                existing_count = 0
                if category_path.exists():
                    existing_count = len(list(category_path.glob('*.jpg')))
                
                # Get new files added in this run
                new_count = category_counts.get(category_dir, 0)
                
                if existing_count > 0 or new_count > 0:
                    total_count = existing_count
                    if new_count > 0:
                        print(f"{category_dir:15} {total_count:4d} (+{new_count})")
                    else:
                        print(f"{category_dir:15} {total_count:4d}")
            
            # Show uncategorized if any
            if 'uncategorized' in category_counts:
                uncategorized_path = target_path
                existing_uncategorized = len(list(uncategorized_path.glob('*.jpg'))) - sum(
                    len(list((target_path / cat_data.get('directory', cat)).glob('*.jpg'))) 
                    for cat, cat_data in category_mapping.get('categories', {}).items()
                    if (target_path / cat_data.get('directory', cat)).exists()
                )
                new_uncategorized = category_counts['uncategorized']
                total_uncategorized = existing_uncategorized
                print(f"{'uncategorized':15} {total_uncategorized:4d} (+{new_uncategorized})")
            
            # Show total
            print("-" * 30)
            total_existing = len(list(target_path.rglob('*.jpg')))
            print(f"{'TOTAL':15} {total_existing:4d} (+{processed_count})")


def main():
    """Main function with command line argument support"""
    parser = argparse.ArgumentParser(description="Aggressively optimize image files to JPEG")
    parser.add_argument(
        "--source", 
        default="./preprocessed_images",
        help="Source directory containing image files (default: ./preprocessed_images)"
    )
    parser.add_argument(
        "--target",
        default="./gallery", 
        help="Target directory for optimized files (default: ./gallery)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of worker threads (default: auto-detect based on CPU cores)"
    )
    parser.add_argument(
        "--no-resize",
        action="store_true",
        help="Keep original image dimensions (default: resize to 75% of original)"
    )
    parser.add_argument(
        "--no-watermark",
        action="store_true",
        help="Disable watermark (default: add 'slop.pictures' watermark)"
    )
    parser.add_argument(
        "--no-categorize",
        action="store_true",
        help="Disable automatic categorization based on prompts (default: enabled)"
    )
    
    args = parser.parse_args()
    
    print("Aggressive Image Optimizer (JPEG Conversion)")
    print("==========================================")
    print(f"Source directory: {args.source}")
    print(f"Target directory: {args.target}")
    print(f"Resize images: {'No' if args.no_resize else 'Yes (75% of original)'}")
    print(f"Add watermark: {'No' if args.no_watermark else 'Yes (slop.pictures)'}")
    print(f"Auto-categorize: {'No' if args.no_categorize else 'Yes (using category_mapping.json)'}")
    print()
    
    process_images(args.source, args.target, args.workers, not args.no_resize, not args.no_watermark, not args.no_categorize)


if __name__ == "__main__":
    main() 