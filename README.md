# Infinite Slop

A minimal image gallery generator with automatic optimization and deployment.

**Live at: [http://slop.pictures/](http://slop.pictures/)**

## Usage

1. Run `./download_and_cleanup.sh` to download images
2. Run `python utils/optimize_images.py` to optimize images
3. Run `./build-gallery.sh` to build the gallery locally
4. Push to GitHub to deploy

Gallery deploys automatically to GitHub Pages.

## Requirements

- Python 3.x
- Git

## License

Unlicense (Public Domain)