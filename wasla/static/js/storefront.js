/**
 * Wasla Storefront JavaScript
 * Handles interactive features and user actions
 */

// Utility function to get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Initialize tooltips and popovers
document.addEventListener('DOMContentLoaded', function() {
    // Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Bootstrap popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Handle cart add button
    setupCartHandlers();

    // Initialize quantity selectors
    setupQuantitySelectors();

    // Setup variant selector if present
    setupVariantSelectors();

    // Auto-dismiss alerts after 5 seconds
    autoDismissAlerts();
});

/**
 * Setup cart-related event handlers
 */
function setupCartHandlers() {
    const cartForms = document.querySelectorAll('form[action*="cart/add"]');
    cartForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const btn = form.querySelector('button[type="submit"]');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Adding...';
            }
        });
    });
}

/**
 * Setup quantity selector increment/decrement
 */
function setupQuantitySelectors() {
    const quantityInputs = document.querySelectorAll('input[name="quantity"]');
    quantityInputs.forEach(input => {
        // Prevent non-numeric input
        input.addEventListener('keypress', function(e) {
            if (!/[0-9]/.test(e.key)) {
                e.preventDefault();
            }
        });

        // Ensure minimum is 1
        input.addEventListener('blur', function() {
            if (!this.value || parseInt(this.value) < 1) {
                this.value = 1;
            }
        });
    });
}

/**
 * Setup variant selection changes
 */
function setupVariantSelectors() {
    const variantSelect = document.getElementById('variantSelect');
    if (variantSelect) {
        variantSelect.addEventListener('change', updateVariantInfo);
    }
}

/**
 * Update variant information when selection changes
 */
function updateVariantInfo() {
    const select = document.getElementById('variantSelect');
    if (!select) return;

    const selectedOption = select.options[select.selectedIndex];
    const stock = selectedOption.dataset.stock || 0;
    const price = selectedOption.dataset.price || '';
    const btn = document.getElementById('addToCartBtn');
    const quantityInput = document.getElementById('quantity');

    if (btn && stock) {
        btn.style.display = 'block';
        btn.disabled = parseInt(stock) === 0;
        if (quantityInput) {
            quantityInput.max = stock;
        }
    }

    if (quantityInput && stock) {
        quantityInput.disabled = parseInt(stock) === 0;
    }
}

/**
 * Apply product filters in category/search
 */
function applyFilters() {
    const form = document.getElementById('filterForm');
    if (form) {
        form.submit();
    }
}

/**
 * Apply product sorting  
 */
function applySorting() {
    const sortSelect = document.getElementById('sortBy');
    if (sortSelect) {
        const form = sortSelect.closest('form') || document.createElement('form');
        form.method = 'GET';
        
        // Preserve current filters
        const url = new URL(window.location);
        url.searchParams.set('sort', sortSelect.value);
        window.location.href = url.toString();
    }
}

/**
 * Auto-dismiss alert messages after 5 seconds
 */
function autoDismissAlerts() {
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
}

/**
 * Delete address from customer addresses page
 */
function deleteAddress(addressId) {
    if (confirm('Are you sure you want to delete this address?')) {
        // Make API call to delete address
        fetch(`/customer/addresses/${addressId}/delete/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            }
        }).then(response => {
            if (response.ok) {
                location.reload();
            } else {
                alert('Error deleting address');
            }
        }).catch(error => {
            console.error('Error:', error);
            alert('Error deleting address');
        });
    }
}

/**
 * Handle product image carousel thumbnail clicks
 */
function setupImageCarousel() {
    const thumbnails = document.querySelectorAll('.carousel-thumbnails img');
    const carousel = document.querySelector('#productImageCarousel');
    
    if (!carousel || !thumbnails.length) return;

    thumbnails.forEach((thumb, index) => {
        thumb.addEventListener('click', function() {
            const bsCarousel = new bootstrap.Carousel(carousel);
            bsCarousel.to(index);
            
            // Update selected thumbnail
            thumbnails.forEach(t => t.style.opacity = '0.5');
            thumb.style.opacity = '1';
        });

        // Initial state
        if (index === 0) {
            thumb.style.opacity = '1';
        } else {
            thumb.style.opacity = '0.5';
        }
    });
}

/**
 * Handle customer reorder action
 */
function handleReorder(orderId) {
    if (confirm('Add all items from this order to your cart?')) {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = `/customer/reorder/${orderId}/`;
        
        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrfmiddlewaretoken';
        csrfInput.value = getCookie('csrftoken');
        
        form.appendChild(csrfInput);
        document.body.appendChild(form);
        form.submit();
    }
}

/**
 * Handle search form submission with validation
 */
function setupSearchForm() {
    const searchForm = document.querySelector('form[action*="search"]');
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            const searchInput = this.querySelector('input[name="q"]');
            if (!searchInput || !searchInput.value.trim()) {
                e.preventDefault();
                searchInput?.focus();
                alert('Please enter a search term');
            }
        });
    }
}

/**
 * Lazy load images for better performance
 */
function setupLazyLoading() {
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src || img.src;
                    img.classList.remove('lazy');
                    observer.unobserve(img);
                }
            });
        });

        document.querySelectorAll('img.lazy').forEach(img => {
            imageObserver.observe(img);
        });
    }
}

/**
 * Format currency values
 */
function formatCurrency(amount, currency = 'SAR') {
    return new Intl.NumberFormat('ar-SA', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 2
    }).format(amount);
}

/**
 * Show loading indicator
 */
function showLoading() {
    const overlay = document.createElement('div');
    overlay.id = 'loadingOverlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0,0,0,0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
    `;
    overlay.innerHTML = `
        <div class="spinner-border text-primary" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
    `;
    document.body.appendChild(overlay);
}

/**
 * Hide loading indicator
 */
function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.remove();
    }
}

/**
 * Handle responsive navbar collapse
 */
function setupNavbar() {
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbarCollapse = document.querySelector('.navbar-collapse');

    if (navbarToggler) {
        navbarToggler.addEventListener('click', function() {
            navbarCollapse?.classList.toggle('show');
        });
    }
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        setupSearchForm();
        setupImageCarousel();
        setupLazyLoading();
        setupNavbar();
    });
} else {
    setupSearchForm();
    setupImageCarousel();
    setupLazyLoading();
    setupNavbar();
}
