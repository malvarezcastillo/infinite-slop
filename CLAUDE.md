# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Infinite Slop is an automated AI-generated image gallery that:
- Downloads images from a ComfyUI instance
- Processes and optimizes images (watermarking, JPEG conversion, EXIF removal)
- Generates a static website with lazy loading and virtualization
- Automatically deploys to GitHub Pages at http://slop.pictures/

## Key Commands

### Full Workflow
```bash
# 1. Download new images from server
./download_and_cleanup.sh

# 2. Process and categorize images
python utils/optimize_images.py

# 3. Build static gallery locally  
./build-gallery.sh

# 4. Commit and push to deploy
git add gallery/ build_output/
git commit -m "Update gallery"
git push
```

### Individual Commands
```bash
# Process images with 75% resize (default)
python utils/optimize_images.py

# Process without resizing
python utils/optimize_images.py --no-resize

# Build gallery with tooltips enabled
./build-gallery.sh --tooltips
```

## Architecture

### Image Pipeline
1. **download_and_cleanup.sh**: Downloads PNG images from ComfyUI server (192.168.1.174)
2. **utils/optimize_images.py**: 
   - Converts to JPEG (90% quality)
   - Adds "slop.pictures" watermark
   - Removes EXIF data
   - Renames to UUID v7
   - Auto-categorizes based on prompts using category_mapping.json
   - Moves originals to raw_processed_images/
3. **generate_gallery.py**: Creates static HTML with lazy loading
4. **replace-image-urls.py**: Updates URLs to GitHub raw links

### Directory Structure
- `preprocessed_images/` - Downloaded images waiting to be processed
- `gallery/` - Optimized images organized by category
  - `main/` - Main gallery
  - `landscape/` - Landscape images  
  - `architecture/` - Architecture images
  - `interiors/` - Interior design images
  - `things/` - Objects and atmosphere images
- `raw_processed_images/` - Original images backup (gitignored)
- `build_output/` - Generated static site (committed and deployed)

### Categorization
Images are auto-categorized based on ComfyUI prompts via `category_mapping.json`. Images without matching categories are skipped (skip_unmatched: true).

### Deployment
GitHub Actions deploys `build_output/` to GitHub Pages when pushed to master branch. Images are served from GitHub raw URLs to avoid file size limits.

## Important Notes

- Always commit both `gallery/` and `build_output/` directories
- The build process runs locally to avoid GitHub Actions timeouts
- All image filenames are UUIDs to prevent conflicts
- Watermark placement is bottom-right corner with semi-transparent white text
- Gallery supports multiple categories with filter navigation