#!/bin/bash

# ==== Configuration ====
USER="nummy"
HOST="192.168.1.174"
REMOTE_DIR="/home/nummy/ComfyUI/output"
PATTERN="*.png"
LOCAL_DIR="preprocessed_images"
TMP_LIST="files_to_download.txt"
REMOTE_LIST="/home/nummy/files_to_delete.txt"
# ========================

echo "Fetching file list from server..."
ssh "${USER}@${HOST}" "find '${REMOTE_DIR}' -name '${PATTERN}'" > "$TMP_LIST"

if [[ ! -s "$TMP_LIST" ]]; then
    echo "No files matched the pattern. Exiting."
    exit 0
fi

echo "Creating local directory: $LOCAL_DIR"
mkdir -p "$LOCAL_DIR"

# Count total files
TOTAL_FILES=$(wc -l < "$TMP_LIST")
echo "Found $TOTAL_FILES files to download"

# Method 1: Use rsync for efficient batch transfer
echo "Downloading files using rsync..."
# Create a file list relative to the remote directory
ssh "${USER}@${HOST}" "cd '${REMOTE_DIR}' && find . -name '${PATTERN}' -type f" > rsync_list.txt

# Use rsync with minimal options to avoid hanging
# -r: recursive, -t: preserve times, --timeout: prevent hanging
rsync -rt --timeout=30 --files-from=rsync_list.txt "${USER}@${HOST}:${REMOTE_DIR}" "$LOCAL_DIR/"

# Clean up temporary rsync list
rm -f rsync_list.txt

echo "Sending list back to server for deletion..."
scp "$TMP_LIST" "${USER}@${HOST}:${REMOTE_LIST}"

echo "Deleting files on server..."
ssh "${USER}@${HOST}" "xargs -d '\n' rm -f < '${REMOTE_LIST}' && rm -f '${REMOTE_LIST}'"

# Clean up local temp file
rm -f "$TMP_LIST"

echo "Cleanup complete. Downloaded $TOTAL_FILES files."