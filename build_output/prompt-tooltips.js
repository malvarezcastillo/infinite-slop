// Prompt tooltip functionality
(function() {
    'use strict';
    
    // Create tooltip element
    const tooltip = document.createElement('div');
    tooltip.className = 'prompt-tooltip';
    tooltip.style.cssText = `
        position: fixed;
        background-color: rgba(0, 0, 0, 0.9);
        color: white;
        padding: 12px 16px;
        border-radius: 8px;
        font-size: 14px;
        line-height: 1.5;
        max-width: 400px;
        min-width: 200px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        pointer-events: none;
        opacity: 0;
        transition: opacity 0.3s ease;
        z-index: 10000;
        white-space: pre-wrap;
        word-wrap: break-word;
    `;
    document.body.appendChild(tooltip);
    
    let currentTarget = null;
    let hideTimeout = null;
    
    function showTooltip(e) {
        const target = e.currentTarget;
        let promptText = target.getAttribute('title') || target.getAttribute('data-original-title');
        
        if (!promptText || promptText.trim() === '') return;
        
        // Store original title and remove it to prevent browser tooltip
        if (target.hasAttribute('title')) {
            target.setAttribute('data-original-title', promptText);
            target.removeAttribute('title');
        }
        
        currentTarget = target;
        tooltip.textContent = promptText;
        tooltip.style.opacity = '1';
        
        // Clear any pending hide
        if (hideTimeout) {
            clearTimeout(hideTimeout);
            hideTimeout = null;
        }
        
        updatePosition(e);
    }
    
    function updatePosition(e) {
        const x = e.clientX;
        const y = e.clientY;
        
        // Calculate position - always show below cursor to avoid interference
        let left = x - tooltip.offsetWidth / 2;
        let top = y + 20; // Always show below cursor with gap
        
        // Keep tooltip within viewport
        const padding = 10;
        if (left < padding) left = padding;
        if (left + tooltip.offsetWidth > window.innerWidth - padding) {
            left = window.innerWidth - tooltip.offsetWidth - padding;
        }
        
        // If tooltip would go off bottom of screen, show above cursor
        if (top + tooltip.offsetHeight > window.innerHeight - padding) {
            top = y - tooltip.offsetHeight - 20;
        }
        
        tooltip.style.left = left + 'px';
        tooltip.style.top = top + 'px';
    }
    
    function hideTooltip() {
        hideTimeout = setTimeout(() => {
            tooltip.style.opacity = '0';
            currentTarget = null;
        }, 200); // Increased delay for better stability
    }
    
    // Initialize tooltips when DOM is ready
    function initTooltips() {
        // Target the link containers with either title or data-original-title
        const links = document.querySelectorAll('#media li a[title], #media li a[data-original-title]');
        
        links.forEach(link => {
            // Remove existing listeners to prevent duplicates
            link.removeEventListener('mouseenter', showTooltip);
            link.removeEventListener('mousemove', updatePosition);
            link.removeEventListener('mouseleave', hideTooltip);
            
            // Add new listeners
            link.addEventListener('mouseenter', showTooltip);
            link.addEventListener('mousemove', updatePosition);
            link.addEventListener('mouseleave', hideTooltip);
            
            // Also handle mouse events on the image inside
            const img = link.querySelector('img');
            if (img) {
                img.addEventListener('mouseenter', function(e) {
                    e.stopPropagation();
                    showTooltip.call(link, e);
                });
                img.addEventListener('mousemove', function(e) {
                    e.stopPropagation();
                    updatePosition(e);
                });
            }
        });
        
        console.log(`Initialized tooltips for ${links.length} images`);
    }
    
    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTooltips);
    } else {
        initTooltips();
    }
    
    // Re-initialize when new images are loaded (for lazy loading)
    if (typeof window.checkVisibility === 'function') {
        const originalCheckVisibility = window.checkVisibility;
        window.checkVisibility = function() {
            originalCheckVisibility.apply(this, arguments);
            setTimeout(initTooltips, 500);
        };
    }
    
    // Also reinitialize on filter changes
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('filter-btn')) {
            setTimeout(initTooltips, 300);
        }
    });
})();