#!/bin/bash

# Clone with sparse checkout to get only source files
git clone --filter=blob:none --sparse git@github.com:malvarezcastillo/infinite-slop.git source-history
cd source-history

# Configure sparse checkout to exclude images
git sparse-checkout init --cone
git sparse-checkout set --no-cone '/*' '!*.png' '!*.jpg' '!*.jpeg' '!*.gif' '!*.webp' '!gallery/' '!raw_processed_images/'

# Fetch history
git checkout master