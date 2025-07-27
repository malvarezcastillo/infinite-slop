# Infinite Slop

A minimal image gallery generator with automatic optimization and deployment.

**Live at: [http://slop.pictures/](http://slop.pictures/)**

## Usage

### Full Deployment Workflow

```bash
# Download and process images
./download_and_cleanup.sh && \
python utils/optimize_images.py --no-resize && \
python detect_faces_simple.py --gallery-dir gallery --move && \
python detect_faces_simple.py --model-type face --move && \
python detect_animals.py --model-size large --move && \
./build-gallery.sh

# Commit and deploy
git add -A && git commit -a -m "Update gallery" && git push
```

### Individual Steps

1. **Download images**: `./download_and_cleanup.sh`
2. **Optimize images**: `python utils/optimize_images.py` (add `--no-resize` to keep original size)
3. **Detect and move faces**: `python detect_faces_simple.py --gallery-dir gallery --move`
4. **Detect faces with face model**: `python detect_faces_simple.py --model-type face --move`
5. **Detect and move animals**: `python detect_animals.py --model-size large --move`
6. **Build gallery**: `./build-gallery.sh`
7. **Deploy**: Push to GitHub

Gallery deploys automatically to GitHub Pages.

## Requirements

- Python 3.x
- Git

## License

Unlicense (Public Domain)