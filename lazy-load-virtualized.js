// Enhanced lazy loading with DOM virtualization and retry mechanism
(function() {
  'use strict';

  // Configuration
  const CONFIG = {
    initialLoad: 20,           // Number of images to load initially
    bufferDistance: 1200,      // Pixels above/below viewport to keep loaded (increased for stability)
    checkInterval: 150,        // Throttle for scroll events (ms) - increased for better performance
    placeholderSrc: 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', // 1x1 transparent gif
    unloadDelay: 2000,         // Delay before unloading images (ms) - increased to prevent flickering
    maxConcurrentLoads: 6,     // Maximum concurrent image loads
    maxRetries: 3,             // Maximum retry attempts per image
    retryDelays: [1000, 2000, 4000] // Exponential backoff delays (ms)
  };

  // State management
  const state = {
    images: [],
    loadedImages: new Set(),
    scrollTimeout: null,
    unloadTimeout: null,
    loadQueue: [],
    currentLoads: 0,
    retryTracker: new Map(),   // Track retry attempts per image
    failedImages: new Set()    // Track permanently failed images
  };

  // Wait for DOM ready
  document.addEventListener('DOMContentLoaded', function() {
    initializeLazyLoading();
  });

  function initializeLazyLoading() {
    // Get all images and store their data
    const imageElements = document.querySelectorAll('#media img');
    let visibleCount = 0;
    
    imageElements.forEach((img, index) => {
      const container = img.closest('li');
      const isVisible = container.style.display !== 'none';
      
      const imageData = {
        element: img,
        index: index,
        originalSrc: img.src,
        loaded: false,
        container: container,
        loadAttempts: 0,
        lastFailure: null
      };
      
      state.images.push(imageData);
      
      // Load first N visible images immediately
      if (isVisible && visibleCount < CONFIG.initialLoad) {
        queueImageLoad(imageData);
        visibleCount++;
      } else {
        // Set up for lazy loading
        img.dataset.src = img.src;
        img.src = CONFIG.placeholderSrc;
        img.classList.add('lazy');
      }
    });

    // Set up scroll handler with throttling
    window.addEventListener('scroll', throttledScrollHandler, { passive: true });
    window.addEventListener('resize', throttledScrollHandler, { passive: true });
    
    // Initial check to load any additional visible images
    checkVisibility();
  }

  function throttledScrollHandler() {
    if (state.scrollTimeout) {
      clearTimeout(state.scrollTimeout);
    }
    
    state.scrollTimeout = setTimeout(() => {
      checkVisibility();
    }, CONFIG.checkInterval);
  }

  function checkVisibility() {
    const viewportTop = window.pageYOffset - CONFIG.bufferDistance;
    const viewportBottom = window.pageYOffset + window.innerHeight + CONFIG.bufferDistance;
    
    // Arrays to track what needs to be loaded/unloaded
    const toLoad = [];
    const toUnload = [];
    
    state.images.forEach((imageData, index) => {
      // Skip hidden elements (filtered out by categories)
      const isHidden = imageData.container.style.display === 'none';
      if (isHidden) {
        return;
      }
      
      const rect = imageData.container.getBoundingClientRect();
      const elementTop = rect.top + window.pageYOffset;
      const elementBottom = elementTop + rect.height;
      
      const isInViewport = elementBottom >= viewportTop && elementTop <= viewportBottom;
      
      if (isInViewport && !imageData.loaded) {
        toLoad.push(imageData);
      } else if (!isInViewport && imageData.loaded && index >= CONFIG.initialLoad) {
        toUnload.push(imageData);
      }
    });
    
    // Queue images that came into viewport for loading
    toLoad.forEach(imageData => {
      queueImageLoad(imageData);
    });
    
    // Process the load queue
    processLoadQueue();
    
    // Unload images that are far from viewport (with delay to prevent flickering)
    if (toUnload.length > 0) {
      if (state.unloadTimeout) {
        clearTimeout(state.unloadTimeout);
      }
      
      state.unloadTimeout = setTimeout(() => {
        toUnload.forEach(unloadImage);
      }, CONFIG.unloadDelay);
    }
  }

  // Queue management functions
  function queueImageLoad(imageData) {
    // Skip if already loaded, queued, or permanently failed
    if (imageData.loaded || 
        state.loadQueue.includes(imageData) || 
        state.failedImages.has(imageData.index)) {
      return;
    }
    
    state.loadQueue.push(imageData);
  }
  
  function processLoadQueue() {
    // Process queue if we have capacity
    while (state.loadQueue.length > 0 && state.currentLoads < CONFIG.maxConcurrentLoads) {
      const imageData = state.loadQueue.shift();
      loadImageWithRetry(imageData);
    }
  }
  
  function loadImageWithRetry(imageData, isRetry = false) {
    const img = imageData.element;
    
    // Skip if already loaded
    if (imageData.loaded) {
      return;
    }
    
    // Track concurrent loads
    state.currentLoads++;
    
    // Add loading state
    img.classList.add('loading');
    
    // Determine source URL
    const srcUrl = img.dataset.src || imageData.originalSrc;
    
    if (!srcUrl) {
      console.error('No source URL available for image:', imageData.index);
      handleImageError(imageData, new Error('No source URL'));
      return;
    }
    
    // Create a new image to preload
    const tempImg = new Image();
    
    tempImg.onload = function() {
      // Success - update the actual image
      img.src = srcUrl;
      img.classList.remove('lazy', 'loading', 'error');
      img.classList.add('loaded');
      
      imageData.loaded = true;
      imageData.loadAttempts = 0; // Reset attempts on success
      state.loadedImages.add(imageData.index);
      
      // Remove from retry tracker if it was there
      if (state.retryTracker.has(imageData.index)) {
        clearTimeout(state.retryTracker.get(imageData.index).timeoutId);
        state.retryTracker.delete(imageData.index);
      }
      
      // Decrease load count and process next in queue
      state.currentLoads--;
      processLoadQueue();
    };
    
    tempImg.onerror = function() {
      handleImageError(imageData, new Error('Image load failed'));
    };
    
    // Set a timeout for the load attempt
    const loadTimeout = setTimeout(() => {
      tempImg.onload = null;
      tempImg.onerror = null;
      handleImageError(imageData, new Error('Image load timeout'));
    }, 10000); // 10 second timeout
    
    // Start loading
    tempImg.src = srcUrl;
    
    // Clear timeout on success or error
    const originalOnload = tempImg.onload;
    const originalOnerror = tempImg.onerror;
    
    tempImg.onload = function() {
      clearTimeout(loadTimeout);
      if (originalOnload) originalOnload.apply(this, arguments);
    };
    
    tempImg.onerror = function() {
      clearTimeout(loadTimeout);
      if (originalOnerror) originalOnerror.apply(this, arguments);
    };
  }
  
  function handleImageError(imageData, error) {
    const img = imageData.element;
    
    // Decrease load count
    state.currentLoads--;
    
    // Increment attempt counter
    imageData.loadAttempts++;
    imageData.lastFailure = new Date();
    
    console.warn(`Image load failed (attempt ${imageData.loadAttempts}):`, 
                 img.dataset.src || imageData.originalSrc, error.message);
    
    // Check if we should retry
    if (imageData.loadAttempts < CONFIG.maxRetries) {
      // Schedule retry with exponential backoff
      const retryDelay = CONFIG.retryDelays[imageData.loadAttempts - 1] || CONFIG.retryDelays[CONFIG.retryDelays.length - 1];
      
      const timeoutId = setTimeout(() => {
        // Retry the load
        loadImageWithRetry(imageData, true);
        state.retryTracker.delete(imageData.index);
      }, retryDelay);
      
      // Track the retry
      state.retryTracker.set(imageData.index, {
        timeoutId,
        nextAttempt: new Date(Date.now() + retryDelay)
      });
      
      // Update UI to show retry state
      img.classList.remove('loading');
      img.classList.add('retrying');
      
    } else {
      // Max retries reached - mark as permanently failed
      state.failedImages.add(imageData.index);
      img.classList.remove('loading', 'retrying');
      img.classList.add('error');
      
      console.error('Image permanently failed after', CONFIG.maxRetries, 'attempts:', 
                   img.dataset.src || imageData.originalSrc);
    }
    
    // Process next item in queue
    processLoadQueue();
  }

  function unloadImage(imageData) {
    const img = imageData.element;
    
    // Only unload if still out of viewport
    const rect = imageData.container.getBoundingClientRect();
    const elementTop = rect.top + window.pageYOffset;
    const elementBottom = elementTop + rect.height;
    const viewportTop = window.pageYOffset - CONFIG.bufferDistance;
    const viewportBottom = window.pageYOffset + window.innerHeight + CONFIG.bufferDistance;
    
    const isInViewport = elementBottom >= viewportTop && elementTop <= viewportBottom;
    
    if (!isInViewport && imageData.loaded) {
      // Cancel any pending retries for this image
      if (state.retryTracker.has(imageData.index)) {
        clearTimeout(state.retryTracker.get(imageData.index).timeoutId);
        state.retryTracker.delete(imageData.index);
      }
      
      // Remove from load queue if present
      const queueIndex = state.loadQueue.indexOf(imageData);
      if (queueIndex !== -1) {
        state.loadQueue.splice(queueIndex, 1);
      }
      
      // Store the source for reloading - always preserve the original source
      if (!img.dataset.src) {
        img.dataset.src = imageData.originalSrc;
      }
      
      img.src = CONFIG.placeholderSrc;
      img.classList.add('lazy');
      img.classList.remove('loaded', 'loading', 'retrying', 'error');
      
      imageData.loaded = false;
      imageData.loadAttempts = 0; // Reset attempts when unloading
      state.loadedImages.delete(imageData.index);
      
      // Remove from failed images set to allow retry when visible again
      state.failedImages.delete(imageData.index);
    }
  }

  // Expose checkVisibility for external calls
  window.checkVisibility = checkVisibility;

  // Function to handle category filter changes
  window.lazyLoadHandleFilterChange = function() {
    // Cancel any pending unload operations
    if (state.unloadTimeout) {
      clearTimeout(state.unloadTimeout);
    }
    
    // Immediately check visibility to load newly visible images
    checkVisibility();
  };

  // Function to handle DOM reordering (for sorting)
  window.lazyLoadHandleReorder = function() {
    // Clear load queue and reset state
    state.loadQueue = [];
    state.images = [];
    state.loadedImages.clear();
    
    // Re-scan all images
    const imageElements = document.querySelectorAll('#media img');
    let visibleCount = 0;
    
    imageElements.forEach((img, index) => {
      const container = img.closest('li');
      const isVisible = container.style.display !== 'none';
      const isAlreadyLoaded = !img.classList.contains('lazy') && img.src !== CONFIG.placeholderSrc;
      
      const imageData = {
        element: img,
        index: index,
        originalSrc: img.dataset.src || img.src,
        loaded: isAlreadyLoaded,
        container: container,
        loadAttempts: 0,
        lastFailure: null
      };
      
      state.images.push(imageData);
      
      if (isAlreadyLoaded) {
        state.loadedImages.add(index);
      }
    });
    
    // Check visibility for any new images that need loading
    checkVisibility();
  };

  // Debug info
  window.lazyLoadDebug = function() {
    console.log({
      totalImages: state.images.length,
      loadedImages: state.loadedImages.size,
      loadedIndices: Array.from(state.loadedImages).sort((a, b) => a - b),
      queuedImages: state.loadQueue.length,
      currentLoads: state.currentLoads,
      retrying: state.retryTracker.size,
      permanentlyFailed: state.failedImages.size,
      retryDetails: Array.from(state.retryTracker.entries()).map(([index, data]) => ({
        imageIndex: index,
        nextAttempt: data.nextAttempt
      }))
    });
  };

  // Function to manually retry failed images
  window.lazyLoadRetryFailed = function() {
    console.log('Retrying', state.failedImages.size, 'failed images...');
    
    // Clear failed images set and reset attempts
    state.failedImages.forEach(index => {
      const imageData = state.images[index];
      if (imageData) {
        imageData.loadAttempts = 0;
        imageData.lastFailure = null;
      }
    });
    state.failedImages.clear();
    
    // Trigger visibility check to reload failed images
    checkVisibility();
  };

  // Cleanup function
  window.lazyLoadCleanup = function() {
    window.removeEventListener('scroll', throttledScrollHandler);
    window.removeEventListener('resize', throttledScrollHandler);
    if (state.scrollTimeout) clearTimeout(state.scrollTimeout);
    if (state.unloadTimeout) clearTimeout(state.unloadTimeout);
    
    // Clear all retry timeouts
    state.retryTracker.forEach(retryData => {
      clearTimeout(retryData.timeoutId);
    });
    state.retryTracker.clear();
  };

})();