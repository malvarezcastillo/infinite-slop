# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Infinite Slop is an automated AI-generated image gallery that:
- Downloads images from a ComfyUI instance  
- Processes and optimizes images (watermarking, JPEG conversion, EXIF removal)
- Detects and moves images with faces/animals to review directories
- Generates a static website with lazy loading and virtualization
- Automatically deploys to GitHub Pages at http://slop.pictures/

## Key Commands

### Full Deployment Workflow
```bash
# Complete workflow from README
./download_and_cleanup.sh && \
python utils/optimize_images.py --no-resize && \
python detect_faces_simple.py --gallery-dir gallery --move && \
python detect_faces_simple.py --model-type face --move && \
python detect_animals.py --model-size large --move && \
./build-gallery.sh

# Commit and deploy
git add -A && git commit -a -m "Update gallery" && git push
```

### Individual Commands
```bash
# Download images from ComfyUI server
./download_and_cleanup.sh

# Process images (with 75% resize by default)
python utils/optimize_images.py

# Process without resizing
python utils/optimize_images.py --no-resize

# Detect and move faces (YOLOv8-face model)
python detect_faces_simple.py --gallery-dir gallery --move

# Detect faces with face model
python detect_faces_simple.py --model-type face --move

# Detect and move animals
python detect_animals.py --model-size large --move

# Build static gallery
./build-gallery.sh
```

## Architecture

### Image Pipeline
1. **download_and_cleanup.sh**: Downloads PNG images from ComfyUI server (192.168.1.174) using rsync
2. **utils/optimize_images.py**: 
   - Converts to JPEG (90% quality)
   - Adds "slop.pictures" watermark (bottom-right, semi-transparent white)
   - Removes EXIF data
   - Renames to UUID v7
   - Auto-categorizes based on ComfyUI prompts using category_mapping.json
   - Moves originals to raw_processed_images/
   - Parallel processing with ThreadPoolExecutor
3. **detect_faces_simple.py**: YOLOv8-face detection with caching
4. **detect_animals.py**: YOLOv8 COCO animal detection (classes 14-23)
5. **generate_gallery.py**: Creates static HTML with category filters
6. **replace-image-urls.py**: Updates URLs to GitHub raw links

### Directory Structure
- `preprocessed_images/` - Downloaded images waiting to be processed
- `gallery/` - Optimized images organized by category
  - `landscape/` - Landscape images  
  - `architecture/` - Architecture images
  - `interiors/` - Interior design images
  - `things/` - Objects and atmosphere images
- `raw_processed_images/` - Original images backup (gitignored)
- `build_output/` - Generated static site (committed and deployed)
- `review_animals/` - Animals detected for review
  - `by_animal_type/` - Organized by animal type
  - `mixed_animals/` - Multiple animal types
- `.face_detection_cache/` - Face detection cache
- `.animal_detection_cache/` - Animal detection cache

### Categorization
Images are auto-categorized based on ComfyUI prompt templates extracted from PNG metadata (DPRandomGenerator node). Configuration in `category_mapping.json`:
- Categories: landscape, architecture, interiors, things
- `skip_unmatched: true` - Images without matching categories are skipped
- `case_sensitive: false` - Case-insensitive keyword matching

### Deployment
GitHub Actions (.github/workflows/gallery.yml) deploys `build_output/` to GitHub Pages when pushed to master branch. Uses sparse checkout to exclude gallery/ directory. Images are served from GitHub raw URLs (https://raw.githubusercontent.com).

## Python Environment
Always use venv for Python scripts (Python 3.13 in current setup).

## Server Configuration
- Host: 192.168.1.174
- User: nummy
- Remote directory: /home/nummy/ComfyUI/output