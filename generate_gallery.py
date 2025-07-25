#!/usr/bin/env python3
"""Generate a static image gallery HTML without Thumbsup."""

import os
import random
from pathlib import Path
import sys
import json
import html
import argparse

def generate_single_page_gallery(enable_tooltips=False):
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
                
                all_images.append({
                    'path': f"{category}/{img.name}",
                    'category': category,
                    'filename': img.name,
                    'prompt': prompt_text
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
      <div class="layout-toggle">
        <button class="layout-btn" data-columns="2" title="2 columns">▦</button>
        <button class="layout-btn active" data-columns="fill" title="Fill width">▦▦</button>
      </div>"""
    
    html_content += """
    
      <!--
        All photos and videos
      -->
      <ul id="media" class="clearfix">
"""
    
    # Add all images as list items with category data
    for img in all_images:
        img_path = img['path']
        img_name = img['filename']
        category = img['category']
        prompt = img.get('prompt', '')
        
        # Escape HTML entities in prompt for safe display
        escaped_prompt = html.escape(prompt)
        
        # Use media paths that will be replaced by replace-image-urls.py
        html_content += f"""          
            <li class="gallery-item" data-category="{category}"
                data-src="media/large/{img_path}"
                data-sub-html=""
                data-download-url="media/original/{img_path}"
                data-filename="{img_name}"
              >
              <a href="media/original/{img_path}" target="_blank" title="{escaped_prompt}">
                <img src="media/thumbs/{img_path}"
                     width="512"
                     height="512"
                     alt="{img_name}"
                     title="{escaped_prompt}" />
              </a>
            </li>"""
    
    html_content += """  </ul>
    
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

    <script src="lazy-load-virtualized.js"></script>"""
    
    if enable_tooltips:
        html_content += """
    <script src="prompt-tooltips.js"></script>"""
    
    html_content += """
    <script>
    // Filter functionality
    document.addEventListener('DOMContentLoaded', function() {
        const filterButtons = document.querySelectorAll('.filter-btn');
        const galleryItems = document.querySelectorAll('.gallery-item');
        const activeCategories = new Set();
        
        // Initialize all categories as active
        filterButtons.forEach(btn => {
            activeCategories.add(btn.dataset.category);
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
                
                // Handle lazy loading for filtered items
                if (typeof lazyLoadHandleFilterChange === 'function') {
                    lazyLoadHandleFilterChange();
                }
            });
        });
        
        // Layout toggle functionality
        const layoutButtons = document.querySelectorAll('.layout-btn');
        const mediaGrid = document.getElementById('media');
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
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Generate image gallery')
    parser.add_argument('--tooltips', action='store_true', help='Enable prompt tooltips on hover')
    args = parser.parse_args()
    
    # Set random seed for consistent shuffling across builds
    random.seed()
    
    print("Generating single-page gallery with filters...")
    return generate_single_page_gallery(enable_tooltips=args.tooltips)

if __name__ == "__main__":
    main()