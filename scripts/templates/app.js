/**
 * MCP Security Hub - Interactive functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const searchInput = document.getElementById('searchInput');
    const categoryFilters = document.getElementById('categoryFilters');
    const serverCards = document.querySelectorAll('.server-card');
    const categorySections = document.querySelectorAll('.category-section');
    const copyButtons = document.querySelectorAll('.copy-btn');
    const copyToast = document.getElementById('copyToast');

    let activeCategory = 'all';
    let searchQuery = '';

    // Initialize Bootstrap toast
    const toast = new bootstrap.Toast(copyToast, { delay: 2000 });

    /**
     * Filter servers based on category and search query
     */
    function filterServers() {
        serverCards.forEach(card => {
            const name = card.dataset.name.toLowerCase();
            const category = card.dataset.category;
            const description = (card.dataset.description || '').toLowerCase();

            const matchesCategory = activeCategory === 'all' || category === activeCategory;
            const matchesSearch = searchQuery === '' ||
                name.includes(searchQuery) ||
                description.includes(searchQuery) ||
                category.toLowerCase().includes(searchQuery);

            if (matchesCategory && matchesSearch) {
                card.classList.remove('hidden');
            } else {
                card.classList.add('hidden');
            }
        });

        // Show/hide category sections
        categorySections.forEach(section => {
            const category = section.dataset.category;
            const visibleCards = section.querySelectorAll('.server-card:not(.hidden)');

            if (visibleCards.length === 0) {
                section.classList.add('hidden');
            } else {
                section.classList.remove('hidden');
            }
        });

        // Update result count in search placeholder
        const visibleCount = document.querySelectorAll('.server-card:not(.hidden)').length;
        searchInput.placeholder = `Search servers, tools... (${visibleCount} shown)`;
    }

    /**
     * Handle category filter clicks
     */
    categoryFilters.addEventListener('click', function(e) {
        const button = e.target.closest('button');
        if (!button) return;

        // Update active state
        categoryFilters.querySelectorAll('.btn').forEach(btn => {
            btn.classList.remove('active', 'btn-primary');
            btn.classList.add('btn-outline-secondary');
        });
        button.classList.add('active', 'btn-primary');
        button.classList.remove('btn-outline-secondary');

        // Set active category
        activeCategory = button.dataset.category;
        filterServers();
    });

    /**
     * Handle search input
     */
    searchInput.addEventListener('input', function(e) {
        searchQuery = e.target.value.toLowerCase().trim();
        filterServers();
    });

    /**
     * Handle copy button clicks
     */
    copyButtons.forEach(button => {
        button.addEventListener('click', async function() {
            const command = this.dataset.command;

            try {
                await navigator.clipboard.writeText(command);

                // Visual feedback
                this.classList.add('copied');
                const originalHTML = this.innerHTML;
                this.innerHTML = '<i class="bi bi-check me-1"></i> Copied!';

                // Show toast
                toast.show();

                // Reset button after delay
                setTimeout(() => {
                    this.classList.remove('copied');
                    this.innerHTML = originalHTML;
                }, 1500);
            } catch (err) {
                console.error('Failed to copy:', err);
                // Fallback for older browsers
                const textArea = document.createElement('textarea');
                textArea.value = command;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
            }
        });
    });

    /**
     * Keyboard shortcuts
     */
    document.addEventListener('keydown', function(e) {
        // Focus search on '/' key
        if (e.key === '/' && document.activeElement !== searchInput) {
            e.preventDefault();
            searchInput.focus();
        }

        // Clear search on Escape
        if (e.key === 'Escape' && document.activeElement === searchInput) {
            searchInput.value = '';
            searchQuery = '';
            filterServers();
            searchInput.blur();
        }
    });

    // Initial filter
    filterServers();
});
