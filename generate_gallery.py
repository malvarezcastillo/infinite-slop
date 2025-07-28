#!/usr/bin/env python3
"""Generate a static image gallery HTML without Thumbsup."""

import os
import random
from pathlib import Path
import sys
import json
import html
import argparse

def generate_single_page_gallery():
    """Generate a single-page gallery with all images and category filters."""
    
    # Get all gallery subdirectories
    gallery_base = Path("gallery")
    if not gallery_base.exists():
        print("No gallery directory found")
        return False
        
    # Collect all images from all subdirectories
    all_images = []
    categories = []
    
    for subdir in sorted(gallery_base.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith('.'):
            category = subdir.name
            categories.append(category)
            
            # Get all images from this category
            images = list(subdir.glob("*.jpg"))
            for img in images:
                # Try to read the prompt from corresponding .txt file
                prompt_file = img.with_suffix('.txt')
                prompt_text = ""
                if prompt_file.exists():
                    try:
                        with open(prompt_file, 'r', encoding='utf-8') as f:
                            prompt_text = f.read().strip()
                    except Exception as e:
                        print(f"Warning: Could not read prompt file {prompt_file}: {e}")
                
                # Get file modification time (creation time for UUIDv7 files)
                mtime = img.stat().st_mtime
                
                all_images.append({
                    'path': f"{category}/{img.name}",
                    'category': category,
                    'filename': img.name,
                    'prompt': prompt_text,
                    'mtime': mtime
                })
            
            print(f"Found {len(images)} images in {category} category")
    
    # Shuffle all images
    random.shuffle(all_images)
    
    print(f"Total images: {len(all_images)} across {len(categories)} categories")
    
    # Create output directory
    output_dir = Path("build_output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create public directory for CSS
    public_dir = output_dir / "public"
    public_dir.mkdir(exist_ok=True)
    
    # Copy custom CSS to public directory
    if Path("custom.css").exists():
        with open("custom.css", "r") as f:
            css_content = f.read()
        with open(public_dir / "theme.css", "w") as f:
            f.write(css_content)
    
    # Generate minimal core.css
    with open(public_dir / "core.css", "w") as f:
        f.write("/* Minimal core CSS */\n")
    
    # Generate HTML with filter menu
    html_content = f"""<!DOCTYPE html>
<html>

  <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, user-scalable=no" />
      <title>Slop Gallery</title>
      <link rel="stylesheet" href="public/core.css" />
      <link rel="stylesheet" href="public/theme.css" />
      <!-- Preconnect to GitHub for faster image loading -->
      <link rel="preconnect" href="https://raw.githubusercontent.com" crossorigin>
      <link rel="dns-prefetch" href="https://raw.githubusercontent.com">
  </head>

  <body>

    <div id="container">"""
    
    # Add filter menu
    if categories:
        html_content += f"""
      <nav class="filter-menu">
        <div class="filter-label">Categories:</div>
        <div class="filter-buttons">""" 
        
        for category in sorted(categories):
            display_name = category.replace('-', ' ').replace('_', ' ').title()
            html_content += f"""
          <button class="filter-btn active" data-category="{category}">{display_name}</button>"""
        
        html_content += """
        </div>
      </nav>"""
    
    # Add layout toggle button (desktop only)
    html_content += """
      <div class="layout-toggle" style="opacity: 0.5; pointer-events: none;">
        <button class="layout-btn" data-columns="2" title="2 columns" disabled>▦</button>
        <button class="layout-btn active" data-columns="fill" title="Fill width" disabled>▦▦</button>
      </div>
      
      <div class="sort-toggle" style="opacity: 0.5; pointer-events: none;">
        <button class="sort-btn active" data-sort="random" title="Random order" disabled>🔀</button>
        <button class="sort-btn" data-sort="newest" title="Newest first" disabled>📅</button>
      </div>
      
      <div class="loading-indicator">
        <span class="loading-text">Loading gallery...</span>
      </div>"""
    
    html_content += """
    
      <!--
        All photos and videos
      -->
      <ul id="media" class="clearfix">
"""
    
    # Progressive loading: render first batch in DOM, rest as JSON
    initial_batch_size = 500  # Render first 500 items in DOM
    
    # Add first batch of images as list items
    for i, img in enumerate(all_images[:initial_batch_size]):
        img_path = img['path']
        img_name = img['filename']
        category = img['category']
        prompt = img.get('prompt', '')
        mtime = img.get('mtime', 0)
        
        # Escape HTML entities in prompt for safe display
        escaped_prompt = html.escape(prompt)
        
        # Use media paths that will be replaced by replace-image-urls.py
        html_content += f"""          
            <li class="gallery-item" data-category="{category}"
                data-src="media/large/{img_path}"
                data-sub-html=""
                data-download-url="media/original/{img_path}"
                data-filename="{img_name}"
                data-mtime="{mtime}"
              >
              <a href="media/original/{img_path}" target="_blank" title="{escaped_prompt}">
                <img src="media/thumbs/{img_path}"
                     width="512"
                     height="512"
                     alt="{img_name}"
                     loading="lazy"
                     title="{escaped_prompt}" />
              </a>
            </li>"""
    
    html_content += """  </ul>
    
      <!-- Load more indicator -->
      <div id="load-more-indicator" style="display: none; text-align: center; padding: 40px;">
        <span>Loading more images...</span>
      </div>
    
      <!--
        Pagination
      -->
    
      <!--
        Zip file link
      -->
    
    
      <!--
        Optional footer
      -->
    
    </div>

    <!-- Store remaining images as JSON for progressive loading -->
    <script>
      window.remainingImages = """ + json.dumps([{
            'path': img['path'],
            'category': img['category'],
            'filename': img['filename'],
            'prompt': img.get('prompt', ''),
            'mtime': img.get('mtime', 0)
        } for img in all_images[initial_batch_size:]]) + """;
      window.progressiveLoadConfig = {
        batchSize: 100,
        loadMoreThreshold: 800,
        currentIndex: """ + str(initial_batch_size) + """
      };
    </script>

    <script src="lazy-load-virtualized.js"></script>
    <script src="progressive-loader.js"></script>"""
    
    html_content += """
    <script>
    // Filter and sort functionality
    document.addEventListener('DOMContentLoaded', function() {
        const filterButtons = document.querySelectorAll('.filter-btn');
        const sortButtons = document.querySelectorAll('.sort-btn');
        const layoutButtons = document.querySelectorAll('.layout-btn');
        let galleryItems = document.querySelectorAll('.gallery-item');
        const activeCategories = new Set();
        const mediaGrid = document.getElementById('media');
        const loadingIndicator = document.querySelector('.loading-indicator');
        const sortToggle = document.querySelector('.sort-toggle');
        const layoutToggle = document.querySelector('.layout-toggle');
        let currentSort = 'random';
        let originalOrder = [];
        let isInitialized = false;
        
        // Function to enable all controls
        function enableControls() {
            if (isInitialized) return;
            isInitialized = true;
            
            // Enable all buttons
            sortButtons.forEach(btn => btn.disabled = false);
            layoutButtons.forEach(btn => btn.disabled = false);
            filterButtons.forEach(btn => btn.disabled = false);
            
            // Remove disabled styling
            sortToggle.style.opacity = '';
            sortToggle.style.pointerEvents = '';
            layoutToggle.style.opacity = '';
            layoutToggle.style.pointerEvents = '';
            
            // Hide loading indicator
            loadingIndicator.classList.add('hidden');
        }
        
        // Store original order of items
        galleryItems.forEach((item, index) => {
            originalOrder.push({element: item, index: index});
        });
        
        // Initialize all categories as active
        filterButtons.forEach(btn => {
            activeCategories.add(btn.dataset.category);
        });
        
        // Wait for initial images to load before enabling controls
        setTimeout(() => {
            enableControls();
        }, 1500); // Give lazy loading time to initialize
        
        // Also enable when first batch of images loads
        const checkFirstLoad = setInterval(() => {
            const loadedImages = document.querySelectorAll('#media img.loaded');
            if (loadedImages.length >= 10) { // At least initial batch loaded
                clearInterval(checkFirstLoad);
                enableControls();
            }
        }, 200);
        
        // Sort functionality
        function sortGallery(sortType) {
            // Re-query items to include dynamically loaded ones
            galleryItems = document.querySelectorAll('.gallery-item');
            const items = Array.from(galleryItems);
            let sortedItems;
            
            // Store current image states before sorting
            const imageStates = new Map();
            items.forEach(item => {
                const img = item.querySelector('img');
                if (img) {
                    imageStates.set(item, {
                        src: img.src,
                        hasOriginalSrc: !img.classList.contains('lazy'),
                        classes: [...img.classList]
                    });
                }
            });
            
            if (sortType === 'newest') {
                // Sort by mtime (newest first)
                sortedItems = items.sort((a, b) => {
                    const timeA = parseFloat(a.dataset.mtime || 0);
                    const timeB = parseFloat(b.dataset.mtime || 0);
                    return timeB - timeA; // Descending order (newest first)
                });
            } else {
                // Random order (restore original shuffled order)
                sortedItems = originalOrder.map(item => item.element);
            }
            
            // Reorder items without destroying them
            sortedItems.forEach(item => {
                mediaGrid.appendChild(item);
            });
            
            // Restore image states
            sortedItems.forEach((item, newIndex) => {
                const img = item.querySelector('img');
                const state = imageStates.get(item);
                if (img && state) {
                    // Keep loaded images loaded
                    if (state.hasOriginalSrc) {
                        img.src = state.src;
                        state.classes.forEach(cls => img.classList.add(cls));
                    }
                }
            });
            
            // Signal lazy loader to handle reordering
            setTimeout(() => {
                if (typeof lazyLoadHandleReorder === 'function') {
                    lazyLoadHandleReorder();
                }
            }, 100);
            
            // Handle visibility for filtered items
            galleryItems.forEach(item => {
                if (activeCategories.has(item.dataset.category)) {
                    item.style.display = '';
                } else {
                    item.style.display = 'none';
                }
            });
        }
        
        // Handle sort button clicks
        sortButtons.forEach(btn => {
            btn.addEventListener('click', function() {
                const sortType = this.dataset.sort;
                
                // Don't do anything if already active
                if (this.classList.contains('active')) return;
                
                // Update active state
                sortButtons.forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                
                // Add loading state
                mediaGrid.style.opacity = '0.5';
                mediaGrid.style.pointerEvents = 'none';
                
                // Apply sort with a small delay for visual feedback
                setTimeout(() => {
                    currentSort = sortType;
                    sortGallery(sortType);
                    
                    // Dispatch event for progressive loader
                    window.dispatchEvent(new CustomEvent('sortChange', {
                        detail: { sortType: sortType }
                    }));
                    
                    // Remove loading state
                    setTimeout(() => {
                        mediaGrid.style.opacity = '1';
                        mediaGrid.style.pointerEvents = '';
                    }, 200);
                }, 100);
            });
        });
        
        // Handle filter button clicks
        filterButtons.forEach(btn => {
            btn.addEventListener('click', function() {
                const category = this.dataset.category;
                
                if (this.classList.contains('active')) {
                    this.classList.remove('active');
                    activeCategories.delete(category);
                } else {
                    this.classList.add('active');
                    activeCategories.add(category);
                }
                
                // Update gallery visibility
                galleryItems.forEach(item => {
                    if (activeCategories.has(item.dataset.category)) {
                        item.style.display = '';
                    } else {
                        item.style.display = 'none';
                    }
                });
                
                // Dispatch event for progressive loader
                window.dispatchEvent(new CustomEvent('filterChange', {
                    detail: { activeCategories: Array.from(activeCategories) }
                }));
                
                // Handle lazy loading for filtered items
                if (typeof lazyLoadHandleFilterChange === 'function') {
                    lazyLoadHandleFilterChange();
                }
            });
        });
        
        // Layout toggle functionality
        const container = document.getElementById('container');
        
        layoutButtons.forEach(btn => {
            btn.addEventListener('click', function() {
                const columns = this.dataset.columns;
                
                // Update active state
                layoutButtons.forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                
                // Update grid columns
                if (columns === '2') {
                    mediaGrid.style.gridTemplateColumns = 'repeat(2, 1fr)';
                    container.style.maxWidth = '1200px';
                    mediaGrid.style.gap = '25px';
                } else {
                    // Fill mode - auto-fill with 256px images
                    mediaGrid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(256px, 1fr))';
                    container.style.maxWidth = '90%';
                    mediaGrid.style.gap = '15px';
                }
                
                // Handle lazy loading after layout change
                if (typeof lazyLoadHandleFilterChange === 'function') {
                    setTimeout(lazyLoadHandleFilterChange, 100);
                }
            });
        });
    });
    </script>

  </body>

</html>
"""
    
    # Write HTML file
    with open(output_dir / "index.html", "w") as f:
        f.write(html_content)
    
    print(f"Generated {output_dir / 'index.html'} with {len(all_images)} images")
    return True

def main():
    """Main function to generate single-page gallery."""
    # Set random seed for consistent shuffling across builds
    random.seed()
    
    print("Generating single-page gallery with filters...")
    return generate_single_page_gallery()

if __name__ == "__main__":
    main()