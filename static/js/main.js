/* ==========================================================================
   Movie Discovery System - Modular Theme & Interactive Client JS
   ========================================================================== */

(function () {
    'use strict';

    // Theme Management Engine
    const getStoredTheme = () => localStorage.getItem('theme');
    const setStoredTheme = theme => localStorage.setItem('theme', theme);

    const getPreferredTheme = () => {
        const storedTheme = getStoredTheme();
        if (storedTheme) {
            return storedTheme;
        }
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    };

    const setTheme = theme => {
        document.documentElement.setAttribute('data-bs-theme', theme);
        updateThemeIcons(theme);
    };

    const updateThemeIcons = theme => {
        const desktopIcon = document.getElementById('themeIcon');
        const mobileIcon = document.getElementById('themeIconMobile');

        const applyIcon = elem => {
            if (!elem) return;
            if (theme === 'dark') {
                elem.className = 'fa-solid fa-sun text-warning';
                elem.setAttribute('title', 'Switch to Light Mode');
            } else {
                elem.className = 'fa-solid fa-moon text-info';
                elem.setAttribute('title', 'Switch to Dark Mode');
            }
        };

        applyIcon(desktopIcon);
        applyIcon(mobileIcon);
    };

    // Apply theme immediately on load
    const initialTheme = getPreferredTheme();
    setTheme(initialTheme);

    document.addEventListener('DOMContentLoaded', () => {
        setTheme(getPreferredTheme());

        // Bind click events to both desktop and mobile theme buttons
        const desktopBtn = document.getElementById('themeToggleBtn');
        const mobileBtn = document.getElementById('themeToggleBtnMobile');

        const toggleHandler = () => {
            const currentTheme = document.documentElement.getAttribute('data-bs-theme');
            const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
            setStoredTheme(nextTheme);
            setTheme(nextTheme);
        };

        if (desktopBtn) desktopBtn.addEventListener('click', toggleHandler);
        if (mobileBtn) mobileBtn.addEventListener('click', toggleHandler);

        // Listen for OS Theme Preference changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
            if (!getStoredTheme()) {
                setTheme(getPreferredTheme());
            }
        });

        // Auto dismiss alert messages after 5 seconds
        const alerts = document.querySelectorAll('.alert-dismissible');
        alerts.forEach(alert => {
            setTimeout(() => {
                const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                if (bsAlert) bsAlert.close();
            }, 5000);
        });

        // Auto-submit filter selects on change
        const autoFilterSelects = document.querySelectorAll('.auto-filter');
        autoFilterSelects.forEach(select => {
            select.addEventListener('change', () => {
                const form = select.closest('form');
                if (form) form.submit();
            });
        });

        // Global Broken Image Handler (works for static and dynamically loaded images)
        const handleImageError = (img) => {
            if (!img.dataset.fallbackApplied) {
                img.dataset.fallbackApplied = "true";
                img.src = '/static/images/fallback_poster.png';
            }
        };

        document.querySelectorAll('img').forEach(img => {
            img.addEventListener('error', () => handleImageError(img));
        });

        // Live Movie Search Suggestions & Autocomplete Engine
        const initSearchSuggestions = () => {
            const searchInput = document.getElementById('movieSearchInput');
            const dropdown = document.getElementById('searchSuggestionsDropdown');
            const list = document.getElementById('suggestionsList');
            const viewAllLink = document.getElementById('viewAllSearchLink');

            if (!searchInput || !dropdown || !list) return;

            let debounceTimer = null;
            let currentFocusIndex = -1;

            const renderSuggestions = (items, query) => {
                list.innerHTML = '';
                currentFocusIndex = -1;

                if (viewAllLink) {
                    viewAllLink.href = query ? `/discover/?q=${encodeURIComponent(query)}` : '/discover/';
                }

                if (!items || items.length === 0) {
                    list.innerHTML = `
                        <div class="p-3 text-center text-secondary">
                            <i class="fa-solid fa-film mb-2 fs-4 text-secondary opacity-50"></i>
                            <div class="small">No matching movies found</div>
                            <div class="text-white-50 small mt-1">Try another title, genre, or keyword</div>
                        </div>
                    `;
                    dropdown.classList.remove('d-none');
                    return;
                }

                items.forEach((movie, idx) => {
                    const itemLink = document.createElement('a');
                    itemLink.className = 'suggestion-item';
                    itemLink.href = movie.url;
                    itemLink.setAttribute('data-index', idx);

                    const genresHtml = (movie.genres || []).map(g => `<span class="badge bg-secondary bg-opacity-25 text-white-50 small me-1">${g}</span>`).join('');
                    const ratingHtml = movie.rating > 0
                        ? `<span class="suggestion-rating"><i class="fa-solid fa-star me-1"></i>${movie.rating}</span>`
                        : '';
                    const bookingBadge = movie.has_active_shows
                        ? `<span class="badge bg-danger-subtle text-danger border border-danger-subtle ms-auto small"><i class="fa-solid fa-ticket me-1"></i>Book</span>`
                        : `<span class="badge bg-secondary-subtle text-secondary ms-auto small">Details</span>`;

                    itemLink.innerHTML = `
                        <img src="${movie.poster_url}" alt="${movie.title}" class="suggestion-poster" onerror="this.onerror=null; this.src='/static/images/fallback_poster.png';">
                        <div class="flex-grow-1 min-w-0">
                            <div class="suggestion-title text-truncate">${movie.title}</div>
                            <div class="suggestion-meta">
                                ${ratingHtml}
                                ${movie.release_year ? `<span>${movie.release_year}</span>` : ''}
                                ${movie.language ? `<span>${movie.language}</span>` : ''}
                                <span>${genresHtml}</span>
                            </div>
                        </div>
                        ${bookingBadge}
                    `;
                    list.appendChild(itemLink);
                });

                dropdown.classList.remove('d-none');
            };

            const fetchSuggestions = async (query) => {
                try {
                    const res = await fetch(`/api/movies/suggestions/?q=${encodeURIComponent(query)}&limit=6`);
                    if (!res.ok) return;
                    const data = await res.json();
                    if (data && data.suggestions) {
                        renderSuggestions(data.suggestions, query);
                    }
                } catch (err) {
                    console.warn('Movie suggestions fetch warning:', err);
                }
            };

            searchInput.addEventListener('input', (e) => {
                const q = e.target.value.trim();
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    fetchSuggestions(q);
                }, 200);
            });

            searchInput.addEventListener('focus', () => {
                const q = searchInput.value.trim();
                fetchSuggestions(q);
            });

            // Keyboard navigation for suggestions
            searchInput.addEventListener('keydown', (e) => {
                const items = list.querySelectorAll('.suggestion-item');
                if (!items.length || dropdown.classList.contains('d-none')) return;

                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    currentFocusIndex = (currentFocusIndex + 1) % items.length;
                    updateActiveItem(items);
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    currentFocusIndex = (currentFocusIndex - 1 + items.length) % items.length;
                    updateActiveItem(items);
                } else if (e.key === 'Enter') {
                    if (currentFocusIndex >= 0 && items[currentFocusIndex]) {
                        e.preventDefault();
                        window.location.href = items[currentFocusIndex].href;
                    }
                } else if (e.key === 'Escape') {
                    dropdown.classList.add('d-none');
                }
            });

            const updateActiveItem = (items) => {
                items.forEach((item, idx) => {
                    if (idx === currentFocusIndex) {
                        item.classList.add('active');
                        item.scrollIntoView({ block: 'nearest' });
                    } else {
                        item.classList.remove('active');
                    }
                });
            };

            // Close dropdown on outside click
            document.addEventListener('click', (e) => {
                if (!dropdown.contains(e.target) && !searchInput.contains(e.target)) {
                    dropdown.classList.add('d-none');
                }
            });
        };

        initSearchSuggestions();

        // Global Interactive Trailer Modal Handler
        const trailerModalEl = document.getElementById('globalTrailerModal');
        if (trailerModalEl) {
            const trailerIframe = document.getElementById('globalTrailerIframe');
            const trailerTitle = document.getElementById('globalTrailerMovieTitle');
            const trailerWatchBtn = document.getElementById('globalTrailerWatchBtn');
            const trailerFallback = document.getElementById('globalTrailerFallback');
            const trailerFallbackLink = document.getElementById('globalTrailerFallbackLink');

            const populateTrailer = (btn) => {
                if (!btn) return;
                let embedUrl = btn.getAttribute('data-trailer-url');
                const videoKey = btn.getAttribute('data-trailer-key');
                const title = btn.getAttribute('data-trailer-title') || 'Official Trailer';
                const watchUrl = btn.getAttribute('data-watch-url') || '#';

                let finalKey = (videoKey && videoKey.length === 11) ? videoKey : null;
                if (!finalKey && embedUrl) {
                    const m = embedUrl.match(/(?:embed\/|v=|\/)([\w-]{11})/);
                    if (m) finalKey = m[1];
                }

                if (finalKey) {
                    embedUrl = `https://www.youtube.com/embed/${finalKey}?autoplay=1`;
                }

                if (trailerTitle) trailerTitle.textContent = `${title} - Official Trailer`;
                if (trailerWatchBtn) trailerWatchBtn.href = watchUrl;
                if (trailerFallbackLink) trailerFallbackLink.href = watchUrl;

                if (trailerFallback) trailerFallback.classList.add('d-none');
                if (trailerIframe && embedUrl) {
                    trailerIframe.parentElement.classList.remove('d-none');
                    trailerIframe.src = embedUrl;
                }
            };

            // Bootstrap show.bs.modal event trigger
            trailerModalEl.addEventListener('show.bs.modal', (e) => {
                const btn = e.relatedTarget || document.activeElement;
                populateTrailer(btn);
            });

            // Manual click event fallback
            document.addEventListener('click', (e) => {
                const btn = e.target.closest('.play-trailer-btn');
                if (btn) {
                    populateTrailer(btn);
                    if (window.bootstrap && bootstrap.Modal) {
                        const modalInstance = bootstrap.Modal.getOrCreateInstance(trailerModalEl);
                        modalInstance.show();
                    }
                }
            });

            // Stop audio/video playback when modal is closed
            trailerModalEl.addEventListener('hide.bs.modal', () => {
                if (trailerIframe) {
                    trailerIframe.src = '';
                }
            });
        }

    });
})();

