#!/bin/bash
# Build the gallery locally

set -e

# Parse command line arguments
ENABLE_TOOLTIPS=false
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --tooltips) ENABLE_TOOLTIPS=true ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

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
if [ "$ENABLE_TOOLTIPS" = true ]; then
    echo "  ℹ️  Tooltips enabled"
    python3 generate_gallery.py --tooltips
else
    echo "  ℹ️  Tooltips disabled (use --tooltips to enable)"
    python3 generate_gallery.py
fi

# Copy custom scripts to build output root
echo "📝 Adding custom scripts..."
cp lazy-load-virtualized.js build_output/
cp prompt-tooltips.js build_output/
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