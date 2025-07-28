// Progressive DOM loader for handling large galleries
(function() {
  'use strict';

  const state = {
    loading: false,
    allLoaded: false,
    activeCategories: new Set(),
    currentSort: 'random'
  };

  // Initialize after DOM loads
  document.addEventListener('DOMContentLoaded', function() {
    initializeProgressiveLoader();
  });

  function initializeProgressiveLoader() {
    // Get initial active categories
    const filterButtons = document.querySelectorAll('.filter-btn.active');
    filterButtons.forEach(btn => {
      state.activeCategories.add(btn.dataset.category);
    });

    // Set up scroll listener for infinite loading
    window.addEventListener('scroll', checkScrollPosition, { passive: true });
    
    // Check initial position in case user refreshed while scrolled
    checkScrollPosition();
  }

  function checkScrollPosition() {
    if (state.loading || state.allLoaded) return;

    const scrollPosition = window.pageYOffset + window.innerHeight;
    const threshold = document.body.offsetHeight - window.progressiveLoadConfig.loadMoreThreshold;

    if (scrollPosition > threshold) {
      loadMoreImages();
    }
  }

  function loadMoreImages() {
    if (!window.remainingImages || window.remainingImages.length === 0) {
      state.allLoaded = true;
      return;
    }

    state.loading = true;
    const indicator = document.getElementById('load-more-indicator');
    if (indicator) indicator.style.display = 'block';

    // Get next batch
    const { batchSize, currentIndex } = window.progressiveLoadConfig;
    const nextBatch = window.remainingImages.slice(0, batchSize);
    window.remainingImages = window.remainingImages.slice(batchSize);

    // Create DOM elements
    const mediaList = document.getElementById('media');
    const fragment = document.createDocumentFragment();

    nextBatch.forEach(img => {
      const li = createImageElement(img);
      fragment.appendChild(li);
    });

    // Append to DOM
    mediaList.appendChild(fragment);

    // Update index
    window.progressiveLoadConfig.currentIndex += nextBatch.length;

    // Apply current sort if not random
    if (state.currentSort !== 'random') {
      applySortToNewItems();
    }

    // Update lazy loader
    setTimeout(() => {
      if (typeof lazyLoadHandleReorder === 'function') {
        lazyLoadHandleReorder();
      }
      
      state.loading = false;
      if (indicator) indicator.style.display = 'none';
      
      // Check if we need to load more
      checkScrollPosition();
    }, 100);
  }

  function createImageElement(img) {
    const li = document.createElement('li');
    li.className = 'gallery-item';
    li.dataset.category = img.category;
    li.dataset.src = `media/large/${img.path}`;
    li.dataset.subHtml = '';
    li.dataset.downloadUrl = `media/original/${img.path}`;
    li.dataset.filename = img.filename;
    li.dataset.mtime = img.mtime;

    // Set display based on active categories
    if (!state.activeCategories.has(img.category)) {
      li.style.display = 'none';
    }

    const a = document.createElement('a');
    a.href = `media/original/${img.path}`;
    a.target = '_blank';
    a.title = img.prompt;

    const imgEl = document.createElement('img');
    imgEl.src = `media/thumbs/${img.path}`;
    imgEl.width = 512;
    imgEl.height = 512;
    imgEl.alt = img.filename;
    imgEl.loading = 'lazy';
    imgEl.title = img.prompt;

    // Mark as lazy for our custom lazy loader
    imgEl.dataset.src = imgEl.src;
    imgEl.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
    imgEl.classList.add('lazy');

    a.appendChild(imgEl);
    li.appendChild(a);

    return li;
  }

  function applySortToNewItems() {
    // This will be called by the main sort handler
    // Just need to ensure new items participate in sorting
  }

  // Track filter changes
  window.addEventListener('filterChange', function(e) {
    state.activeCategories = new Set(e.detail.activeCategories);
  });

  // Track sort changes
  window.addEventListener('sortChange', function(e) {
    state.currentSort = e.detail.sortType;
  });

  // Expose function to check if all images are loaded
  window.progressiveLoaderStatus = function() {
    return {
      allLoaded: state.allLoaded,
      loading: state.loading,
      remainingCount: window.remainingImages ? window.remainingImages.length : 0
    };
  };

})();