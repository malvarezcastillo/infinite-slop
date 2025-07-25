# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Infinite Slop is an automated image gallery generator that processes images and creates a static website gallery with lazy loading. The project uses Python for image optimization and custom HTML generation (previously used Thumbsup), with automatic deployment to GitHub Pages. Supports multiple galleries with sub-URLs.

## Key Commands

### Image Processing
```bash
# Process images from preprocessed_images/ to gallery/
python utils/optimize_images.py

# Process with 75% resize (optional)
python utils/optimize_images.py --resize
```

### Gallery Generation
```bash
# Generate static gallery locally
./build-gallery.sh
```

### Development Workflow

#### New Workflow
1. Run `./download_and_cleanup.sh` to download new images to `preprocessed_images/`
2. Run `python utils/optimize_images.py` to optimize and move to `gallery/`
3. Organize images into subdirectories:
   - `gallery/main/` - Main gallery (displayed at root URL)
   - `gallery/landscape/` - Landscape gallery (displayed at /landscape/)
   - `gallery/[category]/` - Any other category galleries
4. Run `./build-gallery.sh` to generate the static site locally
5. Commit and push changes to both `gallery/` and `build_output/`
6. GitHub Actions automatically deploys the pre-built gallery to GitHub Pages

The build process is now done locally to avoid timeout issues with large galleries on GitHub's free tier.

## Architecture

### Image Processing Pipeline (`utils/optimize_images.py`)
- Converts images to JPEG with 85% quality
- Removes EXIF data for privacy
- Renames files to UUID v7 for unique naming
- Moves originals to `raw_processed_images/` for backup
- Uses parallel processing for efficiency

### Gallery Generation (`generate_gallery.py`)
- **Custom HTML Generator**: Generates static HTML without image processing
- **Multi-Gallery Support**: Handles main gallery at root and sub-galleries in subdirectories
- **Image Shuffling**: Built-in random shuffling of images
- **Navigation**: Automatic navigation links between galleries
- **Custom Styling** (`custom.css`): Clean white background with responsive grid layout, gallery navigation links
- **Lazy Loading** (`lazy-load-virtualized.js`): Enhanced lazy loading with DOM virtualization - loads first 10 images immediately, virtualizes off-screen images to improve performance
- **Prompt Tooltips** (`prompt-tooltips.js`): Optional tooltip functionality to display image prompts on hover (enabled with --tooltips flag)

### CI/CD Pipeline (`.github/workflows/gallery.yml`)
- Triggers on push to master branch when `build_output/` changes
- Deploys the pre-built gallery directly to GitHub Pages
- Images are served from the GitHub repository (raw URLs)

## Important Notes

- The `build_output/` directory now contains the generated static site and should be committed
- The `raw_processed_images/` directory is gitignored and contains original images after processing
- Images in `gallery/` are the optimized versions used for the website, organized by category:
  - `gallery/main/` - Main gallery images (shown at root)
  - `gallery/landscape/` - Landscape images (shown at /landscape/)
  - Additional galleries can be created by adding subdirectories
- All image filenames are converted to UUIDs to avoid naming conflicts
- No longer requires Thumbsup - uses custom Python generator