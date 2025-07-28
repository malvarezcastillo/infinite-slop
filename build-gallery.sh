#!/bin/bash
# Build the gallery locally

set -e

# No command line arguments needed anymore

echo "🖼️  Building gallery..."

# Check if gallery directory exists
if [ ! -d "gallery" ]; then
    echo "❌ Error: gallery directory not found"
    echo "Please run 'python utils/optimize_images.py' first to process images"
    exit 1
fi

# Clean previous build
if [ -d "build_output" ]; then
    echo "🧹 Cleaning previous build..."
    rm -rf build_output
fi

# Generate all galleries
echo "🔨 Generating gallery HTML..."
python3 generate_gallery.py

# Copy custom scripts to build output root
echo "📝 Adding custom scripts..."
cp lazy-load-virtualized.js build_output/
cp progressive-loader.js build_output/
cp favicon.ico build_output/ 2>/dev/null || true

# No need to copy scripts to subdirectories anymore

# Scripts are already included in the generated HTML, no need to add them

# Replace image URLs with GitHub raw URLs for all HTML files
echo "🔗 Replacing image URLs..."
python3 replace-image-urls.py build_output/

echo "✅ Gallery built successfully!"
echo ""
echo "The build_output directory is ready to be deployed."
echo "Next steps:"
echo "1. Commit and push your changes to the gallery/ directory"
echo "2. The build_output directory will be deployed by GitHub Actions"
echo ""
echo "Gallery structure:"
echo "  - Main gallery: yoursite.github.io/infinite-slop/"
if [ -d "gallery/landscape" ]; then
    echo "  - Landscape gallery: yoursite.github.io/infinite-slop/landscape/"
fi