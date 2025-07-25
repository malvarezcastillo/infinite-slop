#!/usr/bin/env python3
import os
import re
import sys
from pathlib import Path

def replace_image_urls(build_dir, github_user, github_repo, branch='master'):
    base_url = f"https://raw.githubusercontent.com/{github_user}/{github_repo}/{branch}"
    
    # Find all HTML files recursively
    html_files = list(Path(build_dir).rglob('*.html'))
    
    for html_file in html_files:
        print(f"Processing {html_file}")
        
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Replace image sources in img tags (thumbnails)
        content = re.sub(
            r'src="media/thumbs/([^"]+\.jpg)"',
            rf'src="{base_url}/gallery/\1"',
            content
        )
        
        # Replace full-size image links in href
        content = re.sub(
            r'href="media/original/([^"]+\.jpg)"',
            rf'href="{base_url}/gallery/\1"',
            content
        )
        
        # Replace data-src for lightbox (large images)
        content = re.sub(
            r'data-src="media/large/([^"]+\.jpg)"',
            rf'data-src="{base_url}/gallery/\1"',
            content
        )
        
        # Replace data-download-url (original images)
        content = re.sub(
            r'data-download-url="media/original/([^"]+\.jpg)"',
            rf'data-download-url="{base_url}/gallery/\1"',
            content
        )
        
        # Replace any remaining media paths
        content = re.sub(
            r'"media/(thumbs|small|large|original)/([^"]+\.jpg)"',
            rf'"{base_url}/gallery/\2"',
            content
        )
        
        if content != original_content:
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  - Updated image URLs in {html_file.name}")
        else:
            print(f"  - No changes needed in {html_file.name}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python replace-image-urls.py <build_directory> [github_user] [github_repo] [branch]")
        sys.exit(1)
    
    build_dir = sys.argv[1]
    github_user = sys.argv[2] if len(sys.argv) > 2 else os.environ.get('GITHUB_REPOSITORY_OWNER', 'malvarezcastillo')
    github_repo = sys.argv[3] if len(sys.argv) > 3 else os.environ.get('GITHUB_REPOSITORY', 'malvarezcastillo/infinite-slop').split('/')[-1]
    branch = sys.argv[4] if len(sys.argv) > 4 else 'master'
    
    print(f"Replacing image URLs with GitHub raw URLs:")
    print(f"  Repository: {github_user}/{github_repo}")
    print(f"  Branch: {branch}")
    print(f"  Build directory: {build_dir}")
    
    replace_image_urls(build_dir, github_user, github_repo, branch)