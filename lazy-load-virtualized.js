// Enhanced lazy loading with DOM virtualization for cards theme
(function() {
  'use strict';

  // Configuration
  const CONFIG = {
    initialLoad: 20,           // Number of images to load initially (increased)
    bufferDistance: 600,       // Pixels above/below viewport to keep loaded (reduced)
    checkInterval: 100,        // Throttle for scroll events (ms)
    placeholderSrc: 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', // 1x1 transparent gif
    unloadDelay: 500          // Delay before unloading images (ms)
  };

  // State management
  const state = {
    images: [],
    loadedImages: new Set(),
    scrollTimeout: null,
    unloadTimeout: null
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
        container: container
      };
      
      state.images.push(imageData);
      
      // Load first N visible images immediately
      if (isVisible && visibleCount < CONFIG.initialLoad) {
        imageData.loaded = true;
        state.loadedImages.add(index);
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
    
    // Load images that came into viewport
    toLoad.forEach(loadImage);
    
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

  function loadImage(imageData) {
    const img = imageData.element;
    
    if (img.dataset.src) {
      // Create a new image to preload
      const tempImg = new Image();
      
      tempImg.onload = function() {
        img.src = img.dataset.src;
        img.classList.remove('lazy');
        img.classList.add('loaded');
        delete img.dataset.src;
        
        imageData.loaded = true;
        state.loadedImages.add(imageData.index);
      };
      
      tempImg.onerror = function() {
        console.error('Failed to load image:', img.dataset.src);
        img.classList.add('error');
      };
      
      tempImg.src = img.dataset.src;
    } else if (!imageData.loaded) {
      // Restore from original source if dataset.src was deleted
      img.src = imageData.originalSrc;
      img.classList.remove('lazy');
      img.classList.add('loaded');
      
      imageData.loaded = true;
      state.loadedImages.add(imageData.index);
    }
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
    
    if (!isInViewport) {
      // Store the source for reloading
      img.dataset.src = imageData.originalSrc;
      img.src = CONFIG.placeholderSrc;
      img.classList.add('lazy');
      img.classList.remove('loaded', 'error');
      
      imageData.loaded = false;
      state.loadedImages.delete(imageData.index);
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
    // Clear state
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
        container: container
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
      loadedIndices: Array.from(state.loadedImages).sort((a, b) => a - b)
    });
  };

  // Cleanup function
  window.lazyLoadCleanup = function() {
    window.removeEventListener('scroll', throttledScrollHandler);
    window.removeEventListener('resize', throttledScrollHandler);
    if (state.scrollTimeout) clearTimeout(state.scrollTimeout);
    if (state.unloadTimeout) clearTimeout(state.unloadTimeout);
  };

})();